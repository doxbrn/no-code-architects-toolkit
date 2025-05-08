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

from flask import Blueprint
import logging
from app_utils import validate_payload, queue_task_wrapper
from services.v1.video.create_zoom_video import process_create_zoom_video
from services.authentication import authenticate
from services.cloud_storage import upload_file

v1_video_create_zoom_video_bp = Blueprint(
    'v1_video_create_zoom_video', __name__
)
logger = logging.getLogger(__name__)

@v1_video_create_zoom_video_bp.route('/v1/video/create_zoom_video', methods=['POST'])
@authenticate
@validate_payload({
    "type": "object",
    "properties": {
        "conteudo": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "canalId": {"type": "string"},
                "nomeCanal": {"type": "string"},
                "tema": {"type": "string"},
                "status": {"type": "string"},
                "roteiro": {"type": "string"},
                "palavras": {"type": ["integer", "null"]},
                "tamanhoTexto": {"type": ["integer", "null"]},
                "criadoEm": {"type": "string"},
                "modificadoEm": {"type": "string"},
                "cid": {"type": ["integer", "null"]},
                "identificador": {"type": "string"},
                "tituloVideo": {"type": "string"},
                "transcript": {"type": "string"}
            }
        },
        "cenas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "ordem": {"type": "integer"},
                    "status": {"type": "string"},
                    "texto": {"type": "string"},
                    "duracao": {"type": "number"},
                    "urlImagem": {"type": "string", "format": "uri"},
                    "urlAudio": {"type": "string", "format": "uri"},
                    "imagem": {"type": "object"},
                    "audio": {"type": "object"}
                },
                "required": ["id", "urlImagem", "urlAudio", "duracao"]
            },
            "minItems": 1
        },
        "webhook_url": {"type": "string", "format": "uri"},
        "id": {"type": "string"}
    },
    "required": ["cenas"],
    "additionalProperties": False
})
@queue_task_wrapper(bypass_queue=False)
def create_zoom_video(job_id, data):
    """
    Create a video with zoom effects from multiple scenes.
    Each scene consists of an image with a zoom effect and an audio file.
    """
    logger.info(f"Job {job_id}: Received create_zoom_video request")

    try:
        # Process the request
        output_file = process_create_zoom_video(data, job_id)
        logger.info(
            f"Job {job_id}: Zoom video creation completed successfully"
        )

        # Upload the final video to cloud storage
        cloud_url = upload_file(output_file)
        logger.info(
            f"Job {job_id}: Zoom video uploaded to cloud storage: {cloud_url}"
        )

        return cloud_url, "/v1/video/create_zoom_video", 200

    except Exception as e:
        logger.error(
            f"Job {job_id}: Error during zoom video creation process - {str(e)}"
        )
        return str(e), "/v1/video/create_zoom_video", 500 