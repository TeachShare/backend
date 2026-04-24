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

    msg = EmailMessage(
        subject="Your TeachShare Verification Code",
        body=html_body, # Pass the HTML string here
        to=[teacher.email]
    )
    
    # CRITICAL: Tell mailman to render this as HTML
    msg.content_subtype = "html"
    
    msg.send()