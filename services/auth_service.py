from models import Teacher, UserAuth, db
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from flask_jwt_extended import create_access_token, set_access_cookies

class AuthService:
    @staticmethod
    def register_new_account(data):
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        email = data.get('email')
        password = data.get('password')

        if not all([first_name, last_name, email, password]):
            return {"success": False, "message": "Missing required fields."}
        
        if Teacher.query.filter_by(email=email).first():
            return {"success": False, "message": "This email is already in use!"}
        
        try:
            new_teacher = Teacher(
                first_name=first_name,
                last_name=last_name,
                email=email
            )
            db.session.add(new_teacher)

            db.session.flush()

            new_auth = UserAuth(
                teacher_id=new_teacher.teacher_id,
                hashed_password=generate_password_hash(password)
            )
            db.session.add(new_auth)

            db.session.commit()
            return {"success": True, "message": "Registration complete!"}
        
        except IntegrityError as e:
            db.session.rollback()
            # This prints the REAL error (like "joined_date cannot be null") to your console
            print(f"DATABASE ERROR: {e.orig}") 
            return {"success": False, "message": "A database integrity error occurred."}
        except Exception as e:
            return {"success": False, "message": "An unexpected error occured."}
        

    @staticmethod
    def login(data):
        email = data.get('email')
        password = data.get('password')

        found_teacher = Teacher.query.filter_by(email=email).first()
        if not found_teacher:
            return {"success": False, "message": "Email not found!"}
        
      
        if found_teacher.auth and check_password_hash(found_teacher.auth.hashed_password, password):
            access_token = create_access_token(identity=str(found_teacher.teacher_id))

            payload= {
                "success": True,
                "message": f"Welcome , {found_teacher.first_name}!",
                "user": {"id": found_teacher.teacher_id}
            }

            return payload, access_token
        
        return {"success": False, "message": "Invalid email or password"}, None
    
    @staticmethod
    def logout():
        return {"success": True, "message": "Successfully logged out!"}, None
    


        
