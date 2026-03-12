from flask import Flask
from controller.v1 import v1_bp
from dotenv import load_dotenv
from models import db
import os
from flask_cors import CORS
from flask_jwt_extended import JWTManager

load_dotenv()

app = Flask(__name__)

CORS(app, supports_credentials=True, origins=["http://localhost:3000"])

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_ACCESS_COOKIE_NAME"] = "access_token_cookie"
app.config["JWT_COOKIE_SECURE"] = False  # Set to True in production (HTTPS)
app.config["JWT_COOKIE_CSRF_PROTECT"] = True  # Modern security requirement
app.config["JWT_ACCESS_CSRF_HEADER_NAME"] = "X-CSRF-TOKEN"

db.init_app(app)

jwt = JWTManager(app)

app.register_blueprint(v1_bp, url_prefix="/api/v1")

if __name__ == '__main__':
    app.run(debug=True)