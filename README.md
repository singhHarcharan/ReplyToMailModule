# ReplyToEmail Module

A simple Python module to reply to Gmail threads using the Gmail API. Handles OAuth2 authentication, thread fetching, and correct email threading headers automatically.

---

## Features

- Reply to any Gmail thread by thread ID
- Supports plain-text and HTML replies
- Correct RFC-2822 threading via `In-Reply-To` and `References` headers
- OAuth2 authentication with automatic token refresh
- Token cached locally — browser prompt only on first run

---

## Requirements

- Python 3.7+
- A Google Cloud project with the Gmail API enabled
- OAuth2 credentials (Client ID + Secret) from Google Cloud Console

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
   - Under **Test users** → add the Gmail address you will authenticate with
4. Go to **APIs & Services → Credentials**
   - Click **Create Credentials → OAuth 2.0 Client ID**
   - Choose **Desktop app** as the application type
   - Copy the **Client ID** and **Client Secret**
5. Create a `.env` file in the project directory:
   ```
   GOOGLE_CLIENT_ID=your_client_id_here
   GOOGLE_CLIENT_SECRET=your_client_secret_here
   ```

> **Note:** Never commit `.env` or `token.json` to version control.

---

## File Structure

```
ReplyToEmail_Module/
├── reply_to_email.py   # Core module
├── test_reply.py       # Step-by-step test script
├── example_usage.py    # Quick usage examples
├── requirements.txt    # Python dependencies
├── .env                # Your credentials (do not commit)
└── token.json          # Auto-generated after first login (do not commit)
```

---

## How It Works — Under the Hood

Understanding what happens at each stage helps you debug issues and extend the module confidently.

---

### Stage 1 — OAuth2 Authentication

**What happens:**
When you instantiate `GmailReplier()`, the module checks if a `token.json` file already exists locally.

- **If it does not exist** — the OAuth2 flow starts. The module builds a client config from your `.env` credentials and calls `flow.run_local_server()`. This:
  1. Starts a temporary HTTP server on `localhost`
  2. Opens your browser to Google's authorization URL
  3. You sign in and grant the requested permissions
  4. Google redirects back to `localhost` with a one-time authorization code
  5. The library exchanges that code for an **access token** + **refresh token**
  6. Both are saved to `token.json`

- **If it exists** — the module loads the saved token. If the access token is expired (they last ~1 hour), the refresh token is used to get a new one silently — no browser needed.

**Why this matters:**
The access token is a short-lived credential that proves your app has permission to act on behalf of your Gmail account. The refresh token is long-lived and is what makes subsequent runs seamless.

```
Your App → Google Authorization Server → Access Token + Refresh Token → token.json
```

---

### Stage 2 — Fetching the Thread

**What happens:**
When you call `reply(thread_id, ...)`, the module first calls `get_thread()` which makes a `GET` request to:

```
GET https://gmail.googleapis.com/gmail/v1/users/me/threads/{thread_id}?format=full
```

Google returns the entire thread as a JSON object — a list of all messages in that conversation, each with:
- Headers (`From`, `To`, `Subject`, `Message-ID`, `References`, `In-Reply-To`)
- Body (base64-encoded)
- Labels, timestamps, metadata

The module picks the **last message** in the list — that's the one you're replying to.

**Why we need this:**
To send a properly threaded reply, we need specific headers from the original message — particularly `Message-ID` and `References`. Without fetching the thread first, we'd be sending a standalone email, not a reply.

```
Gmail API → Full Thread JSON → Extract last message → Read headers
```

---

### Stage 3 — Building the Reply Message

**What happens:**
The module extracts four headers from the original message and uses them to construct the reply:

| Header extracted | Used to build |
|---|---|
| `Message-ID` | `In-Reply-To` header on the reply |
| `References` | `References` header on the reply (chain extended) |
| `From` | `To` header on the reply (you're replying to the sender) |
| `Subject` | `Subject` on the reply, prefixed with `Re:` if not already |

The reply is built as a standard **RFC-2822 email message** using Python's `MIMEText` (plain) or `MIMEMultipart` (HTML). This is the same format any email client uses.

The composed message is then **base64url-encoded** — this is required by the Gmail API which only accepts raw email bytes encoded in this format.

**Why the headers matter:**
Email threading is not controlled by Gmail alone — it's an open standard. `In-Reply-To` tells the receiving email client which message this is a reply to. `References` is the full chain of Message-IDs in the conversation. Email clients (Gmail, Outlook, Apple Mail) use these two headers to group messages into threads. Without them, your reply would appear as a new standalone email.

```
Original headers → RFC-2822 message → base64url encoded → API-ready payload
```

---

### Stage 4 — Sending via the Gmail API

**What happens:**
The encoded message payload is sent as a `POST` request to:

```
POST https://gmail.googleapis.com/gmail/v1/users/me/messages/send
Body: { "raw": "<base64url encoded message>", "threadId": "<thread_id>" }
```

The `threadId` field in the body tells Gmail to place this message inside the existing thread. Combined with the `In-Reply-To` and `References` headers, this ensures the reply is threaded both in Gmail's UI and in any other email client.

Google returns a Message resource with the sent message's ID and thread ID.

```
Encoded payload + threadId → Gmail API → Message delivered → Message ID returned
```

---

## Full Flow Diagram

```
GmailReplier()
     │
     ▼
[Check token.json]
     │
     ├── exists & valid ──────────────────────────────┐
     │                                                 │
     └── missing/expired                               │
           │                                           │
           ▼                                           │
     [Browser OAuth flow]                              │
     Google issues Access Token + Refresh Token        │
     Saved to token.json                               │
           │                                           │
           └───────────────────────────────────────────┤
                                                       │
                                                       ▼
                                              [Gmail API service ready]
                                                       │
                                                       ▼
                                         reply(thread_id, reply_body)
                                                       │
                                                       ▼
                                        GET /threads/{thread_id}
                                        → Full thread JSON returned
                                                       │
                                                       ▼
                                        Extract last message headers
                                        (Message-ID, References, From, Subject)
                                                       │
                                                       ▼
                                        Build RFC-2822 message
                                        Set In-Reply-To, References, To, Subject
                                        base64url encode
                                                       │
                                                       ▼
                                        POST /messages/send
                                        { raw: "...", threadId: "..." }
                                                       │
                                                       ▼
                                        { id: "sent_msg_id", threadId: "..." }
```

---

## Usage

### Basic reply (plain text)

```python
from reply_to_email import GmailReplier

replier = GmailReplier()

result = replier.reply(
    thread_id="YOUR_THREAD_ID_HERE",
    reply_body="Hi, thanks for your email! I'll get back to you shortly."
)

print("Sent message ID:", result["id"])
```

### HTML reply

```python
result = replier.reply(
    thread_id="YOUR_THREAD_ID_HERE",
    reply_body="<p>Hi,</p><p>Thanks for your email!</p>",
    html=True
)
```

### Fetch a thread directly

```python
thread = replier.get_thread("YOUR_THREAD_ID_HERE")
print(thread)
```

---

## Running the Test Script

`test_reply.py` walks through all four stages interactively:

```bash
python test_reply.py
```

| Step | What it does |
|------|-------------|
| 1 — Auth | Authenticates and confirms token is working |
| 2 — List threads | Prints your 5 most recent thread IDs |
| 3 — Inspect | Shows Subject, From, Message-ID of the target thread |
| 4 — Reply | Asks for confirmation then sends the reply |

---

## API Reference

### `GmailReplier(token_path)`

| Parameter    | Type  | Default        | Description                              |
|--------------|-------|----------------|------------------------------------------|
| `token_path` | `str` | `"token.json"` | Path where the access token is cached    |

Reads `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` from the `.env` file automatically.

---

### `reply(thread_id, reply_body, html=False) → dict`

| Parameter    | Type   | Default | Description                              |
|--------------|--------|---------|------------------------------------------|
| `thread_id`  | `str`  | —       | Gmail thread ID to reply to              |
| `reply_body` | `str`  | —       | Body text of the reply                   |
| `html`       | `bool` | `False` | Set `True` to send `reply_body` as HTML  |

Returns the sent [Message resource](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages) from the Gmail API.

---

### `get_thread(thread_id) → dict`

| Parameter   | Type  | Description      |
|-------------|-------|------------------|
| `thread_id` | `str` | Gmail thread ID  |

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

You can also list them programmatically — `test_reply.py` does this automatically in Step 2.

---

## Rate Limits

Gmail API enforces quota at two levels — per project and per user.

### Quota Limits

| Level | Limit |
|---|---|
| Per project | 1,200,000 quota units / minute |
| Per user | 15,000 quota units / minute |
| Max recipients per message | 500 |

### Quota Cost Per Operation

| Operation | Units |
|---|---|
| `threads.get` (fetch thread) | 5 units |
| `messages.send` (send reply) | 100 units |
| **Total per `reply()` call** | **105 units** |

### Practical Limits for This Module

| Scenario | Max per minute |
|---|---|
| Replies per user | ~142 (15,000 ÷ 105) |
| Replies per project | ~11,428 (1,200,000 ÷ 105) |

For normal use (replying to emails one at a time) you are well within limits. If you are bulk-replying to many threads in a loop, you may hit the per-user cap.

### Error Codes

| Error | Cause |
|---|---|
| `rateLimitExceeded` | Project-level cap hit |
| `userRateLimitExceeded` | Per-user cap hit |

Both errors should be handled with **exponential backoff** — retry after 2s, then 4s, 8s, 16s, 32s, up to a maximum of ~64 seconds before giving up.
