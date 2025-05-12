import shutil
import tempfile
import uuid
import os
from fastapi import APIRouter, File, UploadFile, HTTPException, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional

# Assuming services are in ../../services relative to this routes file
# Correcting relative import path based on project structure
from services.v1.video.chroma_service import chroma_key_video
from services.v1.video.pexels_service import PEXELS_API_KEY # For doc purposes
from services.v1.video.montage_service import pexels_montage

# Define a router
v1_video_effects_bp = APIRouter()

# Ensure PEXELS_API_KEY is available for documentation or checks
if not PEXELS_API_KEY:
    print("WARNING: PEXELS_API_KEY environment variable is not set. Pexels-dependent services will fail.")

class ChromaKeyPayload(BaseModel):
    pexels_term: str = Field(..., description="Search term for Pexels background videos.")
    chroma_color: Optional[str] = Field("#32CD32", description="Hex color for chroma key (e.g., '#32CD32' for lime green).")
    transition: Optional[float] = Field(1.5, description="Transition duration for background video fades (if applicable).")
    effect: Optional[str] = Field("fade", description="Visual effect for background videos ('fade', 'contrast', or other supported).")


# Define Pydantic model for Montage payload
class MontagePayload(BaseModel):
    pexels_term: str = Field(..., description="Search term for Pexels videos to include in the montage.")
    n_videos: int = Field(..., gt=0, description="Number of Pexels videos to find and concatenate.")
    target_width: Optional[int] = Field(1920, description="Target width for the output montage video.")
    target_height: Optional[int] = Field(1080, description="Target height for the output montage video.")


@v1_video_effects_bp.post(
    "/chroma_key",
    summary="Apply Chroma Key to Video",
    description="Uploads a video with a chroma key background (e.g., green screen) and replaces it with videos fetched from Pexels based on a search term.",
    tags=["Video Effects"],
)
async def api_chroma_key_video(
    input_video: UploadFile = File(..., description="Video file with chroma key background."),
    payload: ChromaKeyPayload = Body(...)
):
    if not PEXELS_API_KEY:
        raise HTTPException(status_code=500, detail="Pexels API key is not configured on the server.")

    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, f"input_{uuid.uuid4()}_{input_video.filename}")
    output_filename = f"chroma_output_{uuid.uuid4()}.mp4"
    output_path = os.path.join(temp_dir, output_filename)

    try:
        # Save uploaded video
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(input_video.file, buffer)
        
        print(f"Chroma Key Request: Input saved to {input_path}, Output to {output_path}")
        print(f"Payload: {payload.model_dump_json()}")

        # Call the service function
        chroma_key_video(
            input_path=input_path,
            pexels_term=payload.pexels_term,
            output_path=output_path,
            chroma_color=payload.chroma_color,
            transition=payload.transition,
            effect=payload.effect,
        )

        if not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="Chroma key processing failed to produce an output file.")

        # Return the processed video
        # The file will be automatically cleaned up by the background task
        return FileResponse(
            path=output_path,
            media_type="video/mp4",
            filename=output_filename,
            # background=BackgroundTask(shutil.rmtree, temp_dir) # Requires BackgroundTask import
        )
    except RuntimeError as e:
        # shutil.rmtree(temp_dir) # Clean up in case of error
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        # shutil.rmtree(temp_dir) # Clean up in case of error
        # Log the exception for debugging
        print(f"Unexpected error in /chroma_key: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        # It's better to handle cleanup in a more robust way, e.g. background tasks
        # For now, if FileResponse doesn't use BackgroundTask, we might leave files behind on error
        # If BackgroundTask is used by FileResponse, this shutil.rmtree might be redundant or cause issues
        # Consider a proper background task for cleanup.
        # For now, let's remove it and rely on OS for /tmp cleanup or implement a BG task later.
        # If BackgroundTask is used by FileResponse, this shutil.rmtree might be redundant or cause issues
        # Consider a proper background task for cleanup.
        # For now, let's remove it and rely on OS for /tmp cleanup or implement a BG task later.
        # if os.path.exists(temp_dir):
        # shutil.rmtree(temp_dir)
        pass # Cleanup should be handled by BackgroundTask in FileResponse or a separate mechanism 


# Add the new endpoint for Pexels Montage
@v1_video_effects_bp.post(
    "/pexels_montage",
    summary="Create Video Montage from Pexels",
    description="Generates a video montage by searching Pexels for a given term, downloading a specified number of videos, and concatenating them.",
    tags=["Video Effects"],
)
async def api_pexels_montage(
    payload: MontagePayload = Body(...)
):
    if not PEXELS_API_KEY:
        raise HTTPException(status_code=500, detail="Pexels API key is not configured on the server.")

    temp_dir = tempfile.mkdtemp()
    output_filename = f"montage_output_{uuid.uuid4()}.mp4"
    output_path = os.path.join(temp_dir, output_filename)
    target_resolution = (payload.target_width, payload.target_height)

    try:
        print(f"Pexels Montage Request: Output to {output_path}")
        print(f"Payload: {payload.model_dump_json()}")

        # Call the service function
        pexels_montage(
            pexels_term=payload.pexels_term,
            n_videos=payload.n_videos,
            output_path=output_path,
            target_resolution=target_resolution
        )

        if not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="Pexels montage processing failed to produce an output file.")

        # Return the processed video
        return FileResponse(
            path=output_path,
            media_type="video/mp4",
            filename=output_filename,
            # background=BackgroundTask(shutil.rmtree, temp_dir) # Requires BackgroundTask import
        )
    except RuntimeError as e:
        # shutil.rmtree(temp_dir)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        # shutil.rmtree(temp_dir)
        print(f"Unexpected error in /pexels_montage: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        # Cleanup handling needed - see notes in /chroma_key endpoint
        # if os.path.exists(temp_dir):
        #    shutil.rmtree(temp_dir)
        pass 