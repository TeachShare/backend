from authlib.integrations.flask_client import OAuth
from flask_jwt_extended import JWTManager


jwt = JWTManager()
oauth = OAuth()
