from flask import Blueprint, request, jsonify, current_app
from services.v1.youtube.channel_id import get_channel_id_from_url
from app_utils import validate_payload

youtube_channel_id_bp = Blueprint(
    'youtube_channel_id_bp', __name__, url_prefix='/v1/youtube'
)


# Define JSON schema for request validation
CHANNEL_ID_SCHEMA = {
    "type": "object",
    "required": ["youtube_url"],
    "properties": {
        "youtube_url": {"type": "string"}
    }
}

@youtube_channel_id_bp.route('/get_channel_id', methods=['POST'])
@validate_payload(CHANNEL_ID_SCHEMA)
def handle_get_channel_id():
    """
    API endpoint to get YouTube channel ID from a URL.
    Expects a JSON payload with 'youtube_url'.
    """
    data = request.get_json()
    youtube_url = data.get('youtube_url')

    if not youtube_url:
        return jsonify({"error": "'youtube_url' is required"}), 400

    current_app.logger.info(f"Received request to get channel ID for URL: {youtube_url}")

    try:
        channel_id = get_channel_id_from_url(youtube_url)
        if channel_id:
            current_app.logger.info(
                f"Extracted channel ID: {channel_id} for URL: {youtube_url}"
            )
            return jsonify({
                "channel_id": channel_id,
                "youtube_url": youtube_url
            }), 200
        else:
            current_app.logger.warning(f"Could not extract channel ID for URL: {youtube_url}")
            return jsonify({
                "error": "Could not extract channel ID from provided URL.",
                "youtube_url": youtube_url
            }), 404
    except Exception as e:
        current_app.logger.error(f"Error processing get_channel_id for {youtube_url}: {str(e)}")
        return jsonify({
            "error": "An unexpected error occurred.",
            "details": str(e)
        }), 500 