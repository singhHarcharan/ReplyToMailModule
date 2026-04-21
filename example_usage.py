"""
example_usage.py  —  quick demo of GmailReplier
"""

from reply_to_email import GmailReplier

# 1. Authenticate (opens browser on first run to grant OAuth consent)
replier = GmailReplier(
    credentials_path="credentials.json",  # from Google Cloud Console
    token_path="token.json"               # cached after first login
)

# 2. Reply to a thread (plain text)
result = replier.reply(
    thread_id="room_820aae3784a5fdb2d0afb219188c0056@email.upwork.com",
    reply_body="Hi, thanks for your email! I'll get back to you shortly."
)
print("Sent message ID:", result["id"])

# 3. Reply with HTML body
result_html = replier.reply(
    thread_id="YOUR_THREAD_ID_HERE",
    reply_body="<p>Hi, thanks for your email!</p><p>I'll get back to you shortly.</p>",
    html=True
)
print("Sent message ID:", result_html["id"])
