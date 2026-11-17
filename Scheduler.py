import os
import time
from datetime import datetime, time as dt_time

from AppointmentAccepter import check_for_appointment_emails, mark_as_read
from interactWithUI import accept_appointments

# ---- Configuration -------------------------------------------------------
# Keep secrets out of the source file (and out of git). Set them once in a
# terminal with:
#   setx APPT_EMAIL "address@gmail.com"
#   setx APPT_APP_PASSWORD "xxxx xxxx xxxx xxxx"
# then open a NEW terminal before running this script.
EMAIL = os.environ.get("APPT_EMAIL")
PASSWORD = os.environ.get("APPT_APP_PASSWORD")
SENDER_FILTER = "support.desk@scheduleinterpreter.com"

START = dt_time(9, 0)
END = dt_time(18, 0)
WORKDAYS = {0, 1, 2, 3, 4}   # Mon-Fri
POLL_SECONDS = 15            # Gmail can throttle very frequent logins
IDLE_SECONDS = 60            # sleep between checks outside working hours
# --------------------------------------------------------------------------


def in_window(now):
    return now.weekday() in WORKDAYS and START <= now.time() < END


def process_new_emails():
    """Handle every new appointment email. Returns total requests clicked."""
    found = check_for_appointment_emails(EMAIL, PASSWORD, SENDER_FILTER)
    total = 0
    handled_uids = []
    seen_links = set()

    for item in found:
        link = item["link"]
        if link in seen_links:          # duplicate email, same form
            handled_uids.append(item["uid"])
            continue
        seen_links.add(link)

        print(f"Opening form from: {item['subject']}")
        clicked = accept_appointments(link)
        if clicked > 0:
            print(f"✓ {clicked} request(s) accepted from this email")
            total += clicked
            handled_uids.append(item["uid"])
        else:
            # Leave it unread so the next poll tries again
            print("✗ Nothing accepted from this email; will retry")

    mark_as_read(EMAIL, PASSWORD, handled_uids)
    return total


def main():
    if not EMAIL or not PASSWORD:
        raise SystemExit("Set APPT_EMAIL and APPT_APP_PASSWORD environment variables first.")

    print("Running. Checks Mon-Fri 9:00-17:00 for appointment emails.")
    accepted_today = 0
    current_day = datetime.now().date()

    while True:
        now = datetime.now()
        if now.date() != current_day:
            print(f"Day summary {current_day}: {accepted_today} accepted")
            current_day, accepted_today = now.date(), 0

        if in_window(now):
            try:
                accepted_today += process_new_emails()
            except Exception as e:
                # One bad poll shouldn't kill the whole day
                print(f"Poll failed: {e}")
            time.sleep(POLL_SECONDS)
        else:
            time.sleep(IDLE_SECONDS)


if __name__ == "__main__":
    main()
