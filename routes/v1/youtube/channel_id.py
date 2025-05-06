from flask import Blueprint, request, jsonify
from services.v1.youtube.channel_id import get_channel_id_from_url
from app_utils import validate_json_request, LOG

youtube_channel_id_bp = Blueprint(
    'youtube_channel_id_bp', __name__, url_prefix='/v1/youtube'
)

@youtube_channel_id_bp.route('/get_channel_id', methods=['POST'])
@validate_json_request(['youtube_url'])
def handle_get_channel_id():
    """
    API endpoint to get YouTube channel ID from a URL.
    Expects a JSON payload with 'youtube_url'.
    """
    data = request.get_json()
    youtube_url = data.get('youtube_url')

    if not youtube_url:
        LOG.error("youtube_url not provided in request")
        return jsonify({"error": "'youtube_url' is required"}), 400

    LOG.info(f"Received request to get channel ID for URL: {youtube_url}")

    try:
        channel_id = get_channel_id_from_url(youtube_url)
        if channel_id:
            LOG.info(
                f"Extracted channel ID: {channel_id} for URL: {youtube_url}"
            )
            return jsonify({
                "channel_id": channel_id,
                "youtube_url": youtube_url
            }), 200
        else:
            LOG.warning(f"Could not extract channel ID for URL: {youtube_url}")
            return jsonify({
                "error": "Could not extract channel ID from provided URL.",
                "youtube_url": youtube_url
            }), 404
    except Exception as e:
        LOG.error(f"Error processing get_channel_id for {youtube_url}: {str(e)}")
        return jsonify({
            "error": "An unexpected error occurred.",
            "details": str(e)
        }), 500 