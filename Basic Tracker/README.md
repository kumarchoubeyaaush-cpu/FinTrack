# 💰 FinTrack Local - Smart Money Tracker (₹ INR Base)

A privacy-focused, zero-dependency personal finance tracker that runs **exclusively on your local device**, monitors **upper spending limits** and **safe lower limits in Rupees (₹)**, warns you via **in-app messages & email alerts**, automatically **mails you your monthly records**, breaks down spending into **hierarchical subcategories**, includes a **live currency converter**, and can even be **controlled remotely by email**.

---

## 🌟 Key Updates & Features

1. **Two-Page Architecture (Gmail Account & Dashboard)**:
   - **Page 1 (Login / Account Setup)**: Sign in or create an account using your personal Gmail address and password. All your records and settings are tied to your personal account.
   - **Page 2 (Financial Dashboard)**: Once signed in, access the full suite of money tracking, analytics, subcategories, limits, and email automation tools.
   - Profile chip in the header displays your name and Gmail address with a secure **Sign Out** button.

2. **Rupees (₹ INR) as the Primary Currency**:
   - The entire application uses **Rupees (₹ / INR)** as the default currency for balances, income, expenses, monthly limits, and email alerts.
   - Default limits: **Upper Limit: ₹25,000** | **Lower Limit: ₹5,000** (fully customizable in Settings).

3. **Built-in Live Currency Converter**:
   - Dedicated **"Currency Converter"** tab in the navigation bar.
   - Instant two-way conversions between **₹ INR** and major global currencies: **USD ($), EUR (€), GBP (£), AED (AED), CAD (C$), AUD (A$), SGD (S$), JPY (¥), SAR, CNY**, and more.
   - **Multi-Currency Logging**: When recording a transaction, you can pick any foreign currency (e.g. paying $50 USD for software or travel). The app automatically calculates the equivalent in ₹ INR at the current exchange rate and logs it seamlessly.

4. **100% Clean Slate (0 Pre-existing Transactions)**:
   - All sample and demo transactions have been completely cleared.
   - The database starts with **0 transactions**, allowing you to create and manage your own financial records from day one.

5. **Gmail Connection Helper & Diagnostic Fix**:
   - Explains why normal Gmail passwords get rejected: Google requires a **16-character Google App Password**.
   - Clear, step-by-step visual instructions are provided directly inside the app to generate a Google App Password in 30 seconds.
   - Auto-fills your registered Gmail into SMTP, IMAP, and notification settings so you never have to retype it.

6. **Upper & Lower Limits with Overspending Alerts**:
   - **Monthly Upper Limit**: Set your monthly spending ceiling (e.g., ₹25,000). Visual progress bar changes from Green &rarr; Yellow (at 80%) &rarr; Red (at 100%+).
   - **Safe Lower Limit**: Minimum account balance safety threshold (e.g., ₹5,000).
   - **Dual Warning System**: In-app notifications, desktop alerts (Web Notifications API), and instant HTML alert emails sent straight to your Gmail.

7. **Automated Monthly Record via Email**:
   - Compiles a complete financial statement on the 1st of each month with total income, expenses, net savings, and itemized subcategory breakdown in ₹ INR.
   - Attached `FinTrack_INR_YYYY_MM.csv` with all transaction records.
   - **"Send Statement Now"** button to dispatch any month's statement on-demand.

8. **Remote Control via Email (IMAP Command Engine)**:
   - Control your tracker on the go from your smartphone simply by sending an email from your authorized Gmail address!
   - Example commands:
     - `ADD 450 Food Groceries Supermarket`
     - `SPENT 250 Transport Petrol Shell pump`
     - `INCOME 50000 Salary Monthly credit`
     - `STATUS` or `BALANCE`
     - `REPORT`
     - `LIMIT UPPER 30000`

---

## 🏁 How to Access and Run

1. Open your project folder:
   📂 `C:\Users\HP\OneDrive\Desktop\PROJECTS\Basic Tracker`
2. **Double-click** `start.bat`.
3. Your browser will automatically open:
   👉 **`http://localhost:5000`**
4. On **Page 1**, enter your personal Gmail and choose a password to sign in / create your local account.
5. You will immediately enter **Page 2** (the Dashboard) with a clean 0-transaction database ready for your entries!
