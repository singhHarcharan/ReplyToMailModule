"""
test_reply.py
-------------
Step-by-step test for the GmailReplier module.

Steps:
  1. Authenticate  — triggers browser login on first run
  2. List threads  — fetches your 5 most recent Gmail threads
  3. Inspect       — prints headers of the latest message in a chosen thread
  4. Reply         — sends a plain-text reply to that thread
"""

from reply_to_email import GmailReplier


def step1_authenticate():
    print("\n--- Step 1: Authenticate ---")
    replier = GmailReplier()
    print("Authentication successful.")
    return replier


def step2_list_threads(replier: GmailReplier):
    print("\n--- Step 2: List 5 recent threads ---")
    result = (
        replier.service.users()
        .threads()
        .list(userId="me", maxResults=5)
        .execute()
    )
    threads = result.get("threads", [])
    if not threads:
        print("No threads found in your inbox.")
        return []

    for i, t in enumerate(threads):
        print(f"  [{i}] Thread ID: {t['id']}")

    return threads


def step3_inspect_thread(replier: GmailReplier, thread_id: str):
    print(f"\n--- Step 3: Inspect thread {thread_id} ---")
    thread  = replier.get_thread(thread_id)
    message = replier._latest_message(thread)

    subject    = replier._get_header(message, "Subject")
    sender     = replier._get_header(message, "From")
    message_id = replier._get_header(message, "Message-ID")

    print(f"  Subject    : {subject}")
    print(f"  From       : {sender}")
    print(f"  Message-ID : {message_id}")
    print(f"  Total messages in thread: {len(thread['messages'])}")


def step4_send_reply(replier: GmailReplier, thread_id: str):
    print(f"\n--- Step 4: Send reply to thread {thread_id} ---")
    result = replier.reply(
        thread_id=thread_id,
        reply_body="This is a test reply sent via the GmailReplier module.",
        reply_to="46248742640089516201987776980031ver2@mg.upwork.com"
    )
    print(f"  Reply sent successfully!")
    print(f"  Sent Message ID : {result['id']}")
    print(f"  Thread ID       : {result['threadId']}")


if __name__ == "__main__":
    # Step 1 — authenticate
    replier = step1_authenticate()

    # Step 2 — list recent threads
    threads = step2_list_threads(replier)
    if not threads:
        exit(1)

    # Hardcoded thread ID for testing — change this to your target thread
    target_thread_id = "19db07f9e9862566"

    # Step 3 — inspect the thread so you can verify it before replying
    step3_inspect_thread(replier, target_thread_id)

    # Step 4 — send a reply
    confirm = input("\nSend a test reply to this thread? (yes/no): ").strip().lower()
    if confirm == "yes":
        step4_send_reply(replier, target_thread_id)
    else:
        print("Reply skipped.")
