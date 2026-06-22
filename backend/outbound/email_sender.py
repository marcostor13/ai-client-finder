"""
Email sender — Zoho SMTP via asyncio.to_thread (non-blocking).
Called immediately when a draft is approved.
"""
import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.database import settings


def _smtp_send_blocking(to_email: str, subject: str, body_text: str, body_html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.outbound_from_name} <{settings.outbound_from_email}>"
    msg["To"] = to_email
    msg["Reply-To"] = settings.outbound_from_email
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    with smtplib.SMTP(settings.zoho_smtp_host, settings.zoho_smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.zoho_smtp_user, settings.zoho_smtp_password)
        server.sendmail(settings.outbound_from_email, [to_email], msg.as_string())


async def send_draft(draft: dict) -> bool:
    """Send one draft via Zoho SMTP. Returns True on success."""
    to_email = draft.get("contact_email", "")
    if not to_email:
        print(f"[email_sender] no contact_email for draft {draft.get('_id')}")
        return False
    try:
        await asyncio.to_thread(
            _smtp_send_blocking,
            to_email,
            draft.get("subject", "(sin asunto)"),
            draft.get("body_text", ""),
            draft.get("body_html", ""),
        )
        print(f"[email_sender] OK sent to {to_email}")
        return True
    except Exception as e:
        print(f"[email_sender] FAIL {to_email}: {e}")
        return False
