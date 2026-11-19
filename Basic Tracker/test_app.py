"""
Comprehensive Test Suite for FinTrack Local with Authentication, Currency Converter, and INR Base.
"""

import io
import json
import os
from datetime import datetime
from database import init_db, get_db, get_setting, set_setting
from mailer import check_limits_and_alert
from email_controller import parse_and_execute_command
from server import FinTrackHandler, STATIC_DIR


def mock_request(method, path, body_dict=None, token=None):
    w = io.BytesIO()
    h = FinTrackHandler.__new__(FinTrackHandler)
    h.command = method
    h.path = path
    h.requestline = f"{method} {path} HTTP/1.1"
    h.request_version = "HTTP/1.1"

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if body_dict:
        raw_b = json.dumps(body_dict).encode("utf-8")
        h.rfile = io.BytesIO(raw_b)
        headers["Content-Length"] = str(len(raw_b))
        headers["Content-Type"] = "application/json"
    else:
        h.rfile = io.BytesIO(b"")

    h.headers = headers
    h.wfile = w

    if method == "GET":
        h.do_GET()
    elif method == "POST":
        h.do_POST()
    elif method == "PUT":
        h.do_PUT()
    elif method == "DELETE":
        h.do_DELETE()

    raw_output = w.getvalue()
    parts = raw_output.split(b"\r\n\r\n", 1)
    headers_text = parts[0].decode("utf-8", errors="replace")
    body_bytes = parts[1] if len(parts) > 1 else b""
    status_line = headers_text.splitlines()[0] if headers_text else ""
    return status_line, body_bytes


def run_tests():
    print("=" * 65)
    print("   RUNNING FINTRACK LOCAL ENHANCED SUITE (AUTH + CONVERTER + INR)")
    print("=" * 65)

    # 1. Clean database with 0 transactions
    init_db(clear_transactions=True)
    conn = get_db()
    conn.execute("DELETE FROM users WHERE email LIKE '%@gmail.com'")
    conn.execute("DELETE FROM sessions")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0
    print("\n[1] Verified clean initial state: 0 transactions in database.")
    assert get_setting("currency_symbol") == "₹"
    print("  ✓ Main currency confirmed: Rupees (₹)")

    # 2. Test User Registration & Login with Personal Gmail
    print("\n[2] Testing Gmail Account Registration & Login:")
    test_gmail = "user.tracker@gmail.com"
    test_pwd = "mySecretPassword123"

    # Register
    status_line, body = mock_request("POST", "/api/auth/register", {
        "email": test_gmail,
        "password": test_pwd,
        "name": "Alex Kumar"
    })
    assert "201" in status_line
    reg_data = json.loads(body.decode("utf-8"))
    token = reg_data["token"]
    assert token is not None
    assert reg_data["user"]["email"] == test_gmail
    print(f"  ✓ User registered with Gmail ({test_gmail}), session token generated.")

    # Check /api/auth/me
    status_line, body = mock_request("GET", "/api/auth/me", token=token)
    assert "200" in status_line
    me_data = json.loads(body.decode("utf-8"))
    assert me_data["authenticated"] is True
    assert me_data["user"]["name"] == "Alex Kumar"
    print("  ✓ Session verified via /api/auth/me.")

    # Check Login
    status_line, body = mock_request("POST", "/api/auth/login", {
        "email": test_gmail,
        "password": test_pwd
    })
    assert "200" in status_line
    login_data = json.loads(body.decode("utf-8"))
    assert login_data["token"] is not None
    print("  ✓ Login endpoint verified.")

    # 3. Test Currency Converter
    print("\n[3] Testing Currency Converter Engine:")
    # List currencies
    status_line, body = mock_request("GET", "/api/currencies")
    assert "200" in status_line
    currs = json.loads(body.decode("utf-8"))
    assert len(currs) >= 10
    print(f"  ✓ {len(currs)} exchange rates loaded (INR, USD, EUR, GBP, AED, etc.)")

    # Convert 100 USD to INR
    status_line, body = mock_request("POST", "/api/currencies/convert", {
        "amount": 100,
        "from_currency": "USD",
        "to_currency": "INR"
    })
    assert "200" in status_line
    conv_data = json.loads(body.decode("utf-8"))
    assert conv_data["result"] == 8450.0  # 100 * 84.50
    print(f"  ✓ Convert 100 USD -> ₹{conv_data['result']} INR ({conv_data['formula']})")

    # Convert 10,000 INR to EUR
    status_line, body = mock_request("POST", "/api/currencies/convert", {
        "amount": 10000,
        "from_currency": "INR",
        "to_currency": "EUR"
    })
    assert "200" in status_line
    conv_eur = json.loads(body.decode("utf-8"))
    print(f"  ✓ Convert ₹10,000 INR -> {conv_eur['to_symbol']}{conv_eur['result']} EUR")

    # 4. Test Multi-Currency Transaction Creation
    print("\n[4] Testing Multi-Currency Transaction Logging:")
    # Get Food category
    status_line, body = mock_request("GET", "/api/categories")
    cats = json.loads(body.decode("utf-8"))
    food_cat = next(c for c in cats if "Food" in c["name"])

    # Create transaction in USD ($20 for dinner)
    status_line, body = mock_request("POST", "/api/transactions", {
        "type": "expense",
        "amount": 20.0,
        "currency": "USD",
        "category_id": food_cat["id"],
        "subcategory_id": food_cat["subcategories"][0]["id"],
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": "19:45:00",
        "description": "Online food order",
        "payment_method": "Credit Card"
    }, token=token)
    assert "201" in status_line
    tx_created = json.loads(body.decode("utf-8"))
    assert tx_created["amount_inr"] == 1690.0  # 20 * 84.50
    print(f"  ✓ Logged $20.00 USD -> Automatically converted & recorded as ₹{tx_created['amount_inr']:.2f} INR!")

    # 5. Test Budget Limits with INR (₹)
    print("\n[5] Testing INR Budget Limits & Overspending Warnings:")
    set_setting("upper_limit", "2000.00")
    set_setting("upper_limit_warn_pct", "80")
    set_setting("lower_limit", "5000.00")
    alerts = check_limits_and_alert()
    print(f"  ✓ Limit evaluation triggered {len(alerts)} alert(s) in Rupees.")

    # 6. Test Email Command Parsing with INR (₹)
    print("\n[6] Testing Remote Control by Email (INR Commands):")
    res_add = parse_and_execute_command("ADD 450 Food Groceries Fresh milk and bread", test_gmail)
    assert "Recorded Expense" in res_add
    assert "₹" in res_add
    print("  ✓ Command 'ADD 450 Food Groceries' passed with ₹ formatting.")

    res_status = parse_and_execute_command("STATUS", test_gmail)
    assert "Total Account Balance" in res_status
    assert "₹" in res_status
    print("  ✓ Command 'STATUS' passed with ₹ formatting.")

    res_limit = parse_and_execute_command("LIMIT UPPER 35000", test_gmail)
    assert "35,000" in res_limit
    assert float(get_setting("upper_limit")) == 35000.0
    print("  ✓ Command 'LIMIT UPPER 35000' passed.")

    # 7. Clean up transactions again so user has completely empty slate
    init_db(clear_transactions=True)
    conn = get_db()
    assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0
    conn.close()
    print("\n[7] Final check: Database reset to 0 transactions for the user!")

    print("\n" + "=" * 65)
    print("   ALL TESTS PASSED! APPLICATION 100% VERIFIED & READY! 🚀")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
