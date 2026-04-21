"""
reply_to_email.py
-----------------
Simple module to reply to an email thread using the Gmail API.

Requirements:
    pip install google-auth google-auth-oauthlib google-api-python-client python-dotenv

.env file (required):
    GOOGLE_CLIENT_ID=your_client_id
    GOOGLE_CLIENT_SECRET=your_client_secret

Usage:
    from reply_to_email import GmailReplier

    replier = GmailReplier()
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
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.send",
          "https://www.googleapis.com/auth/gmail.readonly"]


class GmailReplier:
    def __init__(self, token_path: str = "token.json"):
        """
        Reads GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET from the .env file.

        Args:
            token_path: Path where the access/refresh token is cached
                        after the first browser login.
        """
        self.token_path    = token_path
        self.client_id     = os.environ["GOOGLE_CLIENT_ID"]
        self.client_secret = os.environ["GOOGLE_CLIENT_SECRET"]
        self.service       = self._authenticate()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _authenticate(self):
        creds = None

        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                client_config = {
                    "installed": {
                        "client_id":     self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uris": ["http://localhost"],
                        "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                        "token_uri":     "https://oauth2.googleapis.com/token",
                    }
                }
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(self.token_path, "w") as f:
                f.write(creds.to_json())

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
        sender      = reply_to or self._get_header(original_message, "Reply-To") or self._get_header(original_message, "From")
        references  = self._get_header(original_message, "References")

        reply_subject = subject if subject.startswith("Re:") else f"Re: {subject}"

        # Build References chain
        if references:
            new_references = f"{references} {message_id}"
        else:
            new_references = message_id

        if html:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(reply_body, "html"))
        else:
            msg = MIMEText(reply_body, "plain")

        msg["To"]          = sender
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
