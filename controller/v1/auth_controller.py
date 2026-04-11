from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import set_access_cookies, unset_jwt_cookies, jwt_required, get_jwt_identity
from services.auth_service import AuthService
from models import Teacher

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    
    data = request.get_json()

    result = AuthService.register_new_account(data)

    if result.get("success"):
        return jsonify(result), 201
    else:
        return jsonify(result), 400
    

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    result, token = AuthService.login(data)

    if not token:
        return jsonify(result), 401
        
    res = make_response(jsonify(result))

    set_access_cookies(res, token)

    return res, 200

@auth_bp.route('/logout', methods=['POST'])
def logout():
    result = AuthService.logout()

    res = make_response(jsonify(result))

    unset_jwt_cookies(res)

    return res, 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    teacher_id = get_jwt_identity()

    teacher = Teacher.query.get(teacher_id)

    if not teacher:
        return jsonify({"error": "User not found"}), 404
    
    teacher_profile = Teacher.query.filter_by(teacher_id=teacher.teacher_id).first()

    response_data = {
        "id": teacher.teacher_id,
        "first_name": teacher.first_name,
        "last_name": teacher.last_name,
        "email": teacher.email,
        "profile": teacher. profile_image_url
    }

    if teacher_profile:
        response_data["teacher_info"] = {
         "id": teacher_profile.teacher_id,
         "first_name": teacher_profile.first_name,
         "last_name": teacher_profile.last_name,
         "email": teacher_profile.email,
         "profile": teacher_profile. profile_image_url
        }   

    return jsonify(response_data), 200