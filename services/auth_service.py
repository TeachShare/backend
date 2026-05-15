from models import Teacher, UserAuth, db, VerificationCodes
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from flask_jwt_extended import create_access_token
from datetime import datetime, timezone, timedelta
from supabase_config import supabase
from services.email_service import EmailService
import random
import string
import re

class AuthService:
    @staticmethod
    def validate_password_strength(password):
        """Enforces strong password: 8+ chars, upper, lower, digit, special."""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long."
        if not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter."
        if not re.search(r"[a-z]", password):
            return False, "Password must contain at least one lowercase letter."
        if not re.search(r"\d", password):
            return False, "Password must contain at least one digit."
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return False, "Password must contain at least one special character."
        return True, ""

    @staticmethod
    def generate_otp(length=6):
        return ''.join(random.choices(string.digits, k=length))

    @staticmethod
    def register_new_account(data):
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        institution = data.get('institution')

        if not all([first_name, last_name, username, email, password]):
            return {"success": False, "message": "Missing required fields."}
        
        # Enforce strong password
        is_strong, msg = AuthService.validate_password_strength(password)
        if not is_strong:
            return {"success": False, "message": msg}

        if Teacher.query.filter_by(email=email).first():
            return {"success": False, "message": "This email is already in use!"}
        
        if Teacher.query.filter_by(username=username).first():
            return {"success": False, "message": "This username is already taken!"}
        
        try:
            # 1. Save to local Teacher table
            new_teacher = Teacher(
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                institution=institution,
                profile_image_url=None,
                is_verified=False
            )
            db.session.add(new_teacher)
            db.session.flush()

            new_auth = UserAuth(
                teacher_id=new_teacher.teacher_id,
                hashed_password=generate_password_hash(password)
            )
            db.session.add(new_auth)
            
            # 2. Generate and Store Local OTP
            otp_code = AuthService.generate_otp()
            # Generate a random token for the URL
            verif_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            
            new_code = VerificationCodes(
                user_id=new_teacher.teacher_id,
                code_hash=otp_code,  # The model calls it code_hash, but currently it's stored plain in the code below. 
                token=verif_token,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)
            )
            db.session.add(new_code)
            
            # 3. Send Email via EmailService
            email_sent = EmailService.send_verification_email(
                recipient_email=email,
                recipient_name=f"{first_name} {last_name}",
                code=otp_code
            )
            
            if not email_sent:
                # We still commit but warn the user. They can try "Resend" later.
                db.session.commit()
                return {
                    "success": True, 
                    "message": "Account created, but we couldn't send the email. Please try 'Resend Code' on the verification page.",
                    "id": new_teacher.teacher_id,
                    "username": new_teacher.username,
                    "verification_token": verif_token,
                    "is_verified": False 
                }

            db.session.commit()
            return {
                "success": True, 
                "message": "Registration complete! Please check your email for the verification code.",
                "id": new_teacher.teacher_id,
                "username": new_teacher.username,
                "verification_token": verif_token,
                "is_verified": False 
            }
        
        except Exception as e:
            db.session.rollback()
            print(f"DEBUG REGISTER ERROR: {e}")
            return {"success": False, "message": f"An error occured during account creation: {str(e)}"}

    @staticmethod
    def get_verification_info(token):
        # The frontend calls this to get the user's email to show on the verify page.
        # We look up the email via the verification token in our database.
        try:
            verif_record = VerificationCodes.query.filter_by(token=token).first()
            if not verif_record:
                return None
            
            teacher = verif_record.teacher
            if not teacher:
                return None
                
            return {
                "id": teacher.teacher_id,
                "email": teacher.email,
                "is_verified": teacher.is_verified
            }
        except Exception as e:
            print(f"DEBUG VERIF INFO ERROR: {e}")
            return None

    @staticmethod
    def login(data):
        email = data.get('email')
        password = data.get('password')

        found_teacher = Teacher.query.filter_by(email=email).first()
        if not found_teacher:
            return {"success": False, "message": "Email not found!"}, None
        
        if found_teacher.auth:
            if found_teacher.auth.auth_provider != 'local' or not found_teacher.auth.hashed_password:
                 return {"success": False, "message": f"This account uses {found_teacher.auth.auth_provider.capitalize()} Login."}, None

            if check_password_hash(found_teacher.auth.hashed_password, password):
                access_token = create_access_token(identity=str(found_teacher.teacher_id))
                
                # Get the latest verification token if unverified
                verif_token = None
                if not found_teacher.is_verified:
                    latest_code = VerificationCodes.query.filter_by(teacher_id=found_teacher.teacher_id).order_by(VerificationCodes.created_at.desc()).first()
                    verif_token = latest_code.token if latest_code else "pending"

                return {
                    "success": True,
                    "message": f"Welcome back!",
                    "user": {
                        "id": found_teacher.teacher_id,
                        "username": found_teacher.username,
                        "first_name": found_teacher.first_name,
                        "last_name": found_teacher.last_name,
                        "email": found_teacher.email,
                        "profile_image_url": found_teacher.profile_image_url,
                        "is_admin": found_teacher.is_admin
                    },
                    "is_verified": found_teacher.is_verified,
                    "is_suspended": found_teacher.is_suspended,
                    "verification_token": verif_token
                }, access_token
            else:
                return {"success": False, "message": "Invalid password"}, None
        else:
            return {"success": False, "message": "Authentication record missing. Try Google Login."}, None

    @staticmethod
    def logout():
        return {"success": True, "message": "Successfully logged out!"}, None

    @staticmethod
    def login_or_register_google(user_info):
        google_id = user_info.get('sub')
        email = user_info.get('email')

        auth_record = UserAuth.query.filter_by(google_id=google_id).first()
        found_teacher = None
        is_new_account = False

        if auth_record:
            found_teacher = auth_record.teacher
        else:
            found_teacher = Teacher.query.filter_by(email=email).first()

            if not found_teacher:
                is_new_account = True
                try:
                    # Generate a basic username from email or name
                    base_username = email.split('@')[0].replace('.', '_').lower()
                    username = base_username
                    counter = 1
                    while Teacher.query.filter_by(username=username).first():
                        username = f"{base_username}{counter}"
                        counter += 1

                    # Store Google picture as initial default
                    profile_pic = user_info.get('picture')

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
                
                # Link existing account to Google
                if not auth_record:
                    auth_record = UserAuth(teacher_id=found_teacher.teacher_id)
                    db.session.add(auth_record)
                
                auth_record.google_id = google_id
                auth_record.auth_provider = 'google'
                db.session.commit()
        
        if not found_teacher:
            return {"success": False, "message": "User not found"}, None

        access_token = create_access_token(identity=str(found_teacher.teacher_id))

        # Always fetch data from our database record (found_teacher) 
        # instead of relying on live session data from Google.
        payload = {
            "success": True,
            "message": f"Welcome back, {found_teacher.first_name}",
            "user": {
                "id": found_teacher.teacher_id,
                "username": found_teacher.username,
                "first_name": found_teacher.first_name,
                "last_name": found_teacher.last_name,
                "email": found_teacher.email,
                "profile_image_url": found_teacher.profile_image_url,
                "is_admin": found_teacher.is_admin
            },
            "is_verified": found_teacher.is_verified,
            "is_suspended": found_teacher.is_suspended,
            "needs_onboarding": is_new_account # Frontend can use this to show profile prompt
        }

        return payload, access_token

    @staticmethod
    def verification_code(teacher_id, user_input_code, token=None):
        print(f"DEBUG VERIFY: Request for ID {teacher_id} with code {user_input_code}")
        
        if not teacher_id:
             return {"error": "Teacher ID is missing", "status": 400}

        teacher = Teacher.query.get(teacher_id)
        if not teacher:
            return {"error": "Teacher not found", "status": 404}

        # Find the valid code for this teacher
        verif_record = VerificationCodes.query.filter_by(
            user_id=teacher_id, 
            code_hash=user_input_code
        ).order_by(VerificationCodes.created_at.desc()).first()

        if not verif_record:
            return {"error": "Invalid verification code.", "status": 400}
        
        # Robust expiration check
        expires_at = verif_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at < datetime.now(timezone.utc):
            return {"error": "Code has expired. Please request a new one.", "status": 400}

        try:
            teacher.is_verified = True
            # Optional: Delete the used code
            # db.session.delete(verif_record)
            db.session.commit()
            return {"message": "Verified successfully", "status": 200}
        except Exception as e:
            db.session.rollback()
            return {"error": f"Database error: {str(e)}", "status": 500}
    
    @staticmethod
    def resend_code(teacher_id):
        teacher = Teacher.query.get(teacher_id)
        if not teacher:
            return {"success": False, "message": "Teacher not found."}, 404
        
        try:
            otp_code = AuthService.generate_otp()
            verif_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))

            new_code = VerificationCodes(
                user_id=teacher.teacher_id,
                code_hash=otp_code,
                token=verif_token,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)
            )
            db.session.add(new_code)
            
            email_sent = EmailService.send_verification_email(
                recipient_email=teacher.email,
                recipient_name=f"{teacher.first_name} {teacher.last_name}",
                code=otp_code
            )
            
            if not email_sent:
                return {"success": False, "message": "Failed to send email. Please try again later."}, 500

            db.session.commit()
            return {"success": True, "message": "A new code has been sent!", "verification_token": verif_token}, 200
        except Exception as e:
            db.session.rollback()
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
            
        # Enforce strong password
        is_strong, msg = AuthService.validate_password_strength(new_password)
        if not is_strong:
            return {"success": False, "message": msg}

        try:
            # Update local DB
            teacher.auth.hashed_password = generate_password_hash(new_password)
            db.session.commit()
            return {"success": True, "message": "Password changed successfully!"}
        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": f"Failed to change password: {str(e)}"}

    @staticmethod
    def forgot_password(email):
        print(f"DEBUG: Forgot password request for {email}")
        teacher = Teacher.query.filter_by(email=email).first()
        if not teacher:
            return {"success": False, "message": "No account found with this email."}
            
        if not teacher.auth or teacher.auth.auth_provider != 'local':
            provider = teacher.auth.auth_provider if teacher.auth else "Google"
            return {"success": False, "message": f"This account uses {provider.capitalize()} Login."}

        try:
            otp_code = AuthService.generate_otp()
            # In a real app, you might want a separate table or type for recovery codes
            # But we can reuse VerificationCodes for now
            new_code = VerificationCodes(
                user_id=teacher.teacher_id,
                code_hash=otp_code,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)
            )
            db.session.add(new_code)
            
            # Use EmailService for reset
            email_sent = EmailService.send_password_reset_email(
                recipient_email=email,
                recipient_name=teacher.first_name,
                code=otp_code
            )

            if not email_sent:
                db.session.rollback()
                return {"success": False, "message": "Failed to send reset code. Please try again later."}

            db.session.commit()
            return {"success": True, "message": "A reset code has been sent to your email."}
        except Exception as e:
            db.session.rollback()
            print(f"FORGOT PASSWORD ERROR: {e}")
            return {"success": False, "message": "Failed to send reset code. Please try again later."}

    @staticmethod
    def reset_password_with_otp(email, otp_code, new_password):
        teacher = Teacher.query.filter_by(email=email).first()
        if not teacher:
            return {"success": False, "message": "User not found."}

        try:
            # Verify the OTP
            verif_record = VerificationCodes.query.filter_by(
                user_id=teacher.teacher_id, 
                code_hash=otp_code
            ).order_by(VerificationCodes.created_at.desc()).first()
            
            if not verif_record:
                return {"success": False, "message": "Invalid reset code."}

            # Robust expiration check
            expires_at = verif_record.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at < datetime.now(timezone.utc):
                return {"success": False, "message": "Reset code has expired."}

            # Enforce strong password
            is_strong, msg = AuthService.validate_password_strength(new_password)
            if not is_strong:
                return {"success": False, "message": msg}

            # Update Local DB
            teacher.auth.hashed_password = generate_password_hash(new_password)
            # Delete the code
            db.session.delete(verif_record)
            db.session.commit()
            
            return {"success": True, "message": "Password reset successful! You can now log in."}
            
        except Exception as e:
            db.session.rollback()
            print(f"RESET PASSWORD ERROR: {e}")
            return {"success": False, "message": "Reset failed. Please try again."}
