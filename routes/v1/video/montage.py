import os
import logging
import uuid
from flask import Blueprint, request, jsonify
from marshmallow import Schema, fields
from app_utils import queue_task_wrapper, validate_payload
from services.authentication import authenticate
from services.v1.video.montage_service import pexels_montage

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
    pexels_query = fields.String(required=True)
    num_clips = fields.Integer(load_default=5)
    clip_duration = fields.Integer(load_default=5)
    output_filename = fields.String(required=True)
    webhook_url = fields.Url(required=False)
    transition_type = fields.String(load_default="fade", enum=["fade", "slide", "wipe"])
    audio_track_url = fields.Url(required=False)

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
        "pexels_term": payload["pexels_query"],
        "n_videos": payload.get("num_clips", 5),
        "min_duration": payload.get("clip_duration", 5),
        "max_duration": payload.get("clip_duration", 5),
        "output_path": full_output_path,
        "transition": 1.5,
        "target_fps": payload.get("target_fps", 24),
        "target_size": payload.get("target_size", (1920, 1080)),
        "apply_color_correction": payload.get("apply_color_correction", True)
    }

    logger.info(f"Job {job_id}: Queuing montage task with args: {task_args}")

    result = queue_task_wrapper(
        job_id,
        pexels_montage,
        task_args,
        payload.get("webhook_url"),
        request.path,
        output_file_path_relative=relative_output_path
    )
    
    logger.info(f"Job {job_id}: Task queued. Response: {result}")
    return jsonify(result), 202 