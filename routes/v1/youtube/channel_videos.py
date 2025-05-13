from flask import Blueprint, request, jsonify, current_app
from services.v1.youtube.channel_videos import get_videos_by_channel_id
from app_utils import validate_payload


youtube_channel_videos_bp = Blueprint(
    'youtube_channel_videos_bp', __name__, url_prefix='/v1/youtube'
)


# Define JSON schema for request validation
CHANNEL_VIDEOS_SCHEMA = {
    "type": "object",
    "required": ["channel_id"],
    "properties": {
        "channel_id": {"type": "string"},
        "max_results": {"type": "integer", "minimum": 1, "maximum": 50000},
        "order_by": {"type": "string", "enum": ["viewCount", "date", "rating", "title"]}
    }
}


@youtube_channel_videos_bp.route('/get_channel_videos', methods=['POST'])
@validate_payload(CHANNEL_VIDEOS_SCHEMA)
def handle_get_channel_videos():
    """
    API endpoint para obter vídeos de um canal do YouTube.
    Espera um payload JSON com 'channel_id' e opcionalmente 'max_results' e 'order_by'.
    """
    data = request.get_json()
    channel_id = data.get('channel_id')
    max_results = data.get('max_results', 500)
    order_by = data.get('order_by', 'viewCount')

    if not channel_id:
        return jsonify({"error": "'channel_id' é obrigatório"}), 400

    current_app.logger.info(
        f"Requisição recebida para obter vídeos do canal ID: {channel_id}, max_results: {max_results}"
    )

    try:
        # Chamar o serviço para obter os vídeos
        result = get_videos_by_channel_id(
            channel_id=channel_id, 
            max_results=max_results,
            order_by=order_by
        )
        
        # Verificar se houve erro no processamento
        if 'error' in result:
            current_app.logger.error(
                f"Erro ao buscar vídeos do canal {channel_id}: {result['error']}"
            )
            return jsonify(result), 404
        
        # Log de sucesso
        current_app.logger.info(
            f"Vídeos obtidos com sucesso para o canal {channel_id}. "
            f"Total: {result['total_videos_fetched']}"
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        current_app.logger.error(
            f"Erro ao processar get_channel_videos para {channel_id}: {str(e)}"
        )
        return jsonify({
            "error": "Ocorreu um erro inesperado.",
            "details": str(e)
        }), 500 