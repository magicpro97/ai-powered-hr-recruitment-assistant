"""Email service for sending transactional emails via SMTP (Gmail)."""

# Standard library imports
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from os import getenv

# Local application imports
from backend.logging_config import get_logger

logger = get_logger(__name__)

SMTP_HOST = getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(getenv("SMTP_PORT", "587"))
SMTP_USER = getenv("SMTP_USER", "")
SMTP_PASSWORD = getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = getenv("SMTP_FROM_EMAIL", "") or SMTP_USER
SMTP_FROM_NAME = getenv("SMTP_FROM_NAME", "HR Assistant")
SUPPORT_URL = "https://github.com/magicpro97/ai-powered-hr-recruitment-assistant/issues"


def is_email_configured() -> bool:
    return bool(SMTP_USER and SMTP_PASSWORD)


def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email via SMTP. Returns True on success."""
    if not is_email_configured():
        logger.warning("SMTP not configured, skipping email to %s", to_email)
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL, to_email, msg.as_string())
        logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False


def send_reset_email(to_email: str, reset_token: str, frontend_url: str) -> bool:
    """Send password reset email with a reset link."""
    reset_url = f"{frontend_url.rstrip('/')}/reset-password?token={reset_token}"
    subject = "Đặt lại mật khẩu — HR Assistant"
    html = f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#1e293b">
  <div style="text-align:center;margin-bottom:24px">
    <div style="display:inline-block;width:48px;height:48px;background:linear-gradient(135deg,#3b82f6,#6366f1);border-radius:12px;line-height:48px;color:#fff;font-size:24px">👤</div>
    <h2 style="margin:12px 0 0;color:#0f172a">HR Assistant</h2>
  </div>
  <p>Xin chào,</p>
  <p>Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản <strong>{to_email}</strong>.</p>
  <p>Nhấn nút bên dưới để đặt mật khẩu mới. Link có hiệu lực trong <strong>1 giờ</strong>.</p>
  <div style="text-align:center;margin:28px 0">
    <a href="{reset_url}"
       style="display:inline-block;padding:12px 32px;background:linear-gradient(90deg,#3b82f6,#6366f1);
              color:#fff;text-decoration:none;border-radius:10px;font-weight:600;font-size:15px">Đặt lại mật khẩu</a>
  </div>
  <p style="font-size:13px;color:#64748b">Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua email này. Tài khoản của bạn vẫn an toàn.</p>
  <p style="font-size:13px;color:#64748b">Cần hỗ trợ? Hãy mở một yêu cầu tại <a href="{SUPPORT_URL}">GitHub Issues</a>.</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="font-size:12px;color:#94a3b8;text-align:center">© 2025 HR Assistant · AI-Powered Recruitment</p>
</body>
</html>"""
    return _send_email(to_email, subject, html)
