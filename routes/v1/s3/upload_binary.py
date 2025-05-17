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

from flask import Blueprint, request
from services.authentication import authenticate
from app_utils import queue_task_wrapper
from services.v1.s3.upload import upload_fileobj_to_s3
import logging
import mimetypes
import uuid

logger = logging.getLogger(__name__)
v1_s3_upload_binary_bp = Blueprint('v1_s3_upload_binary', __name__)


@v1_s3_upload_binary_bp.route('/v1/s3/upload-binary', methods=['POST'])
@authenticate
@queue_task_wrapper(bypass_queue=False)
def s3_upload_binary_endpoint(job_id, data=None):
    try:
        if 'file' not in request.files:
            return {'error': 'No file part in the request'}, "/v1/s3/upload-binary", 400
        file = request.files['file']
        # 1. Nome original do arquivo
        original_filename = file.filename or ''
        # 2. Nome customizado do formulário
        custom_filename = request.form.get('filename') or request.form.get('name')
        # 3. Tenta usar o nome customizado, senão o original, senão gera um nome
        filename = custom_filename or original_filename
        # 4. Se não tem nome, gera um nome único
        if not filename or filename.strip() == '':
            filename = str(uuid.uuid4())
        # 5. Garante extensão: se não tem, tenta inferir pelo mimetype
        if '.' not in filename:
            guessed_ext = None
            if file.mimetype:
                guessed_ext = mimetypes.guess_extension(file.mimetype)
            if not guessed_ext:
                guessed_ext = ''
            filename = filename + guessed_ext
        # 6. Torna o nome seguro (remove barras, etc)
        filename = filename.replace('/', '_').replace('\\', '_')
        make_public = request.form.get('public', 'false').lower() == 'true'

        logger.info(
            f"Job {job_id}: Starting S3 binary upload for {filename}"
        )
        result = upload_fileobj_to_s3(file, filename, make_public)
        logger.info(
            f"Job {job_id}: Successfully uploaded binary to S3"
        )
        return result, "/v1/s3/upload-binary", 200
    except Exception as e:
        logger.error(f"Job {job_id}: Error uploading binary to S3 - {str(e)}")
        return {'error': str(e)}, "/v1/s3/upload-binary", 500 