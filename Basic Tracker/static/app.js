/**
 * FinTrack Local - Client Application Logic (Rupees ₹ Base & Multi-Currency)
 */

// Global Application State
const state = {
    user: null,
    token: localStorage.getItem("fintrack_token") || null,
    selectedMonth: new Date().toISOString().slice(0, 7), // YYYY-MM
    currency: "₹",
    summary: null,
    categories: [],
    currencies: [],
    transactions: [],
    txTotal: 0,
    txLimit: 25,
    txOffset: 0,
    notifications: [],
    activeTab: "dashboard",
    editingTxId: null,
    authMode: "login"
};

// =============================================================================
// INITIALIZATION
// =============================================================================
document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initAuth();
    initMonthPicker();
    initTabs();
    initModalsAndForms();
    initConverter();

    // Check Authentication on Page Load
    checkAuthSession();

    // Periodic background sync every 30 seconds
    setInterval(() => {
        if (state.user) {
            loadNotifications(false);
            loadSchedulerStatus();
        }
    }, 30000);
});

// =============================================================================
// AUTHENTICATION & SESSION MANAGEMENT
// =============================================================================
function initAuth() {
    const authForm = document.getElementById("authForm");
    if (authForm) {
        authForm.addEventListener("submit", handleAuthSubmit);
    }

    const logoutBtn = document.getElementById("logoutBtn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", handleLogout);
    }
}

function switchAuthMode(mode) {
    state.authMode = mode;
    const isReg = mode === "register";

    document.getElementById("authTabLogin").classList.toggle("active", !isReg);
    document.getElementById("authTabRegister").classList.toggle("active", isReg);
    document.getElementById("nameGroup").style.display = isReg ? "block" : "none";
    document.getElementById("authSubmitBtn").textContent = isReg ? "Create Account & Start" : "Sign In with Gmail";
    hideAuthAlerts();
}

function hideAuthAlerts() {
    document.getElementById("authErrorMsg").style.display = "none";
    document.getElementById("authSuccessMsg").style.display = "none";
}

async function handleAuthSubmit(e) {
    e.preventDefault();
    hideAuthAlerts();

    const email = document.getElementById("authEmail").value.trim();
    const password = document.getElementById("authPassword").value;
    const name = document.getElementById("authName")?.value.trim() || "";

    const isReg = state.authMode === "register";
    const endpoint = isReg ? "/api/auth/register" : "/api/auth/login";
    const payload = isReg ? { email, password, name } : { email, password };

    try {
        const res = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (!res.ok) {
            const errDiv = document.getElementById("authErrorMsg");
            errDiv.textContent = data.error || "Authentication failed.";
            errDiv.style.display = "block";
            return;
        }

        // Save session token
        state.token = data.token;
        state.user = data.user;
        localStorage.setItem("fintrack_token", data.token);

        showToast(isReg ? "Account created successfully!" : "Signed in successfully!", "success");
        transitionToApp();
    } catch (err) {
        const errDiv = document.getElementById("authErrorMsg");
        errDiv.textContent = "Error: " + err.message;
        errDiv.style.display = "block";
    }
}

async function checkAuthSession() {
    if (!state.token) {
        showAuthScreen();
        return;
    }

    try {
        const res = await fetch("/api/auth/me", {
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        const data = await res.json();

        if (res.ok && data.authenticated) {
            state.user = data.user;
            transitionToApp();
        } else {
            localStorage.removeItem("fintrack_token");
            state.token = null;
            state.user = null;
            showAuthScreen();
        }
    } catch (e) {
        showAuthScreen();
    }
}

function showAuthScreen() {
    document.getElementById("authScreen").style.display = "flex";
    document.getElementById("appScreen").style.display = "none";
}

function transitionToApp() {
    document.getElementById("authScreen").style.display = "none";
    document.getElementById("appScreen").style.display = "flex";

    // Populate user profile info in header
    if (state.user) {
        document.getElementById("headerUserName").textContent = state.user.name || state.user.email;
        document.getElementById("headerUserName").title = state.user.email;
    }

    // Load full app data
    loadAllData();
}

async function handleLogout() {
    try {
        await fetch("/api/auth/logout", {
            method: "POST",
            headers: { "Authorization": `Bearer ${state.token}` }
        });
    } catch (e) {}

    localStorage.removeItem("fintrack_token");
    state.token = null;
    state.user = null;
    showAuthScreen();
    showToast("Signed out", "info");
}

async function loadAllData() {
    await loadSettings();
    await loadCurrencies();
    await loadCategories();
    await loadSummary();
    await loadTransactions();
    await loadNotifications(false);
    await loadSchedulerStatus();
}

// =============================================================================
// THEME MANAGEMENT
// =============================================================================
function initTheme() {
    const savedTheme = localStorage.getItem("fintrack_theme") || "dark-theme";
    document.body.className = savedTheme;
    updateThemeIcon(savedTheme);

    document.getElementById("themeToggleBtn")?.addEventListener("click", () => {
        const isDark = document.body.classList.contains("dark-theme");
        const newTheme = isDark ? "light-theme" : "dark-theme";
        document.body.className = newTheme;
        localStorage.setItem("fintrack_theme", newTheme);
        updateThemeIcon(newTheme);
    });
}

function updateThemeIcon(theme) {
    const btn = document.getElementById("themeToggleBtn");
    if (btn) btn.textContent = theme === "dark-theme" ? "🌙" : "☀️";
}

// =============================================================================
// MONTH PICKER & NAVIGATION
// =============================================================================
function initMonthPicker() {
    const monthInput = document.getElementById("selectedMonthInput");
    if (!monthInput) return;
    monthInput.value = state.selectedMonth;

    monthInput.addEventListener("change", (e) => {
        if (e.target.value) {
            state.selectedMonth = e.target.value;
            state.txOffset = 0;
            refreshDashboardAndLists();
        }
    });

    document.getElementById("prevMonthBtn")?.addEventListener("click", () => changeMonthOffset(-1));
    document.getElementById("nextMonthBtn")?.addEventListener("click", () => changeMonthOffset(1));
}

function changeMonthOffset(delta) {
    const [year, month] = state.selectedMonth.split("-").map(Number);
    const d = new Date(year, month - 1 + delta, 1);
    state.selectedMonth = d.toISOString().slice(0, 7);
    document.getElementById("selectedMonthInput").value = state.selectedMonth;
    state.txOffset = 0;
    refreshDashboardAndLists();
}

function refreshDashboardAndLists() {
    loadSummary();
    loadTransactions();
    if (state.activeTab === "analytics") {
        loadAnalytics();
    }
}

// =============================================================================
// TAB NAVIGATION
// =============================================================================
function initTabs() {
    const tabBtns = document.querySelectorAll(".nav-tab");
    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const tabId = btn.getAttribute("data-tab");
            navigateToTab(tabId);
        });
    });
}

function navigateToTab(tabId) {
    state.activeTab = tabId;
    document.querySelectorAll(".nav-tab").forEach(b => {
        b.classList.toggle("active", b.getAttribute("data-tab") === tabId);
    });
    document.querySelectorAll(".tab-content").forEach(c => {
        c.classList.toggle("active", c.id === `tab-${tabId}`);
    });

    if (tabId === "analytics") {
        loadAnalytics();
    } else if (tabId === "converter") {
        renderConverterTab();
    } else if (tabId === "email-control") {
        loadSchedulerStatus();
        loadEmailLogs();
    } else if (tabId === "manage-categories") {
        renderCategoriesManager();
    } else if (tabId === "transactions") {
        loadTransactions();
    } else if (tabId === "settings") {
        loadSettingsToForm();
    }
}

// =============================================================================
// CURRENCY CONVERTER ENGINE
// =============================================================================
async function loadCurrencies() {
    try {
        const res = await fetch("/api/currencies");
        state.currencies = await res.json();
        populateCurrencySelects();
    } catch (e) {
        console.error("Failed to load currencies:", e);
    }
}

function populateCurrencySelects() {
    const convFrom = document.getElementById("convFrom");
    const convTo = document.getElementById("convTo");
    const txCurr = document.getElementById("txCurrency");

    if (!state.currencies || state.currencies.length === 0) return;

    const optionsHtml = state.currencies.map(c =>
        `<option value="${c.code}">${c.code} (${c.symbol} - ${c.name})</option>`
    ).join("");

    if (convFrom) {
        convFrom.innerHTML = optionsHtml;
        convFrom.value = "USD"; // Default From
    }
    if (convTo) {
        convTo.innerHTML = optionsHtml;
        convTo.value = "INR"; // Default To
    }
    if (txCurr) {
        txCurr.innerHTML = optionsHtml;
        txCurr.value = "INR"; // Default transaction currency: ₹ INR
    }

    performLiveConversion();
}

function initConverter() {
    const amountInput = document.getElementById("convAmount");
    const fromSelect = document.getElementById("convFrom");
    const toSelect = document.getElementById("convTo");
    const swapBtn = document.getElementById("convSwapBtn");

    amountInput?.addEventListener("input", performLiveConversion);
    fromSelect?.addEventListener("change", performLiveConversion);
    toSelect?.addEventListener("change", performLiveConversion);

    swapBtn?.addEventListener("click", () => {
        if (!fromSelect || !toSelect) return;
        const temp = fromSelect.value;
        fromSelect.value = toSelect.value;
        toSelect.value = temp;
        performLiveConversion();
    });

    // Transaction Modal currency live preview
    const txAmount = document.getElementById("txAmount");
    const txCurr = document.getElementById("txCurrency");
    const previewDiv = document.getElementById("txConvertedPreview");

    const updateTxPreview = () => {
        if (!txAmount || !txCurr || !previewDiv) return;
        const val = parseFloat(txAmount.value);
        const code = txCurr.value;
        const curObj = state.currencies.find(c => c.code === code);
        const modalPrefix = document.getElementById("txModalCurrencyPrefix");
        if (modalPrefix && curObj) modalPrefix.textContent = curObj.symbol;

        if (code === "INR" || !val || isNaN(val)) {
            previewDiv.style.display = "none";
        } else if (curObj) {
            const inrAmt = val * curObj.rate_to_inr;
            previewDiv.style.display = "block";
            previewDiv.textContent = `≈ ₹${formatNumber(inrAmt)} INR (Exchange rate: 1 ${code} = ₹${curObj.rate_to_inr})`;
        }
    };

    txAmount?.addEventListener("input", updateTxPreview);
    txCurr?.addEventListener("change", updateTxPreview);
}

async function performLiveConversion() {
    const amountInput = document.getElementById("convAmount");
    const fromSelect = document.getElementById("convFrom");
    const toSelect = document.getElementById("convTo");
    const resVal = document.getElementById("convResultValue");
    const rateNote = document.getElementById("convRateNote");

    if (!amountInput || !fromSelect || !toSelect || !resVal) return;

    const amount = parseFloat(amountInput.value) || 0;
    const fromCurr = fromSelect.value;
    const toCurr = toSelect.value;

    try {
        const res = await fetch("/api/currencies/convert", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ amount, from_currency: fromCurr, to_currency: toCurr })
        });
        const data = await res.json();

        if (res.ok) {
            resVal.textContent = `${data.to_symbol} ${formatNumber(data.result)}`;
            if (rateNote) {
                rateNote.textContent = `${data.formula} • (${amount} ${fromCurr} = ₹${formatNumber(data.amount_inr)} INR)`;
            }
        }
    } catch (e) {
        console.error("Conversion error:", e);
    }
}

function renderConverterTab() {
    performLiveConversion();
    renderExchangeRatesTable();
}

function renderExchangeRatesTable() {
    const tbody = document.getElementById("exchangeRatesTableBody");
    if (!tbody || !state.currencies) return;

    tbody.innerHTML = state.currencies.map(c => `
        <tr>
            <td><strong>${escapeHtml(c.name)}</strong></td>
            <td><span class="badge-tag" style="background: rgba(99,102,241,0.15); color: #818cf8;">${c.code}</span></td>
            <td><strong style="font-size: 15px;">${c.symbol}</strong></td>
            <td class="text-right font-bold" style="font-size: 14px;">₹${formatNumber(c.rate_to_inr)}</td>
            <td class="text-center">
                <button class="btn btn-secondary btn-sm" onclick="setConverterCurrencies('${c.code}', 'INR')">Convert</button>
            </td>
        </tr>
    `).join("");
}

function setConverterCurrencies(fromCode, toCode) {
    navigateToTab("converter");
    const fromSelect = document.getElementById("convFrom");
    const toSelect = document.getElementById("convTo");
    if (fromSelect && toSelect) {
        fromSelect.value = fromCode;
        toSelect.value = toCode;
        performLiveConversion();
    }
}

// =============================================================================
// API CALLS: SUMMARY & DASHBOARD
// =============================================================================
async function loadSummary() {
    try {
        const res = await fetch(`/api/summary?month=${state.selectedMonth}`);
        const data = await res.json();
        state.summary = data;
        state.currency = data.currency_symbol || "₹";

        renderDashboardSummary(data);
    } catch (err) {
        console.error("Failed to load summary:", err);
    }
}

function renderDashboardSummary(data) {
    const cur = state.currency;

    // Balance Card
    const kpiBalance = document.getElementById("kpiBalance");
    kpiBalance.textContent = `${cur}${formatNumber(data.total_balance)}`;
    kpiBalance.className = `kpi-value ${data.total_balance < 0 ? 'text-expense' : 'text-income'}`;

    const lowerLimitBadge = document.getElementById("lowerLimitBadge");
    const kpiLowerLimitText = document.getElementById("kpiLowerLimitText");
    kpiLowerLimitText.textContent = `Lower limit: ${cur}${formatNumber(data.lower_limit)}`;

    if (data.is_below_lower_limit) {
        lowerLimitBadge.textContent = "Below Lower Limit!";
        lowerLimitBadge.className = "status-pill pill-danger";
    } else {
        lowerLimitBadge.textContent = "Safe Balance";
        lowerLimitBadge.className = "status-pill pill-safe";
    }

    // Monthly Expenses & Upper Limit Progress Bar
    document.getElementById("kpiMonthExpense").textContent = `${cur}${formatNumber(data.month_expense)}`;
    const upperLimitBar = document.getElementById("upperLimitProgressBar");
    const upperLimitPercentText = document.getElementById("upperLimitPercentText");
    const upperLimitMaxText = document.getElementById("upperLimitMaxText");

    upperLimitMaxText.textContent = `Max: ${cur}${formatNumber(data.upper_limit)}`;
    const usedPct = data.upper_limit_used_pct || 0;
    upperLimitPercentText.textContent = `${usedPct}% of limit`;

    const barWidth = Math.min(usedPct, 100);
    upperLimitBar.style.width = `${barWidth}%`;
    upperLimitBar.className = "progress-bar-fill " + (
        data.is_over_limit ? "progress-red" : (data.is_near_limit ? "progress-yellow" : "progress-green")
    );

    // Monthly Income & Net Savings
    document.getElementById("kpiMonthIncome").textContent = `+${cur}${formatNumber(data.month_income)}`;
    document.getElementById("kpiTxCount").textContent = `${data.tx_count} transaction(s) this month`;

    const kpiNet = document.getElementById("kpiNetSavings");
    kpiNet.textContent = `${data.net_savings >= 0 ? '+' : ''}${cur}${formatNumber(data.net_savings)}`;
    kpiNet.className = `kpi-value ${data.net_savings >= 0 ? 'text-income' : 'text-expense'}`;

    const kpiRemaining = document.getElementById("kpiRemainingBudget");
    kpiRemaining.textContent = data.remaining_budget >= 0
        ? `Remaining budget: ${cur}${formatNumber(data.remaining_budget)}`
        : `Over budget by: ${cur}${formatNumber(Math.abs(data.remaining_budget))}`;

    // Render Global Alert Banners
    renderGlobalAlertBanners(data);

    // Render Recent Transactions Table
    renderRecentTransactions(data.recent_transactions || []);

    // Load Donut Chart & Top Subcategories
    loadAnalyticsMini();
}

function renderGlobalAlertBanners(data) {
    const container = document.getElementById("globalAlertContainer");
    container.innerHTML = "";
    const cur = state.currency;

    if (data.is_over_limit) {
        const div = document.createElement("div");
        div.className = "alert-banner alert-danger";
        div.innerHTML = `
            <div>
                🚨 <strong>OVERSPENDING ALERT:</strong> You have spent <strong>${cur}${formatNumber(data.month_expense)}</strong>, 
                exceeding your monthly upper limit of <strong>${cur}${formatNumber(data.upper_limit)}</strong> by <strong>${cur}${formatNumber(data.month_expense - data.upper_limit)}</strong>!
            </div>
            <button class="btn btn-secondary btn-sm" onclick="navigateToTab('settings')">Adjust Limit</button>
        `;
        container.appendChild(div);
    } else if (data.is_near_limit) {
        const div = document.createElement("div");
        div.className = "alert-banner alert-warning";
        div.innerHTML = `
            <div>
                ⚠️ <strong>BUDGET WARNING:</strong> You have consumed <strong>${data.upper_limit_used_pct}%</strong> of your monthly upper limit 
                (${cur}${formatNumber(data.month_expense)} / ${cur}${formatNumber(data.upper_limit)}). Remaining: <strong>${cur}${formatNumber(data.remaining_budget)}</strong>.
            </div>
            <button class="btn btn-secondary btn-sm" onclick="navigateToTab('analytics')">View Breakdown</button>
        `;
        container.appendChild(div);
    }

    if (data.is_below_lower_limit) {
        const div = document.createElement("div");
        div.className = "alert-banner alert-warning";
        div.innerHTML = `
            <div>
                ⚠️ <strong>LOW BALANCE WARNING:</strong> Total account balance (<strong>${cur}${formatNumber(data.total_balance)}</strong>) 
                is below your minimum safety lower limit of <strong>${cur}${formatNumber(data.lower_limit)}</strong>.
            </div>
            <button class="btn btn-secondary btn-sm" onclick="navigateToTab('settings')">Settings</button>
        `;
        container.appendChild(div);
    }
}

function renderRecentTransactions(txs) {
    const tbody = document.getElementById("recentTransactionsTableBody");
    if (!txs || txs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4">No transactions recorded yet. Click "Add Transaction" to create your first record!</td></tr>`;
        return;
    }

    const cur = state.currency;
    tbody.innerHTML = txs.map(t => {
        const isInc = t.type === "income";
        const amtClass = isInc ? "text-income" : "text-expense";
        const sign = isInc ? "+" : "-";
        const subTag = t.subcategory_name ? `<span class="subcat-tag">${escapeHtml(t.subcategory_name)}</span>` : "";
        const sourceBadge = t.source === "email" ? `<span class="badge-tag" style="background: rgba(99,102,241,0.15); color: #818cf8;">✉️ Email</span>` : `<span class="text-muted text-sm">Web</span>`;

        return `
            <tr>
                <td style="white-space: nowrap;">${t.date}</td>
                <td>
                    <span class="badge-tag" style="background: ${t.category_color}22; color: ${t.category_color};">
                        ${t.category_icon || '🏷️'} ${escapeHtml(t.category_name)}
                    </span>
                    ${subTag}
                </td>
                <td>${escapeHtml(t.description || '—')}</td>
                <td>${sourceBadge}</td>
                <td class="text-right font-bold ${amtClass}">${sign}${cur}${formatNumber(t.amount)}</td>
            </tr>
        `;
    }).join("");
}

async function loadAnalyticsMini() {
    try {
        const res = await fetch(`/api/analytics?month=${state.selectedMonth}`);
        const data = await res.json();
        renderDonutChart(data.category_breakdown, data.total_expense);
        renderTopSubcategories(data.subcategory_breakdown, data.total_expense);
    } catch (e) {
        console.error("Mini analytics error:", e);
    }
}

function renderDonutChart(categories, totalExpense) {
    const cur = state.currency;
    document.getElementById("chartTotalExpense").textContent = `${cur}${formatNumber(totalExpense)}`;
    document.getElementById("donutCenterAmount").textContent = `${cur}${formatNumber(totalExpense)}`;

    const svg = document.getElementById("donutSvg");
    const legend = document.getElementById("categoryLegend");

    svg.querySelectorAll(".donut-segment").forEach(el => el.remove());

    if (!categories || categories.length === 0 || totalExpense <= 0) {
        legend.innerHTML = `<div class="text-muted text-center text-sm py-2">No expenses logged yet this month.</div>`;
        return;
    }

    const radius = 70;
    const circumference = 2 * Math.PI * radius;
    let currentOffset = 0;
    let legendHtml = "";

    categories.forEach(cat => {
        const strokeLength = (cat.amount / totalExpense) * circumference;
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", "100");
        circle.setAttribute("cy", "100");
        circle.setAttribute("r", radius.toString());
        circle.setAttribute("class", "donut-segment");
        circle.setAttribute("stroke", cat.color || "#6366f1");
        circle.setAttribute("stroke-dasharray", `${strokeLength} ${circumference}`);
        circle.setAttribute("stroke-dashoffset", (-currentOffset).toString());

        circle.addEventListener("mouseenter", () => {
            document.querySelector(".donut-center-label").textContent = cat.name;
            document.getElementById("donutCenterAmount").textContent = `${cur}${formatNumber(cat.amount)}`;
        });
        circle.addEventListener("mouseleave", () => {
            document.querySelector(".donut-center-label").textContent = "Total Spent";
            document.getElementById("donutCenterAmount").textContent = `${cur}${formatNumber(totalExpense)}`;
        });

        svg.appendChild(circle);
        currentOffset += strokeLength;

        legendHtml += `
            <div class="legend-item" style="cursor: pointer;" onclick="filterTransactionsByCategory(${cat.id})">
                <div class="legend-label">
                    <span class="legend-dot" style="background: ${cat.color};"></span>
                    <span>${cat.icon || '🏷️'} ${escapeHtml(cat.name)}</span>
                </div>
                <div class="font-bold text-sm">
                    ${cur}${formatNumber(cat.amount)} <span class="text-muted text-sm">(${cat.percentage}%)</span>
                </div>
            </div>
        `;
    });

    legend.innerHTML = legendHtml;
}

function renderTopSubcategories(subcats, totalExpense) {
    const container = document.getElementById("dashboardSubcatList");
    if (!subcats || subcats.length === 0 || totalExpense <= 0) {
        container.innerHTML = `<div class="text-muted text-sm text-center full-width">No subcategory data recorded yet.</div>`;
        return;
    }

    const cur = state.currency;
    const top5 = subcats.slice(0, 6);

    container.innerHTML = top5.map(s => `
        <div class="subcat-progress-item">
            <div class="subcat-item-top">
                <div>
                    <span class="subcat-name">${escapeHtml(s.subcategory_name)}</span>
                    <span class="subcat-parent">(${escapeHtml(s.category_name)})</span>
                </div>
                <div class="subcat-amount">${cur}${formatNumber(s.amount)} <span class="text-muted text-sm">(${s.percentage}%)</span></div>
            </div>
            <div class="subcat-mini-bar">
                <div class="subcat-mini-fill" style="width: ${s.percentage}%; background: ${s.category_color || 'var(--primary)'};"></div>
            </div>
        </div>
    `).join("");
}

// =============================================================================
// API CALLS: CATEGORIES & SUBCATEGORIES
// =============================================================================
async function loadCategories() {
    try {
        const res = await fetch("/api/categories");
        state.categories = await res.json();
        populateCategorySelects();
    } catch (e) {
        console.error("Failed to load categories:", e);
    }
}

function populateCategorySelects() {
    const txCatSelect = document.getElementById("txCategory");
    const filterCatSelect = document.getElementById("txCategoryFilter");
    const quickSubCatSelect = document.getElementById("quickSubcatCategory");

    if (filterCatSelect) {
        filterCatSelect.innerHTML = `<option value="">All Categories</option>` +
            state.categories.map(c => `<option value="${c.id}">${c.icon || '🏷️'} ${escapeHtml(c.name)}</option>`).join("");
    }

    if (quickSubCatSelect) {
        quickSubCatSelect.innerHTML = state.categories.map(c =>
            `<option value="${c.id}">${c.icon || '🏷️'} ${escapeHtml(c.name)} (${c.type})</option>`
        ).join("");
    }

    updateModalCategoryDropdown();
}

function updateModalCategoryDropdown() {
    const txCatSelect = document.getElementById("txCategory");
    if (!txCatSelect) return;

    const selectedType = document.querySelector('input[name="txType"]:checked')?.value || "expense";
    const filtered = state.categories.filter(c => c.type === selectedType);

    txCatSelect.innerHTML = filtered.map(c =>
        `<option value="${c.id}">${c.icon || '🏷️'} ${escapeHtml(c.name)}</option>`
    ).join("");

    updateModalSubcategoryDropdown();
}

function updateModalSubcategoryDropdown() {
    const catSelect = document.getElementById("txCategory");
    const subSelect = document.getElementById("txSubcategory");
    if (!catSelect || !subSelect) return;

    const catId = parseInt(catSelect.value);
    const cat = state.categories.find(c => c.id === catId);

    if (cat && cat.subcategories && cat.subcategories.length > 0) {
        subSelect.innerHTML = `<option value="">-- Choose Subcategory --</option>` +
            cat.subcategories.map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join("");
        subSelect.disabled = false;
    } else {
        subSelect.innerHTML = `<option value="">(No subcategories defined)</option>`;
        subSelect.disabled = true;
    }
}

// =============================================================================
// API CALLS: TRANSACTIONS LIST
// =============================================================================
async function loadTransactions() {
    try {
        const search = document.getElementById("txSearchInput")?.value || "";
        const type = document.getElementById("txTypeFilter")?.value || "";
        const catId = document.getElementById("txCategoryFilter")?.value || "";

        const query = new URLSearchParams({
            month: state.selectedMonth,
            type: type,
            category_id: catId,
            search: search,
            limit: state.txLimit,
            offset: state.txOffset
        });

        const res = await fetch(`/api/transactions?${query}`);
        const data = await res.json();
        state.transactions = data.transactions || [];
        state.txTotal = data.total || 0;

        renderTransactionsTable();
        updatePaginationControls();
    } catch (e) {
        console.error("Failed to load transactions:", e);
    }
}

function renderTransactionsTable() {
    const tbody = document.getElementById("allTransactionsTableBody");
    const cur = state.currency;

    if (!state.transactions || state.transactions.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4">No transactions found. Click "New Transaction" to create your first record!</td></tr>`;
        return;
    }

    tbody.innerHTML = state.transactions.map(t => {
        const isInc = t.type === "income";
        const amtClass = isInc ? "text-income" : "text-expense";
        const sign = isInc ? "+" : "-";
        const subTag = t.subcategory_name ? `<span class="subcat-tag">${escapeHtml(t.subcategory_name)}</span>` : '<span class="text-muted">—</span>';
        const srcTag = t.source === "email" ? `<span class="badge-tag" style="background: rgba(99,102,241,0.15); color: #818cf8;">✉️ Email</span>` : `<span class="text-muted text-sm">Web</span>`;

        return `
            <tr>
                <td style="white-space: nowrap;">
                    <div>${t.date}</div>
                    <div class="text-muted text-sm">${t.time}</div>
                </td>
                <td>
                    <span class="status-pill ${isInc ? 'pill-safe' : 'pill-warning'}">
                        ${isInc ? 'Income' : 'Expense'}
                    </span>
                </td>
                <td>
                    <span class="badge-tag" style="background: ${t.category_color}22; color: ${t.category_color};">
                        ${t.category_icon || '🏷️'} ${escapeHtml(t.category_name)}
                    </span>
                </td>
                <td>${subTag}</td>
                <td>${escapeHtml(t.description || '—')}</td>
                <td><span class="text-sm text-secondary">${escapeHtml(t.payment_method || 'UPI / Card')}</span></td>
                <td>${srcTag}</td>
                <td class="text-right font-bold ${amtClass}" style="font-size: 14px;">${sign}${cur}${formatNumber(t.amount)}</td>
                <td class="text-center">
                    <div class="actions-cell">
                        <button class="btn-icon-sm" title="Edit" onclick="openEditTransactionModal(${t.id})">✏️</button>
                        <button class="btn-icon-sm" title="Delete" onclick="deleteTransaction(${t.id})">🗑️</button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");
}

function updatePaginationControls() {
    const label = document.getElementById("txCountLabel");
    const prevBtn = document.getElementById("txPrevPageBtn");
    const nextBtn = document.getElementById("txNextPageBtn");

    const start = state.txTotal > 0 ? state.txOffset + 1 : 0;
    const end = Math.min(state.txOffset + state.txLimit, state.txTotal);

    if (label) label.textContent = `Showing ${start}–${end} of ${state.txTotal}`;
    if (prevBtn) prevBtn.disabled = state.txOffset === 0;
    if (nextBtn) nextBtn.disabled = state.txOffset + state.txLimit >= state.txTotal;
}

function filterTransactionsByCategory(catId) {
    navigateToTab("transactions");
    const catSelect = document.getElementById("txCategoryFilter");
    if (catSelect) {
        catSelect.value = catId;
        state.txOffset = 0;
        loadTransactions();
    }
}

// =============================================================================
// MODALS & FORMS HANDLING
// =============================================================================
function initModalsAndForms() {
    document.getElementById("quickAddBtn")?.addEventListener("click", openAddTransactionModal);

    document.getElementById("txSearchInput")?.addEventListener("input", debounce(() => {
        state.txOffset = 0;
        loadTransactions();
    }, 300));
    document.getElementById("txTypeFilter")?.addEventListener("change", () => {
        state.txOffset = 0;
        loadTransactions();
    });
    document.getElementById("txCategoryFilter")?.addEventListener("change", () => {
        state.txOffset = 0;
        loadTransactions();
    });

    document.getElementById("txPrevPageBtn")?.addEventListener("click", () => {
        if (state.txOffset >= state.txLimit) {
            state.txOffset -= state.txLimit;
            loadTransactions();
        }
    });
    document.getElementById("txNextPageBtn")?.addEventListener("click", () => {
        if (state.txOffset + state.txLimit < state.txTotal) {
            state.txOffset += state.txLimit;
            loadTransactions();
        }
    });

    document.getElementById("exportCsvBtn")?.addEventListener("click", () => {
        window.location.href = `/api/export/csv?month=${state.selectedMonth}`;
    });

    document.querySelectorAll('input[name="txType"]').forEach(r => {
        r.addEventListener("change", updateModalCategoryDropdown);
    });

    document.getElementById("txCategory")?.addEventListener("change", updateModalSubcategoryDropdown);
    document.getElementById("txForm")?.addEventListener("submit", handleTransactionSubmit);
    document.getElementById("categoryForm")?.addEventListener("submit", handleCategorySubmit);
    document.getElementById("quickSubcatForm")?.addEventListener("submit", handleQuickSubcatSubmit);

    // Notifications bell
    const bellBtn = document.getElementById("notifBellBtn");
    const dropdown = document.getElementById("notifDropdown");
    bellBtn?.addEventListener("click", (e) => {
        e.stopPropagation();
        dropdown.classList.toggle("show");
    });
    document.addEventListener("click", (e) => {
        if (dropdown && !dropdown.contains(e.target) && e.target !== bellBtn) {
            dropdown.classList.remove("show");
        }
    });

    document.getElementById("markReadBtn")?.addEventListener("click", async () => {
        await fetch("/api/notifications/mark-read", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        loadNotifications(false);
    });

    document.getElementById("clearNotifsBtn")?.addEventListener("click", async () => {
        await fetch("/api/notifications/clear", { method: "POST" });
        loadNotifications(false);
    });

    document.getElementById("limitsForm")?.addEventListener("submit", handleLimitsSubmit);
    document.getElementById("smtpForm")?.addEventListener("submit", handleSmtpSubmit);
    document.getElementById("testSmtpBtn")?.addEventListener("click", handleTestSmtp);
    document.getElementById("imapForm")?.addEventListener("submit", handleImapSubmit);
    document.getElementById("testImapBtn")?.addEventListener("click", handleTestImap);
    document.getElementById("sendReportNowBtn")?.addEventListener("click", handleSendReportNow);
    document.getElementById("refreshLogsBtn")?.addEventListener("click", loadEmailLogs);
}

function openAddTransactionModal() {
    state.editingTxId = null;
    document.getElementById("txModalTitle").textContent = "Add Transaction";
    document.getElementById("txForm").reset();
    document.getElementById("txEditId").value = "";

    const today = new Date().toISOString().slice(0, 10);
    document.getElementById("txDate").value = today;
    document.querySelector('input[name="txType"][value="expense"]').checked = true;

    // Reset currency to INR ₹
    const txCurr = document.getElementById("txCurrency");
    if (txCurr) txCurr.value = "INR";
    const modalPrefix = document.getElementById("txModalCurrencyPrefix");
    if (modalPrefix) modalPrefix.textContent = "₹";
    const previewDiv = document.getElementById("txConvertedPreview");
    if (previewDiv) previewDiv.style.display = "none";

    updateModalCategoryDropdown();
    document.getElementById("txModal").classList.add("show");
}

function openEditTransactionModal(id) {
    const tx = state.transactions.find(t => t.id === id);
    if (!tx) return;

    state.editingTxId = id;
    document.getElementById("txModalTitle").textContent = "Edit Transaction";
    document.getElementById("txEditId").value = id;

    const radio = document.querySelector(`input[name="txType"][value="${tx.type}"]`);
    if (radio) radio.checked = true;
    updateModalCategoryDropdown();

    document.getElementById("txAmount").value = tx.amount;
    document.getElementById("txDate").value = tx.date;
    document.getElementById("txCategory").value = tx.category_id;
    updateModalSubcategoryDropdown();
    if (tx.subcategory_id) {
        document.getElementById("txSubcategory").value = tx.subcategory_id;
    }
    document.getElementById("txPaymentMethod").value = tx.payment_method || "UPI / Card";
    document.getElementById("txDescription").value = tx.description || "";

    const txCurr = document.getElementById("txCurrency");
    if (txCurr) txCurr.value = tx.original_currency || "INR";
    const previewDiv = document.getElementById("txConvertedPreview");
    if (previewDiv) previewDiv.style.display = "none";

    document.getElementById("txModal").classList.add("show");
}

function closeTxModal() {
    document.getElementById("txModal").classList.remove("show");
}

async function handleTransactionSubmit(e) {
    e.preventDefault();
    const isEdit = !!state.editingTxId;
    const txType = document.querySelector('input[name="txType"]:checked').value;
    const amount = parseFloat(document.getElementById("txAmount").value);
    const currency = document.getElementById("txCurrency")?.value || "INR";
    const category_id = parseInt(document.getElementById("txCategory").value);
    const subcatVal = document.getElementById("txSubcategory").value;
    const subcategory_id = subcatVal ? parseInt(subcatVal) : null;
    const date = document.getElementById("txDate").value;
    const payment_method = document.getElementById("txPaymentMethod").value;
    const description = document.getElementById("txDescription").value.trim();

    const payload = {
        type: txType,
        amount: amount,
        currency: currency,
        category_id: category_id,
        subcategory_id: subcategory_id,
        date: date,
        payment_method: payment_method,
        description: description
    };

    try {
        const url = isEdit ? `/api/transactions/${state.editingTxId}` : "/api/transactions";
        const method = isEdit ? "PUT" : "POST";

        const res = await fetch(url, {
            method: method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) {
            showToast(data.error || "Failed to save transaction", "error");
            return;
        }

        closeTxModal();
        showToast(isEdit ? "Transaction updated!" : `Recorded ₹${formatNumber(data.amount_inr || amount)}!`, "success");

        if (data.alerts && data.alerts.length > 0) {
            data.alerts.forEach(a => {
                showToast(a.message, a.type === "danger" ? "error" : "warning");
            });
        }

        await loadSummary();
        await loadTransactions();
        await loadNotifications(false);
    } catch (err) {
        showToast("Error saving transaction: " + err.message, "error");
    }
}

async function deleteTransaction(id) {
    if (!confirm("Are you sure you want to delete this transaction?")) return;

    try {
        const res = await fetch(`/api/transactions/${id}`, { method: "DELETE" });
        if (res.ok) {
            showToast("Transaction deleted", "success");
            await loadSummary();
            await loadTransactions();
        } else {
            showToast("Failed to delete transaction", "error");
        }
    } catch (e) {
        showToast(e.message, "error");
    }
}

// =============================================================================
// CATEGORIES MANAGEMENT
// =============================================================================
function openAddCategoryModal() {
    document.getElementById("categoryForm").reset();
    document.getElementById("categoryModal").classList.add("show");
}

function closeCategoryModal() {
    document.getElementById("categoryModal").classList.remove("show");
}

async function handleCategorySubmit(e) {
    e.preventDefault();
    const name = document.getElementById("catName").value.trim();
    const type = document.getElementById("catType").value;
    const icon = document.getElementById("catIcon").value.trim() || "🏷️";
    const color = document.getElementById("catColor").value;
    const rawSubs = document.getElementById("catInitialSubs").value;
    const subs = rawSubs.split(",").map(s => s.trim()).filter(Boolean);

    try {
        const res = await fetch("/api/categories", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, type, icon, color, subcategories: subs })
        });
        const data = await res.json();
        if (res.ok) {
            closeCategoryModal();
            showToast("Category created!", "success");
            await loadCategories();
            renderCategoriesManager();
        } else {
            showToast(data.error || "Failed to create category", "error");
        }
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function handleQuickSubcatSubmit(e) {
    e.preventDefault();
    const catId = parseInt(document.getElementById("quickSubcatCategory").value);
    const name = document.getElementById("quickSubcatName").value.trim();
    const desc = document.getElementById("quickSubcatDesc").value.trim();

    try {
        const res = await fetch("/api/subcategories", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ category_id: catId, name, description: desc })
        });
        const data = await res.json();
        if (res.ok) {
            document.getElementById("quickSubcatName").value = "";
            document.getElementById("quickSubcatDesc").value = "";
            showToast("Subcategory added!", "success");
            await loadCategories();
            renderCategoriesManager();
        } else {
            showToast(data.error || "Failed to add subcategory", "error");
        }
    } catch (e) {
        showToast(e.message, "error");
    }
}

function renderCategoriesManager() {
    const list = document.getElementById("categoriesManagementList");
    if (!list) return;

    list.innerHTML = state.categories.map(c => {
        const subsHtml = (c.subcategories && c.subcategories.length > 0)
            ? c.subcategories.map(s => `
                <span class="subcat-pill">
                    ${escapeHtml(s.name)}
                    <button class="del-subcat-btn" title="Delete subcategory" onclick="deleteSubcategory(${s.id})">&times;</button>
                </span>
            `).join("")
            : `<span class="text-muted text-sm">No subcategories defined</span>`;

        return `
            <div class="cat-tree-item">
                <div class="cat-tree-header">
                    <div class="cat-tree-title">
                        <span style="font-size: 18px;">${c.icon || '🏷️'}</span>
                        <span style="color: ${c.color}; font-weight: 800;">${escapeHtml(c.name)}</span>
                        <span class="status-pill ${c.type === 'income' ? 'pill-safe' : 'pill-warning'}">${c.type}</span>
                    </div>
                    <button class="btn-icon-sm text-danger" title="Delete Category" onclick="deleteCategory(${c.id})">🗑️</button>
                </div>
                <div class="cat-sub-tags">
                    ${subsHtml}
                </div>
            </div>
        `;
    }).join("");
}

async function deleteCategory(id) {
    if (!confirm("Are you sure you want to delete this category?")) return;
    try {
        const res = await fetch(`/api/categories/${id}`, { method: "DELETE" });
        const data = await res.json();
        if (res.ok) {
            showToast("Category deleted", "success");
            await loadCategories();
            renderCategoriesManager();
        } else {
            showToast(data.error || "Cannot delete category", "error");
        }
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function deleteSubcategory(id) {
    if (!confirm("Delete this subcategory? Existing transactions will remain.")) return;
    try {
        const res = await fetch(`/api/subcategories/${id}`, { method: "DELETE" });
        if (res.ok) {
            showToast("Subcategory deleted", "success");
            await loadCategories();
            renderCategoriesManager();
        }
    } catch (e) {
        showToast(e.message, "error");
    }
}

// =============================================================================
// ANALYTICS TAB
// =============================================================================
async function loadAnalytics() {
    try {
        const res = await fetch(`/api/analytics?month=${state.selectedMonth}`);
        const data = await res.json();
        renderDetailedAnalytics(data);
    } catch (e) {
        console.error("Analytics load error:", e);
    }
}

function renderDetailedAnalytics(data) {
    const cur = state.currency;

    const subList = document.getElementById("fullSubcategoryBreakdownList");
    if (!data.subcategory_breakdown || data.subcategory_breakdown.length === 0) {
        subList.innerHTML = `<div class="text-center text-muted py-4">No expense breakdown recorded yet for this month.</div>`;
    } else {
        subList.innerHTML = data.subcategory_breakdown.map(s => `
            <div class="subcat-detail-card">
                <div class="subcat-detail-header">
                    <div>
                        <span style="color:${s.category_color};">●</span>
                        <strong>${escapeHtml(s.subcategory_name)}</strong>
                        <span class="text-muted text-sm" style="font-weight: normal;"> (${escapeHtml(s.category_name)})</span>
                    </div>
                    <div>
                        <span class="text-expense font-bold">${cur}${formatNumber(s.amount)}</span>
                        <span class="text-muted text-sm"> (${s.percentage}%)</span>
                    </div>
                </div>
                <div class="progress-bar-bg" style="height: 6px;">
                    <div class="progress-bar-fill" style="width: ${s.percentage}%; background: ${s.category_color};"></div>
                </div>
                <div class="text-muted text-sm mt-2" style="font-size: 11px;">
                    ${s.count} transaction(s) under this subcategory.
                </div>
            </div>
        `).join("");
    }

    const dailyContainer = document.getElementById("dailyTrendChartContainer");
    if (!data.daily_trend || data.daily_trend.length === 0) {
        dailyContainer.innerHTML = `<div class="text-center text-muted full-width py-4">No daily spending recorded yet.</div>`;
    } else {
        const maxDaily = Math.max(...data.daily_trend.map(d => d.amount), 1);
        dailyContainer.innerHTML = data.daily_trend.map(d => {
            const h = (d.amount / maxDaily) * 100;
            const dayNum = d.date.slice(8);
            return `
                <div class="daily-bar-wrap" title="${d.date}: ${cur}${formatNumber(d.amount)}">
                    <div class="daily-bar" style="height: ${Math.max(h, 4)}%;"></div>
                    <span class="daily-bar-label">${dayNum}</span>
                </div>
            `;
        }).join("");
    }

    const histContainer = document.getElementById("history6MonthContainer");
    if (data.history_6_months && data.history_6_months.length > 0) {
        const maxVal = Math.max(...data.history_6_months.map(m => Math.max(m.income, m.expense)), 1);
        histContainer.innerHTML = data.history_6_months.map(m => {
            const incH = (m.income / maxVal) * 100;
            const expH = (m.expense / maxVal) * 100;
            return `
                <div class="history-col">
                    <div class="history-bars-duo">
                        <div class="history-bar-inc" style="height: ${Math.max(incH, 2)}%;" title="Income: ${cur}${formatNumber(m.income)}"></div>
                        <div class="history-bar-exp" style="height: ${Math.max(expH, 2)}%;" title="Expense: ${cur}${formatNumber(m.expense)}"></div>
                    </div>
                    <span class="history-label">${m.label}</span>
                </div>
            `;
        }).join("");
    }
}

// =============================================================================
// EMAIL CONTROL & NOTIFICATIONS
// =============================================================================
async function loadSchedulerStatus() {
    try {
        const res = await fetch("/api/scheduler/status");
        const data = await res.json();

        const badge = document.getElementById("schedulerBadge");
        if (badge) {
            badge.textContent = data.is_running ? "Active" : "Stopped";
            badge.className = `status-pill ${data.is_running ? 'pill-safe' : 'pill-danger'}`;
        }

        const imapStatus = document.getElementById("imapStatusText");
        if (imapStatus) {
            imapStatus.textContent = data.imap_enabled ? `Running (${data.last_imap_status})` : "Disabled in Settings";
            imapStatus.style.color = data.imap_enabled ? "var(--success)" : "var(--text-muted)";
        }

        const lastCheck = document.getElementById("imapLastCheckText");
        if (lastCheck) lastCheck.textContent = data.last_imap_check || "Never";

        const monthlyAuto = document.getElementById("monthlyAutoStatusText");
        if (monthlyAuto) {
            monthlyAuto.textContent = data.monthly_reports_enabled ? "Enabled (1st of month)" : "Disabled";
            monthlyAuto.style.color = data.monthly_reports_enabled ? "var(--success)" : "var(--text-muted)";
        }

        const lastMonthly = document.getElementById("monthlyLastSentText");
        if (lastMonthly) lastMonthly.textContent = data.last_monthly_report_sent || "None";
    } catch (e) {
        console.error("Scheduler status error:", e);
    }
}

async function loadEmailLogs() {
    try {
        const res = await fetch("/api/email/logs");
        const logs = await res.json();
        const tbody = document.getElementById("emailLogsTableBody");
        if (!tbody) return;

        if (!logs || logs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4">No email commands received yet.</td></tr>`;
            return;
        }

        tbody.innerHTML = logs.map(l => `
            <tr>
                <td style="white-space: nowrap;">${l.created_at}</td>
                <td><strong>${escapeHtml(l.sender || '—')}</strong></td>
                <td><code>${escapeHtml(l.command || l.subject || '—')}</code></td>
                <td><span class="status-pill ${l.status === 'SUCCESS' ? 'pill-safe' : 'pill-danger'}">${l.status}</span></td>
                <td><div class="text-sm text-secondary" style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(l.response_msg || '—')}</div></td>
            </tr>
        `).join("");
    } catch (e) {
        console.error("Logs error:", e);
    }
}

async function handleSendReportNow() {
    const feedback = document.getElementById("reportSendFeedback");
    const monthInput = document.getElementById("reportTargetMonth");
    const targetMonth = monthInput?.value || state.selectedMonth;

    feedback.className = "feedback-msg show";
    feedback.textContent = `Compiling financial statement and sending email for ${targetMonth}...`;

    try {
        const res = await fetch("/api/email/send-monthly-report", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ month: targetMonth })
        });
        const data = await res.json();

        if (data.success) {
            feedback.className = "feedback-msg show success";
            feedback.textContent = `✅ ${data.message}`;
            showToast("Monthly statement sent!", "success");
            loadSchedulerStatus();
        } else {
            feedback.className = "feedback-msg show error";
            feedback.textContent = `❌ ${data.message}`;
            showToast(data.message, "error");
        }
    } catch (e) {
        feedback.className = "feedback-msg show error";
        feedback.textContent = `❌ Error: ${e.message}`;
    }
}

async function loadNotifications(showPopups = true) {
    try {
        const res = await fetch("/api/notifications");
        const notifs = await res.json();
        state.notifications = notifs;

        const badge = document.getElementById("notifBadge");
        const unreadCount = notifs.filter(n => n.is_read === 0).length;

        if (unreadCount > 0) {
            badge.style.display = "block";
            badge.textContent = unreadCount > 99 ? "99+" : unreadCount;
        } else {
            badge.style.display = "none";
        }

        const list = document.getElementById("notifList");
        if (notifs.length === 0) {
            list.innerHTML = `<div class="empty-notifs">No notifications</div>`;
            return;
        }

        list.innerHTML = notifs.map(n => {
            const icon = n.type === 'danger' ? '🚨' : (n.type === 'warning' ? '⚠️' : 'ℹ️');
            return `
                <div class="notif-item ${n.is_read === 0 ? 'unread' : ''}">
                    <div class="notif-item-icon">${icon}</div>
                    <div class="notif-item-content">
                        <div class="notif-item-title">${escapeHtml(n.title)}</div>
                        <div class="notif-item-msg">${escapeHtml(n.message)}</div>
                        <div class="notif-item-time">${n.created_at}</div>
                    </div>
                </div>
            `;
        }).join("");
    } catch (e) {
        console.error("Notifications error:", e);
    }
}

// =============================================================================
// SETTINGS FORMS & API
// =============================================================================
async function loadSettings() {
    try {
        const res = await fetch("/api/settings");
        const data = await res.json();
        state.currency = data.currency_symbol || "₹";
    } catch (e) {
        console.error("Settings load error:", e);
    }
}

async function loadSettingsToForm() {
    try {
        const res = await fetch("/api/settings");
        const s = await res.json();

        document.getElementById("settingCurrency").value = s.currency_symbol || "₹";
        document.getElementById("settingUpperLimit").value = s.upper_limit || "25000";
        document.getElementById("settingWarnPct").value = s.upper_limit_warn_pct || "80";
        document.getElementById("settingLowerLimit").value = s.lower_limit || "5000";

        document.getElementById("settingEmailAlerts").checked = s.email_alerts_enabled === "1";
        document.getElementById("settingMonthlyReports").checked = s.monthly_reports_enabled === "1";
        document.getElementById("settingAlertEmail").value = s.alert_email || (state.user ? state.user.email : "");
        document.getElementById("settingSmtpHost").value = s.smtp_host || "smtp.gmail.com";
        document.getElementById("settingSmtpPort").value = s.smtp_port || "587";
        document.getElementById("settingSmtpUser").value = s.smtp_user || (state.user ? state.user.email : "");
        if (s.smtp_pass_masked) {
            document.getElementById("settingSmtpPass").placeholder = s.smtp_pass_masked;
        }

        document.getElementById("settingImapEnabled").checked = s.imap_enabled === "1";
        document.getElementById("settingAuthSender").value = s.authorized_sender || (state.user ? state.user.email : "");
        document.getElementById("settingImapPollInterval").value = s.imap_poll_interval || "60";
        document.getElementById("settingImapHost").value = s.imap_host || "imap.gmail.com";
        document.getElementById("settingImapPort").value = s.imap_port || "993";
        document.getElementById("settingImapUser").value = s.imap_user || (state.user ? state.user.email : "");
        if (s.imap_pass_masked) {
            document.getElementById("settingImapPass").placeholder = s.imap_pass_masked;
        }

        const reportTarget = document.getElementById("reportTargetMonth");
        if (reportTarget) reportTarget.value = state.selectedMonth;
    } catch (e) {
        console.error("Settings form load error:", e);
    }
}

async function handleLimitsSubmit(e) {
    e.preventDefault();
    const payload = {
        currency_symbol: document.getElementById("settingCurrency").value.trim() || "₹",
        upper_limit: document.getElementById("settingUpperLimit").value,
        upper_limit_warn_pct: document.getElementById("settingWarnPct").value,
        lower_limit: document.getElementById("settingLowerLimit").value
    };

    try {
        const res = await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            showToast("Budget limits saved successfully!", "success");
            await loadSummary();
        }
    } catch (err) {
        showToast("Error saving limits: " + err.message, "error");
    }
}

async function handleSmtpSubmit(e) {
    e.preventDefault();
    const payload = {
        email_alerts_enabled: document.getElementById("settingEmailAlerts").checked ? "1" : "0",
        monthly_reports_enabled: document.getElementById("settingMonthlyReports").checked ? "1" : "0",
        alert_email: document.getElementById("settingAlertEmail").value.trim(),
        smtp_host: document.getElementById("settingSmtpHost").value.trim(),
        smtp_port: document.getElementById("settingSmtpPort").value.trim(),
        smtp_user: document.getElementById("settingSmtpUser").value.trim(),
        smtp_pass: document.getElementById("settingSmtpPass").value
    };

    try {
        const res = await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            showToast("SMTP settings saved successfully!", "success");
            loadSchedulerStatus();
        }
    } catch (err) {
        showToast("Error saving SMTP settings: " + err.message, "error");
    }
}

async function handleTestSmtp() {
    const feedback = document.getElementById("smtpTestFeedback");
    feedback.className = "feedback-msg show";
    feedback.textContent = "Connecting to Gmail SMTP server...";

    const payload = {
        smtp_host: document.getElementById("settingSmtpHost").value.trim(),
        smtp_port: document.getElementById("settingSmtpPort").value.trim(),
        smtp_user: document.getElementById("settingSmtpUser").value.trim(),
        smtp_pass: document.getElementById("settingSmtpPass").value,
        alert_email: document.getElementById("settingAlertEmail").value.trim()
    };

    try {
        const res = await fetch("/api/email/test-smtp", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            feedback.className = "feedback-msg show success";
            feedback.textContent = data.message;
            showToast("Test email sent!", "success");
        } else {
            feedback.className = "feedback-msg show error";
            feedback.innerHTML = `<pre style="white-space: pre-wrap; font-family: inherit;">${escapeHtml(data.message)}</pre>`;
            showToast("Gmail test failed", "error");
        }
    } catch (e) {
        feedback.className = "feedback-msg show error";
        feedback.textContent = `❌ Error: ${e.message}`;
    }
}

async function handleImapSubmit(e) {
    e.preventDefault();
    const payload = {
        imap_enabled: document.getElementById("settingImapEnabled").checked ? "1" : "0",
        authorized_sender: document.getElementById("settingAuthSender").value.trim(),
        imap_poll_interval: document.getElementById("settingImapPollInterval").value,
        imap_host: document.getElementById("settingImapHost").value.trim(),
        imap_port: document.getElementById("settingImapPort").value.trim(),
        imap_user: document.getElementById("settingImapUser").value.trim(),
        imap_pass: document.getElementById("settingImapPass").value
    };

    try {
        const res = await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            showToast("IMAP settings saved successfully!", "success");
            loadSchedulerStatus();
        }
    } catch (err) {
        showToast("Error saving IMAP settings: " + err.message, "error");
    }
}

async function handleTestImap() {
    const feedback = document.getElementById("imapTestFeedback");
    feedback.className = "feedback-msg show";
    feedback.textContent = "Connecting to Gmail IMAP server...";

    const payload = {
        imap_host: document.getElementById("settingImapHost").value.trim(),
        imap_port: document.getElementById("settingImapPort").value.trim(),
        imap_user: document.getElementById("settingImapUser").value.trim(),
        imap_pass: document.getElementById("settingImapPass").value
    };

    try {
        const res = await fetch("/api/email/test-imap", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            feedback.className = "feedback-msg show success";
            feedback.textContent = data.message;
            showToast("IMAP connected!", "success");
        } else {
            feedback.className = "feedback-msg show error";
            feedback.innerHTML = `<pre style="white-space: pre-wrap; font-family: inherit;">${escapeHtml(data.message)}</pre>`;
            showToast("IMAP test failed", "error");
        }
    } catch (e) {
        feedback.className = "feedback-msg show error";
        feedback.textContent = `❌ Error: ${e.message}`;
    }
}

// =============================================================================
// UTILITIES
// =============================================================================
function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    const icon = type === "success" ? "✅" : (type === "error" ? "🚨" : "ℹ️");
    toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(20px)";
        toast.style.transition = "all 0.3s ease";
        setTimeout(() => toast.remove(), 300);
    }, 4500);
}

function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) return "0.00";
    return Number(num).toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function debounce(fn, wait) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => fn.apply(this, args), wait);
    };
}
