from flask import Flask
from controller.v1 import v1_bp
from dotenv import load_dotenv
from extensions import  jwt, oauth
from models import db
import os
from flask_cors import CORS
from flask_migrate import Migrate

load_dotenv()

app = Flask(__name__)

# CONFIGS
app.config['GOOGLE_CLIENT_ID'] = os.getenv("GOOGLE_CLIENT_ID")
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv("GOOGLE_CLIENT_SECRET")
app.secret_key = os.getenv("APP_SECRET_KEY", "dev-mode-fallback-only")

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_ACCESS_COOKIE_NAME"] = "access_token_cookie"
app.config["JWT_COOKIE_SECURE"] = False
app.config["JWT_COOKIE_SAMESITE"] = "Lax"
app.config["JWT_COOKIE_CSRF_PROTECT"] = True
app.config["JWT_ACCESS_CSRF_HEADER_NAME"] = "X-CSRF-TOKEN"

# HI :)

# INIT EXTENSIONS
db.init_app(app)
jwt.init_app(app)
oauth.init_app(app)
migrate = Migrate(app, db)

# REGISTER GOOGLE
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# CORS
CORS(app, supports_credentials=True, origins=["http://localhost:3000"])

# ROUTES
app.register_blueprint(v1_bp, url_prefix="/api/v1")

if __name__ == '__main__':
    app.run(debug=True)