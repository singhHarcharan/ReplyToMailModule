# ReplyToEmail Module

A Python module to reply to Gmail threads using the Gmail API. Supports multiple sender accounts — each request specifies which Gmail address to send from, and the backend picks the corresponding OAuth token automatically.

---

## Features

- Reply to any Gmail thread by thread ID
- **Multi-account support** — send from different Gmail addresses by passing `from_email` in the request
- Supports plain-text and HTML replies
- Correct RFC-2822 threading via `In-Reply-To` and `References` headers
- OAuth2 authentication with automatic token refresh

---

## Requirements

- Python 3.7+
- A Google Cloud project with the Gmail API enabled
- OAuth2 credentials for each Gmail account you want to send from

---

## Installation

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project
2. Navigate to **APIs & Services → Library** → enable the **Gmail API**
3. Go to **APIs & Services → OAuth consent screen**
   - Choose **External** → fill in app name and your email
   - Under **Test users** → add every Gmail address you want to send from
4. Go to **APIs & Services → Credentials**
   - Click **Create Credentials → OAuth 2.0 Client ID**
   - Choose **Desktop app** as the application type
5. Complete the OAuth flow for each account to generate a `token.json` per account

> **Note:** Never commit `.env` or `token.json` to version control.

---

## Configuration — `GMAIL_ACCOUNTS`

All accounts are configured via a single `GMAIL_ACCOUNTS` environment variable in `.env`. It is a JSON object where each key is a Gmail address and each value is that account's full OAuth token JSON (the contents of `token.json` after completing the OAuth flow).

**`.env` format** (must be on a single line):

```
GMAIL_ACCOUNTS={"user1@gmail.com": {"token": "...", "refresh_token": "...", "token_uri": "https://oauth2.googleapis.com/token", "client_id": "...", "client_secret": "...", "scopes": [...], "universe_domain": "googleapis.com", "account": "", "expiry": "..."}, "user2@gmail.com": {...}}
```

To add a new account, append another key-value pair to the JSON object.

---

## File Structure

```
ReplyToEmail_Module/
├── reply_to_email.py   # Core GmailReplier module
├── app.py              # Flask REST API wrapper
├── requirements.txt    # Python dependencies
└── .env                # GMAIL_ACCOUNTS mapping (do not commit)
```

---

## How It Works — Under the Hood

---

### Stage 1 — Account Resolution

When a request comes in with a `from_email`, the backend:

1. Reads the `GMAIL_ACCOUNTS` env var and parses the JSON mapping
2. Looks up the token for the requested email address
3. Builds a `google.oauth2.credentials.Credentials` object from that token
4. If the token is expired, refreshes it automatically using the refresh token
5. Builds a Gmail API service scoped to that account

```
from_email → GMAIL_ACCOUNTS map → OAuth token → Gmail API service
```

If the email is not found in the mapping, the API returns a 400 error.

---

### Stage 2 — Fetching the Thread

When you call `reply(thread_id, ...)`, the module fetches the full thread:

```
GET https://gmail.googleapis.com/gmail/v1/users/me/threads/{thread_id}?format=full
```

Google returns all messages in the thread. The module picks the **last message** — that's the one being replied to.

---

### Stage 3 — Building the Reply Message

The module extracts headers from the original message to construct a properly threaded reply:

| Header extracted | Used to build |
|---|---|
| `Message-ID` | `In-Reply-To` header on the reply |
| `References` | `References` header on the reply (chain extended) |
| `From` / `Reply-To` | `To` header on the reply |
| `Subject` | `Subject` on the reply, prefixed with `Re:` if not already |

The reply is built as a standard RFC-2822 message, base64url-encoded for the Gmail API.

---

### Stage 4 — Sending via the Gmail API

```
POST https://gmail.googleapis.com/gmail/v1/users/me/messages/send
Body: { "raw": "<base64url encoded message>", "threadId": "<thread_id>" }
```

Google returns the sent message's ID and thread ID.

---

## Flask REST API

`app.py` wraps `GmailReplier` in a lightweight Flask server. Start it with:

```bash
python app.py
# Runs on http://localhost:5000
# Use PORT env var to change: PORT=5001 python app.py
```

---

### `GET /`

Health check.

```bash
curl http://localhost:5000/
# {"status": "ok"}
```

---

### `GET /search`

Search a Gmail inbox and return matching thread IDs.

**Query params:**

| Param        | Required | Description |
|--------------|----------|-------------|
| `from_email` | Yes      | Gmail address whose inbox to search |
| `q`          | Yes      | Any Gmail search query (e.g. `subject:test from:someone@gmail.com`) |

**Response:**

```json
{
  "threads": [
    {
      "thread_id": "19db07f9e9862566",
      "subject": "Re: Your inquiry",
      "from": "sender@example.com",
      "date": "Mon, 21 Apr 2026 10:00:00 +0000"
    }
  ]
}
```

**Example:**

```bash
curl "http://localhost:5000/search?from_email=dwhsoftwareaccess@gmail.com&q=subject:invoice"
```

---

### `POST /reply`

Reply to a Gmail thread from a specified sender account.

**Request body (JSON):**

| Field        | Type     | Required | Description |
|--------------|----------|----------|-------------|
| `from_email` | `string` | Yes      | Gmail address to send from (must be in `GMAIL_ACCOUNTS`) |
| `thread_id`  | `string` | Yes      | Gmail thread ID to reply to |
| `reply_body` | `string` | Yes      | Body text of the reply |
| `reply_to`   | `string` | No       | Override recipient address |
| `html`       | `bool`   | No       | Send `reply_body` as HTML (default `false`) |

**Response:**

```json
{
  "success": true,
  "message_id": "19db07f9e9862567",
  "thread_id": "19db07f9e9862566"
}
```

**Examples:**

```bash
# Plain text reply
curl -X POST http://localhost:5000/reply \
  -H "Content-Type: application/json" \
  -d '{
    "from_email": "dwhsoftwareaccess@gmail.com",
    "thread_id": "19db07f9e9862566",
    "reply_body": "Thanks for reaching out!"
  }'

# HTML reply with a custom recipient
curl -X POST http://localhost:5000/reply \
  -H "Content-Type: application/json" \
  -d '{
    "from_email": "dwhsoftwareaccess@gmail.com",
    "thread_id": "19db07f9e9862566",
    "reply_body": "<p>Thanks for reaching out!</p>",
    "html": true,
    "reply_to": "custom@example.com"
  }'
```

---

## Python Usage

```python
from reply_to_email import GmailReplier

replier = GmailReplier(from_email="dwhsoftwareaccess@gmail.com")

# Plain text reply
result = replier.reply(
    thread_id="YOUR_THREAD_ID_HERE",
    reply_body="Hi, thanks for your email!"
)
print("Sent message ID:", result["id"])

# HTML reply
result = replier.reply(
    thread_id="YOUR_THREAD_ID_HERE",
    reply_body="<p>Hi,</p><p>Thanks for your email!</p>",
    html=True
)

# Override recipient
result = replier.reply(
    thread_id="YOUR_THREAD_ID_HERE",
    reply_body="Following up on your request.",
    reply_to="custom-recipient@example.com"
)
```

---

## API Reference

### `GmailReplier(from_email)`

| Parameter    | Type  | Required | Description |
|--------------|-------|----------|-------------|
| `from_email` | `str` | Yes      | Gmail address to send from. Must be a key in the `GMAIL_ACCOUNTS` env var. |

---

### `reply(thread_id, reply_body, html=False, reply_to=None) → dict`

| Parameter    | Type   | Default | Description |
|--------------|--------|---------|-------------|
| `thread_id`  | `str`  | —       | Gmail thread ID to reply to |
| `reply_body` | `str`  | —       | Body text of the reply |
| `html`       | `bool` | `False` | Set `True` to send `reply_body` as HTML |
| `reply_to`   | `str`  | `None`  | Override recipient. Falls back to `Reply-To` header, then `From` header |

Returns the sent [Message resource](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages) from the Gmail API.

---

### `get_thread(thread_id) → dict`

| Parameter   | Type  | Description     |
|-------------|-------|-----------------|
| `thread_id` | `str` | Gmail thread ID |

---

## OAuth Scopes

| Scope | Purpose |
|---|---|
| `https://www.googleapis.com/auth/gmail.send` | Send emails |
| `https://www.googleapis.com/auth/gmail.readonly` | Read threads to extract headers |

---

## Finding a Thread ID

Thread IDs appear in the Gmail URL when you open a conversation:

```
https://mail.google.com/mail/u/0/#inbox/THREAD_ID_HERE
```

Or use the `/search` endpoint to find them programmatically.

---

## Rate Limits

| Operation | Quota units |
|---|---|
| `threads.get` | 5 units |
| `messages.send` | 100 units |
| **Total per `reply()` call** | **105 units** |

| Level | Limit |
|---|---|
| Per user | 15,000 units / minute (~142 replies/min) |
| Per project | 1,200,000 units / minute |

Both `rateLimitExceeded` and `userRateLimitExceeded` errors should be handled with exponential backoff (2s → 4s → 8s → 16s → 32s → 64s).

---

## Deployment (Render)

Set the `GMAIL_ACCOUNTS` environment variable in Render's dashboard with the single-line JSON mapping of all accounts. No other credentials env vars are needed.
