"""
automation/email_sender.py — Sends application emails via Gmail SMTP.
Requires GMAIL_USER and GMAIL_APP_PASSWORD env vars.
"""
import smtplib
import logging
import random
import time
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from config import (
    GMAIL_USER, GMAIL_APP_PASSWORD, SMTP_HOST, SMTP_PORT,
    EMAIL_DELAY_MIN, EMAIL_DELAY_MAX
)

logger = logging.getLogger(__name__)


def _build_message(to: str, subject: str, body: str, cv_path: Path | None) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = f"<{uuid.uuid4()}@jobhunter>"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if cv_path and cv_path.exists():
        with cv_path.open("rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={cv_path.name}")
        msg.attach(part)
    return msg


def send_email(
    to: str,
    subject: str,
    body: str,
    cv_path: Path | None = None,
    dry_run: bool = False,
) -> tuple[bool, str | None]:
    """Send email. Returns (success, message_id)."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        logger.error("GMAIL_USER / GMAIL_APP_PASSWORD not set in environment.")
        return False, None

    if dry_run:
        dry_id = f"<dry-run-{uuid.uuid4()}@jobhunter>"
        logger.info("[DRY-RUN] Would send email to %s: %s", to, subject)
        return True, dry_id

    try:
        msg = _build_message(to, subject, body, cv_path)
        message_id = msg["Message-ID"]
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, to, msg.as_string())
        logger.info("Email sent to %s (id=%s)", to, message_id)
        return True, message_id
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to, e)
        return False, None


def rate_limited_send(
    to: str, subject: str, body: str, cv_path: Path | None = None, dry_run: bool = False
) -> tuple[bool, str | None]:
    result, message_id = send_email(to, subject, body, cv_path, dry_run)
    delay = random.uniform(EMAIL_DELAY_MIN, EMAIL_DELAY_MAX)
    logger.debug("Rate limit: sleeping %.0fs before next email", delay)
    time.sleep(delay)
    return result, message_id
