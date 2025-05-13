# Note: Ensure moviepy and numpy are installed (e.g., in requirements.txt)
from services.v1.video.pexels_service import (
    get_pexels_videos_for_duration, download_asset
)

try:
    from moviepy.editor import (
        VideoFileClip,
        CompositeVideoClip,
        concatenate_videoclips,
    )
    from moviepy.video import fx as vfx  # Use moviepy.video.fx for vfx
    import numpy as np
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    # Define dummy classes/functions if moviepy is not installed
    # This allows the service to load but fail gracefully at runtime
    class VideoFileClip:
        pass

    class CompositeVideoClip:
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

    import numpy as np  # numpy might still be available
    print("Warning: moviepy library not found. Chroma key functionality disabled.")

import os
import logging

logger = logging.getLogger(__name__)


def hex_to_rgb(hex_color: str) -> tuple:
    """Converts a hex color string (e.g., '#RRGGBB') to an RGB tuple (0-255)."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        raise ValueError("Invalid hex color format. Use #RRGGBB.")
    try:
        # Convert hex pairs to integers
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        raise ValueError("Invalid hex character in color string.")


def chroma_key_video(
    input_path: str,
    pexels_term: str,
    output_path: str,
    chroma_color: str = "#00FF00",  # Default to green
    threshold: int = 40,         # Chroma key sensitivity
    transition: float = 1.0,     # Transition duration for fades
    effect: str = "fade",        # Effect ("fade", "contrast", None)
):
    """
    Applies chroma key to an input video using Pexels videos as background.

    Args:
        input_path: Path to the foreground video (with chroma background).
        pexels_term: Search term for background videos on Pexels.
        output_path: Path where the final composited video will be saved.
        chroma_color: Hex color code (e.g., '#00FF00') for background removal.
        threshold: Sensitivity for chroma keying (10-100 recommended).
        transition: Duration (in seconds) for fade effects.
        effect: Visual effect for background clips ('fade', 'contrast', None).
    """
    if not MOVIEPY_AVAILABLE:
        raise RuntimeError("Moviepy required but not installed.")

    logger.info(f"Chroma key: input={input_path}, output={output_path}")
    logger.info(f"Pexels='{pexels_term}', Color={chroma_color}, Thresh={threshold}")

    try:
        fg_clip = VideoFileClip(input_path)
    except Exception as e:
        logger.error(f"Failed loading FG video '{input_path}': {e}")
        raise RuntimeError(f"Could not load foreground video: {e}") from e

    fg_duration = fg_clip.duration
    fg_size = fg_clip.size  # (width, height)
    fg_fps = fg_clip.fps
    logger.info(f"FG: Dur={fg_duration:.2f}s, Size={fg_size}, FPS={fg_fps}")

    logger.info(f"Fetching Pexels videos for '{pexels_term}'")
    # Fetch slightly longer total duration for transitions/padding
    target_bg_duration = fg_duration + (transition * 2 if effect == "fade" else 0)
    bg_urls, _, bg_ids = get_pexels_videos_for_duration(
        pexels_term,
        target_bg_duration,
        min_duration=max(5, transition * 2),
        max_duration=60,
        max_videos=10
    )

    if not bg_urls:
        logger.error("Failed to get Pexels background videos.")
        raise RuntimeError("Could not retrieve Pexels background videos.")

    logger.info(f"Found {len(bg_urls)} potential Pexels videos.")

    bg_clips = []
    total_bg_duration_added = 0
    downloaded_paths = []

    for i, url in enumerate(bg_urls):
        try:
            logger.info(f"Downloading BG video {i+1}/{len(bg_urls)}: {url}")
            video_id_str = bg_ids[i] if i < len(bg_ids) else f'temp_{i}'
            bg_filename = f"chroma_bg_{video_id_str}.mp4"
            bg_path = download_asset(url, bg_filename)
            downloaded_paths.append(bg_path)

            logger.info(f"Loading background clip: {bg_path}")
            clip = VideoFileClip(bg_path)

            if clip.size != fg_size:
                logger.warning(f"Resizing BG {i+1} from {clip.size} to {fg_size}")
                clip = clip.resize(height=fg_size[1])

            applied_effects = []
            if effect == "contrast":
                clip = clip.fx(vfx.colorx, 1.2)
                applied_effects.append("contrast")
            elif effect == "fade" and transition > 0:
                if i == 0:  # Fade in first clip
                    clip = clip.fx(vfx.fadein, transition)
                    applied_effects.append("fadein")
                # Last clip fade out is handled by concatenate padding

            logger.info(f"BG {i+1}: Dur={clip.duration:.2f}s. Effects: {applied_effects}")
            bg_clips.append(clip)
            total_bg_duration_added += clip.duration

            if total_bg_duration_added >= target_bg_duration:
                logger.info(f"Reached target duration with {len(bg_clips)} BG clips.")
                break

        except Exception as e:
            # Log error and continue with next video
            logger.error(f"Failed processing BG video {i+1} from {url}: {e}", exc_info=True)
            continue

    if not bg_clips:
        logger.error("No background clips could be processed.")
        raise RuntimeError("Failed to prepare any background clips.")

    logger.info(f"Concatenating {len(bg_clips)} background clips.")
    # Use negative padding for cross-fade effect if using fade
    padding_val = -transition if effect == "fade" and transition > 0 and len(bg_clips) > 1 else 0
    try:
        bg_concat = concatenate_videoclips(bg_clips, method="compose", padding=padding_val)
        # Trim concatenated clip precisely to foreground duration
        bg_concat = bg_concat.subclip(0, fg_duration)
        logger.info(f"BG concatenation done. Duration: {bg_concat.duration:.2f}s")
    except Exception as e:
        logger.error(f"Failed to concatenate background clips: {e}", exc_info=True)
        raise RuntimeError(f"Error concatenating background videos: {e}") from e

    try:
        chroma_rgb_val = hex_to_rgb(chroma_color)
        logger.info(f"Converted hex {chroma_color} to RGB {chroma_rgb_val}")
    except ValueError as e:
        logger.error(f"Invalid chroma color format: {chroma_color}. {e}")
        raise ValueError(f"Invalid chroma_color: {chroma_color}") from e

    logger.info(f"Creating chroma mask with threshold: {threshold}")

    # Mask function: 1.0 = keep, 0.0 = remove
    def chroma_mask_func(frame):
        frame_int = frame.astype(int)
        color_arr = np.array(chroma_rgb_val, dtype=int)
        diff = np.abs(frame_int - color_arr)
        # True where ALL channel diffs are less than threshold
        mask_bool = (diff < threshold).all(axis=2)
        # Invert: Keep pixels where mask is False (not the chroma color)
        return (~mask_bool).astype(float)

    try:
        mask_clip = fg_clip.fl_image(chroma_mask_func)
        mask_clip.is_mask = True
        # Apply the generated mask to the foreground clip
        fg_masked = fg_clip.set_mask(mask_clip)
        logger.info("Chroma mask applied to foreground.")
    except Exception as e:
        logger.error(f"Failed to apply chroma mask: {e}", exc_info=True)
        raise RuntimeError(f"Error applying chroma mask: {e}") from e

    logger.info("Compositing final video.")
    try:
        # Composite background and masked foreground
        final_clip = CompositeVideoClip(
            [bg_concat, fg_masked],
            size=fg_size,
            use_bgclip=True  # Use background as the base canvas
        ).set_duration(fg_duration)
    except Exception as e:
        logger.error(f"Failed to composite clips: {e}", exc_info=True)
        raise RuntimeError(f"Error during final composition: {e}") from e

    logger.info(f"Writing final video to: {output_path}")
    try:
        # Write video with specified settings
        final_clip.write_videofile(
            output_path,
            fps=fg_fps,
            codec="libx264",
            audio_codec="aac",
            bitrate="8000k",
            preset="medium",  # Good balance of speed and quality
            threads=max(1, os.cpu_count() // 2),  # Use half CPU cores
            logger='bar',
            ffmpeg_params=["-crf", "22"]  # Constant Rate Factor (lower=better)
        )
        logger.info(f"Successfully created chroma key video: {output_path}")
    except Exception as e:
        logger.error(f"Failed to write final video: {e}", exc_info=True)
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError as rm_e:
                logger.warning(f"Could not remove partial output {output_path}: {rm_e}")
        raise RuntimeError(f"Failed to write video file: {e}") from e
    finally:
        # Ensure all moviepy clips are closed to release resources
        logger.info("Closing video clips...")
        try:
            fg_clip.close()
            bg_concat.close()
            final_clip.close()
            for clip in bg_clips:
                clip.close()
        except Exception as close_e:
            logger.warning(f"Error closing moviepy clips: {close_e}")

        # Optionally remove downloaded background videos
        # for path in downloaded_paths:
        #     try:
        #         if os.path.exists(path):
        #             os.remove(path)
        #             logger.info(f"Removed temporary background file: {path}")
        #     except OSError as rm_e:
        #         logger.warning(f"Could not remove temp file {path}: {rm_e}") 