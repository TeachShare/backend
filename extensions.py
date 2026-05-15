from authlib.integrations.flask_client import OAuth
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_socketio import SocketIO


jwt = JWTManager()
oauth = OAuth()
mail = Mail()
socketio = SocketIO()
