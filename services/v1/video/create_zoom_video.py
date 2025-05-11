# Copyright (c) 2025 Stephen G. Pope
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os
import subprocess
import logging
from services.file_management import download_file
from config import LOCAL_STORAGE_PATH

# Set up logging
logger = logging.getLogger(__name__)

def generate_zoom_video_from_image(image_path, output_path, duration, zoom_type="in", custom=None):
    """
    Generate a video with zoom effect from an image.
    
    Args:
        image_path (str): Path to the input image
        output_path (str): Path for the output video
        duration (float): Duration of the video in seconds
        zoom_type (str): Type of zoom effect ("in" or "out")
        custom (dict): Custom overrides for zoom and fps/resolution
        
    Returns:
        str: Path to the generated video
    """
    logger.info(
        f"Generating zoom video from image {image_path} with duration {duration}s"
    )
    
    # Determine zoom parameters based on zoom type
    if zoom_type == "in":
        # Start normal, end zoomed in
        zoom_start = 1.0
        zoom_end = 1.3
    elif zoom_type == "out":
        # Start zoomed in, end normal
        zoom_start = 1.3
        zoom_end = 1.0
    else:
        # Random zoom movement (pan effect)
        zoom_start = 1.0
        zoom_end = 1.15
    
    try:
        # Handle custom overrides
        user_custom = custom or {}
        # Zoom range and speed percentage
        zoom_speed_pct = user_custom.get('zoom_speed', 100) / 100
        # Frame rate and resolution
        fps = user_custom.get('fps', 30)
        resolution = user_custom.get('resolution', '3840:2160')
        # Override zoom start/end if provided
        zoom_start = user_custom.get('zoom_start', zoom_start)
        zoom_end = user_custom.get('zoom_end', zoom_end)
        # Calculate frames and per-frame speed
        total_frames = int(duration * fps)
        speed = (zoom_end - zoom_start) * zoom_speed_pct / total_frames
        # Build zoompan filter
        filter_str = (
            f"zoompan=z='if(eq(on,0),{zoom_start},zoom+{speed})':"
            f"d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',fps={fps},"
            f"scale={resolution}"
        )

        # Command to generate video with zoom effect using ffmpeg
        threads = os.cpu_count() or 1
        cmd = [
            'ffmpeg',
            '-threads', str(threads),
            '-loop', '1',           # Loop a single image
            '-i', image_path,       # Input image
            '-vf', filter_str,
            '-t', str(duration),    # Set output duration explicitly
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-crf', '18',
            '-preset', 'slow',
            output_path
        ]
        
        logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
        
        # Run the FFmpeg command
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode != 0:
            logger.error(f"Error during zoom video generation: {process.stderr}")
            raise Exception(f"FFmpeg error: {process.stderr}")
            
        return output_path
        
    except Exception as e:
        logger.error(f"Zoom video generation failed: {str(e)}")
        raise

def combine_video_with_audio(video_path, audio_path, output_path):
    """
    Combine a video with an audio file.
    
    Args:
        video_path (str): Path to the video file
        audio_path (str): Path to the audio file
        output_path (str): Path for the output video with audio
        
    Returns:
        str: Path to the combined video
    """
    logger.info(
        f"Combining video {video_path} with audio {audio_path}"
    )
    
    try:
        # Command to combine video with audio using ffmpeg
        cmd = [
            'ffmpeg',
            '-i', video_path,       # Input video
            '-i', audio_path,       # Input audio
            '-map', '0:v',          # Map video from first input
            '-map', '1:a',          # Map audio from second input
            '-c:v', 'copy',         # Copy video stream without re-encoding
            '-c:a', 'aac',          # Audio codec
            '-b:a', '192k',         # Audio bitrate
            '-shortest',            # End when shortest input ends
            output_path             # Output path
        ]
        
        logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
        
        # Run the FFmpeg command
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode != 0:
            logger.error(f"Error during video-audio combination: {process.stderr}")
            raise Exception(f"FFmpeg error: {process.stderr}")
            
        return output_path
        
    except Exception as e:
        logger.error(f"Video-audio combination failed: {str(e)}")
        raise

def concatenate_videos(video_paths, output_path):
    """
    Concatenate multiple videos into one.
    
    Args:
        video_paths (list): List of paths to the videos to concatenate
        output_path (str): Path for the concatenated video
        
    Returns:
        str: Path to the concatenated video
    """
    logger.info(f"Concatenating {len(video_paths)} videos")
    
    try:
        # Create a temporary file for the concat list
        concat_file_path = f"{output_path}_concat_list.txt"
        
        with open(concat_file_path, 'w') as concat_file:
            for video_path in video_paths:
                # Write absolute paths to the concat list
                concat_file.write(f"file '{os.path.abspath(video_path)}'\n")
        
        # Command to concatenate videos using ffmpeg
        cmd = [
            'ffmpeg',
            '-f', 'concat',         # Concatenate format
            '-safe', '0',           # Allow unsafe file paths
            '-i', concat_file_path,  # Input concat list
            '-c', 'copy',           # Copy streams without re-encoding
            output_path             # Output path
        ]
        
        logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
        
        # Run the FFmpeg command
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        # Clean up the concat list file
        if os.path.exists(concat_file_path):
            os.remove(concat_file_path)
        
        if process.returncode != 0:
            logger.error(f"Error during video concatenation: {process.stderr}")
            raise Exception(f"FFmpeg error: {process.stderr}")
            
        return output_path
        
    except Exception as e:
        logger.error(f"Video concatenation failed: {str(e)}")
        raise

def process_create_zoom_video(content_data, job_id):
    """
    Process a request to create a video with zoom effects for multiple scenes.
    
    Args:
        content_data (dict): Data containing content and scenes information
        job_id (str): Unique job identifier
        
    Returns:
        str: Path to the final video
    """
    logger.info(f"Starting zoom video creation for job {job_id}")
    
    # Create temporary directory for all files
    temp_dir = os.path.join(LOCAL_STORAGE_PATH, job_id)
    os.makedirs(temp_dir, exist_ok=True)
    
    # List to store all temporary files for cleanup
    temp_files = []
    
    try:
        # List to store paths of individual scene videos
        scene_videos = []
        
        # Process each scene
        conteudo = content_data.get('conteudo', {})
        cenas = content_data.get('cenas', [])
        
        logger.info(f"Processing {len(cenas)} scenes for video creation")
        
        for i, scene in enumerate(cenas):
            logger.info(f"Processing scene {i+1}/{len(cenas)}")
            
            scene_id = scene.get('id', f"scene_{i}")
            image_url = scene.get('urlImagem')
            audio_url = scene.get('urlAudio')
            duration = scene.get('duracao', 10)  # Default to 10 seconds if not specified
            
            if not image_url or not audio_url:
                logger.warning(f"Missing image or audio URL for scene {scene_id}, skipping")
                continue
            
            # Download image and audio
            image_path = download_file(image_url, temp_dir)
            audio_path = download_file(audio_url, temp_dir)
            
            temp_files.extend([image_path, audio_path])
            
            # Generate zoom video from image
            zoom_video_path = os.path.join(temp_dir, f"{scene_id}_zoom.mp4")
            generate_zoom_video_from_image(image_path, zoom_video_path, duration)
            temp_files.append(zoom_video_path)
            
            # Combine zoom video with audio
            scene_video_path = os.path.join(temp_dir, f"{scene_id}_with_audio.mp4")
            combine_video_with_audio(zoom_video_path, audio_path, scene_video_path)
            temp_files.append(scene_video_path)
            
            scene_videos.append(scene_video_path)
        
        if not scene_videos:
            raise ValueError("No valid scenes were processed, cannot create video")
        
        # Concatenate all scene videos into the final video
        final_video_path = os.path.join(LOCAL_STORAGE_PATH, f"{job_id}_final.mp4")
        concatenate_videos(scene_videos, final_video_path)
        
        logger.info(f"Final video created successfully: {final_video_path}")
        
        return final_video_path
    
    except Exception as e:
        logger.error(f"Error during zoom video creation: {str(e)}")
        raise
    
    finally:
        # Clean up temporary files
        for file_path in temp_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.debug(f"Removed temporary file: {file_path}")
                except Exception as e:
                    logger.warning(
                        f"Failed to remove temporary file {file_path}: {str(e)}"
                    ) 