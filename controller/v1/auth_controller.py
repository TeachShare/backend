from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import set_access_cookies, unset_jwt_cookies
from services.auth_service import AuthService

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