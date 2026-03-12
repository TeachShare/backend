from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .teachers import Teacher, UserAuth