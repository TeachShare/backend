from flask_mail import Message
from extensions import mail
from flask import current_app
import os

class EmailService:
    @staticmethod
    def send_email(subject, recipients, html_body, sender=None):
        """Generic method to send an email."""
        if not sender:
            sender = current_app.config.get('MAIL_DEFAULT_SENDER')
            
        msg = Message(subject, recipients=recipients, sender=sender)
        msg.html = html_body
        
        try:
            mail.send(msg)
            print(f"DEBUG: Email sent successfully to {recipients}")
            return True
        except Exception as e:
            print(f"DEBUG: Failed to send email: {e}")
            return False

    @staticmethod
    def send_verification_email(recipient_email, recipient_name, code):
        """Sends a 6-digit verification code."""
        subject = f"{code} is your TeachShare verification code"
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
            <h2 style="color: #059669;">Welcome to TeachShare!</h2>
            <p>Hi {recipient_name},</p>
            <p>Thank you for joining our community of educators. Please use the verification code below to complete your registration:</p>
            <div style="background: #f3f4f6; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #111827; border-radius: 8px; margin: 20px 0;">
                {code}
            </div>
            <p style="color: #6b7280; font-size: 14px;">This code will expire in 10 minutes. If you didn't request this, you can safely ignore this email.</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;" />
            <p style="font-size: 12px; color: #9ca3af;">&copy; 2026 TeachShare. All rights reserved.</p>
        </div>
        """
        return EmailService.send_email(subject, [recipient_email], html_content)

    @staticmethod
    def send_password_reset_email(recipient_email, recipient_name, code):
        """Sends a password reset code."""
        subject = f"{code} is your password reset code"
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
            <h2 style="color: #059669;">Password Reset Request</h2>
            <p>Hi {recipient_name},</p>
            <p>We received a request to reset your TeachShare password. Use the code below to proceed:</p>
            <div style="background: #f3f4f6; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #111827; border-radius: 8px; margin: 20px 0;">
                {code}
            </div>
            <p style="color: #6b7280; font-size: 14px;">This code will expire in 15 minutes. If you didn't request this, you can safely ignore this email.</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;" />
            <p style="font-size: 12px; color: #9ca3af;">&copy; 2026 TeachShare. All rights reserved.</p>
        </div>
        """
        return EmailService.send_email(subject, [recipient_email], html_content)
