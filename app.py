from gevent import monkey
monkey.patch_all()

import os
from dotenv import load_dotenv
load_dotenv()
from datetime import timedelta
from flask import Flask
from controller.v1 import v1_bp
from extensions import jwt, oauth, mail, socketio
from models import db
from flask_cors import CORS
from flask_migrate import Migrate
from flask_socketio import emit, join_room
from services.message_service import MessageService
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
# Apply ProxyFix middleware to handle headers from reverse proxies (mandatory for Render/Vercel connectivity)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# CONFIGS
IS_PRODUCTION = os.getenv("FLASK_ENV") == "production"
CORS_ORIGIN = os.getenv("CORS_ORIGIN", "http://localhost:3000")

# Use 'SECRET_KEY' in app.config for consistent session encryption
app.config['SECRET_KEY'] = os.getenv("APP_SECRET_KEY", "dev-mode-fallback-only")
app.config['GOOGLE_CLIENT_ID'] = os.getenv("GOOGLE_CLIENT_ID")
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv("GOOGLE_CLIENT_SECRET")
# app.secret_key is also set by config['SECRET_KEY'] automatically

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

# MAIL CONFIGURATION
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT", 587))
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS", "True") == "True"
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER", "noreply@teachshare.com")

# SESSION COOKIE SETTINGS (Used by Authlib for OAuth State)
app.config["SESSION_COOKIE_NAME"] = "teachshare_session"
app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION
app.config["SESSION_COOKIE_SAMESITE"] = "None" if IS_PRODUCTION else "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_DOMAIN"] = None  # Prevents domain-locking issues on localhost/subdomains

# INIT EXTENSIONS
db.init_app(app)

# AUTO-SEED DATA (Crucial for fresh production DBs)
# In development, we only run this in the main worker process to avoid noise from the reloader
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or IS_PRODUCTION:
    with app.app_context():
        from models import Subject, GradeLevel, ContentType
        try:
            # 1. Seed Subjects
            if Subject.query.count() == 0:
                print("AUTO-SEED: Populating Subjects...")
                subjects = [
                    ("Mathematics", "General", 1), ("Science", "General", 2),
                    ("English Language Arts", "General", 3), ("Social Studies", "General", 4),
                    ("Art", "Elective", 5), ("Music", "Elective", 6),
                    ("Physical Education", "General", 7), ("Computer Science", "STEM", 8)
                ]
                for name, tier, rank in subjects:
                    db.session.add(Subject(subject_name=name, tier=tier, rank=rank))
            
            # 2. Seed Grade Levels
            if GradeLevel.query.count() == 0:
                print("AUTO-SEED: Populating Grade Levels...")
                grades = [
                    ("Preschool", "Early Childhood", 1), ("Kindergarten", "Early Childhood", 2),
                    ("Elementary", "Primary", 3), ("Secondary", "Junior High", 4),
                    ("Senior High School", "Secondary", 5), ("College / Higher Education", "Tertiary", 6)
                ]
                for name, tier, rank in grades:
                    db.session.add(GradeLevel(grade_name=name, tier=tier, rank=rank))
            
            # 3. Seed Content Types
            if ContentType.query.count() == 0:
                print("AUTO-SEED: Populating Content Types...")
                types = ["Lesson Plan", "Worksheet", "Assessment", "Activity", "Syllabus"]
                for name in types:
                    db.session.add(ContentType(type_name=name))
            
            db.session.commit()
            print("AUTO-SEED: Database tables ready.")
        except Exception as e:
            print(f"AUTO-SEED ERROR: {e}")
            db.session.rollback()

jwt.init_app(app)
mail.init_app(app)

# REGISTER OAUTH CLIENTS
oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

oauth.init_app(app)
migrate = Migrate(app, db)

# CORS configuration
CORS_ORIGINS = [CORS_ORIGIN]
if not IS_PRODUCTION:
    # Allow any local origin for development flexibility
    CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

CORS(app, supports_credentials=True, origins=CORS_ORIGINS)

# Initialize SocketIO with correct CORS settings
socketio.init_app(app, cors_allowed_origins=CORS_ORIGINS, async_mode='gevent')

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

# CHIPS (Partitioned Cookies) Fix for Cross-Domain Deployment
@app.after_request
def add_partitioned_attribute(response):
    if IS_PRODUCTION:
        for name, cookie in response.headers.getlist('Set-Cookie'):
            if 'SameSite=None' in cookie and 'Partitioned' not in cookie:
                # Add Partitioned attribute to the header
                response.headers.add('Set-Cookie', f"{cookie}; Partitioned")
                # Remove the original header (since we added a new corrected one)
                # Note: This is a bit tricky with getlist/add, so we'll use a more surgical approach
        
        # More robust way to replace the header values
        cookies = response.headers.getlist('Set-Cookie')
        response.headers.remove('Set-Cookie')
        for cookie in cookies:
            if 'SameSite=None' in cookie and 'Partitioned' not in cookie:
                response.headers.add('Set-Cookie', f"{cookie}; Partitioned")
            else:
                response.headers.add('Set-Cookie', cookie)
    return response

if __name__ == '__main__':
    socketio.run(app, debug=True)
