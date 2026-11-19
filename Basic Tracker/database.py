"""
Database models, user authentication, exchange rates, and helper functions for FinTrack Local.
"""

import sqlite3
import os
import hashlib
import secrets
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracker.db")

DEFAULT_CATEGORIES = [
    {
        "name": "Food & Dining",
        "type": "expense",
        "icon": "🍔",
        "color": "#f97316",
        "subcategories": ["Groceries & Supermarket", "Restaurants & Dining", "Coffee & Tea", "Food Delivery (Zomato/Swiggy)", "Snacks & Sweets"]
    },
    {
        "name": "Housing & Utilities",
        "type": "expense",
        "icon": "🏠",
        "color": "#3b82f6",
        "subcategories": ["House Rent", "Electricity Bill", "Water & Gas", "Broadband Internet & Mobile", "Maintenance & Maid"]
    },
    {
        "name": "Transportation & Travel",
        "type": "expense",
        "icon": "🚗",
        "color": "#eab308",
        "subcategories": ["Petrol / Diesel", "Metro & Bus Transit", "Auto & Taxi (Ola/Uber)", "Vehicle Service & Insurance", "Toll & Parking"]
    },
    {
        "name": "Shopping & Lifestyle",
        "type": "expense",
        "icon": "🛍️",
        "color": "#ec4899",
        "subcategories": ["Clothing & Footwear", "Electronics & Gadgets", "Home & Kitchen Items", "Personal Care & Grooming"]
    },
    {
        "name": "Entertainment & Subscriptions",
        "type": "expense",
        "icon": "🎬",
        "color": "#8b5cf6",
        "subcategories": ["OTT Subscriptions (Netflix, Prime, Hotstar)", "Movies & Events", "Gaming", "Books & Hobbies"]
    },
    {
        "name": "Health & Medical",
        "type": "expense",
        "icon": "💊",
        "color": "#10b981",
        "subcategories": ["Doctor Consultations", "Medicines & Pharmacy", "Diagnostic Tests", "Gym & Fitness", "Health Insurance"]
    },
    {
        "name": "Financial & Investments",
        "type": "expense",
        "icon": "💳",
        "color": "#64748b",
        "subcategories": ["EMI / Loan Payment", "Credit Card Bill", "SIP / Mutual Funds", "Taxes & Govt Fees"]
    },
    {
        "name": "Income",
        "type": "income",
        "icon": "💰",
        "color": "#22c55e",
        "subcategories": ["Monthly Salary", "Freelance & Consulting", "Business Income", "Dividends & Returns", "Gifts & Cashback", "Other Income"]
    }
]

# Standard Exchange Rates to INR (₹)
DEFAULT_EXCHANGE_RATES = [
    {"code": "INR", "name": "Indian Rupee", "symbol": "₹", "rate_to_inr": 1.00},
    {"code": "USD", "name": "US Dollar", "symbol": "$", "rate_to_inr": 84.50},
    {"code": "EUR", "name": "Euro", "symbol": "€", "rate_to_inr": 91.20},
    {"code": "GBP", "name": "British Pound", "symbol": "£", "rate_to_inr": 107.80},
    {"code": "AED", "name": "UAE Dirham", "symbol": "AED", "rate_to_inr": 23.01},
    {"code": "CAD", "name": "Canadian Dollar", "symbol": "C$", "rate_to_inr": 61.80},
    {"code": "AUD", "name": "Australian Dollar", "symbol": "A$", "rate_to_inr": 55.20},
    {"code": "SGD", "name": "Singapore Dollar", "symbol": "S$", "rate_to_inr": 63.50},
    {"code": "SAR", "name": "Saudi Riyal", "symbol": "SAR", "rate_to_inr": 22.50},
    {"code": "JPY", "name": "Japanese Yen", "symbol": "¥", "rate_to_inr": 0.56},
    {"code": "CNY", "name": "Chinese Yuan", "symbol": "¥", "rate_to_inr": 11.65},
    {"code": "KWD", "name": "Kuwaiti Dinar", "symbol": "KWD", "rate_to_inr": 274.50},
    {"code": "QAR", "name": "Qatari Riyal", "symbol": "QAR", "rate_to_inr": 23.20}
]

DEFAULT_SETTINGS = {
    "currency_symbol": "₹",
    "currency_code": "INR",
    "upper_limit": "25000.00",
    "upper_limit_warn_pct": "80",
    "lower_limit": "5000.00",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_pass": "",
    "smtp_use_tls": "1",
    "alert_email": "",
    "email_alerts_enabled": "0",
    "monthly_reports_enabled": "0",
    "last_monthly_report_sent": "",
    "imap_enabled": "0",
    "imap_host": "imap.gmail.com",
    "imap_port": "993",
    "imap_user": "",
    "imap_pass": "",
    "imap_poll_interval": "60",
    "authorized_sender": "",
    "last_processed_email_id": "",
    "dark_mode": "1"
}


def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return hashed, salt


def verify_password(password, salt, hashed):
    check, _ = hash_password(password, salt)
    return check == hashed


def init_db(clear_transactions=False):
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login TEXT
        )
    """)

    # User Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL
        )
    """)

    # Settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Currency Exchange Rates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            rate_to_inr REAL NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Categories table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL CHECK(type IN ('expense', 'income')),
            icon TEXT DEFAULT '🏷️',
            color TEXT DEFAULT '#6366f1'
        )
    """)

    # Subcategories table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subcategories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT,
            UNIQUE(category_id, name)
        )
    """)

    # Transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            type TEXT NOT NULL CHECK(type IN ('expense', 'income')),
            amount REAL NOT NULL,
            category_id INTEGER NOT NULL REFERENCES categories(id),
            subcategory_id INTEGER REFERENCES subcategories(id),
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            description TEXT,
            payment_method TEXT DEFAULT 'UPI / Card',
            source TEXT DEFAULT 'web',
            original_currency TEXT DEFAULT 'INR',
            original_amount REAL,
            created_at TEXT NOT NULL
        )
    """)

    # Ensure migration columns in transactions table
    cursor.execute("PRAGMA table_info(transactions)")
    cols = [col[1] for col in cursor.fetchall()]
    if "original_currency" not in cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN original_currency TEXT DEFAULT 'INR'")
    if "original_amount" not in cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN original_amount REAL")
    if "user_id" not in cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN user_id INTEGER REFERENCES users(id)")

    # Notifications table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK(type IN ('warning', 'danger', 'info', 'success')),
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            email_sent INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    # Email Command Logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            subject TEXT,
            command TEXT,
            status TEXT,
            response_msg TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # If requested to clear demo transactions, wipe transactions and notifications
    if clear_transactions:
        cursor.execute("DELETE FROM transactions")
        cursor.execute("DELETE FROM notifications")
        cursor.execute("DELETE FROM email_logs")

    # Seed default settings
    for key, val in DEFAULT_SETTINGS.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

    # Force currency to Rupees ₹
    cursor.execute("UPDATE settings SET value = '₹' WHERE key = 'currency_symbol'")
    cursor.execute("UPDATE settings SET value = 'INR' WHERE key = 'currency_code'")

    # Seed default exchange rates
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in DEFAULT_EXCHANGE_RATES:
        cursor.execute("""
            INSERT INTO exchange_rates (code, name, symbol, rate_to_inr, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET rate_to_inr = excluded.rate_to_inr, symbol = excluded.symbol, updated_at = excluded.updated_at
        """, (r["code"], r["name"], r["symbol"], r["rate_to_inr"], now_str))

    # Seed default categories & subcategories if empty
    cursor.execute("SELECT COUNT(*) as cnt FROM categories")
    if cursor.fetchone()["cnt"] == 0:
        for cat in DEFAULT_CATEGORIES:
            cursor.execute(
                "INSERT INTO categories (name, type, icon, color) VALUES (?, ?, ?, ?)",
                (cat["name"], cat["type"], cat["icon"], cat["color"])
            )
            cat_id = cursor.lastrowid
            for sub in cat["subcategories"]:
                cursor.execute(
                    "INSERT INTO subcategories (category_id, name) VALUES (?, ?)",
                    (cat_id, sub)
                )

    conn.commit()
    conn.close()


def get_setting(key, default=""):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def get_all_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    res = {}
    for r in rows:
        res[r["key"]] = r["value"]
    return res


def set_setting(key, value):
    conn = get_db()
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))
    conn.commit()
    conn.close()


def set_many_settings(settings_dict):
    conn = get_db()
    for k, v in settings_dict.items():
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, str(v)))
    conn.commit()
    conn.close()


def add_notification(ntype, title, message, email_sent=0):
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO notifications (type, title, message, is_read, email_sent, created_at) VALUES (?, ?, ?, 0, ?, ?)",
        (ntype, title, message, email_sent, now)
    )
    conn.commit()
    notif_id = cursor.lastrowid
    conn.close()
    return notif_id


# =============================================================================
# USER AUTHENTICATION HELPERS
# =============================================================================
def register_user(email, password, name):
    email = email.lower().strip()
    name = name.strip() or email.split("@")[0]
    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return None, "An account with this email already exists. Please log in."

    hashed, salt = hash_password(password)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (email, name, salt, password_hash, created_at, last_login)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (email, name, salt, hashed, now_str, now_str))
    user_id = cursor.lastrowid

    # Create session token
    token = secrets.token_hex(24)
    cursor.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user_id, now_str))

    # Auto-fill user email into settings for mail alerts and email control
    cursor.execute("UPDATE settings SET value = ? WHERE key = 'alert_email' AND (value = '' OR value IS NULL)", (email,))
    cursor.execute("UPDATE settings SET value = ? WHERE key = 'authorized_sender' AND (value = '' OR value IS NULL)", (email,))
    cursor.execute("UPDATE settings SET value = ? WHERE key = 'smtp_user' AND (value = '' OR value IS NULL)", (email,))
    cursor.execute("UPDATE settings SET value = ? WHERE key = 'imap_user' AND (value = '' OR value IS NULL)", (email,))

    conn.commit()
    conn.close()
    return {"token": token, "user": {"id": user_id, "email": email, "name": name}}, None


def login_user(email, password):
    email = email.lower().strip()
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user:
        conn.close()
        return None, "No account found with this Gmail address. Please create an account."

    if not verify_password(password, user["salt"], user["password_hash"]):
        conn.close()
        return None, "Incorrect password. Please verify your password."

    token = secrets.token_hex(24)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user["id"], now_str))
    conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now_str, user["id"]))

    # Also update settings with user email if unset
    conn.execute("UPDATE settings SET value = ? WHERE key = 'alert_email' AND (value = '' OR value IS NULL)", (email,))
    conn.execute("UPDATE settings SET value = ? WHERE key = 'authorized_sender' AND (value = '' OR value IS NULL)", (email,))
    conn.execute("UPDATE settings SET value = ? WHERE key = 'smtp_user' AND (value = '' OR value IS NULL)", (email,))
    conn.execute("UPDATE settings SET value = ? WHERE key = 'imap_user' AND (value = '' OR value IS NULL)", (email,))

    conn.commit()
    conn.close()
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}, None


def get_user_from_token(token):
    if not token:
        return None
    conn = get_db()
    row = conn.execute("""
        SELECT u.id, u.email, u.name, u.created_at, u.last_login
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,)).fetchone()
    conn.close()
    return dict(row) if row else None


def logout_user(token):
    if not token:
        return
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
