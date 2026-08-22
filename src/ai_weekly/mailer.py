from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def send_email(subject: str, html: str) -> bool:
    required = ["SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "EMAIL_TO"]
    if any(not os.environ.get(name) for name in required):
        return False

    sender = os.environ.get("EMAIL_FROM") or os.environ["SMTP_USERNAME"]
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = os.environ["EMAIL_TO"]
    message.set_content("本週全球 AI 科技情報週報已產生，請使用支援 HTML 的郵件程式閱讀。")
    message.add_alternative(html, subtype="html")

    port = int(os.environ.get("SMTP_PORT", "465"))
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, context=context, timeout=30) as smtp:
            smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    else:
        with smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=30) as smtp:
            smtp.starttls(context=context)
            smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    return True

