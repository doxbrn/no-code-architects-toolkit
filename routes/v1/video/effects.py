import shutil
import tempfile
import uuid
import os
# Use Flask components instead of FastAPI
from flask import Blueprint, request, jsonify, send_file, current_app, abort
import traceback
import json

# Correcting relative import path based on project structure
from services.v1.video.chroma_service import chroma_key_video
from services.v1.video.montage_service import pexels_montage
from services.v1.video.pexels_service import PEXELS_API_KEY

# Define a Blueprint
v1_video_effects_bp = Blueprint(
    'v1_video_effects', 
    __name__,
    url_prefix='/v1/video' # Set URL prefix for all routes in this blueprint
)

# Ensure PEXELS_API_KEY is available for documentation or checks
if not PEXELS_API_KEY:
    print("WARNING: PEXELS_API_KEY environment variable is not set. Pexels-dependent services will fail.")

# Helper function for cleanup
def cleanup_dir(path):
    if path and os.path.exists(path):
        try:
            shutil.rmtree(path)
            print(f"Cleaned up temporary directory: {path}")
        except Exception as e:
            print(f"Error cleaning up directory {path}: {e}")

@v1_video_effects_bp.route('/chroma_key', methods=['POST'])
def api_chroma_key_video():
    """Apply Chroma Key to Video using Flask."""
    if not PEXELS_API_KEY:
        return jsonify({"error": "Pexels API key is not configured on the server."}), 500

    if 'input_video' not in request.files:
        return jsonify({"error": "Missing 'input_video' file part."}), 400

    input_video_file = request.files['input_video']
    if input_video_file.filename == '':
        return jsonify({"error": "No selected file for 'input_video'."}), 400

    # Get payload from form data (assuming it's sent as a JSON string field)
    try:
        # Look for payload in form data first
        payload_str = request.form.get('payload')
        if payload_str:
             payload = json.loads(payload_str)
        elif request.is_json:
             # Fallback to request.json if 'payload' form field isn't present
             payload = request.json
        else:
            # If neither form field nor application/json, try getting individual fields
            payload = {
                "pexels_term": request.form.get("pexels_term"),
                "chroma_color": request.form.get("chroma_color", "#32CD32"),
                "transition": float(request.form.get("transition", 1.5)),
                "effect": request.form.get("effect", "fade"),
            }
            if not payload["pexels_term"]:
                raise ValueError("Missing required field: pexels_term")
        
        # Basic validation
        if 'pexels_term' not in payload or not payload['pexels_term']:
            return jsonify({"error": "Missing required field in payload: 'pexels_term'."}), 400
            
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        return jsonify({"error": f"Invalid or missing payload: {str(e)}"}), 400

    temp_dir = None # Initialize to None
    try:
        temp_dir = tempfile.mkdtemp()
        # Ensure filename is safe
        # filename = secure_filename(input_video_file.filename)
        filename = f"input_{uuid.uuid4()}_{input_video_file.filename}" # Use UUID to avoid collisions
        input_path = os.path.join(temp_dir, filename)
        output_filename = f"chroma_output_{uuid.uuid4()}.mp4"
        output_path = os.path.join(temp_dir, output_filename)

        # Save uploaded video
        input_video_file.save(input_path)
        print(f"Chroma Key Request (Flask): Input saved to {input_path}, Output to {output_path}")
        print(f"Payload: {payload}")

        # Call the service function
        chroma_key_video(
            input_path=input_path,
            pexels_term=payload['pexels_term'],
            output_path=output_path,
            chroma_color=payload.get('chroma_color', '#32CD32'),
            transition=float(payload.get('transition', 1.5)),
            effect=payload.get('effect', 'fade'),
        )

        if not os.path.exists(output_path):
             raise RuntimeError("Chroma key processing failed to produce an output file.")

        # Return the processed video using send_file
        # Set as_attachment=True if you want download behavior
        return send_file(
            output_path,
            mimetype='video/mp4',
            as_attachment=False, # Serve inline by default
            download_name=output_filename, # Suggested filename for download
        )
        # Note: send_file doesn't automatically clean up. Cleanup happens in `finally`.

    except RuntimeError as e:
        # Specific errors raised by the service
        print(f"Runtime error in /chroma_key: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        # Catch-all for unexpected errors
        print(f"Unexpected error in /chroma_key: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"An unexpected server error occurred: {str(e)}"}), 500
    finally:
        # Ensure cleanup happens even if send_file is successful or an error occurs
        # This requires the response to be fully sent before cleanup
        # Using flask.after_this_request might be safer if available/appropriate
        cleanup_dir(temp_dir)


@v1_video_effects_bp.route('/pexels_montage', methods=['POST'])
def api_pexels_montage():
    """Create Video Montage from Pexels using Flask."""
    if not PEXELS_API_KEY:
        return jsonify({"error": "Pexels API key is not configured on the server."}), 500

    if not request.is_json:
        return jsonify({"error": "Request must be JSON."}), 400

    payload = request.json

    # Basic validation
    if 'pexels_term' not in payload or not payload['pexels_term']:
        return jsonify({"error": "Missing required field: 'pexels_term'."}), 400
    if 'n_videos' not in payload or not isinstance(payload['n_videos'], int) or payload['n_videos'] <= 0:
        return jsonify({"error": "Missing or invalid required field: 'n_videos' (must be a positive integer)."}), 400

    temp_dir = None # Initialize
    try:
        temp_dir = tempfile.mkdtemp()
        output_filename = f"montage_output_{uuid.uuid4()}.mp4"
        output_path = os.path.join(temp_dir, output_filename)
        
        target_width = payload.get('target_width', 1920)
        target_height = payload.get('target_height', 1080)
        if not isinstance(target_width, int) or not isinstance(target_height, int):
            return jsonify({"error": "Optional fields 'target_width' and 'target_height' must be integers."}), 400
        target_resolution = (target_width, target_height)

        print(f"Pexels Montage Request (Flask): Output to {output_path}")
        print(f"Payload: {payload}")

        # Call the service function
        pexels_montage(
            pexels_term=payload['pexels_term'],
            n_videos=payload['n_videos'],
            output_path=output_path,
            target_resolution=target_resolution
        )

        if not os.path.exists(output_path):
            raise RuntimeError("Pexels montage processing failed to produce an output file.")

        # Return the processed video
        return send_file(
            output_path,
            mimetype='video/mp4',
            as_attachment=False, 
            download_name=output_filename,
        )

    except RuntimeError as e:
        print(f"Runtime error in /pexels_montage: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Unexpected error in /pexels_montage: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"An unexpected server error occurred: {str(e)}"}), 500
    finally:
        cleanup_dir(temp_dir) 