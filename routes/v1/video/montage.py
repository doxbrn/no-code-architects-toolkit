from flask import Blueprint, request, jsonify
import logging
import os
import uuid

# Import utils EXCEPT authenticate
from app_utils import (
    validate_payload, queue_task_wrapper, get_env_var_or_default
)
# Import authenticate from its correct location
from services.authentication import authenticate
from services.v1.video.montage_service import pexels_montage

logger = logging.getLogger(__name__)

v1_video_montage_bp = Blueprint('v1_video_montage_bp', __name__)

# Define schema for the montage payload
MONTAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "pexels_term": {
            "type": "string",
            "description": "Search term for Pexels videos."
        },
        "n_videos": {
            "type": "integer",
            "minimum": 1,
            "maximum": 20,
            "description": "Number of videos for the montage (1-20)."
        },
        "output_filename": {
            "type": "string",
            "description": "Desired filename for output (e.g., my_montage.mp4)."
        },
        "webhook_url": {
            "type": "string",
            "format": "uri",
            "description": "Optional URL for completion notification."
        },
        "min_duration": {
            "type": "integer",
            "minimum": 3,
            "default": 5,
            "description": "Min duration for individual clips."
        },
        "max_duration": {
            "type": "integer",
            "minimum": 5,
            "default": 30,
            "description": "Max duration for individual clips."
        },
        "transition": {
            "type": "number",
            "minimum": 0,
            "default": 1.5,
            "description": "Fade transition duration (seconds)."
        },
        "target_fps": {
            "type": "integer",
            "enum": [24, 25, 30],
            "default": 24,
            "description": "Output FPS (24, 25, or 30)."
        },
        "target_width": {
            "type": "integer",
            "enum": [1280, 1920, 2560, 3840],
            "default": 1920,
            "description": "Output width."
        },
        "target_height": {
            "type": "integer",
            "enum": [720, 1080, 1440, 2160],
            "default": 1080,
            "description": "Output height."
        },
        "apply_color_correction": {
            "type": "boolean",
            "default": True,
            "description": "Apply subtle color correction."
        }
    },
    "required": ["pexels_term", "n_videos", "output_filename"]
}

@v1_video_montage_bp.route('/v1/video/montage', methods=['POST'])
@authenticate
@validate_payload(MONTAGE_SCHEMA)
def queue_montage_task():
    """Queues a background task to create a Pexels video montage."""
    payload = request.json
    job_id = str(uuid.uuid4())
    logger.info(f"Job {job_id}: Received montage request")

    # --- Output Path --- Generate full output path in storage
    storage_base = get_env_var_or_default("STORAGE_BASE_PATH", "/app/storage")
    output_dir = os.path.join(storage_base, job_id)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, payload["output_filename"])

    # --- Task Arguments --- Prepare arguments for the service function
    # Combine width/height defaults from schema
    default_width = MONTAGE_SCHEMA["properties"]["target_width"]["default"]
    default_height = MONTAGE_SCHEMA["properties"]["target_height"]["default"]
    target_size = (
        payload.get("target_width", default_width),
        payload.get("target_height", default_height)
    )

    # Extract defaults from schema cleanly
    min_dur_def = MONTAGE_SCHEMA["properties"]["min_duration"]["default"]
    max_dur_def = MONTAGE_SCHEMA["properties"]["max_duration"]["default"]
    trans_def = MONTAGE_SCHEMA["properties"]["transition"]["default"]
    fps_def = MONTAGE_SCHEMA["properties"]["target_fps"]["default"]
    color_def = MONTAGE_SCHEMA["properties"]["apply_color_correction"]["default"]

    task_args = {
        "pexels_term": payload["pexels_term"],
        "n_videos": payload["n_videos"],
        "output_path": output_path,
        "min_duration": payload.get("min_duration", min_dur_def),
        "max_duration": payload.get("max_duration", max_dur_def),
        "transition": payload.get("transition", trans_def),
        "target_fps": payload.get("target_fps", fps_def),
        "target_size": target_size,
        "apply_color_correction": payload.get("apply_color_correction", color_def)
    }

    # --- Queue Task --- Use the wrapper
    result = queue_task_wrapper(
        job_id,
        pexels_montage,  # The service function
        task_args,
        payload.get("webhook_url"),
        request.path
    )

    return jsonify(result), 202 