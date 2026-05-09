import eventlet
eventlet.monkey_patch()

import os
from dotenv import load_dotenv
load_dotenv()
from datetime import timedelta
from flask import Flask
from controller.v1 import v1_bp
from extensions import jwt, oauth
from models import db
from flask_cors import CORS
from flask_migrate import Migrate
from flask_mailman import Mail
from flask_socketio import SocketIO, emit, join_room
from services.message_service import MessageService

app = Flask(__name__)

# CONFIGS
IS_PRODUCTION = os.getenv("FLASK_ENV") == "production"
CORS_ORIGIN = os.getenv("CORS_ORIGIN", "http://localhost:3000")

app.config['GOOGLE_CLIENT_ID'] = os.getenv("GOOGLE_CLIENT_ID")
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv("GOOGLE_CLIENT_SECRET")
app.secret_key = os.getenv("APP_SECRET_KEY", "dev-mode-fallback-only")

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("GOOGLE_EMAIL")
app.config['MAIL_PASSWORD'] = os.getenv("GOOGLE_EMAIL_PASSWORD") 

app.config['MAIL_DEFAULT_SENDER'] = os.getenv("GOOGLE_EMAIL")

db_url = os.getenv("DATABASE_URL")
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=24)
app.config["JWT_ACCESS_COOKIE_NAME"] = "access_token_cookie"

# PRODUCTION COOKIE SETTINGS
app.config["JWT_COOKIE_SECURE"] = IS_PRODUCTION
app.config["JWT_COOKIE_SAMESITE"] = "None" if IS_PRODUCTION else "Lax"
app.config["JWT_COOKIE_CSRF_PROTECT"] = True
app.config["JWT_ACCESS_CSRF_HEADER_NAME"] = "X-CSRF-TOKEN"

# INIT EXTENSIONS
db.init_app(app)
jwt.init_app(app)
oauth.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)
socketio = SocketIO(app, cors_allowed_origins=CORS_ORIGIN, async_mode='eventlet')

# REGISTER GOOGLE
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# CORS
CORS(app, supports_credentials=True, origins=[CORS_ORIGIN])

# SOCKET IO HANDLERS
@socketio.on('join')
def on_join(data):
    teacher_id = data.get('teacher_id')
    if teacher_id:
        room = f"user_{teacher_id}"
        join_room(room)

@socketio.on('send_message')
def handle_send_message(data):
    sender_id = data.get('sender_id')
    receiver_id = data.get('receiver_id')
    content = data.get('content')
    file_url = data.get('file_url')
    file_name = data.get('file_name')
    file_type = data.get('file_type')

    if all([sender_id, receiver_id]) and (content or file_url):
        saved_msg = MessageService.save_message(
            sender_id, 
            receiver_id, 
            content or "", 
            file_url=file_url,
            file_name=file_name,
            file_type=file_type
        )
        room = f"user_{receiver_id}"
        emit('new_message', saved_msg, room=room)
        emit('message_sent', saved_msg)

# ROUTES
app.register_blueprint(v1_bp, url_prefix="/api/v1")

if __name__ == '__main__':
    socketio.run(app, debug=True)
