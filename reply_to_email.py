"""
reply_to_email.py
-----------------
Simple module to reply to an email thread using the Gmail API.

Requirements:
    pip install google-auth google-auth-oauthlib google-api-python-client python-dotenv

Environment variables:
    GMAIL_ACCOUNTS  JSON object mapping email address → token JSON contents
                    e.g. {"user@example.com": {"token": "...", "refresh_token": "...", ...}}

    For single-account fallback (legacy):
    GOOGLE_TOKEN_JSON  Contents of token.json for a single account

Usage:
    from reply_to_email import GmailReplier

    replier = GmailReplier(from_email="user@example.com")
    replier.reply(
        thread_id="<your-thread-id>",
        reply_body="Thanks for reaching out!"
    )
"""

import base64
import json
import os

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.send",
          "https://www.googleapis.com/auth/gmail.readonly"]


def _load_accounts_map() -> dict:
    """Parse GMAIL_ACCOUNTS env var into a dict of {email: token_dict}."""
    raw = os.environ.get("GMAIL_ACCOUNTS")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"GMAIL_ACCOUNTS env var is not valid JSON: {e}")


class GmailReplier:
    def __init__(self, from_email: str = None):
        """
        Build a Gmail service for the given sender email address.

        Looks up the OAuth token from GMAIL_ACCOUNTS env var (a JSON map of
        email → token dict). Falls back to GOOGLE_TOKEN_JSON for single-account
        setups when from_email is not provided.

        Args:
            from_email: The Gmail address to send from. Must exist as a key in
                        the GMAIL_ACCOUNTS mapping (or omit for legacy single-account mode).
        """
        self.from_email = from_email
        self.service = self._authenticate()

    def _authenticate(self):
        creds = None

        if self.from_email:
            accounts = _load_accounts_map()
            if self.from_email not in accounts:
                raise RuntimeError(
                    f"No OAuth token found for '{self.from_email}'. "
                    "Add it to the GMAIL_ACCOUNTS environment variable."
                )
            token_info = accounts[self.from_email]
            # token_info may be a dict or a JSON string
            if isinstance(token_info, str):
                token_info = json.loads(token_info)
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        elif os.environ.get("GOOGLE_TOKEN_JSON"):
            creds = Credentials.from_authorized_user_info(
                json.loads(os.environ["GOOGLE_TOKEN_JSON"]), SCOPES
            )
        else:
            raise RuntimeError(
                "from_email is required. Set GMAIL_ACCOUNTS env var with a "
                "JSON mapping of email addresses to their OAuth token JSON."
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                raise RuntimeError(
                    f"Credentials for '{self.from_email}' are invalid or expired "
                    "and cannot be refreshed automatically."
                )

        return build("gmail", "v1", credentials=creds)

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def get_thread(self, thread_id: str) -> dict:
        """Fetch a full thread and return the raw API response."""
        return (
            self.service.users()
            .threads()
            .get(userId="me", id=thread_id, format="full")
            .execute()
        )

    def _latest_message(self, thread: dict) -> dict:
        """Return the last message in a thread."""
        messages = thread.get("messages", [])
        if not messages:
            raise ValueError("Thread contains no messages.")
        return messages[-1]

    def _get_header(self, message: dict, name: str) -> str:
        """Extract a header value from a Gmail message payload."""
        headers = message.get("payload", {}).get("headers", [])
        for h in headers:
            if h["name"].lower() == name.lower():
                return h["value"]
        return ""

    def _build_reply(self, original_message: dict, reply_body: str,
                     thread_id: str, html: bool = False,
                     reply_to: str = None) -> dict:
        """
        Build an RFC-2822 reply message and return it encoded for the API.

        Sets the required headers so the reply is threaded correctly:
          - To          → reply_to (if provided) → Reply-To header → From header
          - Subject     → Re: <original subject>
          - In-Reply-To → Message-ID of the message being replied to
          - References  → existing References + Message-ID
        """
        message_id  = self._get_header(original_message, "Message-ID")
        subject     = self._get_header(original_message, "Subject")
        recipient   = reply_to or self._get_header(original_message, "Reply-To") or self._get_header(original_message, "From")
        references  = self._get_header(original_message, "References")

        reply_subject = subject if subject.startswith("Re:") else f"Re: {subject}"

        if references:
            new_references = f"{references} {message_id}"
        else:
            new_references = message_id

        if html:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(reply_body, "html"))
        else:
            msg = MIMEText(reply_body, "plain")

        msg["To"]          = recipient
        msg["Subject"]     = reply_subject
        msg["In-Reply-To"] = message_id
        msg["References"]  = new_references

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        return {"raw": raw, "threadId": thread_id}

    def reply(self, thread_id: str, reply_body: str, html: bool = False,
              reply_to: str = None) -> dict:
        """
        Reply to the latest message in a thread.

        Args:
            thread_id:  Gmail thread ID to reply to.
            reply_body: Plain-text (or HTML) body for the reply.
            html:       Set True to send reply_body as HTML.
            reply_to:   Override the recipient address (ignores Reply-To/From headers).

        Returns:
            The sent Message resource returned by the Gmail API.
        """
        thread   = self.get_thread(thread_id)
        original = self._latest_message(thread)
        payload  = self._build_reply(original, reply_body, thread_id, html=html, reply_to=reply_to)

        sent = (
            self.service.users()
            .messages()
            .send(userId="me", body=payload)
            .execute()
        )
        return sent
