"""Send contact-form messages to the site owner's Gmail."""
from __future__ import annotations

import re
import smtplib
import ssl
import time
from email.message import EmailMessage

from ..config import get_settings
from ..schemas import ContactRequest

_recent: dict[str, list[float]] = {}


class ContactError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def send(body: ContactRequest) -> None:
    if body.botcheck:  # hidden field filled in: a bot, pretend it worked
        return
    settings = get_settings()
    user, password = settings.gmail_user.strip(), settings.gmail_app_password.replace(" ", "")
    if not user or not password:
        raise ContactError(503, "The contact form is not connected yet. Please try again later.")
    now, sender = time.time(), body.email.lower()
    sent = [t for t in _recent.get(sender, []) if now - t < 3600]
    if len(sent) >= 5:
        raise ContactError(429, "Too many messages. Please try again later.")
    _recent[sender] = [*sent, now]

    name = re.sub(r"[\r\n]+", " ", body.name)
    msg = EmailMessage()
    msg["Subject"] = f"Segmora enquiry from {name}"
    msg["From"] = f"Segmora website <{user}>"
    msg["To"] = user
    msg["Reply-To"] = f"{name} <{body.email}>"
    msg.set_content(f"New message from the Segmora website\n\nName: {name}\nEmail: {body.email}\n\n{body.message}\n")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=15) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    except Exception as exc:
        raise ContactError(502, "The message could not be sent. Please try again in a minute.") from exc
