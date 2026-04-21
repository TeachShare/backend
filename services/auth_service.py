from models import Teacher, UserAuth, db, VerificationCodes
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from flask_jwt_extended import create_access_token, set_access_cookies
from datetime import datetime
from lib import send_verification_code

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

            send_verification_code(new_teacher)

            verif_entry = VerificationCodes.query.filter_by(user_id=new_teacher.teacher_id).order_by(VerificationCodes.created_at.desc()).first()

            
            return {
                "success": True, 
                "message": "Registration complete! Please verify your email.",
                "id": new_teacher.teacher_id,
                "verification_hash": verif_entry.code_hash if verif_entry else None,
                "is_verified": False 
            }
        
        except IntegrityError as e:
            db.session.rollback()
            # This prints the REAL error (like "joined_date cannot be null") to your console
            print(f"DATABASE ERROR: {e.orig}") 
            return {"success": False, "message": "A database integrity error occurred."}
        except Exception as e:
            print(f"DEBUG REGISTER ERROR: {e}")
            return {"success": False, "message": f"An unexpected error occured: {e}"}
        

    @staticmethod
    def login(data):
        email = data.get('email')
        password = data.get('password')

        found_teacher = Teacher.query.filter_by(email=email).first()
        if not found_teacher:
            return {"success": False, "message": "Email not found!"}
        

        if found_teacher.auth and found_teacher.auth.hashed_password:
            if check_password_hash(found_teacher.auth.hashed_password, password):
                access_token = create_access_token(identity=str(found_teacher.teacher_id))

                verif_entry = VerificationCodes.query.filter_by(user_id=found_teacher.teacher_id).order_by(VerificationCodes.created_at.desc()).first()

                payload= {
                    "success": True,
                    "message": f"Welcome , {found_teacher.first_name}!",
                    "user": {"id": found_teacher.teacher_id},
                    "is_verified": found_teacher.is_verified,
                    "verification_hash": verif_entry.code_hash if verif_entry else None
                }

                return payload, access_token
        else:
            return {"success": False, "message": "This account uses Google Login."}, None
        
        return {"success": False, "message": "Invalid email or password"}, None
    
    @staticmethod
    def logout():
        return {"success": True, "message": "Successfully logged out!"}, None
    
    @staticmethod
    def login_or_register_google(user_info):
        google_id = user_info.get('sub')
        email = user_info.get('email')

        auth_record = UserAuth.query.filter_by(google_id=google_id).first()
        found_teacher = None

        if auth_record:
            found_teacher = auth_record.teacher
        else:
            found_teacher = Teacher.query.filter_by(email=email).first()

            if not found_teacher:

                try:
                    found_teacher = Teacher(
                        first_name = user_info.get('given_name', 'New'),
                        last_name = user_info.get('family_name', 'User'),
                        email = email,
                        profile_image_url=user_info.get('picture'),
                        is_verified = True
                    )
                    
                    db.session.add(found_teacher)
                    db.session.flush()
                    
                    auth_record = UserAuth(
                        teacher_id = found_teacher.teacher_id,
                        google_id = google_id,
                        auth_provider = 'google',
                        hashed_password = None
                    )
                    
                    db.session.add(auth_record)
                    db.session.commit()
                
                except Exception as e:
                    db.session.rollback()
                    return { "success": False, "message": "Failed to create Google Account."}, None
                
            else:
                auth_record = found_teacher.auth
                auth_record.google_id = google_id
                auth_record.auth_provider = 'google'

                db.session.commit()
        
        if not found_teacher:
            return {"success": False, "message": "User not found"}, None

        access_token = create_access_token(identity=str(found_teacher.teacher_id))

        payload = {
            "success": True,
            "message": f"Welcome back, {found_teacher.first_name}",
            "user": {"id": found_teacher.teacher_id}
        }


        return payload, access_token
    

    @staticmethod
    def verification_code(teacher_id, user_input_code):

        t_id = int(teacher_id)
        record = VerificationCodes.query.filter_by(user_id=t_id).order_by(VerificationCodes.created_at.desc()).first()

        if not record:
            return { "error": "No code found", "status": 404 }
        
        if datetime.utcnow() > record.expires_at:
            db.session.delete(record)
            db.session.commit()
            return {"error": "Code expired", "status": 404 }
        
        if not check_password_hash(record.code_hash, user_input_code):
            return {"error": "Invalid code", "status": 400}
        
        teacher = Teacher.query.get(teacher_id)
        if teacher:
            teacher.is_verified = True
            db.session.delete(record)
            db.session.commit()
            return {"message": "Verified successfully", "status": 200}
        
        return {"error": "Teacher not found", "status": 404}
    
    @staticmethod
    def resend_code(teacher_id):
        teacher = Teacher.query.get(teacher_id)
        if not teacher:
            return {"success": False, "message": "Teacher not found."}, 404
        
        if teacher.is_verified:
            return {"success": False, "message": "Account already verified"}, 400
        
        try:
            VerificationCodes.query.filter_by(user_id=teacher.teacher_id).delete()

            send_verification_code(teacher)

            verif_entry = VerificationCodes.query.filter_by(user_id=teacher.teacher_id)\
                          .order_by(VerificationCodes.created_at.desc()).first()
            
            return {
                "success": True, 
                "message": "A new code has been sent!",
                "verification_hash": verif_entry.code_hash if verif_entry else None
            }, 200

        except Exception as e:
            db.session.rollback()
            print(f"RESEND ERROR: {e}")
            return {"success": False, "message": "Failed to resend code."}, 500
