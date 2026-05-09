from models import Teacher, UserAuth, db
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from flask_jwt_extended import create_access_token
from datetime import datetime, timezone
from supabase_config import supabase

class AuthService:
    @staticmethod
    def register_new_account(data):
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if not all([first_name, last_name, username, email, password]):
            return {"success": False, "message": "Missing required fields."}
        
        if Teacher.query.filter_by(email=email).first():
            return {"success": False, "message": "This email is already in use!"}
        
        if Teacher.query.filter_by(username=username).first():
            return {"success": False, "message": "This username is already taken!"}
        try:
            # 1. Trigger Supabase Auth Sign Up (This sends the email to anyone!)
            if supabase:
                try:
                    # Use dictionary for parameters as required by this SDK version
                    sb_response = supabase.auth.sign_up({
                        "email": email,
                        "password": password,
                        "options": {
                            "data": {
                                "first_name": first_name,
                                "username": username
                            }
                        }
                    })
                    print(f"DEBUG: Supabase Sign Up successful for {email}")
                except Exception as sb_err:
                    print(f"SUPABASE SIGNUP ERROR: {sb_err}")
            else:
                print("DEBUG: Supabase client is NOT initialized. Check your environment variables.")
            
            # 2. Save to local Teacher table for app logic
            default_avatar = f"https://api.dicebear.com/7.x/avataaars/svg?seed={username}"
            
            new_teacher = Teacher(
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                profile_image_url=default_avatar
            )
            db.session.add(new_teacher)
            db.session.flush()

            new_auth = UserAuth(
                teacher_id=new_teacher.teacher_id,
                hashed_password=generate_password_hash(password)
            )
            db.session.add(new_auth)
            db.session.commit()

            return {
                "success": True, 
                "message": "Registration complete! Please check your email for the verification code.",
                "id": new_teacher.teacher_id,
                "username": new_teacher.username,
                "verification_token": "supabase_managed", # UI fallback
                "is_verified": False 
            }
        
        except Exception as e:
            db.session.rollback()
            print(f"DEBUG REGISTER ERROR: {e}")
            return {"success": False, "message": f"An error occured: {str(e)}"}
        

    @staticmethod
    def get_verification_info(token):
        # Since we are using Supabase, we don't use database tokens.
        # The frontend calls this to get the user's email to show on the verify page.
        from flask_jwt_extended import get_jwt_identity
        
        try:
            teacher_id = get_jwt_identity()
            if not teacher_id:
                return None
            
            teacher = Teacher.query.get(teacher_id)
            if not teacher:
                return None
                
            return {
                "id": teacher.teacher_id,
                "email": teacher.email,
                "is_verified": teacher.is_verified
            }
        except:
            return None

    @staticmethod
    def login(data):
        email = data.get('email')
        password = data.get('password')

        found_teacher = Teacher.query.filter_by(email=email).first()
        if not found_teacher:
            return {"success": False, "message": "Email not found!"}
        
        if found_teacher.auth:
            if found_teacher.auth.auth_provider != 'local':
                 return {"success": False, "message": f"This account uses {found_teacher.auth.auth_provider.capitalize()} Login."}, None

            if check_password_hash(found_teacher.auth.hashed_password, password):
                # Check verification status with Supabase if not already verified locally
                if not found_teacher.is_verified and supabase:
                    try:
                        # Attempt to sign in to Supabase to check status
                        sb_auth = supabase.auth.sign_in_with_password({
                            "email": email, 
                            "password": password
                        })
                        if sb_auth.user.email_confirmed_at:
                            found_teacher.is_verified = True
                            db.session.commit()
                    except:
                        pass # User might not be confirmed in SB yet

                access_token = create_access_token(identity=str(found_teacher.teacher_id))

                return {
                    "success": True,
                    "message": f"Welcome , {found_teacher.first_name}!",
                    "user": {
                        "id": found_teacher.teacher_id,
                        "username": found_teacher.username,
                        "is_admin": found_teacher.is_admin
                    },
                    "is_verified": found_teacher.is_verified,
                    "is_suspended": found_teacher.is_suspended,
                    "verification_token": "supabase_managed" if not found_teacher.is_verified else None
                }, access_token
        
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
                    # Generate a basic username from email or name
                    base_username = email.split('@')[0].replace('.', '_').lower()
                    username = base_username
                    counter = 1
                    while Teacher.query.filter_by(username=username).first():
                        username = f"{base_username}{counter}"
                        counter += 1

                    # Default to Dicebear if Google doesn't provide a picture
                    profile_pic = user_info.get('picture') or f"https://api.dicebear.com/7.x/avataaars/svg?seed={username}"

                    found_teacher = Teacher(
                        first_name = user_info.get('given_name', 'New'),
                        last_name = user_info.get('family_name', 'User'),
                        username = username,
                        email = email,
                        profile_image_url=profile_pic,
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
                # User exists but didn't use Google before
                auth_record = found_teacher.auth
                if auth_record and auth_record.auth_provider == 'local':
                    return {"success": False, "message": "This email is registered with a password. Please log in normally."}, None
                
                auth_record.google_id = google_id
                auth_record.auth_provider = 'google'

                db.session.commit()
        
        if not found_teacher:
            return {"success": False, "message": "User not found"}, None

        access_token = create_access_token(identity=str(found_teacher.teacher_id))

        payload = {
            "success": True,
            "message": f"Welcome back, {found_teacher.first_name}",
            "user": {
                "id": found_teacher.teacher_id,
                "username": found_teacher.username,
                "is_admin": found_teacher.is_admin
            },
            "is_verified": found_teacher.is_verified,
            "is_suspended": found_teacher.is_suspended
        }


        return payload, access_token

    @staticmethod
    def verification_code(teacher_id, user_input_code, token=None):
        teacher = Teacher.query.get(teacher_id)
        if not teacher:
            return {"error": "Teacher not found", "status": 404}

        if not supabase:
            return {"error": "Auth service unavailable", "status": 500}

        try:
            # Verify OTP via Supabase using dictionary for params
            print(f"DEBUG VERIFY: Attempting OTP verify for {teacher.email} with code {user_input_code}")
            verify = supabase.auth.verify_otp({
                "email": teacher.email,
                "token": user_input_code,
                "type": "signup"
            })
            
            if verify.user:
                print(f"DEBUG VERIFY: Success for {teacher.email}")
                teacher.is_verified = True
                db.session.commit()
                return {"message": "Verified successfully", "status": 200}
        except Exception as e:
            print(f"DEBUG VERIFY ERROR: {e}")
            return {"error": str(e), "status": 400}
        
        return {"error": "Invalid code", "status": 400}
    
    @staticmethod
    def resend_code(teacher_id):
        teacher = Teacher.query.get(teacher_id)
        if not teacher:
            print(f"DEBUG RESEND: Teacher {teacher_id} not found")
            return {"success": False, "message": "Teacher not found."}, 404
        
        if not supabase:
            print("DEBUG RESEND: Supabase not initialized")
            return {"success": False, "message": "Auth service unavailable."}, 500

        try:
            # Resend OTP via Supabase using dictionary for params
            print(f"DEBUG RESEND: Requesting new code for {teacher.email}")
            supabase.auth.resend({
                "type": "signup",
                "email": teacher.email
            })
            return {"success": True, "message": "A new code has been sent!"}, 200
        except Exception as e:
            print(f"DEBUG RESEND ERROR: {e}")
            return {"success": False, "message": str(e)}, 500

    @staticmethod
    def change_password(teacher_id, current_password, new_password):
        teacher = Teacher.query.get(teacher_id)
        if not teacher or not teacher.auth:
            return {"success": False, "message": "User authentication record not found."}
            
        if teacher.auth.auth_provider != 'local':
            return {"success": False, "message": f"Password cannot be changed for {teacher.auth.auth_provider} accounts."}
            
        if not check_password_hash(teacher.auth.hashed_password, current_password):
            return {"success": False, "message": "Incorrect current password."}
            
        try:
            teacher.auth.hashed_password = generate_password_hash(new_password)
            db.session.commit()
            return {"success": True, "message": "Password changed successfully!"}
        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": f"Failed to change password: {str(e)}"}
