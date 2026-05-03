from flask import Blueprint, request, jsonify, make_response, current_app, url_for, redirect
from flask_jwt_extended import set_access_cookies, unset_jwt_cookies, jwt_required, get_jwt_identity, create_access_token
from services.auth_service import AuthService
from models import Teacher
from extensions import oauth

auth_bp = Blueprint('auth', __name__)
REDIRECT_URI = 'http://localhost:5000/api/v1/auth/callback/google'
@auth_bp.route('/register', methods=['POST'])
def register():
    
    data = request.get_json()

    result = AuthService.register_new_account(data)

    if result.get("success"):
        res = make_response(jsonify(result), 201)

        token = create_access_token(identity=str(result["id"]))
        set_access_cookies(res, token)

        if result.get("verification_hash"):
            res.set_cookie('verif_hash', result["verification_hash"], path='/')
            res.set_cookie('is_verified', 'false', path='/')
            res.set_cookie('teacher_id', str(result["id"]), path='/')
        
        return res
    else:
        return jsonify(result), 400
    

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

    if not result['is_verified'] and result.get('verification_hash'):
        res.set_cookie('verif_hash', result['verification_hash'], path='/')

    return res

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
        "profile": teacher.profile_image_url,
        "role": teacher.role,
        "institution": teacher.institution,
        "bio": teacher.bio,
        "is_verified": teacher.is_verified
    }

    return jsonify(response_data), 200


@auth_bp.route('/login/google')
def google_login():
    # Force the exact redirect URI
    return oauth.google.authorize_redirect(REDIRECT_URI)

@auth_bp.route('/callback/google')
def google_callback():
    # Remove the redirect_uri argument here. 
    # Authlib automatically handles the request context.
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')

    result, jwt_token = AuthService.login_or_register_google(user_info)

    res = redirect("http://localhost:3000/dashboard")
    set_access_cookies(res, jwt_token)

    res.set_cookie('is_verified', 'true', path='/', samesite='Lax')

    return res

@auth_bp.route('/verify', methods=['POST'])
def verify_code():
    data = request.get_json()
    user_input = data.get('code')
    teacher_id = data.get('teacher_id')

    if not user_input or not teacher_id:
        return jsonify({"error": "Missing code or teacher id"}), 400
    
    result = AuthService.verification_code(teacher_id, user_input)

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

    if result.get("success") and result.get("verification_hash"):
        res.set_cookie('verif_hash', result["verification_hash"], path='/')

    return res