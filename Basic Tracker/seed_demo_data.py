"""
Seeds initial realistic data so you can immediately see FinTrack in action.
"""

from datetime import datetime
from database import init_db, get_db

def seed_sample_data():
    init_db()
    conn = get_db()
    
    # Check if there are already transactions
    existing_cnt = conn.execute("SELECT COUNT(*) as c FROM transactions").fetchone()["c"]
    if existing_cnt > 0:
        print(f"Database already contains {existing_cnt} transaction(s). Skipping seed.")
        conn.close()
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    curr_month = datetime.now().strftime("%Y-%m")

    # Helper to get category & subcategory id
    def get_cat_sub(cat_name, sub_name):
        c = conn.execute("SELECT id FROM categories WHERE name = ?", (cat_name,)).fetchone()
        cat_id = c["id"] if c else 1
        s = conn.execute("SELECT id FROM subcategories WHERE category_id = ? AND name = ?", (cat_id, sub_name)).fetchone()
        sub_id = s["id"] if s else None
        return cat_id, sub_id

    # Sample transactions
    sample_records = [
        ("income", 4500.00, "Income", "Salary", f"{curr_month}-01", "09:00:00", "Monthly Paycheck", "UPI / Transfer", "web"),
        ("expense", 1100.00, "Housing & Utilities", "Rent", f"{curr_month}-02", "10:30:00", "Apartment monthly rent", "Net Banking", "web"),
        ("expense", 185.50, "Food & Dining", "Groceries", f"{curr_month}-04", "14:15:00", "Weekly grocery run at Supermarket", "Card", "web"),
        ("expense", 65.00, "Transportation", "Fuel / Gas", f"{curr_month}-06", "11:20:00", "Gas tank refill", "Card", "web"),
        ("expense", 72.00, "Housing & Utilities", "Electricity", f"{curr_month}-08", "16:00:00", "Monthly electricity bill", "UPI / Transfer", "web"),
        ("expense", 48.00, "Food & Dining", "Restaurants", f"{curr_month}-10", "20:00:00", "Dinner with friends at Italian bistro", "Card", "web"),
        ("expense", 15.99, "Entertainment & Leisure", "Streaming Subscriptions", f"{curr_month}-12", "08:00:00", "Monthly Netflix 4K", "Card", "web"),
        ("expense", 125.00, "Shopping", "Clothing", f"{curr_month}-14", "17:45:00", "Winter jacket and shoes", "Card", "web"),
        ("expense", 24.50, "Food & Dining", "Coffee & Snacks", f"{curr_month}-15", "15:10:00", "Artisan cafe coffee and pastries", "Card", "web"),
        ("income", 350.00, "Income", "Freelance / Projects", f"{curr_month}-16", "18:30:00", "Frontend bugfix milestone payout", "UPI / Transfer", "web"),
        ("expense", 45.00, "Health & Medical", "Medicines & Pharmacy", f"{curr_month}-17", "12:00:00", "Vitamins & prescription refill", "Cash", "web"),
        ("expense", 32.00, "Food & Dining", "Food Delivery", f"{curr_month}-18", "19:30:00", "Late night pizza delivery", "UPI / Transfer", "email"),
    ]

    for tx in sample_records:
        tx_type, amt, cat_name, sub_name, d_str, t_str, desc, pay_meth, src = tx
        cid, sid = get_cat_sub(cat_name, sub_name)
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO transactions (type, amount, category_id, subcategory_id, date, time, description, payment_method, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (tx_type, amt, cid, sid, d_str, t_str, desc, pay_meth, src, now_ts))

    conn.commit()
    conn.close()
    print("Sample transactions seeded successfully!")

if __name__ == "__main__":
    seed_sample_data()
