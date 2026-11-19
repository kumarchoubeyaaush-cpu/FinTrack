"""
FinTrack Local - Web Application Server
Lightweight, zero-dependency local web server built with Python standard library.
Features: User Authentication with Gmail, Currency Converter (INR ₹ base),
Budget Limit Warnings, Hierarchical Subcategories, and IMAP/SMTP Email Control.
"""

import sys
import os
import json
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
import mimetypes

from database import (
    init_db, get_db, get_setting, get_all_settings,
    set_setting, set_many_settings, add_notification,
    register_user, login_user, get_user_from_token, logout_user
)
from mailer import (
    check_limits_and_alert, generate_and_send_monthly_statement,
    test_smtp_connection
)
from email_controller import test_imap_connection
from scheduler import start_scheduler, stop_scheduler, get_background_status

PORT = 5000
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class FinTrackHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        try:
            msg = format % args
            sys.stdout.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        except Exception:
            pass

    def send_json(self, data, status_code=200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                raw = self.rfile.read(content_length).decode("utf-8")
                return json.loads(raw)
        except Exception:
            pass
        return {}

    def get_auth_token(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        # Fallback to query parameter or cookie if needed
        return None

    def get_current_user(self):
        token = self.get_auth_token()
        return get_user_from_token(token)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    # ==========================
    # GET REQUEST ROUTER
    # ==========================
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Static assets routing
        if path == "/" or path == "/index.html":
            self.serve_static_file(os.path.join(STATIC_DIR, "index.html"), "text/html")
            return
        elif path.startswith("/static/"):
            rel_path = path[8:]
            target_path = os.path.join(STATIC_DIR, rel_path)
            mime, _ = mimetypes.guess_type(target_path)
            self.serve_static_file(target_path, mime or "application/octet-stream")
            return

        # Auth Routes
        if path == "/api/auth/me":
            user = self.get_current_user()
            if user:
                self.send_json({"authenticated": True, "user": user})
            else:
                self.send_json({"authenticated": False, "user": None}, 401)
            return

        # API Routes
        if path == "/api/summary":
            self.api_get_summary(query)
        elif path == "/api/transactions":
            self.api_get_transactions(query)
        elif path == "/api/categories":
            self.api_get_categories()
        elif path == "/api/currencies":
            self.api_get_currencies()
        elif path == "/api/analytics":
            self.api_get_analytics(query)
        elif path == "/api/notifications":
            self.api_get_notifications()
        elif path == "/api/settings":
            self.api_get_settings()
        elif path == "/api/email/logs":
            self.api_get_email_logs()
        elif path == "/api/scheduler/status":
            self.send_json(get_background_status())
        elif path == "/api/export/csv":
            self.api_export_csv(query)
        else:
            self.send_json({"error": "Endpoint not found"}, 404)

    # ==========================
    # POST REQUEST ROUTER
    # ==========================
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        data = self.read_json_body()

        # Auth Routes
        if path == "/api/auth/register":
            self.api_register(data)
        elif path == "/api/auth/login":
            self.api_login(data)
        elif path == "/api/auth/logout":
            token = self.get_auth_token()
            logout_user(token)
            self.send_json({"success": True})
        # Currency Converter
        elif path == "/api/currencies/convert":
            self.api_convert_currency(data)
        elif path == "/api/currencies/update-rate":
            self.api_update_exchange_rate(data)
        # Transactions & Categories
        elif path == "/api/transactions":
            self.api_create_transaction(data)
        elif path == "/api/categories":
            self.api_create_category(data)
        elif path == "/api/subcategories":
            self.api_create_subcategory(data)
        elif path == "/api/notifications/mark-read":
            self.api_mark_notifications_read(data)
        elif path == "/api/notifications/clear":
            self.api_clear_notifications()
        elif path == "/api/settings":
            self.api_save_settings(data)
        elif path == "/api/email/test-smtp":
            self.api_test_smtp(data)
        elif path == "/api/email/test-imap":
            self.api_test_imap(data)
        elif path == "/api/email/send-monthly-report":
            self.api_send_monthly_report(data)
        else:
            self.send_json({"error": "Endpoint not found"}, 404)

    # ==========================
    # PUT REQUEST ROUTER
    # ==========================
    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        data = self.read_json_body()

        if path.startswith("/api/transactions/"):
            try:
                tx_id = int(path.split("/")[-1])
                self.api_update_transaction(tx_id, data)
            except ValueError:
                self.send_json({"error": "Invalid transaction ID"}, 400)
        else:
            self.send_json({"error": "Endpoint not found"}, 404)

    # ==========================
    # DELETE REQUEST ROUTER
    # ==========================
    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/transactions/"):
            try:
                tx_id = int(path.split("/")[-1])
                self.api_delete_transaction(tx_id)
            except ValueError:
                self.send_json({"error": "Invalid transaction ID"}, 400)
        elif path.startswith("/api/categories/"):
            try:
                cat_id = int(path.split("/")[-1])
                self.api_delete_category(cat_id)
            except ValueError:
                self.send_json({"error": "Invalid category ID"}, 400)
        elif path.startswith("/api/subcategories/"):
            try:
                sub_id = int(path.split("/")[-1])
                self.api_delete_subcategory(sub_id)
            except ValueError:
                self.send_json({"error": "Invalid subcategory ID"}, 400)
        else:
            self.send_json({"error": "Endpoint not found"}, 404)

    # ==========================
    # STATIC FILE HANDLER
    # ==========================
    def serve_static_file(self, full_path, mime_type):
        if not os.path.isfile(full_path):
            self.send_json({"error": "File not found"}, 404)
            return
        try:
            with open(full_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    # ==========================
    # AUTHENTICATION HANDLERS
    # ==========================
    def api_register(self, data):
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()
        name = data.get("name", "").strip()

        if not email or "@" not in email:
            self.send_json({"error": "A valid Gmail or email address is required"}, 400)
            return
        if not password or len(password) < 4:
            self.send_json({"error": "Password must be at least 4 characters"}, 400)
            return

        res, err = register_user(email, password, name)
        if err:
            self.send_json({"error": err}, 400)
        else:
            self.send_json(res, 201)

    def api_login(self, data):
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()

        if not email or not password:
            self.send_json({"error": "Email and password are required"}, 400)
            return

        res, err = login_user(email, password)
        if err:
            self.send_json({"error": err}, 401)
        else:
            self.send_json(res)

    # ==========================
    # CURRENCY CONVERTER HANDLERS
    # ==========================
    def api_get_currencies(self):
        conn = get_db()
        rows = conn.execute("SELECT code, name, symbol, rate_to_inr, updated_at FROM exchange_rates ORDER BY code").fetchall()
        conn.close()
        self.send_json([dict(r) for r in rows])

    def api_convert_currency(self, data):
        try:
            amount = float(data.get("amount", 0))
            from_curr = data.get("from_currency", "INR").upper()
            to_curr = data.get("to_currency", "USD").upper()
        except ValueError:
            self.send_json({"error": "Invalid amount"}, 400)
            return

        conn = get_db()
        rates = {r["code"]: r["rate_to_inr"] for r in conn.execute("SELECT code, rate_to_inr FROM exchange_rates").fetchall()}
        symbols = {r["code"]: r["symbol"] for r in conn.execute("SELECT code, symbol FROM exchange_rates").fetchall()}
        conn.close()

        if from_curr not in rates or to_curr not in rates:
            self.send_json({"error": "Unsupported currency code"}, 400)
            return

        # Convert: Amount -> INR -> Target
        amount_in_inr = amount * rates[from_curr]
        converted_amount = amount_in_inr / rates[to_curr]
        effective_rate = rates[from_curr] / rates[to_curr]

        self.send_json({
            "amount": amount,
            "from_currency": from_curr,
            "from_symbol": symbols.get(from_curr, ""),
            "to_currency": to_curr,
            "to_symbol": symbols.get(to_curr, ""),
            "amount_inr": round(amount_in_inr, 2),
            "result": round(converted_amount, 2),
            "rate": round(effective_rate, 4),
            "formula": f"1 {from_curr} = {round(effective_rate, 4)} {to_curr}"
        })

    def api_update_exchange_rate(self, data):
        code = data.get("code", "").upper().strip()
        try:
            rate = float(data.get("rate_to_inr", 0))
            if rate <= 0:
                self.send_json({"error": "Rate must be positive"}, 400)
                return
        except ValueError:
            self.send_json({"error": "Invalid rate"}, 400)
            return

        conn = get_db()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE exchange_rates SET rate_to_inr = ?, updated_at = ? WHERE code = ?", (rate, now_str, code))
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": f"Updated exchange rate for {code} to ₹{rate:.2f}"})

    # ==========================
    # SUMMARY & DASHBOARD
    # ==========================
    def api_get_summary(self, query):
        month = query.get("month", [datetime.now().strftime("%Y-%m")])[0]
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

        conn = get_db()
        m_inc = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='income' AND date LIKE ?",
            (f"{month}%",)
        ).fetchone()["total"]

        m_exp = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='expense' AND date LIKE ?",
            (f"{month}%",)
        ).fetchone()["total"]

        tot_inc = conn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='income'").fetchone()["total"]
        tot_exp = conn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='expense'").fetchone()["total"]
        total_balance = float(tot_inc) - float(tot_exp)

        tx_count = conn.execute("SELECT COUNT(*) as cnt FROM transactions WHERE date LIKE ?", (f"{month}%",)).fetchone()["cnt"]

        recent_txs = conn.execute("""
            SELECT 
                t.id, t.type, t.amount, t.date, t.time, t.description, t.payment_method, t.source,
                t.original_currency, t.original_amount,
                c.id as category_id, c.name as category_name, c.icon as category_icon, c.color as category_color,
                COALESCE(s.name, '') as subcategory_name
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            LEFT JOIN subcategories s ON t.subcategory_id = s.id
            ORDER BY t.date DESC, t.time DESC, t.id DESC
            LIMIT 7
        """).fetchall()

        unread_notifs = conn.execute("SELECT COUNT(*) as cnt FROM notifications WHERE is_read = 0").fetchone()["cnt"]
        conn.close()

        month_income = float(m_inc)
        month_expense = float(m_exp)
        net_savings = month_income - month_expense

        used_pct = (month_expense / upper_limit * 100.0) if upper_limit > 0 else 0.0
        remaining_budget = upper_limit - month_expense

        is_over_limit = upper_limit > 0 and month_expense >= upper_limit
        is_near_limit = upper_limit > 0 and not is_over_limit and used_pct >= warn_pct
        is_below_lower_limit = lower_limit > 0 and total_balance <= lower_limit

        res = {
            "month": month,
            "currency_symbol": currency,
            "currency_code": "INR",
            "total_balance": total_balance,
            "month_income": month_income,
            "month_expense": month_expense,
            "net_savings": net_savings,
            "upper_limit": upper_limit,
            "lower_limit": lower_limit,
            "upper_limit_warn_pct": warn_pct,
            "upper_limit_used_pct": round(used_pct, 1),
            "remaining_budget": remaining_budget,
            "is_over_limit": is_over_limit,
            "is_near_limit": is_near_limit,
            "is_below_lower_limit": is_below_lower_limit,
            "tx_count": tx_count,
            "unread_notifications": unread_notifs,
            "recent_transactions": [dict(r) for r in recent_txs]
        }
        self.send_json(res)

    def api_get_transactions(self, query):
        month = query.get("month", [""])[0]
        tx_type = query.get("type", [""])[0]
        category_id = query.get("category_id", [""])[0]
        subcategory_id = query.get("subcategory_id", [""])[0]
        search = query.get("search", [""])[0].strip()
        limit = int(query.get("limit", [50])[0])
        offset = int(query.get("offset", [0])[0])

        clauses = []
        params = []

        if month:
            clauses.append("t.date LIKE ?")
            params.append(f"{month}%")
        if tx_type:
            clauses.append("t.type = ?")
            params.append(tx_type)
        if category_id:
            clauses.append("t.category_id = ?")
            params.append(int(category_id))
        if subcategory_id:
            clauses.append("t.subcategory_id = ?")
            params.append(int(subcategory_id))
        if search:
            clauses.append("(t.description LIKE ? OR c.name LIKE ? OR s.name LIKE ?)")
            wild = f"%{search}%"
            params.extend([wild, wild, wild])

        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        conn = get_db()
        count_row = conn.execute(f"""
            SELECT COUNT(*) as total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            LEFT JOIN subcategories s ON t.subcategory_id = s.id
            {where_sql}
        """, params).fetchone()
        total_count = count_row["total"]

        tx_rows = conn.execute(f"""
            SELECT 
                t.id, t.type, t.amount, t.date, t.time, t.description, t.payment_method, t.source,
                t.original_currency, t.original_amount,
                c.id as category_id, c.name as category_name, c.icon as category_icon, c.color as category_color,
                COALESCE(s.name, '') as subcategory_name, s.id as subcategory_id
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            LEFT JOIN subcategories s ON t.subcategory_id = s.id
            {where_sql}
            ORDER BY t.date DESC, t.time DESC, t.id DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

        conn.close()

        self.send_json({
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "transactions": [dict(r) for r in tx_rows]
        })

    def api_create_transaction(self, data):
        tx_type = data.get("type", "expense")
        try:
            input_amount = float(data.get("amount", 0))
            if input_amount <= 0:
                self.send_json({"error": "Amount must be greater than zero"}, 400)
                return
        except ValueError:
            self.send_json({"error": "Invalid amount"}, 400)
            return

        # Currency Conversion Support: If entered in another currency, convert to INR (₹)
        curr_code = data.get("currency", "INR").upper().strip()
        conn = get_db()
        rate_row = conn.execute("SELECT rate_to_inr FROM exchange_rates WHERE code = ?", (curr_code,)).fetchone()
        rate = float(rate_row["rate_to_inr"]) if rate_row else 1.0
        conn.close()

        amount_inr = round(input_amount * rate, 2)

        category_id = data.get("category_id")
        if not category_id:
            self.send_json({"error": "Category is required"}, 400)
            return

        subcategory_id = data.get("subcategory_id") or None
        date_str = data.get("date") or datetime.now().strftime("%Y-%m-%d")
        time_str = data.get("time") or datetime.now().strftime("%H:%M:%S")
        description = data.get("description", "").strip()
        payment_method = data.get("payment_method", "UPI / Card")
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # If converted from foreign currency, add note
        if curr_code != "INR":
            conv_note = f"[{input_amount} {curr_code} @ ₹{rate:.2f}]"
            description = f"{description} {conv_note}".strip()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transactions (type, amount, category_id, subcategory_id, date, time, description, payment_method, source, original_currency, original_amount, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'web', ?, ?, ?)
        """, (tx_type, amount_inr, category_id, subcategory_id, date_str, time_str, description, payment_method, curr_code, input_amount, created_at))
        conn.commit()
        tx_id = cursor.lastrowid
        conn.close()

        # Check budget limits
        alerts = check_limits_and_alert(date_str[:7])

        self.send_json({
            "success": True,
            "id": tx_id,
            "amount_inr": amount_inr,
            "message": f"Transaction of ₹{amount_inr:,.2f} recorded successfully",
            "alerts": alerts
        }, 201)

    def api_update_transaction(self, tx_id, data):
        conn = get_db()
        existing = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        if not existing:
            conn.close()
            self.send_json({"error": "Transaction not found"}, 404)
            return

        tx_type = data.get("type", existing["type"])
        try:
            amount = float(data.get("amount", existing["amount"]))
            if amount <= 0:
                conn.close()
                self.send_json({"error": "Amount must be positive"}, 400)
                return
        except ValueError:
            conn.close()
            self.send_json({"error": "Invalid amount"}, 400)
            return

        category_id = data.get("category_id", existing["category_id"])
        subcategory_id = data.get("subcategory_id", existing["subcategory_id"]) or None
        date_str = data.get("date", existing["date"])
        time_str = data.get("time", existing["time"])
        description = data.get("description", existing["description"])
        payment_method = data.get("payment_method", existing["payment_method"])

        conn.execute("""
            UPDATE transactions
            SET type = ?, amount = ?, category_id = ?, subcategory_id = ?, date = ?, time = ?, description = ?, payment_method = ?
            WHERE id = ?
        """, (tx_type, amount, category_id, subcategory_id, date_str, time_str, description, payment_method, tx_id))
        conn.commit()
        conn.close()

        alerts = check_limits_and_alert(date_str[:7])
        self.send_json({"success": True, "message": "Transaction updated successfully", "alerts": alerts})

    def api_delete_transaction(self, tx_id):
        conn = get_db()
        conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": "Transaction deleted"})

    def api_get_categories(self):
        conn = get_db()
        cats = conn.execute("SELECT id, name, type, icon, color FROM categories ORDER BY type, name").fetchall()
        result = []
        for c in cats:
            subcats = conn.execute("SELECT id, name, description FROM subcategories WHERE category_id = ? ORDER BY name", (c["id"],)).fetchall()
            cat_dict = dict(c)
            cat_dict["subcategories"] = [dict(s) for s in subcats]
            result.append(cat_dict)
        conn.close()
        self.send_json(result)

    def api_create_category(self, data):
        name = data.get("name", "").strip()
        cat_type = data.get("type", "expense")
        icon = data.get("icon", "🏷️")
        color = data.get("color", "#6366f1")

        if not name:
            self.send_json({"error": "Category name is required"}, 400)
            return

        conn = get_db()
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (name, type, icon, color) VALUES (?, ?, ?, ?)", (name, cat_type, icon, color))
            cat_id = cursor.lastrowid
            
            subs = data.get("subcategories", [])
            for s in subs:
                s_name = s.strip() if isinstance(s, str) else s.get("name", "").strip()
                if s_name:
                    cursor.execute("INSERT OR IGNORE INTO subcategories (category_id, name) VALUES (?, ?)", (cat_id, s_name))
            
            conn.commit()
            conn.close()
            self.send_json({"success": True, "id": cat_id, "message": "Category created successfully"}, 201)
        except Exception as e:
            conn.close()
            self.send_json({"error": f"Category already exists: {str(e)}"}, 400)

    def api_delete_category(self, cat_id):
        conn = get_db()
        cnt = conn.execute("SELECT COUNT(*) as c FROM transactions WHERE category_id = ?", (cat_id,)).fetchone()["c"]
        if cnt > 0:
            conn.close()
            self.send_json({"error": f"Cannot delete category: it is used in {cnt} transaction(s). Reassign them first."}, 400)
            return
        conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": "Category deleted"})

    def api_create_subcategory(self, data):
        cat_id = data.get("category_id")
        name = data.get("name", "").strip()
        desc = data.get("description", "").strip()
        if not cat_id or not name:
            self.send_json({"error": "Category ID and Subcategory name are required"}, 400)
            return

        conn = get_db()
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO subcategories (category_id, name, description) VALUES (?, ?, ?)", (cat_id, name, desc))
            sub_id = cursor.lastrowid
            conn.commit()
            conn.close()
            self.send_json({"success": True, "id": sub_id, "message": "Subcategory created"}, 201)
        except Exception as e:
            conn.close()
            self.send_json({"error": str(e)}, 400)

    def api_delete_subcategory(self, sub_id):
        conn = get_db()
        cnt = conn.execute("SELECT COUNT(*) as c FROM transactions WHERE subcategory_id = ?", (sub_id,)).fetchone()["c"]
        if cnt > 0:
            conn.execute("UPDATE transactions SET subcategory_id = NULL WHERE subcategory_id = ?", (sub_id,))
        conn.execute("DELETE FROM subcategories WHERE id = ?", (sub_id,))
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": "Subcategory deleted"})

    def api_get_analytics(self, query):
        month = query.get("month", [datetime.now().strftime("%Y-%m")])[0]
        conn = get_db()

        m_exp_total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as tot FROM transactions WHERE type='expense' AND date LIKE ?",
            (f"{month}%",)
        ).fetchone()["tot"]
        m_exp_total = float(m_exp_total)

        cat_rows = conn.execute("""
            SELECT 
                c.id, c.name, c.icon, c.color,
                COALESCE(SUM(t.amount), 0) as total_amount,
                COUNT(t.id) as count
            FROM categories c
            LEFT JOIN transactions t ON t.category_id = c.id AND t.type = 'expense' AND t.date LIKE ?
            WHERE c.type = 'expense'
            GROUP BY c.id
            HAVING total_amount > 0
            ORDER BY total_amount DESC
        """, (f"{month}%",)).fetchall()

        cat_breakdown = []
        for r in cat_rows:
            amt = float(r["total_amount"])
            pct = (amt / m_exp_total * 100.0) if m_exp_total > 0 else 0
            cat_breakdown.append({
                "id": r["id"],
                "name": r["name"],
                "icon": r["icon"],
                "color": r["color"],
                "amount": amt,
                "percentage": round(pct, 1),
                "count": r["count"]
            })

        subcat_rows = conn.execute("""
            SELECT 
                c.name as category_name,
                c.color as category_color,
                COALESCE(s.name, 'Uncategorized') as subcategory_name,
                s.id as subcategory_id,
                COALESCE(SUM(t.amount), 0) as total_amount,
                COUNT(t.id) as count
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            LEFT JOIN subcategories s ON t.subcategory_id = s.id
            WHERE t.type = 'expense' AND t.date LIKE ?
            GROUP BY c.id, s.id
            HAVING total_amount > 0
            ORDER BY total_amount DESC
        """, (f"{month}%",)).fetchall()

        subcat_breakdown = []
        for r in subcat_rows:
            amt = float(r["total_amount"])
            pct = (amt / m_exp_total * 100.0) if m_exp_total > 0 else 0
            subcat_breakdown.append({
                "category_name": r["category_name"],
                "category_color": r["category_color"],
                "subcategory_id": r["subcategory_id"],
                "subcategory_name": r["subcategory_name"],
                "amount": amt,
                "percentage": round(pct, 1),
                "count": r["count"]
            })

        daily_rows = conn.execute("""
            SELECT date, COALESCE(SUM(amount), 0) as daily_total
            FROM transactions
            WHERE type = 'expense' AND date LIKE ?
            GROUP BY date
            ORDER BY date ASC
        """, (f"{month}%",)).fetchall()
        daily_trend = [{"date": r["date"], "amount": float(r["daily_total"])} for r in daily_rows]

        history = []
        curr_dt = datetime.strptime(f"{month}-01", "%Y-%m-%d")
        for i in range(5, -1, -1):
            m_dt = (curr_dt.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
            m_str = m_dt.strftime("%Y-%m")
            inc = conn.execute("SELECT COALESCE(SUM(amount), 0) as t FROM transactions WHERE type='income' AND date LIKE ?", (f"{m_str}%",)).fetchone()["t"]
            exp = conn.execute("SELECT COALESCE(SUM(amount), 0) as t FROM transactions WHERE type='expense' AND date LIKE ?", (f"{m_str}%",)).fetchone()["t"]
            history.append({
                "month": m_str,
                "label": m_dt.strftime("%b %Y"),
                "income": float(inc),
                "expense": float(exp)
            })

        conn.close()

        self.send_json({
            "month": month,
            "total_expense": m_exp_total,
            "category_breakdown": cat_breakdown,
            "subcategory_breakdown": subcat_breakdown,
            "daily_trend": daily_trend,
            "history_6_months": history
        })

    def api_get_notifications(self):
        conn = get_db()
        rows = conn.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 50").fetchall()
        conn.close()
        self.send_json([dict(r) for r in rows])

    def api_mark_notifications_read(self, data):
        conn = get_db()
        notif_id = data.get("id")
        if notif_id:
            conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
        else:
            conn.execute("UPDATE notifications SET is_read = 1")
        conn.commit()
        conn.close()
        self.send_json({"success": True})

    def api_clear_notifications(self):
        conn = get_db()
        conn.execute("DELETE FROM notifications")
        conn.commit()
        conn.close()
        self.send_json({"success": True})

    def api_get_settings(self):
        settings = get_all_settings()
        display_settings = dict(settings)
        if display_settings.get("smtp_pass"):
            display_settings["smtp_pass_masked"] = "••••••••••••"
        if display_settings.get("imap_pass"):
            display_settings["imap_pass_masked"] = "••••••••••••"
        self.send_json(display_settings)

    def api_save_settings(self, data):
        update_dict = {}
        for k, v in data.items():
            if k in ("smtp_pass", "imap_pass") and (v == "" or "••••" in v):
                continue
            update_dict[k] = v

        set_many_settings(update_dict)
        self.send_json({"success": True, "message": "Settings saved successfully"})

    def api_test_smtp(self, data):
        host = data.get("smtp_host") or get_setting("smtp_host", "smtp.gmail.com")
        port = data.get("smtp_port") or get_setting("smtp_port", "587")
        user = data.get("smtp_user") or get_setting("smtp_user", "")
        pwd = data.get("smtp_pass")
        if not pwd or "••••" in pwd:
            pwd = get_setting("smtp_pass", "")
        use_tls = data.get("smtp_use_tls", "1")
        to_email = data.get("alert_email") or user

        if not to_email:
            self.send_json({"success": False, "message": "Please specify recipient email address."}, 400)
            return

        res = test_smtp_connection(host, port, user, pwd, use_tls, to_email)
        self.send_json(res)

    def api_test_imap(self, data):
        host = data.get("imap_host") or get_setting("imap_host", "imap.gmail.com")
        port = data.get("imap_port") or get_setting("imap_port", "993")
        user = data.get("imap_user") or get_setting("imap_user", "")
        pwd = data.get("imap_pass")
        if not pwd or "••••" in pwd:
            pwd = get_setting("imap_pass", "")

        res = test_imap_connection(host, port, user, pwd)
        self.send_json(res)

    def api_send_monthly_report(self, data):
        month = data.get("month") or datetime.now().strftime("%Y-%m")
        target_email = data.get("email") or get_setting("alert_email", "") or get_setting("smtp_user", "")
        success, msg = generate_and_send_monthly_statement(month, target_email)
        self.send_json({"success": success, "message": msg})

    def api_get_email_logs(self):
        conn = get_db()
        rows = conn.execute("SELECT * FROM email_logs ORDER BY created_at DESC LIMIT 30").fetchall()
        conn.close()
        self.send_json([dict(r) for r in rows])

    def api_export_csv(self, query):
        month = query.get("month", [datetime.now().strftime("%Y-%m")])[0]
        conn = get_db()
        txs = conn.execute("""
            SELECT t.date, t.time, t.type, c.name as category, COALESCE(s.name, '') as subcategory,
                   t.amount, t.payment_method, t.description, t.source, t.original_currency, t.original_amount
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            LEFT JOIN subcategories s ON t.subcategory_id = s.id
            WHERE t.date LIKE ?
            ORDER BY t.date DESC, t.time DESC
        """, (f"{month}%",)).fetchall()
        conn.close()

        lines = ["Date,Time,Type,Category,Subcategory,Amount (INR),Original Currency,Original Amount,Payment Method,Description,Source"]
        for t in txs:
            desc = t["description"].replace('"', '""') if t["description"] else ""
            lines.append(f'{t["date"]},{t["time"]},{t["type"].upper()},{t["category"]},{t["subcategory"]},{t["amount"]:.2f},{t["original_currency"]},{t["original_amount"]},{t["payment_method"]},"{desc}",{t["source"]}')
        
        csv_data = "\n".join(lines).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="FinTrack_INR_{month}.csv"')
        self.send_header("Content-Length", str(len(csv_data)))
        self.end_headers()
        self.wfile.write(csv_data)


def run_server():
    init_db(clear_transactions=False)
    start_scheduler()
    server_address = ("127.0.0.1", PORT)
    httpd = ThreadingHTTPServer(server_address, FinTrackHandler)
    print("=" * 65)
    print("   FinTrack Local - Money Tracker (Rupees ₹ INR Base)")
    print(f"   Listening on: http://127.0.0.1:{PORT}")
    print("   Privacy: Runs strictly on your local device")
    print("=" * 65)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        stop_scheduler()
        httpd.server_close()
        print("FinTrack stopped cleanly.")


if __name__ == "__main__":
    run_server()
