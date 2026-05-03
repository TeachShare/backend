from flask import Blueprint
from .auth_controller import auth_bp
from .resource_collection_controller import resource_collection_bp
from .metadata_controller import metadata_bp
from .teacher_controller import teacher_bp
from .community_controller import community_bp
from .message_controller import message_bp

v1_bp = Blueprint('v1', __name__)

v1_bp.register_blueprint(auth_bp, url_prefix='/auth')
v1_bp.register_blueprint(resource_collection_bp, url_prefix='/resource_collection')
v1_bp.register_blueprint(metadata_bp, url_prefix='/data')

v1_bp.register_blueprint(teacher_bp, url_prefix='/teachers')

v1_bp.register_blueprint(community_bp, url_prefix='/community')
v1_bp.register_blueprint(message_bp, url_prefix='/messages')