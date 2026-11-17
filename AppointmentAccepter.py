import imaplib
import email
from datetime import date
from bs4 import BeautifulSoup

IMAP_HOST = "imap.gmail.com"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _connect(email_address, password):
    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    imap.login(email_address, password)
    imap.select("INBOX")
    return imap


def _close(imap):
    try:
        imap.close()
    except Exception:
        pass
    try:
        imap.logout()
    except Exception:
        pass


def check_for_appointment_emails(email_address, password, sender_filter=None):
    """Return a list of {"uid", "subject", "link"} for EVERY unread email from
    today that contains an 'availability form' link.

    Emails are read with BODY.PEEK so they are NOT marked as read here;
    call mark_as_read() once the appointments have actually been accepted.
    """
    today = date.today()
    since = f"{today.day:02d}-{MONTHS[today.month - 1]}-{today.year}"
    criteria = f'(UNSEEN SINCE "{since}")'
    if sender_filter:
        criteria = f'(UNSEEN SINCE "{since}" FROM "{sender_filter}")'

    results = []
    imap = None
    try:
        imap = _connect(email_address, password)
        # UIDs stay valid across connections; sequence numbers don't
        status, data = imap.uid("search", None, criteria)
        if status != "OK" or not data or not data[0]:
            print("No new appointment emails")
            return results

        uids = data[0].split()
        print(f"Found {len(uids)} unread matching email(s) from today")

        for uid in uids:
            try:
                status, msg_data = imap.uid("fetch", uid, "(BODY.PEEK[])")
                if status != "OK":
                    print(f"Failed to fetch email {uid}")
                    continue

                msg = None
                for part in msg_data:
                    if isinstance(part, tuple):
                        msg = email.message_from_bytes(part[1])
                        break
                if msg is None:
                    continue

                subject = msg.get("Subject", "No Subject")
                print(f"Checking: {subject}")

                link = extract_appointment_link(get_email_body(msg))
                if link:
                    results.append({"uid": uid, "subject": subject, "link": link})
                else:
                    print("  No 'availability form' link in this email")
            except Exception as e:
                print(f"Error processing email {uid}: {e}")

        return results

    except imaplib.IMAP4.error as e:
        print(f"IMAP error: {e}")
        return results
    except Exception as e:
        print(f"Unexpected error: {e}")
        return results
    finally:
        if imap is not None:
            _close(imap)


def mark_as_read(email_address, password, uids):
    """Flag the given emails as \\Seen so they aren't processed again."""
    if not uids:
        return
    imap = None
    try:
        imap = _connect(email_address, password)
        for uid in uids:
            imap.uid("store", uid, "+FLAGS", "(\\Seen)")
    except Exception as e:
        print(f"Could not mark emails as read: {e}")
    finally:
        if imap is not None:
            _close(imap)


def get_email_body(msg):
    """Return the HTML body if present, otherwise the plain-text body."""
    try:
        if not msg.is_multipart():
            payload = msg.get_payload(decode=True)
            return payload.decode(errors="ignore") if payload else None

        html_body = text_body = None
        for part in msg.walk():
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            ctype = part.get_content_type()
            if ctype == "text/html" and html_body is None:
                html_body = payload.decode(errors="ignore")
            elif ctype == "text/plain" and text_body is None:
                text_body = payload.decode(errors="ignore")
        return html_body or text_body
    except Exception as e:
        print(f"Error extracting email body: {e}")
        return None


def extract_appointment_link(body):
    """Find the link whose text contains 'availability form'."""
    if not body:
        return None
    try:
        soup = BeautifulSoup(body, "html.parser")
        for a in soup.find_all("a", href=True):
            if "availability form" in a.get_text().strip().lower():
                print(f"  Found link: {a['href']}")
                return a["href"]
        return None
    except Exception as e:
        print(f"Error parsing email: {e}")
        return None
