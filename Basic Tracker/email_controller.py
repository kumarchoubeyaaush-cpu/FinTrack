"""
Email Controller: Reads incoming emails via IMAP from authorized sender,
executes commands (Add expense/income, check balance, update limits, generate reports),
and replies back with status and confirmations.
"""

import imaplib
import email
from email.header import decode_header
import re
import ssl
from datetime import datetime
from database import get_db, get_setting, set_setting, add_notification
from mailer import send_email, check_limits_and_alert, generate_and_send_monthly_statement, sanitize_app_password


def test_imap_connection(host, port, user, password):
    """Verifies IMAP connection and credentials with clear diagnostics."""
    user = user.strip()
    password = sanitize_app_password(password)

    if not host or not user or not password:
        return {"success": False, "message": "Please enter your Gmail address and 16-character Google App Password."}

    try:
        context = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL(host, int(port), ssl_context=context)
        mail.login(user, password)
        status, _ = mail.select("INBOX")
        mail.logout()
        if status == "OK":
            return {"success": True, "message": f"✅ Successfully connected to Gmail IMAP ({host}:993)! Email control is active."}
        else:
            return {"success": False, "message": f"Connected, but failed to select INBOX: {status}"}
    except imaplib.IMAP4.error as imap_err:
        return {
            "success": False,
            "message": (
                "❌ Gmail IMAP Login Failed (Invalid Credentials)!\n\n"
                "Google does NOT accept regular Gmail passwords for IMAP.\n"
                "👉 Solution:\n"
                "1. Go to your Google Account > Security > 2-Step Verification\n"
                "2. Generate an 'App Password' for FinTrack (16 letters)\n"
                "3. Paste the 16-letter App Password into the IMAP Password field."
            )
        }
    except Exception as e:
        return {"success": False, "message": f"❌ IMAP Connection Failed: {str(e)}"}


def decode_str(header_val):
    if not header_val:
        return ""
    decoded_parts = decode_header(header_val)
    res = []
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            try:
                res.append(part.decode(encoding or "utf-8", errors="replace"))
            except Exception:
                res.append(part.decode("utf-8", errors="replace"))
        else:
            res.append(str(part))
    return " ".join(res).strip()


def extract_email_address(from_header):
    match = re.search(r'[\w\.-]+@[\w\.-]+', from_header)
    return match.group(0).lower() if match else from_header.lower().strip()


def find_category_and_subcategory(category_hint, subcategory_hint=None):
    """
    Fuzzy/flexible matcher for categories and subcategories in database.
    """
    conn = get_db()
    cats = conn.execute("SELECT id, name, type FROM categories").fetchall()
    
    matched_cat = None
    clean_cat_hint = category_hint.lower().strip() if category_hint else ""

    # Check exact or partial category match
    for cat in cats:
        c_name = cat["name"].lower()
        if clean_cat_hint == c_name or clean_cat_hint in c_name or c_name in clean_cat_hint:
            matched_cat = cat
            break

    # If still not matched, check keyword hints
    if not matched_cat and clean_cat_hint:
        hints_map = {
            "food": "Food & Dining",
            "dining": "Food & Dining",
            "grocery": "Food & Dining",
            "groceries": "Food & Dining",
            "zomato": "Food & Dining",
            "swiggy": "Food & Dining",
            "house": "Housing & Utilities",
            "rent": "Housing & Utilities",
            "electric": "Housing & Utilities",
            "utility": "Housing & Utilities",
            "transport": "Transportation & Travel",
            "fuel": "Transportation & Travel",
            "petrol": "Transportation & Travel",
            "diesel": "Transportation & Travel",
            "uber": "Transportation & Travel",
            "ola": "Transportation & Travel",
            "metro": "Transportation & Travel",
            "shop": "Shopping & Lifestyle",
            "clothes": "Shopping & Lifestyle",
            "amazon": "Shopping & Lifestyle",
            "flipkart": "Shopping & Lifestyle",
            "movie": "Entertainment & Subscriptions",
            "netflix": "Entertainment & Subscriptions",
            "health": "Health & Medical",
            "med": "Health & Medical",
            "doctor": "Health & Medical",
            "salary": "Income",
            "income": "Income"
        }
        for k, v in hints_map.items():
            if k in clean_cat_hint:
                for cat in cats:
                    if cat["name"] == v:
                        matched_cat = cat
                        break
                if matched_cat:
                    break

    # Default category if none found
    if not matched_cat:
        for cat in cats:
            if cat["name"] == "Food & Dining":
                matched_cat = cat
                break
        if not matched_cat and cats:
            matched_cat = cats[0]

    matched_subcat = None
    if matched_cat:
        subcats = conn.execute("SELECT id, name FROM subcategories WHERE category_id = ?", (matched_cat["id"],)).fetchall()
        if subcategory_hint:
            clean_sub = subcategory_hint.lower().strip()
            for s in subcats:
                s_name = s["name"].lower()
                if clean_sub == s_name or clean_sub in s_name or s_name in clean_sub:
                    matched_subcat = s
                    break
        if not matched_subcat and subcats:
            matched_subcat = subcats[0]

    conn.close()
    return matched_cat, matched_subcat


def parse_and_execute_command(raw_text, sender_email):
    """
    Parses commands received via email and executes them.
    Returns response message string to reply to sender.
    """
    text = raw_text.strip()
    cleaned = re.sub(r'\s+', ' ', text)
    tokens = cleaned.split(' ')
    first_word = tokens[0].upper() if tokens else ""

    currency = get_setting("currency_symbol", "₹")

    # Command: HELP
    if first_word in ("HELP", "?", "COMMANDS"):
        return f"""
FinTrack Local - Email Commands Guide
-------------------------------------
Control your local tracker anytime by sending emails:

1. Add Expense:
   • ADD <amount> <category> [subcategory] [note]
     Example: ADD 450 Food Groceries Supermarket
     Example: SPENT 250 Transport Petrol Shell petrol pump
     Example: EXPENSE 120 Food:Coffee Starbucks latte

2. Add Income:
   • INCOME <amount> [source] [note]
     Example: INCOME 50000 Salary Monthly credit
     Example: ADD INCOME 1500 Freelance Project milestone

3. Check Balance & Status:
   • STATUS or BALANCE
     Returns current balance, monthly spent, remaining budget & safety status.

4. View / Update Spending Limits:
   • LIMIT UPPER <amount>  (e.g., LIMIT UPPER 30000)
   • LIMIT LOWER <amount>  (e.g., LIMIT LOWER 6000)
   • LIMIT WARN <pct>      (e.g., LIMIT WARN 80)

5. Request Full Statement:
   • REPORT
   • REPORT 2026-11
     Instantly replies with itemized monthly statement & attached CSV!

6. List Categories:
   • CATEGORIES
     Replies with all available categories & subcategories.
"""

    # Command: STATUS or BALANCE
    if first_word in ("STATUS", "BALANCE", "SUMMARY"):
        current_month = datetime.now().strftime("%Y-%m")
        conn = get_db()
        row_inc = conn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='income'").fetchone()
        row_exp = conn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='expense'").fetchone()
        all_time_balance = float(row_inc["total"]) - float(row_exp["total"])

        row_m_exp = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='expense' AND date LIKE ?",
            (f"{current_month}%",)
        ).fetchone()
        monthly_expense = float(row_m_exp["total"])

        row_m_inc = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='income' AND date LIKE ?",
            (f"{current_month}%",)
        ).fetchone()
        monthly_income = float(row_m_inc["total"])

        recent = conn.execute("""
            SELECT t.date, t.type, t.amount, c.name as category, COALESCE(s.name, '') as subcat, t.description
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            LEFT JOIN subcategories s ON t.subcategory_id = s.id
            ORDER BY t.date DESC, t.time DESC LIMIT 5
        """).fetchall()
        conn.close()

        upper_limit = float(get_setting("upper_limit", "25000.00"))
        lower_limit = float(get_setting("lower_limit", "5000.00"))
        used_pct = (monthly_expense / upper_limit * 100.0) if upper_limit > 0 else 0
        rem_budget = upper_limit - monthly_expense

        recent_txt = "\n".join([
            f"  • {r['date']}: {'+' if r['type']=='income' else '-'}{currency}{r['amount']:.2f} ({r['category']}{' > ' + r['subcat'] if r['subcat'] else ''}) {r['description']}"
            for r in recent
        ])

        status_flag = "🟢 Safe (Within Limits)"
        if upper_limit > 0 and monthly_expense >= upper_limit:
            status_flag = "🚨 OVERSPENT (Upper Limit Exceeded!)"
        elif all_time_balance <= lower_limit:
            status_flag = "⚠️ LOW BALANCE (Below Lower Limit!)"

        return f"""
FinTrack Local - Financial Status ({current_month})
--------------------------------------------------
Status: {status_flag}

💰 Total Account Balance: {currency}{all_time_balance:,.2f}
📉 Monthly Expenses ({current_month}): {currency}{monthly_expense:,.2f}
📈 Monthly Income ({current_month}): {currency}{monthly_income:,.2f}

Budget Limits:
  • Upper Spending Limit: {currency}{upper_limit:,.2f} ({used_pct:.1f}% used)
  • Remaining Monthly Budget: {currency}{rem_budget:,.2f}
  • Safe Lower Balance Limit: {currency}{lower_limit:,.2f}

Recent Transactions:
{recent_txt or '  No transactions recorded yet.'}

Type 'REPORT' to receive full itemized monthly statement.
"""

    # Command: LIMIT UPPER / LIMIT LOWER / LIMIT WARN
    if first_word in ("LIMIT", "SET"):
        if len(tokens) >= 3:
            sub = tokens[1].upper()
            try:
                val = float(tokens[2].replace(currency, "").replace(",", ""))
                if "UP" in sub:
                    set_setting("upper_limit", f"{val:.2f}")
                    add_notification("info", f"Upper limit updated via email to {currency}{val:,.2f}", f"Sender: {sender_email}")
                    return f"✅ Monthly Upper Spending Limit updated to {currency}{val:,.2f}!"
                elif "LOW" in sub:
                    set_setting("lower_limit", f"{val:.2f}")
                    add_notification("info", f"Lower limit updated via email to {currency}{val:,.2f}", f"Sender: {sender_email}")
                    return f"✅ Safe Lower Balance Limit updated to {currency}{val:,.2f}!"
                elif "WARN" in sub or "PCT" in sub:
                    set_setting("upper_limit_warn_pct", f"{val:.0f}")
                    return f"✅ Upper Limit Warning threshold updated to {val:.0f}%!"
            except ValueError:
                return f"❌ Error: Invalid limit amount. Example: LIMIT UPPER 30000"
        return "❌ Syntax: LIMIT UPPER <amount> or LIMIT LOWER <amount>"

    # Command: REPORT
    if first_word == "REPORT":
        month_target = tokens[1] if len(tokens) > 1 and re.match(r'^\d{4}-\d{2}$', tokens[1]) else datetime.now().strftime("%Y-%m")
        success, msg = generate_and_send_monthly_statement(month_target, sender_email)
        if success:
            return f"✅ Monthly statement for {month_target} generated and sent to {sender_email} with CSV attachment!"
        else:
            return f"❌ Failed to generate report: {msg}"

    # Command: CATEGORIES
    if first_word in ("CATEGORIES", "CATEGORY", "LIST"):
        conn = get_db()
        cats = conn.execute("SELECT id, name, icon, type FROM categories ORDER BY type, name").fetchall()
        lines = ["Available Categories & Subcategories:\n"]
        for c in cats:
            subcats = conn.execute("SELECT name FROM subcategories WHERE category_id = ?", (c["id"],)).fetchall()
            sub_str = ", ".join([s["name"] for s in subcats]) if subcats else "None"
            lines.append(f"{c['icon']} {c['name']} [{c['type'].upper()}]:")
            lines.append(f"   Subcategories: {sub_str}\n")
        conn.close()
        return "\n".join(lines)

    # Command: ADD / SPENT / EXPENSE / INCOME
    is_income = False
    amount = None
    remaining_tokens = []

    if first_word in ("INCOME", "EARNED", "SALARY", "RECEIVED", "CREDIT"):
        is_income = True
        remaining_tokens = tokens[1:]
    elif first_word in ("ADD", "SPENT", "EXPENSE", "PAID", "DEBIT"):
        if len(tokens) > 1 and tokens[1].upper() == "INCOME":
            is_income = True
            remaining_tokens = tokens[2:]
        else:
            is_income = False
            remaining_tokens = tokens[1:]
    else:
        remaining_tokens = tokens

    cat_hint = ""
    subcat_hint = ""
    note_words = []

    for t in remaining_tokens:
        clean_t = t.replace(currency, "").replace("₹", "").replace("$", "").replace(",", "").strip()
        if amount is None:
            try:
                val = float(clean_t)
                if val > 0:
                    amount = val
                    continue
            except ValueError:
                pass
        
        if ":" in t:
            parts = t.split(":", 1)
            cat_hint = parts[0]
            subcat_hint = parts[1]
        elif not cat_hint and t.lower() not in ("on", "for", "in", "at", "to"):
            cat_hint = t
        elif not subcat_hint and t.lower() not in ("on", "for", "in", "at", "to"):
            subcat_hint = t
        else:
            note_words.append(t)

    if amount is None or amount <= 0:
        return f"""
❌ Could not understand command.
To record an expense, send:
  ADD <amount> <category> [subcategory] [note]
  Example: ADD 450 Food Groceries Vegetables

Or send 'HELP' to see all commands.
"""

    tx_type = "income" if is_income else "expense"
    category, subcategory = find_category_and_subcategory(cat_hint, subcat_hint)

    if not category:
        return "❌ Could not find a suitable category. Send 'CATEGORIES' to list available categories."

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    note = " ".join(note_words).strip() or (f"Logged via email from {sender_email}")
    cat_id = category["id"]
    subcat_id = subcategory["id"] if subcategory else None

    # Insert transaction
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (type, amount, category_id, subcategory_id, date, time, description, payment_method, source, original_currency, original_amount, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Email', 'email', 'INR', ?, ?)
    """, (tx_type, amount, cat_id, subcat_id, date_str, time_str, note, amount, now.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

    # Trigger limit evaluation
    alerts = check_limits_and_alert(now.strftime("%Y-%m"))

    upper_limit = float(get_setting("upper_limit", "25000.00"))
    lower_limit = float(get_setting("lower_limit", "5000.00"))

    conn = get_db()
    row_exp = conn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='expense' AND date LIKE ?", (f"{date_str[:7]}%",)).fetchone()
    monthly_exp = float(row_exp["total"])
    row_inc = conn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='income'").fetchone()
    row_all_exp = conn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='expense'").fetchone()
    tot_bal = float(row_inc["total"]) - float(row_all_exp["total"])
    conn.close()

    sub_name_str = f" > {subcategory['name']}" if subcategory else ""
    alert_suffix = ""
    if alerts:
        alert_suffix = "\n\n⚠️ ALERTS TRIGGERED:\n" + "\n".join([f"  • {a['message']}" for a in alerts])

    action_label = "Income" if is_income else "Expense"
    sign = "+" if is_income else "-"

    return f"""
✅ Recorded {action_label} Successfully!
---------------------------------------
Amount: {sign}{currency}{amount:,.2f}
Category: {category['name']}{sub_name_str}
Date: {date_str} {time_str}
Note: {note}

Financial Snapshot:
  • Monthly Expenses ({date_str[:7]}): {currency}{monthly_exp:,.2f} / {currency}{upper_limit:,.2f} ({((monthly_exp/upper_limit)*100 if upper_limit>0 else 0):.1f}% used)
  • Remaining Monthly Budget: {currency}{(upper_limit - monthly_exp):,.2f}
  • Total Account Balance: {currency}{tot_bal:,.2f}{alert_suffix}
"""


def process_incoming_emails():
    """
    Connects to IMAP, searches for UNSEEN emails from authorized sender,
    processes commands, and sends email replies.
    """
    imap_enabled = get_setting("imap_enabled", "0") == "1"
    if not imap_enabled:
        return 0, "IMAP email control is disabled in settings."

    host = get_setting("imap_host", "imap.gmail.com")
    port = int(get_setting("imap_port", "993"))
    user = get_setting("imap_user", "").strip()
    password = sanitize_app_password(get_setting("imap_pass", ""))
    authorized_sender = get_setting("authorized_sender", "").lower().strip()

    if not host or not user or not password:
        return 0, "IMAP credentials not configured."

    processed_count = 0
    try:
        context = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL(host, port, ssl_context=context)
        mail.login(user, password)
        mail.select("INBOX")

        status, search_data = mail.search(None, "UNSEEN")
        if status != "OK" or not search_data[0]:
            mail.logout()
            return 0, "No new emails."

        email_ids = search_data[0].split()
        for e_id in email_ids:
            try:
                res, data = mail.fetch(e_id, "(RFC822)")
                if res != "OK":
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                from_raw = decode_str(msg.get("From", ""))
                sender = extract_email_address(from_raw)
                subject = decode_str(msg.get("Subject", ""))

                body_text = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))
                        if content_type == "text/plain" and "attachment" not in content_disposition:
                            payload = part.get_payload(decode=True)
                            if payload:
                                body_text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                                break
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")

                # Security check
                if authorized_sender and sender != authorized_sender:
                    conn = get_db()
                    conn.execute("""
                        INSERT INTO email_logs (sender, subject, command, status, response_msg, created_at)
                        VALUES (?, ?, ?, 'IGNORED_UNAUTHORIZED', 'Sender not authorized in settings', ?)
                    """, (sender, subject, body_text[:200], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    conn.close()
                    mail.store(e_id, '+FLAGS', '\\Seen')
                    continue

                command_candidate = subject.strip()
                if not command_candidate or command_candidate.lower() in ("expense", "command", "fintrack", "tracker", "update"):
                    for line in body_text.splitlines():
                        if line.strip():
                            command_candidate = line.strip()
                            break

                if not command_candidate:
                    command_candidate = body_text.strip()

                reply_message = parse_and_execute_command(command_candidate, sender)

                reply_subject = f"Re: {subject}" if subject else "FinTrack Local Response"
                send_email(sender, reply_subject, f"<pre style='font-family: monospace; font-size: 14px;'>{reply_message}</pre>", text_content=reply_message)

                conn = get_db()
                conn.execute("""
                    INSERT INTO email_logs (sender, subject, command, status, response_msg, created_at)
                    VALUES (?, ?, ?, 'SUCCESS', ?, ?)
                """, (sender, subject, command_candidate[:250], reply_message[:500], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                conn.close()

                mail.store(e_id, '+FLAGS', '\\Seen')
                processed_count += 1

            except Exception as item_err:
                conn = get_db()
                conn.execute("""
                    INSERT INTO email_logs (sender, subject, command, status, response_msg, created_at)
                    VALUES (?, ?, 'ERROR', 'FAILED', ?, ?)
                """, (sender if 'sender' in locals() else 'unknown', subject if 'subject' in locals() else '', str(item_err), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                conn.close()

        mail.logout()
        return processed_count, f"Processed {processed_count} email command(s)."

    except Exception as e:
        return 0, f"IMAP Error: {str(e)}"
