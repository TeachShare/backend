from flask import Blueprint
from .auth_controller import auth_bp
from .resource_collection_controller import resource_collection_bp
from .metadata_controller import metadata_bp

v1_bp = Blueprint('v1', __name__)

v1_bp.register_blueprint(auth_bp, url_prefix='/auth')
v1_bp.register_blueprint(resource_collection_bp, url_prefix='/resource_collection')
v1_bp.register_blueprint(metadata_bp, url_prefix='/data')