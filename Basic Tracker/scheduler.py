"""
Background scheduler for FinTrack Local.
Handles periodic IMAP email command polling and automated monthly statement delivery.
"""

import threading
import time
from datetime import datetime, timedelta
from database import get_setting, set_setting, add_notification
from email_controller import process_incoming_emails
from mailer import generate_and_send_monthly_statement

_stop_event = threading.Event()
_scheduler_thread = None
_last_imap_check_time = None
_last_imap_status_msg = "Idle"
_last_monthly_check_time = None


def get_background_status():
    global _last_imap_check_time, _last_imap_status_msg, _last_monthly_check_time
    return {
        "is_running": _scheduler_thread is not None and _scheduler_thread.is_alive(),
        "last_imap_check": _last_imap_check_time.strftime("%Y-%m-%d %H:%M:%S") if _last_imap_check_time else "Never",
        "last_imap_status": _last_imap_status_msg,
        "imap_enabled": get_setting("imap_enabled", "0") == "1",
        "monthly_reports_enabled": get_setting("monthly_reports_enabled", "0") == "1",
        "last_monthly_report_sent": get_setting("last_monthly_report_sent", "None")
    }


def _worker_loop():
    global _last_imap_check_time, _last_imap_status_msg, _last_monthly_check_time
    print("[Scheduler] Background service started.")

    while not _stop_event.is_set():
        now = datetime.now()

        # 1. IMAP Email Command Polling
        if get_setting("imap_enabled", "0") == "1":
            try:
                _last_imap_check_time = now
                count, msg = process_incoming_emails()
                _last_imap_status_msg = msg
                if count > 0:
                    print(f"[Email Control] {msg}")
            except Exception as e:
                _last_imap_status_msg = f"Error: {str(e)}"
                print(f"[Email Control Error] {e}")
        else:
            _last_imap_status_msg = "Disabled in settings"

        # 2. Monthly Automated Report Delivery
        if get_setting("monthly_reports_enabled", "0") == "1":
            try:
                # Calculate previous month string (e.g. if today is Nov 2026, prev is 2026-10)
                first_of_this_month = now.replace(day=1)
                last_day_of_prev_month = first_of_this_month - timedelta(days=1)
                prev_month_str = last_day_of_prev_month.strftime("%Y-%m")

                last_sent = get_setting("last_monthly_report_sent", "")

                # If prev month hasn't been sent yet, send it
                if last_sent != prev_month_str:
                    print(f"[Scheduler] Sending automated monthly statement for {prev_month_str}...")
                    success, msg = generate_and_send_monthly_statement(prev_month_str)
                    if success:
                        set_setting("last_monthly_report_sent", prev_month_str)
                        print(f"[Scheduler] Successfully sent monthly statement for {prev_month_str}")
                    else:
                        print(f"[Scheduler] Could not send monthly statement: {msg}")
            except Exception as e:
                print(f"[Scheduler Monthly Error] {e}")

        # Sleep interval
        try:
            poll_int = int(get_setting("imap_poll_interval", "60"))
            if poll_int < 10:
                poll_int = 10
        except ValueError:
            poll_int = 60

        # Wait in small chunks to be responsive to stop_event
        for _ in range(poll_int):
            if _stop_event.is_set():
                break
            time.sleep(1)

    print("[Scheduler] Background service stopped.")


def start_scheduler():
    global _scheduler_thread, _stop_event
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _stop_event.clear()
    _scheduler_thread = threading.Thread(target=_worker_loop, daemon=True, name="FinTrackScheduler")
    _scheduler_thread.start()


def stop_scheduler():
    global _stop_event
    _stop_event.set()
