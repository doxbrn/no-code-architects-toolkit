import os
import logging
import uuid
from flask import Blueprint, request, jsonify
from marshmallow import Schema, fields, ValidationError
from app_utils import queue_task_wrapper, validate_payload
from services.authentication import authenticate
from services.v1.video.montage_service import create_montage_async

logger = logging.getLogger(__name__)

# Get PEXELS_API_KEY from environment variables
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
if not PEXELS_API_KEY:
    # TODO: Consider how to handle this error gracefully in a Flask app
    raise ValueError("PEXELS_API_KEY environment variable not set.")

v1_video_montage_bp = Blueprint(
    "v1_video_montage", __name__, url_prefix="/v1/video"
)

# Define schema for the montage payload
class MontagePayloadSchema(Schema):
    pexels_query = fields.String(required=True, description="Search query for Pexels videos.")
    num_clips = fields.Integer(missing=5, description="Number of video clips to include.")
    clip_duration = fields.Integer(missing=5, description="Duration of each clip in seconds.")
    output_filename = fields.String(required=True, description="Filename for the output montage video.")
    webhook_url = fields.Url(required=False, description="Optional URL for completion notification.")
    transition_type = fields.String(missing="fade", enum=["fade", "slide", "wipe"], description="Transition type between clips.")
    audio_track_url = fields.Url(required=False, description="URL of an audio track to add to the montage.")

@v1_video_montage_bp.route("/montage", methods=["POST"])
@authenticate
@validate_payload(MontagePayloadSchema())
def handle_montage_request():
    payload = request.json
    job_id = str(uuid.uuid4())
    logger.info(f"Job {job_id}: Received montage request with payload: {payload}")

    # --- Output Path --- Generate full output path in storage
    # Use os.environ.get for STORAGE_BASE_PATH
    storage_base = os.environ.get("STORAGE_BASE_PATH", "/app/storage")
    output_dir = os.path.join(storage_base, job_id)
    os.makedirs(output_dir, exist_ok=True)
    # Construct a relative path for the output file to be stored in job details
    output_filename = payload.get("output_filename", f"{job_id}_montage.mp4")
    # Ensure the filename from payload is used if provided, otherwise generate one.
    # The schema requires output_filename, so it should always be present.
    relative_output_path = os.path.join(job_id, output_filename) # Path relative to storage_base
    full_output_path = os.path.join(output_dir, output_filename) # Absolute path


    task_args = {
        "pexels_query": payload["pexels_query"],
        "num_clips": payload.get("num_clips", 5),
        "clip_duration": payload.get("clip_duration", 5),
        "output_path": full_output_path, # Use full_output_path
        "transition_type": payload.get("transition_type", "fade"),
        "audio_track_url": payload.get("audio_track_url"),
        "pexels_api_key": PEXELS_API_KEY, # Pass the key to the service
    }

    logger.info(f"Job {job_id}: Queuing montage task with args: {task_args}")

    result = queue_task_wrapper(
        job_id,
        create_montage_async, # Target function for the async task
        task_args,
        payload.get("webhook_url"),
        request.path,
        # Pass the relative path for storage in job details
        output_file_path_relative=relative_output_path
    )
    
    logger.info(f"Job {job_id}: Task queued. Response: {result}")
    return jsonify(result), 202 