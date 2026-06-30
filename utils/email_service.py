import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def send_password_reset_email(email: str, reset_token: str) -> bool:
    """Send password reset email with the reset token."""
    if not settings.smtp_host or not settings.smtp_from_email:
        logger.warning("Email not configured. Skipping password reset email.")
        return False

    try:
        # Create reset URL
        reset_url = f"{settings.frontend_url}/reset-password?token={reset_token}"

        # Create email message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Password Reset Request - CropSense AI"
        msg["From"] = settings.smtp_from_email
        msg["To"] = email

        # Create HTML email body
        html_body = f"""
        <html>
        <body>
            <h2>Password Reset Request</h2>
            <p>You have requested to reset your password for CropSense AI.</p>
            <p>Click the link below to reset your password:</p>
            <p><a href="{reset_url}">Reset Password</a></p>
            <p>This link will expire in 30 minutes.</p>
            <p>If you did not request this password reset, please ignore this email.</p>
            <p>Best regards,<br>CropSense AI Team</p>
        </body>
        </html>
        """

        # Create plain text version
        text_body = f"""
        Password Reset Request

        You have requested to reset your password for CropSense AI.

        Click the link below to reset your password:
        {reset_url}

        This link will expire in 30 minutes.

        If you did not request this password reset, please ignore this email.

        Best regards,
        CropSense AI Team
        """

        part1 = MIMEText(text_body, "plain")
        part2 = MIMEText(html_body, "html")
        msg.attach(part1)
        msg.attach(part2)

        # Send email
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)

        logger.info(f"Password reset email sent to {email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send password reset email to {email}: {e}")
        return False
