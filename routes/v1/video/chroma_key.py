from flask import Blueprint, request, jsonify
import logging
import os
import uuid
# from marshmallow import Schema, fields, ValidationError # Removed unused imports

# Import utils EXCEPT authenticate
from app_utils import queue_task_wrapper, validate_payload
# Import authenticate from its correct location
from services.authentication import authenticate
from services.v1.video.chroma_service import chroma_key_video

logger = logging.getLogger(__name__)

v1_video_chroma_key_bp = Blueprint('v1_video_chroma_key_bp', __name__)

# Define schema for the chroma key payload
CHROMA_KEY_SCHEMA = {
    "type": "object",
    "properties": {
        "input_path": {
            "type": "string",
            "description": "Path or URL to the foreground video file."
        },
        "pexels_term": {
            "type": "string",
            "description": "Search term for background videos on Pexels."
        },
        "output_filename": {
            "type": "string",
            "description": "Desired filename for the output video (e.g., my_video.mp4)."
        },
        "webhook_url": {
            "type": "string",
            "format": "uri",
            "description": "Optional URL for completion notification."
        },
        "chroma_color": {
            "type": "string",
            "pattern": "^#[0-9a-fA-F]{6}$",
            "default": "#00FF00",
            "description": "Hex color for chroma key (default: green)."
        },
        "threshold": {
            "type": "integer",
            "minimum": 10,
            "maximum": 100,
            "default": 40,
            "description": "Chroma key sensitivity (10-100)."
        },
        "transition": {
            "type": "number",
            "minimum": 0,
            "default": 1.0,
            "description": "Fade transition duration (seconds)."
        },
        "effect": {
            "type": "string",
            "enum": ["fade", "contrast", None],
            "default": "fade",
            "description": "Effect for background clips."
        },
    },
    "required": ["input_path", "pexels_term", "output_filename"]
}

# Get PEXELS_API_KEY from environment variables
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
if not PEXELS_API_KEY:
    # TODO: Consider how to handle this error gracefully in a Flask app
    # For now, raising an error will prevent the app from starting if the key is missing
    raise ValueError("PEXELS_API_KEY environment variable not set.")

@v1_video_chroma_key_bp.route('/v1/video/chroma_key', methods=['POST'])
@authenticate
@validate_payload(CHROMA_KEY_SCHEMA)
def queue_chroma_key_task():
    """Queues a background task to apply chroma key to a video."""
    payload = request.json
    job_id = str(uuid.uuid4())
    logger.info(f"Job {job_id}: Received chroma_key request")

    # --- Input Handling --- Need to potentially download input_path if it's a URL
    # For now, assume input_path is accessible locally within the container/storage
    # A more robust solution would download URL inputs first.
    local_input_path = payload["input_path"]
    if not os.path.exists(local_input_path):
        # Basic check, might need volume mapping understanding
        if not local_input_path.startswith(os.environ.get("STORAGE_BASE_PATH", "/app/storage")):
            logger.error(f"Job {job_id}: Input path '{local_input_path}' does not seem to be in the accessible storage area.")
            # Consider making this a hard error if paths must be local
            # return jsonify({"message": "Input path must be accessible within the service storage"}), 400

    # --- Output Path --- Generate full output path in storage
    storage_base = os.environ.get("STORAGE_BASE_PATH", "/app/storage")
    output_dir = os.path.join(storage_base, job_id)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, payload["output_filename"])

    # --- Task Arguments --- Prepare arguments for the service function
    task_args = {
        "input_path": local_input_path,
        "pexels_term": payload["pexels_term"],
        "output_path": output_path,
        "chroma_color": payload.get("chroma_color", CHROMA_KEY_SCHEMA["properties"]["chroma_color"]["default"]),
        "threshold": payload.get("threshold", CHROMA_KEY_SCHEMA["properties"]["threshold"]["default"]),
        "transition": payload.get("transition", CHROMA_KEY_SCHEMA["properties"]["transition"]["default"]),
        "effect": payload.get("effect", CHROMA_KEY_SCHEMA["properties"]["effect"]["default"]),
    }

    # --- Queue Task --- Use the wrapper
    result = queue_task_wrapper(
        job_id,
        chroma_key_video,
        task_args,
        payload.get("webhook_url"),
        request.path
    )

    return jsonify(result), 202 