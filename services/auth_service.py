from models import Teacher, UserAuth, db, VerificationCodes
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from flask_jwt_extended import create_access_token, set_access_cookies
from datetime import datetime, timezone, timedelta
from lib import send_verification_code

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
            # Assign a default avatar using Dicebear based on username
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

            send_verification_code(new_teacher)

            verif_entry = VerificationCodes.query.filter_by(user_id=new_teacher.teacher_id).order_by(VerificationCodes.created_at.desc()).first()

            
            return {
                "success": True, 
                "message": "Registration complete! Please verify your email.",
                "id": new_teacher.teacher_id,
                "username": new_teacher.username,
                "verification_token": verif_entry.token if verif_entry else None,
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
    def get_verification_info(token):
        record = VerificationCodes.query.filter_by(token=token).first()
        if not record:
            return None
        
        teacher = record.teacher
        return {
            "id": teacher.teacher_id,
            "email": teacher.email,
            "is_verified": teacher.is_verified
        }

    @staticmethod
    def login(data):
        email = data.get('email')
        password = data.get('password')

        found_teacher = Teacher.query.filter_by(email=email).first()
        if not found_teacher:
            return {"success": False, "message": "Email not found!"}
        

        if found_teacher.auth:
            if found_teacher.auth.auth_provider != 'local' or not found_teacher.auth.hashed_password:
                 return {"success": False, "message": f"This account uses {found_teacher.auth.auth_provider.capitalize()} Login. Please use that to sign in."}, None

            if check_password_hash(found_teacher.auth.hashed_password, password):
                access_token = create_access_token(identity=str(found_teacher.teacher_id))

                verif_entry = VerificationCodes.query.filter_by(user_id=found_teacher.teacher_id).order_by(VerificationCodes.created_at.desc()).first()

                # If unverified but no code exists, generate one now
                if not found_teacher.is_verified and not verif_entry:
                    send_verification_code(found_teacher)
                    verif_entry = VerificationCodes.query.filter_by(user_id=found_teacher.teacher_id).order_by(VerificationCodes.created_at.desc()).first()

                payload= {
                    "success": True,
                    "message": f"Welcome , {found_teacher.first_name}!",
                    "user": {
                        "id": found_teacher.teacher_id,
                        "username": found_teacher.username,
                        "is_admin": found_teacher.is_admin
                    },
                    "is_verified": found_teacher.is_verified,
                    "is_suspended": found_teacher.is_suspended,
                    "verification_token": verif_entry.token if verif_entry else None
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
        if token:
            record = VerificationCodes.query.filter_by(token=token).first()
        else:
            t_id = int(teacher_id)
            record = VerificationCodes.query.filter_by(user_id=t_id).order_by(VerificationCodes.created_at.desc()).first()

        if not record:
            return { "error": "No verification session found. Please request a new code.", "status": 404 }
        
        # Use timezone-aware comparison with safety fallback
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
            
        if datetime.now(timezone.utc) > expires_at:
            db.session.delete(record)
            db.session.commit()
            return {"error": "Verification code has expired. Please request a new one.", "status": 404 }
        
        if not check_password_hash(record.code_hash, user_input_code):
            return {"error": "Invalid verification code. Please check and try again.", "status": 400}
        
        teacher = record.teacher
        if teacher:
            teacher.is_verified = True
            VerificationCodes.query.filter_by(user_id=teacher.teacher_id).delete()
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
            # Look for existing token to keep the URL stable
            existing_record = VerificationCodes.query.filter_by(user_id=teacher.teacher_id).first()
            old_token = existing_record.token if existing_record else None

            # Delete old codes
            VerificationCodes.query.filter_by(user_id=teacher.teacher_id).delete()

            # Send new code
            from lib import send_verification_code
            import secrets
            from werkzeug.security import generate_password_hash
            from flask_mailman import EmailMessage

            # Custom inline logic to support stable token
            code = f"{secrets.randbelow(1000000):06d}"
            token = old_token if old_token else secrets.token_urlsafe(32)
            hashed_code = generate_password_hash(code)

            new_code = VerificationCodes(
                user_id = teacher.teacher_id,
                code_hash = hashed_code,
                token = token,
                expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
            )
            db.session.add(new_code)
            db.session.commit()

            # Email logic (copied from send_verification_code for consistency)
            html_body = f"""
            <div style="font-family: sans-serif; max-width: 600px; margin: auto; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px;">
                <h2 style="color: #10b981; margin-bottom: 16px;">Verify your TeachShare account</h2>
                <p style="color: #475569; font-size: 16px;">Hi {teacher.first_name},</p>
                <p style="color: #475569; font-size: 16px;">Use the code below to complete your verification. This code is valid for a limited time.</p>
                
                <div style="background-color: #f8fafc; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
                    <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #1e293b;">{code}</span>
                </div>
                
                <p style="color: #94a3b8; font-size: 12px; border-top: 1px solid #e2e8f0; pt: 16px;">
                    If you didn't request this code, you can safely ignore this email.
                </p>
            </div>
            """
            msg = EmailMessage(subject="Your TeachShare Verification Code", body=html_body, to=[teacher.email])
            msg.content_subtype = "html"
            msg.send()
            
            return {
                "success": True, 
                "message": "A new code has been sent!",
                "verification_token": token
            }, 200

        except Exception as e:
            db.session.rollback()
            print(f"RESEND ERROR: {e}")
            return {"success": False, "message": "Failed to resend code."}, 500

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
