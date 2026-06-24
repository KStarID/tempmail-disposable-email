#!/usr/bin/env python3
"""
Postfix Mail Catcher for Disposable Email Service
=================================================

Called by Postfix's mailbox_command. Receives raw email on stdin,
parses it, and POSTs to FastAPI backend for persistence.

Environment:
  BACKEND_URL  - FastAPI base URL (default: http://backend:8000)
  RECIPIENT    - recipient address (passed by Postfix as argv[1])

Exit codes:
  0  - success (mail accepted)
  69- soft failure (mail will be retried)
  67- hard failure (mail will bounce)
"""

import os
import sys
import json
import re
import email
import email.policy
from email.utils import getaddresses
from datetime import datetime, timezone
import urllib.request
import urllib.error

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
RECIPIENT = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("RECIPIENT", "")


def log(msg):
    """Log to stderr (Postfix captures this)"""
    sys.stderr.write(f"[catcher] {msg}\n")
    sys.stderr.flush()


def parse_address(value):
    """Extract email from 'Name <addr@x>' or 'addr@x' format"""
    if not value:
        return ""
    addrs = getaddresses([value])
    return addrs[0][1] if addrs and addrs[0][1] else value.strip()


def extract_body(msg):
    """Extract plain text + HTML body from email"""
    text_body = ""
    html_body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp.lower():
                continue
            try:
                payload = part.get_content()
            except Exception:
                continue
            if content_type == "text/plain" and not text_body:
                text_body = payload
            elif content_type == "text/html" and not html_body:
                html_body = payload
    else:
        try:
            content_type = msg.get_content_type()
            payload = msg.get_content()
            if content_type == "text/plain":
                text_body = payload
            elif content_type == "text/html":
                html_body = payload
        except Exception:
            text_body = str(msg.get_payload())

    return text_body, html_body


def post_to_backend(recipient, sender, subject, text_body, html_body, raw):
    """Send parsed email to FastAPI backend"""
    url = f"{BACKEND_URL}/api/internal/incoming"
    payload = json.dumps({
        "recipient": recipient,
        "from_": sender,
        "subject": subject or "",
        "body_text": text_body or "",
        "body_html": html_body or "",
        "raw_size": len(raw),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            log(f"backend response: {resp.status} {body[:200]}")
            return resp.status == 200
    except urllib.error.HTTPError as e:
        log(f"backend HTTP error {e.code}: {e.read().decode('utf-8', errors='replace')[:300]}")
        return False
    except urllib.error.URLError as e:
        log(f"backend URL error: {e.reason}")
        return False
    except Exception as e:
        log(f"backend error: {e}")
        return False


def main():
    log(f"=== catcher invoked, recipient={RECIPIENT}, backend={BACKEND_URL} ===")

    try:
        raw = sys.stdin.buffer.read()
        log(f"received {len(raw)} bytes")
    except Exception as e:
        log(f"failed to read stdin: {e}")
        sys.exit(67)

    if not raw:
        log("empty stdin, skipping")
        sys.exit(0)

    try:
        msg = email.message_from_bytes(raw, policy=email.policy.default)
    except Exception as e:
        log(f"failed to parse email: {e}")
        sys.exit(67)

    # Parse headers
    sender = parse_address(msg.get("From", ""))
    # IMPORTANT: Postfix passes the rewritten recipient (tempmail@kstarid.cloud)
    # We need the ORIGINAL recipient from the To: header or X-Original-To header
    recipient = parse_address(
        msg.get("X-Original-To", "")
        or msg.get("Delivered-To", "")
        or msg.get("To", "")
        or RECIPIENT
    )
    subject = msg.get("Subject", "")

    # Remove Re: / Fwd: prefixes? Keep as-is for now
    # Decode subject if needed
    from email.header import decode_header

    def decode_header_value(val):
        if not val:
            return ""
        parts = decode_header(val)
        decoded = []
        for content, charset in parts:
            if isinstance(content, bytes):
                try:
                    decoded.append(content.decode(charset or "utf-8", errors="replace"))
                except Exception:
                    decoded.append(content.decode("utf-8", errors="replace"))
            else:
                decoded.append(content)
        return "".join(decoded)

    subject = decode_header_value(subject)
    sender_name = ""
    sender_addr = sender
    if "<" in sender and ">" in sender:
        m = re.match(r"^(.*?)\s*<([^>]+)>", sender)
        if m:
            sender_name = decode_header_value(m.group(1).strip().strip('"'))
            sender_addr = m.group(2).strip()

    text_body, html_body = extract_body(msg)

    log(f"from={sender_addr} to={recipient} subject={subject[:60]}")

    if not recipient:
        log("no recipient, bouncing")
        sys.exit(67)

    success = post_to_backend(recipient, sender_addr, subject, text_body, html_body, raw.decode("utf-8", errors="replace"))

    if success:
        log("delivered to backend OK")
        sys.exit(0)
    else:
        log("delivery failed, will retry")
        sys.exit(69)


if __name__ == "__main__":
    main()
