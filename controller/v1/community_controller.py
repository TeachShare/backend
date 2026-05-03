from flask import Blueprint, request, jsonify
from services.community_service import CommunityService
# Replace this with the actual import path for your custom decorator
from lib.guards import verification_required 

community_bp = Blueprint('community_controller', __name__)

@community_bp.route('/', methods=['POST'])
@verification_required
def create_post(teacher):
    data = request.get_json()
    response_data, status_code = CommunityService.create_post(teacher.teacher_id, data)
    return jsonify(response_data), status_code

@community_bp.route('/', methods=['GET'])
@verification_required
def get_feed(teacher):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    response_data, status_code = CommunityService.get_feed(teacher.teacher_id, page, per_page)
    return jsonify(response_data), status_code

@community_bp.route('/<int:post_id>/like', methods=['POST'])
@verification_required
def toggle_like(teacher, post_id):
    response_data, status_code = CommunityService.toggle_like(teacher.teacher_id, post_id)
    return jsonify(response_data), status_code

@community_bp.route('/<int:post_id>/comments', methods=['POST'])
@verification_required
def add_comment(teacher, post_id):
    data = request.get_json()
    response_data, status_code = CommunityService.add_comment(teacher.teacher_id, post_id, data)
    return jsonify(response_data), status_code

@community_bp.route('/<int:post_id>/comments', methods=['GET'])
@verification_required
def get_comments(teacher, post_id):
    response_data, status_code = CommunityService.get_post_comments(post_id)
    return jsonify(response_data), status_code