"""
app.py
------
Flask API wrapper around GmailReplier.

POST /reply
    Body (JSON):
        thread_id   string  (required)  Gmail thread ID
        reply_body  string  (required)  Reply content
        reply_to    string  (optional)  Override recipient address
        html        bool    (optional)  Send body as HTML (default false)

Run:
    python app.py
"""

from flask import Flask, request, jsonify
from reply_to_email import GmailReplier

app = Flask(__name__)
replier = GmailReplier()


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/search", methods=["GET"])
def search():
    """
    Find thread IDs by searching Gmail.
    Query params: q (any Gmail search query), e.g. subject:test from:someone@gmail.com
    """
    q = request.args.get("q")
    if not q:
        return jsonify({"error": "q query param is required (e.g. ?q=subject:test)"}), 400

    try:
        result = replier.service.users().messages().list(userId="me", q=q, maxResults=10).execute()
        messages = result.get("messages", [])
        if not messages:
            return jsonify({"threads": [], "message": "No messages found"}), 200

        seen = {}
        for m in messages:
            msg = replier.service.users().messages().get(userId="me", id=m["id"], format="metadata",
                                                         metadataHeaders=["Subject", "From", "Date"]).execute()
            tid = msg.get("threadId")
            if tid not in seen:
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                seen[tid] = {
                    "thread_id": tid,
                    "subject": headers.get("Subject", ""),
                    "from": headers.get("From", ""),
                    "date": headers.get("Date", ""),
                }

        return jsonify({"threads": list(seen.values())}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/reply", methods=["POST"])
def reply():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    thread_id = data.get("thread_id")
    reply_body = data.get("reply_body")

    if not thread_id or not reply_body:
        return jsonify({"error": "thread_id and reply_body are required"}), 400

    reply_to = data.get("reply_to")
    html = bool(data.get("html", False))

    try:
        sent = replier.reply(
            thread_id=thread_id,
            reply_body=reply_body,
            html=html,
            reply_to=reply_to,
        )
        return jsonify({"success": True, "message_id": sent.get("id"), "thread_id": sent.get("threadId")}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
