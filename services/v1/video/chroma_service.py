# Corrected import path
from services.v1.video.pexels_service import get_pexels_videos_for_duration, download_asset
# Try importing the editor module directly
import moviepy.editor as mpy
# from moviepy.editor import (
#     VideoFileClip,
#     CompositeVideoClip,
#     concatenate_videoclips
# )
from moviepy import vfx # Import vfx module directly
import numpy as np
import os


def chroma_key_video(
    input_path,
    pexels_term,
    output_path,
    chroma_color="#32CD32", # Lime Green default
    transition=1.5, # Default transition duration
    effect="fade", # Default background effect
):
    """Applies chroma key effect, replacing background with Pexels videos."""
    
    # Use mpy prefix
    fg_clip = mpy.VideoFileClip(input_path)
    fg_duration = fg_clip.duration

    print(f"Looking for background videos for '{pexels_term}' with total duration ~{fg_duration:.2f}s")
    bg_urls, _ = get_pexels_videos_for_duration(
        pexels_term, fg_duration, min_duration=5, max_duration=60, max_videos=10
    )

    if not bg_urls:
        raise RuntimeError(f"Could not find suitable Pexels videos for query: {pexels_term}")

    print(f"Found {len(bg_urls)} potential background videos from Pexels.")

    bg_clips = []
    total_bg_duration = 0
    for i, url in enumerate(bg_urls):
        # Construct a more descriptive filename
        filename = f"chroma_bg_{pexels_term.replace(' ', '_')}_{i}.mp4"
        bg_path = download_asset(url, filename)
        try:
            # Use mpy prefix
            clip = mpy.VideoFileClip(bg_path)
            # Ensure background matches foreground dimensions
            if clip.size != fg_clip.size:
                print(f"Resizing background clip {i+1} to match foreground size {fg_clip.size}.")
                clip = clip.resize(fg_clip.size)

            # Apply visual effects to the background clip
            if effect == "contrast":
                clip = clip.fx(vfx.colorx, 1.2) # Use .fx() method
            elif effect == "fade" and transition > 0:
                # Apply fade in and fade out using .fx()
                clip = clip.fx(vfx.fadein, transition).fx(vfx.fadeout, transition)

            bg_clips.append(clip)
            total_bg_duration += clip.duration
            print(f"Added background clip {i+1} ({clip.duration:.2f}s). Total BG duration: {total_bg_duration:.2f}s")

            # Stop if we have enough background footage
            if total_bg_duration >= fg_duration:
                break
        except Exception as e:
            print(f"Error processing background video {bg_path}: {e}. Skipping.")
            if os.path.exists(bg_path):
                 try: # Attempt to remove corrupted download
                      os.remove(bg_path)
                 except OSError as remove_error:
                      print(f"Could not remove corrupted file {bg_path}: {remove_error}")

    if not bg_clips:
         raise RuntimeError("Failed to process any background videos.")

    # Concatenate background clips
    # Using compose method with negative padding for crossfade effect
    print("Concatenating background clips...")
    # Use mpy prefix
    bg_concat = mpy.concatenate_videoclips(
        bg_clips, method="compose", padding=-transition, bg_color=(0, 0, 0)
    ).subclip(0, fg_duration) # Trim to exact foreground duration

    # Prepare chroma key mask
    # Convert hex color string to RGB tuple
    chroma_rgb = tuple(int(chroma_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    print(f"Using chroma key color: {chroma_rgb}")

    # Define the masking function based on color distance
    # Increased tolerance slightly for potentially imperfect green screens
    def chroma_mask_func(frame):
        # Calculate Euclidean distance in RGB space (more robust than simple diff)
        # Normalize frame and color to 0-1 range if necessary (depends on frame dtype)
        # Assuming frame is uint8 [0, 255]
        target_color = np.array(chroma_rgb, dtype=np.uint8)
        # Calculate squared distance for efficiency
        dist_sq = np.sum((frame.astype(np.int16) - target_color.astype(np.int16))**2, axis=-1)
        # Tolerance: lower value is stricter (adjust as needed)
        tolerance_sq = 60**2 # Adjust this value based on green screen quality
        mask = dist_sq < tolerance_sq
        # Return inverted mask (1.0 where it's NOT green, 0.0 where it IS green)
        return 1.0 - mask.astype(float)

    print("Generating chroma key mask...")
    # Apply the masking function to the foreground clip
    # Use mpy prefix (fl_image is a method of the clip object, no change needed here)
    mask_clip = fg_clip.fl_image(chroma_mask_func)
    mask_clip = mask_clip.set_duration(fg_clip.duration)
    mask_clip.is_mask = True # Tell moviepy this is a mask

    print("Applying mask to foreground...")
    # Use mpy prefix (set_mask is a method)
    fg_masked = fg_clip.set_mask(mask_clip)

    # Composite the background and masked foreground
    print("Compositing final video...")
    # Use mpy prefix
    final_clip = mpy.CompositeVideoClip(
        [bg_concat, fg_masked.set_position(('center', 'center'))], # Center foreground
        size=fg_clip.size # Ensure final size matches input
    ).set_duration(fg_duration)

    # Write the final video file
    print(f"Writing final video to {output_path}...")
    final_clip.write_videofile(
        output_path,
        fps=fg_clip.fps, # Match original FPS
        codec="libx264",
        audio_codec="aac",
        preset='medium', # Good balance of speed/quality
        bitrate="8000k", # Increased bitrate for potentially complex scenes
        threads=os.cpu_count() or 2, # Use more threads if available
        logger='bar', # Show progress bar
    )
    print("Chroma key video generation complete.")

    # Clean up downloaded files (optional)
    # for clip in bg_clips:
    #    if clip.filename and os.path.exists(clip.filename):
    #        os.remove(clip.filename)
    # print("Cleaned up temporary background files.") 