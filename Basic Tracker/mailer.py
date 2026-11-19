"""
Email notification and monthly report dispatching for FinTrack Local.
Enhanced with smart Gmail diagnostics and auto-fallback.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
import io
import csv
from database import get_db, get_setting, add_notification


def sanitize_app_password(pwd):
    """Strips spaces and quotes from Google App Passwords."""
    if not pwd:
        return ""
    return pwd.replace(" ", "").replace("-", "").strip()


def get_smtp_client(host=None, port=None, user=None, password=None, use_tls=None):
    if host is None:
        host = get_setting("smtp_host", "smtp.gmail.com")
        port = int(get_setting("smtp_port", "587"))
        user = get_setting("smtp_user", "").strip()
        password = sanitize_app_password(get_setting("smtp_pass", ""))
        use_tls = get_setting("smtp_use_tls", "1") == "1"

    if not host or not user or not password:
        raise ValueError("SMTP host, user, and password must be configured in Settings.")

    context = ssl.create_default_context()
    
    # Try configured port
    try:
        if int(port) == 465:
            server = smtplib.SMTP_SSL(host, int(port), context=context, timeout=12)
        else:
            server = smtplib.SMTP(host, int(port), timeout=12)
            if use_tls:
                server.starttls(context=context)
        server.login(user, password)
        return server, user
    except smtplib.SMTPAuthenticationError as auth_err:
        raise ValueError(
            f"Gmail Authentication Failed: {auth_err.smtp_error.decode('utf-8', errors='ignore') if hasattr(auth_err, 'smtp_error') else str(auth_err)}\n"
            "⚠️ IMPORTANT: Google requires a 16-character 'Google App Password', NOT your regular Gmail account password. "
            "Please go to your Google Account > Security > 2-Step Verification > App Passwords, generate a 16-character password, and paste it here."
        )
    except Exception as e:
        # If port 587 failed with timeout/connection error, attempt fallback to port 465 SSL
        if int(port) == 587:
            try:
                server = smtplib.SMTP_SSL(host, 465, context=context, timeout=12)
                server.login(user, password)
                return server, user
            except Exception:
                pass
        raise e


def send_email(to_email, subject, html_content, text_content="", attachments=None):
    """
    Sends an email using configured SMTP settings.
    """
    try:
        server, from_email = get_smtp_client()
        msg = MIMEMultipart("mixed")
        msg["From"] = f"FinTrack Local <{from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        alt_part = MIMEMultipart("alternative")
        if text_content:
            alt_part.attach(MIMEText(text_content, "plain", "utf-8"))
        if html_content:
            alt_part.attach(MIMEText(html_content, "html", "utf-8"))
        msg.attach(alt_part)

        if attachments:
            for att in attachments:
                data = att["data"]
                if isinstance(data, str):
                    data = data.encode("utf-8")
                part = MIMEApplication(data, Name=att["filename"])
                part["Content-Disposition"] = f'attachment; filename="{att["filename"]}"'
                msg.attach(part)

        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        return True, "Email sent successfully"
    except Exception as e:
        return False, str(e)


def test_smtp_connection(host, port, user, password, use_tls, to_email):
    """Verifies SMTP settings and sends a test message with friendly diagnostics."""
    user = user.strip()
    password = sanitize_app_password(password)

    if not user or not password:
        return {"success": False, "message": "Please enter your Gmail address and 16-character Google App Password."}

    context = ssl.create_default_context()
    connected_port = int(port)
    server = None

    try:
        if int(port) == 465:
            server = smtplib.SMTP_SSL(host, int(port), context=context, timeout=12)
        else:
            server = smtplib.SMTP(host, int(port), timeout=12)
            if str(use_tls) in ("1", "true", "True"):
                server.starttls(context=context)

        server.login(user, password)
    except smtplib.SMTPAuthenticationError as auth_err:
        msg = str(auth_err)
        return {
            "success": False,
            "message": (
                "❌ Gmail Login Failed (Incorrect Password or App Password required)!\n\n"
                "Google does NOT allow third-party apps to log in using standard Gmail passwords.\n"
                "👉 Solution: You must generate a 16-letter 'Google App Password':\n"
                "1. Go to your Google Account (myaccount.google.com)\n"
                "2. Click 'Security' on the left menu.\n"
                "3. Under 'How you sign in to Google', ensure 2-Step Verification is ON.\n"
                "4. Search for 'App Passwords' and create one named 'FinTrack'.\n"
                "5. Paste the 16-character code into the password field."
            )
        }
    except Exception as e:
        # Try fallback to SSL 465 if 587 timed out
        if int(port) == 587:
            try:
                server = smtplib.SMTP_SSL(host, 465, context=context, timeout=12)
                server.login(user, password)
                connected_port = 465
            except Exception as e2:
                return {
                    "success": False,
                    "message": f"❌ Connection Error: Could not reach {host} on port 587 or 465. Details: {str(e)}"
                }
        else:
            return {"success": False, "message": f"❌ Connection Error: {str(e)}"}

    try:
        msg = MIMEMultipart()
        msg["From"] = f"FinTrack Local <{user}>"
        msg["To"] = to_email
        msg["Subject"] = "✅ FinTrack Local - Gmail Connection Verified!"
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 580px; margin: auto; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
            <div style="text-align: center; margin-bottom: 20px;">
                <span style="font-size: 42px;">🎉</span>
                <h2 style="color: #10b981; margin: 10px 0 0 0;">Gmail Connected Successfully!</h2>
                <p style="color: #64748b; font-size: 14px; margin-top: 4px;">FinTrack Local is now linked to your Gmail account.</p>
            </div>
            <div style="background: #f8fafc; border-left: 4px solid #10b981; padding: 14px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; color: #334155;">
                Connected to <strong>{host}</strong> via port <strong>{connected_port}</strong> as <strong>{user}</strong>.
            </div>
            <p style="color: #475569; font-size: 14px; line-height: 1.6;">
                You will now automatically receive:
            </p>
            <ul style="color: #334155; line-height: 1.8; font-size: 14px;">
                <li>🚨 <strong>Overspending Alerts</strong> when your monthly expenses exceed your Upper Limit (₹).</li>
                <li>⚠️ <strong>Low Balance Warnings</strong> when your balance drops below your Lower Limit (₹).</li>
                <li>📊 <strong>Monthly Records & Statements</strong> on the 1st of every month with CSV attachments.</li>
            </ul>
            <p style="font-size: 11px; color: #94a3b8; margin-top: 25px; border-top: 1px solid #f1f5f9; padding-top: 12px; text-align: center;">
                FinTrack Local • Tested at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </p>
        </div>
        """
        msg.attach(MIMEText(html, "html", "utf-8"))
        server.sendmail(user, [to_email], msg.as_string())
        server.quit()
        return {"success": True, "message": f"✅ Test email successfully sent to {to_email}! Port {connected_port} verified."}
    except Exception as e:
        return {"success": False, "message": f"Connected to server, but failed to send email: {str(e)}"}


def check_limits_and_alert(current_month=None):
    """
    Evaluates current month spending and overall balance against Upper & Lower limits.
    Triggers In-App Notifications and sends Email Warnings if enabled.
    """
    if not current_month:
        current_month = datetime.now().strftime("%Y-%m")

    currency = get_setting("currency_symbol", "₹")
    try:
        upper_limit = float(get_setting("upper_limit", "25000.00"))
    except ValueError:
        upper_limit = 25000.0

    try:
        lower_limit = float(get_setting("lower_limit", "5000.00"))
    except ValueError:
        lower_limit = 5000.0

    try:
        warn_pct = float(get_setting("upper_limit_warn_pct", "80"))
    except ValueError:
        warn_pct = 80.0

    email_alerts_enabled = get_setting("email_alerts_enabled", "0") == "1"
    alert_email = get_setting("alert_email", "") or get_setting("smtp_user", "")

    conn = get_db()
    # 1. Monthly expenses
    row_exp = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='expense' AND date LIKE ?",
        (f"{current_month}%",)
    ).fetchone()
    monthly_expenses = float(row_exp["total"])

    # 2. Total all-time balance
    row_inc = conn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='income'").fetchone()
    row_all_exp = conn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='expense'").fetchone()
    total_balance = float(row_inc["total"]) - float(row_all_exp["total"])

    conn.close()

    alerts_triggered = []

    # Check UPPER LIMIT
    if upper_limit > 0:
        used_pct = (monthly_expenses / upper_limit) * 100.0

        if monthly_expenses >= upper_limit:
            title = f"🚨 OVERSPENDING ALERT: Upper Limit Exceeded!"
            msg = (f"You have spent {currency}{monthly_expenses:,.2f} this month ({current_month}), "
                   f"which exceeds your monthly upper limit of {currency}{upper_limit:,.2f} by {currency}{(monthly_expenses - upper_limit):,.2f} ({used_pct:.1f}%).")
            
            notif_id = add_notification("danger", title, msg)
            alerts_triggered.append({"type": "danger", "title": title, "message": msg})

            if email_alerts_enabled and alert_email:
                subject = f"🚨 [FinTrack Alert] Upper Spending Limit Exceeded! ({currency}{monthly_expenses:,.2f} / {currency}{upper_limit:,.2f})"
                html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 25px; border: 1px solid #fecaca; border-radius: 12px; background: #fff5f5;">
                    <div style="background: #ef4444; color: white; padding: 12px 20px; border-radius: 8px; font-size: 18px; font-weight: bold;">
                        🚨 Overspending Alert: Monthly Upper Limit Exceeded!
                    </div>
                    <p style="color: #374151; font-size: 15px; margin-top: 18px; line-height: 1.6;">
                        You have exceeded your monthly budget ceiling for <strong>{current_month}</strong>.
                    </p>
                    <table style="width: 100%; border-collapse: collapse; margin: 20px 0; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                        <tr style="background: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                            <td style="padding: 12px 16px; font-weight: bold; color: #64748b;">Monthly Spending Limit:</td>
                            <td style="padding: 12px 16px; text-align: right; font-weight: bold; color: #0f172a;">{currency}{upper_limit:,.2f}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #e2e8f0;">
                            <td style="padding: 12px 16px; font-weight: bold; color: #ef4444;">Current Spent ({current_month}):</td>
                            <td style="padding: 12px 16px; text-align: right; font-weight: bold; color: #ef4444; font-size: 17px;">{currency}{monthly_expenses:,.2f}</td>
                        </tr>
                        <tr style="background: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                            <td style="padding: 12px 16px; font-weight: bold; color: #64748b;">Budget Exceeded By:</td>
                            <td style="padding: 12px 16px; text-align: right; font-weight: bold; color: #dc2626;">+{currency}{(monthly_expenses - upper_limit):,.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px 16px; font-weight: bold; color: #64748b;">Budget Utilization:</td>
                            <td style="padding: 12px 16px; text-align: right; font-weight: bold; color: #ef4444;">{used_pct:.1f}%</td>
                        </tr>
                    </table>
                    <p style="font-size: 11px; color: #9ca3af; margin-top: 25px; border-top: 1px solid #fee2e2; padding-top: 12px;">
                        FinTrack Local • Monitored on your device at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                    </p>
                </div>
                """
                success, _ = send_email(alert_email, subject, html)
                if success:
                    conn = get_db()
                    conn.execute("UPDATE notifications SET email_sent = 1 WHERE id = ?", (notif_id,))
                    conn.commit()
                    conn.close()

        elif used_pct >= warn_pct:
            title = f"⚠️ Budget Warning: {used_pct:.1f}% of Upper Limit Reached"
            msg = (f"You have spent {currency}{monthly_expenses:,.2f} of your {currency}{upper_limit:,.2f} "
                   f"monthly limit ({used_pct:.1f}% used). Remaining buffer: {currency}{(upper_limit - monthly_expenses):,.2f}.")
            
            notif_id = add_notification("warning", title, msg)
            alerts_triggered.append({"type": "warning", "title": title, "message": msg})

            if email_alerts_enabled and alert_email:
                subject = f"⚠️ [FinTrack Warning] {used_pct:.0f}% of Monthly Spending Limit Reached"
                html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 25px; border: 1px solid #fef08a; border-radius: 12px; background: #fefce8;">
                    <div style="background: #eab308; color: white; padding: 12px 20px; border-radius: 8px; font-size: 18px; font-weight: bold;">
                        ⚠️ Spending Warning: Approaching Monthly Upper Limit!
                    </div>
                    <p style="color: #374151; font-size: 15px; margin-top: 18px; line-height: 1.6;">
                        You have reached <strong>{used_pct:.1f}%</strong> of your monthly expense limit for <strong>{current_month}</strong>.
                    </p>
                    <table style="width: 100%; border-collapse: collapse; margin: 20px 0; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                        <tr style="background: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                            <td style="padding: 12px 16px; font-weight: bold; color: #64748b;">Monthly Limit:</td>
                            <td style="padding: 12px 16px; text-align: right; font-weight: bold; color: #0f172a;">{currency}{upper_limit:,.2f}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #e2e8f0;">
                            <td style="padding: 12px 16px; font-weight: bold; color: #ca8a04;">Current Spent:</td>
                            <td style="padding: 12px 16px; text-align: right; font-weight: bold; color: #ca8a04;">{currency}{monthly_expenses:,.2f}</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 12px 16px; font-weight: bold; color: #16a34a;">Remaining Safe Buffer:</td>
                            <td style="padding: 12px 16px; text-align: right; font-weight: bold; color: #16a34a;">{currency}{(upper_limit - monthly_expenses):,.2f}</td>
                        </tr>
                    </table>
                </div>
                """
                send_email(alert_email, subject, html)

    # Check LOWER LIMIT (Minimum Safe Balance)
    if lower_limit > 0 and total_balance <= lower_limit:
        title = f"⚠️ Low Balance Alert: Balance is {currency}{total_balance:,.2f}"
        msg = f"Your total account balance ({currency}{total_balance:,.2f}) has fallen below your safe lower limit of {currency}{lower_limit:,.2f}!"
        
        notif_id = add_notification("warning", title, msg)
        alerts_triggered.append({"type": "warning", "title": title, "message": msg})

        if email_alerts_enabled and alert_email:
            subject = f"⚠️ [FinTrack Alert] Total Balance Below Safe Lower Limit ({currency}{total_balance:,.2f})"
            html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 25px; border: 1px solid #fed7aa; border-radius: 12px; background: #fffaf5;">
                <div style="background: #f97316; color: white; padding: 12px 20px; border-radius: 8px; font-size: 18px; font-weight: bold;">
                    ⚠️ Low Balance Alert: Below Lower Limit!
                </div>
                <p style="color: #374151; font-size: 15px; margin-top: 18px; line-height: 1.6;">
                    Your overall money balance has dropped below your configured safety threshold.
                </p>
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <tr style="background: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                        <td style="padding: 12px 16px; font-weight: bold; color: #64748b;">Current Balance:</td>
                        <td style="padding: 12px 16px; text-align: right; font-weight: bold; color: #ea580c; font-size: 17px;">{currency}{total_balance:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 16px; font-weight: bold; color: #64748b;">Minimum Safe Lower Limit:</td>
                        <td style="padding: 12px 16px; text-align: right; font-weight: bold; color: #0f172a;">{currency}{lower_limit:,.2f}</td>
                    </tr>
                </table>
            </div>
            """
            send_email(alert_email, subject, html)

    return alerts_triggered


def generate_and_send_monthly_statement(month_str=None, target_email=None):
    """
    Generates a full itemized statement and category/subcategory breakdown for the specified month
    and emails it to the user with a CSV attachment.
    """
    if not month_str:
        month_str = datetime.now().strftime("%Y-%m")

    if not target_email:
        target_email = get_setting("alert_email", "") or get_setting("smtp_user", "")

    if not target_email:
        return False, "No recipient email configured in settings."

    currency = get_setting("currency_symbol", "₹")
    conn = get_db()

    # Month financial totals
    row_income = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='income' AND date LIKE ?",
        (f"{month_str}%",)
    ).fetchone()
    month_income = float(row_income["total"])

    row_expense = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='expense' AND date LIKE ?",
        (f"{month_str}%",)
    ).fetchone()
    month_expense = float(row_expense["total"])

    net_savings = month_income - month_expense

    # All-time balance
    tot_inc = conn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='income'").fetchone()["total"]
    tot_exp = conn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='expense'").fetchone()["total"]
    all_time_balance = float(tot_inc) - float(tot_exp)

    # Subcategory breakdown
    subcat_rows = conn.execute("""
        SELECT 
            c.name as category_name,
            COALESCE(s.name, 'Uncategorized') as subcategory_name,
            c.color as category_color,
            SUM(t.amount) as total_amount,
            COUNT(t.id) as tx_count
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        LEFT JOIN subcategories s ON t.subcategory_id = s.id
        WHERE t.type = 'expense' AND t.date LIKE ?
        GROUP BY c.id, s.id
        ORDER BY total_amount DESC
    """, (f"{month_str}%",)).fetchall()

    # Category totals
    cat_rows = conn.execute("""
        SELECT 
            c.name as category_name,
            c.icon as category_icon,
            c.color as category_color,
            SUM(t.amount) as total_amount,
            COUNT(t.id) as tx_count
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.type = 'expense' AND t.date LIKE ?
        GROUP BY c.id
        ORDER BY total_amount DESC
    """, (f"{month_str}%",)).fetchall()

    # All transactions for the month
    all_txs = conn.execute("""
        SELECT 
            t.date,
            t.time,
            t.type,
            t.amount,
            c.name as category_name,
            COALESCE(s.name, '—') as subcategory_name,
            COALESCE(t.description, '') as description,
            COALESCE(t.payment_method, '') as payment_method
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        LEFT JOIN subcategories s ON t.subcategory_id = s.id
        WHERE t.date LIKE ?
        ORDER BY t.date DESC, t.time DESC
    """, (f"{month_str}%",)).fetchall()

    conn.close()

    # Build CSV Attachment
    csv_output = io.StringIO()
    writer = csv.writer(csv_output)
    writer.writerow(["Date", "Time", "Type", "Category", "Subcategory", "Amount (INR)", "Payment Method", "Description"])
    for tx in all_txs:
        writer.writerow([
            tx["date"],
            tx["time"],
            tx["type"].upper(),
            tx["category_name"],
            tx["subcategory_name"],
            f"{tx['amount']:.2f}",
            tx["payment_method"],
            tx["description"]
        ])
    csv_bytes = csv_output.getvalue().encode("utf-8")

    # Build HTML Report
    cat_html = ""
    for c in cat_rows:
        pct = (c["total_amount"] / month_expense * 100.0) if month_expense > 0 else 0
        cat_html += f"""
        <tr style="border-bottom: 1px solid #f1f5f9;">
            <td style="padding: 10px 14px; font-weight: 500;">
                <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: {c['category_color']}; margin-right: 8px;"></span>
                {c['category_icon']} {c['category_name']}
            </td>
            <td style="padding: 10px 14px; text-align: center; color: #64748b;">{c['tx_count']}</td>
            <td style="padding: 10px 14px; text-align: right; font-weight: 600; color: #0f172a;">{currency}{c['total_amount']:,.2f}</td>
            <td style="padding: 10px 14px; text-align: right; color: #64748b;">{pct:.1f}%</td>
        </tr>
        """

    subcat_html = ""
    for s in subcat_rows:
        sub_pct = (s["total_amount"] / month_expense * 100.0) if month_expense > 0 else 0
        subcat_html += f"""
        <tr style="border-bottom: 1px solid #f8fafc; font-size: 13px;">
            <td style="padding: 8px 12px; color: #334155;">{s['category_name']}</td>
            <td style="padding: 8px 12px; font-weight: 600; color: #0f172a;">{s['subcategory_name']}</td>
            <td style="padding: 8px 12px; text-align: center; color: #64748b;">{s['tx_count']}</td>
            <td style="padding: 8px 12px; text-align: right; font-weight: 600; color: #ef4444;">{currency}{s['total_amount']:,.2f}</td>
            <td style="padding: 8px 12px; text-align: right; color: #64748b;">{sub_pct:.1f}%</td>
        </tr>
        """

    subject = f"📊 FinTrack Monthly Statement - {month_str} Financial Record"
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 680px; margin: auto; padding: 25px; border: 1px solid #e2e8f0; border-radius: 14px; background: #ffffff; color: #1e293b;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #6366f1; padding-bottom: 15px; margin-bottom: 20px;">
            <div>
                <h1 style="color: #4f46e5; margin: 0; font-size: 24px;">📊 FinTrack Local</h1>
                <p style="color: #64748b; margin: 4px 0 0 0; font-size: 14px;">Monthly Financial Statement ({month_str})</p>
            </div>
        </div>

        <table style="width: 100%; border-collapse: separate; border-spacing: 10px; margin-bottom: 20px;">
            <tr>
                <td style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px; padding: 15px; text-align: center; width: 33%;">
                    <div style="font-size: 12px; color: #166534; font-weight: 600; text-transform: uppercase;">Total Income</div>
                    <div style="font-size: 20px; font-weight: 800; color: #15803d; margin-top: 5px;">+{currency}{month_income:,.2f}</div>
                </td>
                <td style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 10px; padding: 15px; text-align: center; width: 33%;">
                    <div style="font-size: 12px; color: #991b1b; font-weight: 600; text-transform: uppercase;">Total Expenses</div>
                    <div style="font-size: 20px; font-weight: 800; color: #b91c1c; margin-top: 5px;">-{currency}{month_expense:,.2f}</div>
                </td>
                <td style="background: {'#f0fdf4' if net_savings >= 0 else '#fff1f2'}; border: 1px solid {'#bbf7d0' if net_savings >= 0 else '#fecdd3'}; border-radius: 10px; padding: 15px; text-align: center; width: 33%;">
                    <div style="font-size: 12px; color: {'#166534' if net_savings >= 0 else '#9f1239'}; font-weight: 600; text-transform: uppercase;">Net Savings</div>
                    <div style="font-size: 20px; font-weight: 800; color: {'#15803d' if net_savings >= 0 else '#be123c'}; margin-top: 5px;">
                        {'+' if net_savings >= 0 else ''}{currency}{net_savings:,.2f}
                    </div>
                </td>
            </tr>
        </table>

        <h3 style="color: #0f172a; margin-top: 25px; margin-bottom: 12px; font-size: 16px;">📁 Spending by Category</h3>
        <table style="width: 100%; border-collapse: collapse; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-bottom: 25px;">
            <thead>
                <tr style="background: #f8fafc; border-bottom: 1px solid #e2e8f0; font-size: 12px; color: #64748b; text-transform: uppercase;">
                    <th style="padding: 10px 14px; text-align: left;">Category</th>
                    <th style="padding: 10px 14px; text-align: center;">Count</th>
                    <th style="padding: 10px 14px; text-align: right;">Total Spent</th>
                    <th style="padding: 10px 14px; text-align: right;">Share</th>
                </tr>
            </thead>
            <tbody>
                {cat_html or '<tr><td colspan="4" style="text-align:center; padding: 15px; color:#94a3b8;">No expenses recorded for this month.</td></tr>'}
            </tbody>
        </table>

        <h3 style="color: #0f172a; margin-top: 25px; margin-bottom: 12px; font-size: 16px;">🏷️ Detailed Subcategory Breakdown</h3>
        <table style="width: 100%; border-collapse: collapse; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-bottom: 25px;">
            <thead>
                <tr style="background: #f8fafc; border-bottom: 1px solid #e2e8f0; font-size: 12px; color: #64748b; text-transform: uppercase;">
                    <th style="padding: 8px 12px; text-align: left;">Category</th>
                    <th style="padding: 8px 12px; text-align: left;">Subcategory</th>
                    <th style="padding: 8px 12px; text-align: center;">Count</th>
                    <th style="padding: 8px 12px; text-align: right;">Spent</th>
                    <th style="padding: 8px 12px; text-align: right;">Share</th>
                </tr>
            </thead>
            <tbody>
                {subcat_html or '<tr><td colspan="5" style="text-align:center; padding: 15px; color:#94a3b8;">No subcategories used.</td></tr>'}
            </tbody>
        </table>

        <div style="background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; padding: 14px; text-align: center; color: #475569; font-size: 13px; margin-top: 20px;">
            📎 <strong>Full record attached:</strong> <code>FinTrack_Statement_{month_str}.csv</code> with all {len(all_txs)} transactions is attached.
        </div>
    </div>
    """

    attachments = [{
        "filename": f"FinTrack_Statement_{month_str}.csv",
        "data": csv_bytes,
        "type": "csv"
    }]

    success, err_msg = send_email(target_email, subject, html_content, attachments=attachments)
    if success:
        add_notification("info", f"Monthly statement for {month_str} sent to {target_email}", f"Report delivered with {len(all_txs)} transactions.", email_sent=1)
        return True, f"Monthly report for {month_str} sent successfully to {target_email}!"
    else:
        add_notification("danger", f"Failed to send monthly statement for {month_str}", f"Error: {err_msg}")
        return False, f"Failed to send email: {err_msg}"
