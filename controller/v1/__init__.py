from flask import Blueprint
from .auth_controller import auth_bp

v1_bp = Blueprint('v1', __name__)

v1_bp.register_blueprint(auth_bp, url_prefix='/auth')