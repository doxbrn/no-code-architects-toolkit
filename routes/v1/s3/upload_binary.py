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

from flask import Blueprint, request, jsonify
from services.authentication import authenticate
from app_utils import queue_task_wrapper
from services.v1.s3.upload import upload_fileobj_to_s3
import logging

logger = logging.getLogger(__name__)
v1_s3_upload_binary_bp = Blueprint('v1_s3_upload_binary', __name__)


@v1_s3_upload_binary_bp.route('/v1/s3/upload-binary', methods=['POST'])
@authenticate
@queue_task_wrapper(bypass_queue=False)
def s3_upload_binary_endpoint(job_id, data=None):
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request'}), 400
        file = request.files['file']
        filename = request.form.get('filename', file.filename)
        make_public = request.form.get('public', 'false').lower() == 'true'

        logger.info(f"Job {job_id}: Starting S3 binary upload for {filename}")
        result = upload_fileobj_to_s3(file, filename, make_public)
        logger.info(f"Job {job_id}: Successfully uploaded binary to S3")
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Job {job_id}: Error uploading binary to S3 - {str(e)}")
        return jsonify({'error': str(e)}), 500 