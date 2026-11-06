"""Email: draft first, then send only after the user says yes."""

from __future__ import annotations

import asyncio
import logging

from livekit.agents import ToolError, function_tool

from services.email import contact_email, delete_gmail_draft, save_gmail_draft, smtp_send
from tools.base import ToolBase

logger = logging.getLogger("agent")


class MailTools(ToolBase):
    _draft: dict[str, str] | None = None

    @function_tool
    async def draft_email(self, to: str, subject: str, body: str) -> str:
        """Write an email and hold it for approval. This does NOT send anything.

        Always call this first when someone wants to send an email. Then read the
        draft back to them and ask whether to send it.

        Args:
            to: Who it's for: "me", or an address like "sam@example.com".
            subject: A short subject line.
            body: What the email should say, in full sentences.
        """
        self._require_local("send email")
        address = contact_email(to)
        if not body.strip():
            raise ToolError("The email needs something in it. What should it say?")
        self._draft = {
            "to": address,
            "subject": subject.strip() or "(no subject)",
            "body": body.strip(),
        }
        in_gmail = ""
        try:
            uid = await asyncio.to_thread(
                save_gmail_draft, address, self._draft["subject"], self._draft["body"]
            )
            self._draft["uid"] = uid or ""
            in_gmail = " It's saved in their Gmail drafts, so they can check it there."
        except Exception as e:
            logger.warning("couldn't save the draft to Gmail: %s", e)
        logger.info("draft_email: to %s", address)
        return (
            f"Drafted, NOT yet sent. To: {address}. Subject: {self._draft['subject']}. "
            f"Body: {self._draft['body']}{in_gmail}\n"
            "Read this back to them and ask whether to send it. Only call send_email "
            "once they have clearly said yes."
        )

    @function_tool
    async def send_email(self) -> str:
        """Send the email that draft_email prepared.

        Only call this after reading the draft back to the user and hearing a clear
        yes. If they want anything changed, call draft_email again instead.
        """
        self._require_local("send email")
        if not self._draft:
            raise ToolError("There's no draft ready. What should the email say?")
        draft = self._draft
        await asyncio.to_thread(
            smtp_send, draft["to"], draft["subject"], draft["body"]
        )
        self._draft = None
        if draft.get("uid"):
            try:
                await asyncio.to_thread(delete_gmail_draft, draft["uid"])
            except Exception as e:
                logger.warning("couldn't remove the saved Gmail draft: %s", e)
        return f"Sent to {draft['to']}."
