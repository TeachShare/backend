import sys
import os

# Add the current directory to path so models and app can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Teacher, UserAuth
from werkzeug.security import generate_password_hash

def create_admin():
    with app.app_context():
        email = "admin@teachshare.com"
        username = "admin"
        password = "AdminPassword123!"

        # Check if admin already exists
        admin_teacher = Teacher.query.filter_by(email=email).first()
        if admin_teacher:
            print("Admin account already exists.")
            if not admin_teacher.is_admin:
                admin_teacher.is_admin = True
                db.session.commit()
                print("Existing account elevated to admin.")
            return

        print("Creating admin account...")
        new_teacher = Teacher(
            username=username,
            first_name="System",
            last_name="Admin",
            email=email,
            is_verified=True,
            is_admin=True,
            role="Administrator",
            is_archived=False
        )
        db.session.add(new_teacher)
        db.session.flush()

        hashed_pwd = generate_password_hash(password)
        new_auth = UserAuth(
            teacher_id=new_teacher.teacher_id,
            hashed_password=hashed_pwd,
            auth_provider="local",
            is_active=True
        )
        db.session.add(new_auth)
        db.session.commit()

        print(f"Admin account created successfully!")
        print(f"Email: {email}")
        print(f"Password: {password}")

if __name__ == "__main__":
    create_admin()
