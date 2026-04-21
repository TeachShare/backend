import secrets
from werkzeug.security import generate_password_hash
from flask_mailman import EmailMessage
from models import VerificationCodes, db

def send_verification_code(teacher):
    code = f"{secrets.randbelow(1000000):06d}"

    hashed_code = generate_password_hash(code)

    new_code = VerificationCodes(
        user_id = teacher.teacher_id,
        code_hash = hashed_code
    )

    db.session.add(new_code)
    db.session.commit()

    msg = EmailMessage(
        subject = "Your TeachShare Verification Code",
        body = f"Hi {teacher.first_name}, your 6-digit verification code is: {code}",
        to=[teacher.email]
    )
    msg.send()