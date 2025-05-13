# Corrected import path
from services.v1.video.pexels_service import get_pexels_videos_for_duration, download_asset
# Updated imports for moviepy v2.x
from moviepy import VideoFileClip, concatenate_videoclips, vfx
import os


def pexels_montage(pexels_term, n_videos, output_path, target_resolution=(1920, 1080)):
    """Creates a montage video from Pexels clips."""
    print(f"Searching for {n_videos} Pexels videos matching '{pexels_term}'")
    # We ask for more videos initially to increase chances of getting enough unique ones
    urls, _ = get_pexels_videos_for_duration(
        pexels_term, total_duration=9999, max_videos=n_videos * 2 # Request more initially
    )

    if not urls:
        raise RuntimeError(f"No Pexels videos found for the term: {pexels_term}")

    # Ensure we only use up to n_videos
    urls = urls[:n_videos]
    print(f"Found {len(urls)} videos to use for the montage.")

    clips = []
    for i, url in enumerate(urls):
        filename = f"montage_{pexels_term.replace(' ', '_')}_{i}.mp4"
        path = download_asset(url, filename)
        try:
            # Use updated import
            clip = VideoFileClip(path)
            # Resize to target resolution (e.g., 1920x1080)
            clip = clip.fx(vfx.resize, newsize=target_resolution)
            # Apply effects: slight color boost, fade in/out
            clip = clip.fx(vfx.colorx, 1.1)
            clip = clip.fx(vfx.fadein, 1.5)
            clip = clip.fx(vfx.fadeout, 1.5)
            clips.append(clip)
            print(f"Processed clip {i+1} for montage.")
        except Exception as e:
            print(f"Error processing montage video {path}: {e}. Skipping.")
            if os.path.exists(path):
                 try: # Attempt to remove corrupted download
                      os.remove(path)
                 except OSError as remove_error:
                      print(f"Could not remove corrupted file {path}: {remove_error}")

    if not clips:
         raise RuntimeError("Failed to process any videos for the montage.")

    print("Concatenating montage clips...")
    # Concatenate with crossfade effect
    # Use updated import
    final_montage = concatenate_videoclips(
        clips, method="compose", padding=-1.5, bg_color=(0, 0, 0)
    )

    print(f"Writing final montage video to {output_path}...")
    final_montage.write_videofile(
        output_path,
        fps=24, # Standard film FPS
        codec="libx264",
        audio_codec="aac",
        preset='slow', # Better quality preset
        bitrate="15000k", # High bitrate for montage
        threads=os.cpu_count() or 2, # Use more threads
        logger='bar', # Show progress
    )
    print("Montage video generation complete.")

    # Optional cleanup
    # for clip in clips:
    #    if clip.filename and os.path.exists(clip.filename):
    #        os.remove(clip.filename)
    # print("Cleaned up temporary montage files.") 