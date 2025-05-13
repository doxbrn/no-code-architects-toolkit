# Note: Ensure moviepy is installed
from services.v1.video.pexels_service import (
    get_pexels_videos_for_duration, download_asset
)

try:
    from moviepy.editor import VideoFileClip, concatenate_videoclips
    from moviepy.video import fx as vfx  # Use moviepy.video.fx
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    # Dummy classes/functions if not installed
    class VideoFileClip:
        pass

    def concatenate_videoclips(*args, **kwargs):
        pass

    class vfx:
        class ColorX:
            def __init__(self, factor):
                pass

        class FadeIn:
            def __init__(self, duration):
                pass

        class FadeOut:
            def __init__(self, duration):
                pass

    print("Warning: moviepy library not found. Montage functionality disabled.")

import os
import logging

logger = logging.getLogger(__name__)

# Define standard HD resolution and defaults
DEFAULT_SIZE = (1920, 1080)
DEFAULT_FPS = 24
DEFAULT_TRANSITION = 1.5
DEFAULT_BITRATE = "10000k"  # High quality bitrate
DEFAULT_PRESET = "medium"
DEFAULT_CRF = "20"  # Better quality CRF than default 23


def pexels_montage(
    pexels_term: str,
    n_videos: int,
    output_path: str,
    min_duration: int = 5,
    max_duration: int = 30,
    transition: float = DEFAULT_TRANSITION,
    target_fps: int = DEFAULT_FPS,
    target_size: tuple = DEFAULT_SIZE,
    apply_color_correction: bool = True,
):
    """
    Creates a video montage from Pexels videos based on a search term.

    Args:
        pexels_term: Search term for Pexels.
        n_videos: The desired number of videos in the montage.
        output_path: Path to save the final montage video.
        min_duration: Min duration for individual Pexels clips.
        max_duration: Max duration for individual Pexels clips.
        transition: Duration (seconds) for fade transitions.
        target_fps: Frames per second for the output video.
        target_size: Resolution (width, height) for the output video.
        apply_color_correction: Apply subtle color correction (vfx.colorx).
    """
    if not MOVIEPY_AVAILABLE:
        raise RuntimeError("Moviepy required for montages but not installed.")

    logger.info(f"Montage: term='{pexels_term}', n={n_videos}, output={output_path}")

    # Fetch video URLs from Pexels
    # Request exactly n_videos, total_duration is not primary filter
    urls, _, video_ids = get_pexels_videos_for_duration(
        pexels_term,
        total_duration=9999,  # Arbitrarily large
        min_duration=min_duration,
        max_duration=max_duration,
        max_videos=n_videos  # Request exactly n_videos
    )

    if not urls:
        logger.error(f"No Pexels videos found for term '{pexels_term}'.")
        raise RuntimeError(f"No videos found on Pexels for query: {pexels_term}")

    if len(urls) < n_videos:
        logger.warning(
            f"Found {len(urls)} videos (requested {n_videos}). Using available."
        )

    logger.info(f"Found {len(urls)} videos. Downloading and processing...")

    clips = []
    downloaded_paths = []

    # Download and prepare clips
    for i, url in enumerate(urls):
        try:
            logger.info(f"Downloading montage video {i+1}/{len(urls)}: {url}")
            # Use video ID in filename for uniqueness
            video_id_str = video_ids[i] if i < len(video_ids) else f'temp_{i}'
            clip_filename = f"montage_{video_id_str}.mp4"
            path = download_asset(url, clip_filename)
            downloaded_paths.append(path)

            logger.info(f"Loading montage clip: {path}")
            clip = VideoFileClip(path)

            # Resize clip to target size
            if clip.size != target_size:
                msg = f"Resizing clip {i+1} from {clip.size} to {target_size}"
                logger.warning(msg)
                # High-quality resize might be needed depending on moviepy version
                clip = clip.resize(width=target_size[0], height=target_size[1])

            # Apply effects
            effects_to_apply = []
            if apply_color_correction:
                clip = clip.fx(vfx.colorx, 1.1)  # Subtle correction
                effects_to_apply.append("colorx(1.1)")

            if transition > 0:
                # Apply fade in only to first clip
                if i == 0:
                    clip = clip.fx(vfx.fadein, transition)
                    effects_to_apply.append(f"fadein({transition})")
                # Fade out handled by padding during concatenation

            logger.info(f"Clip {i+1}: Dur={clip.duration:.2f}s. Effects: {effects_to_apply}")
            clips.append(clip)

        except Exception as e:
            err_msg = f"Failed processing clip {i+1} from {url}: {e}"
            logger.error(err_msg, exc_info=True)
            continue  # Skip this clip

    if not clips:
        logger.error("No clips could be processed for the montage.")
        raise RuntimeError("Failed to prepare any clips for the montage.")

    # Concatenate clips with crossfade
    logger.info(f"Concatenating {len(clips)} clips for montage.")
    padding_val = -transition if transition > 0 and len(clips) > 1 else 0
    try:
        final_clip = concatenate_videoclips(
            clips,
            method="compose",
            padding=padding_val,  # Negative padding creates crossfade
        )
    except Exception as e:
        concat_err = f"Error during montage concatenation: {e}"
        logger.error(f"Failed to concatenate montage clips: {e}", exc_info=True)
        raise RuntimeError(concat_err) from e

    # Write final montage video
    logger.info(f"Writing final montage video to: {output_path}")
    try:
        final_clip.write_videofile(
            output_path,
            fps=target_fps,
            codec="libx264",
            audio_codec="aac",  # Include even if silent for compatibility
            bitrate=DEFAULT_BITRATE,
            preset=DEFAULT_PRESET,
            threads=max(1, os.cpu_count() // 2),
            logger='bar',
            ffmpeg_params=["-crf", DEFAULT_CRF]
        )
        logger.info(f"Successfully created montage video: {output_path}")
    except Exception as e:
        write_err = f"Failed to write montage video file: {e}"
        logger.error(f"Failed to write final montage video: {e}", exc_info=True)
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError as rm_e:
                logger.warning(f"Could not remove partial output {output_path}: {rm_e}")
        raise RuntimeError(write_err) from e
    finally:
        # Clean up resources
        logger.info("Closing montage video clips...")
        try:
            if 'final_clip' in locals() and final_clip: final_clip.close()
            for clip in clips:
                if clip: clip.close()
        except Exception as close_e:
            logger.warning(f"Error closing moviepy clips: {close_e}")

        # Optionally remove downloaded clips
        # for path in downloaded_paths:
        #     try:
        #         if os.path.exists(path):
        #             os.remove(path)
        #             logger.info(f"Removed temporary montage file: {path}")
        #     except OSError as rm_e:
        #         logger.warning(f"Could not remove temp file {path}: {rm_e}") 