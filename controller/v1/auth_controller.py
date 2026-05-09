import os
from urllib.parse import quote
from flask import Blueprint, request, jsonify, make_response, current_app, url_for, redirect
from flask_jwt_extended import set_access_cookies, unset_jwt_cookies, jwt_required, get_jwt_identity, create_access_token
from services.auth_service import AuthService
from models import Teacher
from extensions import oauth

auth_bp = Blueprint('auth', __name__)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
REDIRECT_URI = f'{os.getenv("BACKEND_URL", "http://localhost:5000")}/api/v1/auth/callback/google'
@auth_bp.route('/register', methods=['POST'])
def register():
    
    data = request.get_json()

    result = AuthService.register_new_account(data)

    if result.get("success"):
        res = make_response(jsonify(result), 201)

        token = create_access_token(identity=str(result["id"]))
        set_access_cookies(res, token)

        if result.get("verification_token"):
            res.set_cookie('verif_token', result["verification_token"], path='/')
            res.set_cookie('is_verified', 'false', path='/')
            res.set_cookie('teacher_id', str(result["id"]), path='/')
        
        return res
    else:
        return jsonify(result), 400

@auth_bp.route('/verification-info/<string:token>', methods=['GET'])
@jwt_required(optional=True)
def get_verification_info(token):
    info = AuthService.get_verification_info(token)
    if not info:
        return jsonify({"error": "Invalid or expired session"}), 404
    
    return jsonify({"success": True, "data": info}), 200
    

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    result, token = AuthService.login(data)

    if not token:
        return jsonify(result), 401
        
    res = make_response(jsonify(result), 200) # Added 200 explicitly
    set_access_cookies(res, token)

    teacher_id = result.get('user', {}).get('id')
    
    res.set_cookie('is_verified', str(result['is_verified']).lower(), path='/')
    res.set_cookie('teacher_id', str(teacher_id), path='/')

    if not result['is_verified'] and result.get('verification_token'):
        res.set_cookie('verif_token', result['verification_token'], path='/')

    return res

@auth_bp.route('/logout', methods=['POST'])
def logout():
    result = AuthService.logout()

    res = make_response(jsonify(result))

    unset_jwt_cookies(res)
    
    # Explicitly clear manual cookies
    res.set_cookie('is_verified', '', expires=0, path='/')
    res.set_cookie('teacher_id', '', expires=0, path='/')
    res.set_cookie('verif_token', '', expires=0, path='/')

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
        "username": teacher.username,
        "first_name": teacher.first_name,
        "last_name": teacher.last_name,
        "email": teacher.email,
        "profile": teacher.profile_image_url,
        "role": teacher.role,
        "institution": teacher.institution,
        "bio": teacher.bio,
        "is_verified": teacher.is_verified,
        "is_admin": teacher.is_admin
    }

    return jsonify(response_data), 200


@auth_bp.route('/login/google')
def google_login():
    # Force the exact redirect URI
    return oauth.google.authorize_redirect(REDIRECT_URI)

@auth_bp.route('/callback/google')
def google_callback():
    # Authlib automatically retrieves the state and redirect_uri from the session
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')

    result, jwt_token = AuthService.login_or_register_google(user_info)

    if not jwt_token:
        # Redirect back to login with error message
        error_msg = result.get('message', 'Authentication failed')
        return redirect(f"{FRONTEND_URL}/auth?error={error_msg}")

    res = redirect(f"{FRONTEND_URL}/dashboard")
    set_access_cookies(res, jwt_token)

    res.set_cookie('is_verified', 'true', path='/', samesite='Lax')

    return res

@auth_bp.route('/verify', methods=['POST'])
def verify_code():
    data = request.get_json()
    user_input = data.get('code')
    teacher_id = data.get('teacher_id')
    token = data.get('token')

    if not user_input or (not teacher_id and not token):
        return jsonify({"error": "Missing code or session identifier"}), 400
    
    result = AuthService.verification_code(teacher_id, user_input, token=token)

    if "error" in result:
        return jsonify({"error": result["error"]}), result["status"]
    
    res = make_response(jsonify({"message": result["message"]}), 200)
    
    res.set_cookie('is_verified', 'true', path='/', samesite='Lax')

    return res


@auth_bp.route('/resend-code', methods=['POST'])
def resend_code():
    data = request.get_json()
    teacher_id = data.get('teacher_id')

    if not teacher_id:
        return jsonify({"success": False, "message": "ID is required"}), 400

    result, status_code = AuthService.resend_code(teacher_id)

    res = make_response(jsonify(result), status_code)

    if result.get("success") and result.get("verification_token"):
        res.set_cookie('verif_token', result["verification_token"], path='/')

    return res

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    teacher_id = get_jwt_identity()
    data = request.get_json()

    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({"success": False, "message": "Both current and new passwords are required."}), 400

    result = AuthService.change_password(teacher_id, current_password, new_password)

    if result.get("success"):
        return jsonify(result), 200
    else:
        return jsonify(result), 400