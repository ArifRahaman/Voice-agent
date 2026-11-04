"""Gmail helpers: contact resolution, IMAP drafts, SMTP sending."""

from __future__ import annotations

import imaplib
import logging
import os
import re
import smtplib
import time
from email.message import EmailMessage

from livekit.agents import ToolError

from config import IMAP_HOST, SMTP_HOST, SMTP_PORT

logger = logging.getLogger("agent")


def contact_email(who: str) -> str:
    """Turn "me", or an address however it was said, into an email address."""
    key = who.strip().lower()
    if key in ("me", "myself", "my email", "my own email", "my address"):
        own = os.getenv("GMAIL_ADDRESS", "").strip()
        if not own:
            raise ToolError("I don't know your own email address yet.")
        return own
    spoken = re.sub(r"\s+at\s+", "@", key)
    spoken = re.sub(r"\s+dot\s+", ".", spoken).replace(" ", "")
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", spoken):
        return spoken
    raise ToolError(
        f"I don't have an email address for {who}. Say the address itself, or \"me\"."
    )


def mail_credentials() -> tuple[str, str]:
    """The Gmail address and app password, or a spoken error explaining what's missing."""
    sender = os.getenv("GMAIL_ADDRESS", "").strip()
    password = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    if not (sender and password):
        raise ToolError(
            "I can't reach your email yet, because no address and app password "
            "are set up."
        )
    return sender, password


def _build_message(sender: str, to: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def _drafts_folder(imap: imaplib.IMAP4_SSL) -> str:
    """The Drafts mailbox, found by its \\Drafts flag since the name is localized."""
    typ, data = imap.list()
    if typ == "OK":
        for raw in data or []:
            line = raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else str(raw)
            if "\\Drafts" in line:
                quoted = re.findall(r'"([^"]*)"', line)
                if quoted:
                    return f'"{quoted[-1]}"'
    return '"[Gmail]/Drafts"'


def save_gmail_draft(to: str, subject: str, body: str) -> str | None:
    """Put the message in the account's Drafts folder. Returns its UID if Gmail gave one."""
    sender, password = mail_credentials()
    msg = _build_message(sender, to, subject, body)
    with imaplib.IMAP4_SSL(IMAP_HOST, timeout=30) as imap:
        imap.login(sender, password)
        typ, data = imap.append(
            _drafts_folder(imap),
            "\\Draft",
            imaplib.Time2Internaldate(time.time()),
            msg.as_bytes(),
        )
        if typ != "OK":
            raise ToolError("Gmail wouldn't accept the draft.")
        reply = b" ".join(x for x in data if isinstance(x, bytes)).decode(
            "utf-8", "ignore"
        )
        found = re.search(r"APPENDUID\s+\d+\s+(\d+)", reply)
        return found.group(1) if found else None


def delete_gmail_draft(uid: str) -> None:
    """Remove a draft we saved, so a sent email doesn't leave a copy behind."""
    sender, password = mail_credentials()
    with imaplib.IMAP4_SSL(IMAP_HOST, timeout=30) as imap:
        imap.login(sender, password)
        imap.select(_drafts_folder(imap))
        imap.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
        imap.expunge()


def smtp_send(to: str, subject: str, body: str) -> None:
    """Send one plain-text email through Gmail's SMTP."""
    sender, password = mail_credentials()
    msg = _build_message(sender, to, subject, body)
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise ToolError(
            "Gmail wouldn't accept that password. It needs an app password rather "
            "than the normal account password."
        ) from None
    except OSError as e:
        logger.warning("SMTP send failed: %s", e)
        raise ToolError("The email didn't go out; the mail server refused it.") from None
    logger.info("email sent to %s", to)
