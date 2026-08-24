/**
 * Shitcoin Sniper Pro - Real-Time Dashboard Client with Strategy Performance Analytics & Growth Charts
 */

// State Store
let botState = {
    config: {},
    state: {
        initial_capital_usd: 1500.0,
        paper_balance_sol: 10.0,
        paper_balance_usd: 1500.0,
        positions: {},
        trade_history: [],
        scanned_tokens: [],
        activity_logs: [],
        stats: {}
    }
};

let activeChainFilter = "all";
let activeTimeframe = "all";
let wsSocket = null;
let reconnectTimer = null;
let equityChart = null;

// DOM Elements
const navTradingMode = document.getElementById("navTradingMode");
const navSolBalance = document.getElementById("navSolBalance");
const navUsdBalance = document.getElementById("navUsdBalance");
const navNetPnl = document.getElementById("navNetPnl");
const navAiSentiment = document.getElementById("navAiSentiment");
const wsStatusDot = document.getElementById("wsStatusDot");
const wsStatusText = document.getElementById("wsStatusText");

const kpiTotalProfitUsd = document.getElementById("kpiTotalProfitUsd");
const kpiWinRate = document.getElementById("kpiWinRate");
const kpiTradesCount = document.getElementById("kpiTradesCount");
const kpiOpenPositionsCount = document.getElementById("kpiOpenPositionsCount");
const kpiOpenPnlUsd = document.getElementById("kpiOpenPnlUsd");
const kpiMinScore = document.getElementById("kpiMinScore");
const kpiMinAiConf = document.getElementById("kpiMinAiConf");

// Performance Analytics Elements
const metricStartingCapital = document.getElementById("metricStartingCapital");
const metricCurrentEquity = document.getElementById("metricCurrentEquity");
const metricPeriodRoi = document.getElementById("metricPeriodRoi");
const metricPeriodRoiLabel = document.getElementById("metricPeriodRoiLabel");
const metricPeriodProfitUsd = document.getElementById("metricPeriodProfitUsd");
const metricWinRateFactor = document.getElementById("metricWinRateFactor");

const btnToggleAutoBuy = document.getElementById("btnToggleAutoBuy");
const btnToggleAiFilter = document.getElementById("btnToggleAiFilter");
const btnPanicSell = document.getElementById("btnPanicSell");
const btnManualSnipe = document.getElementById("btnManualSnipe");
const manualChainSelect = document.getElementById("manualChainSelect");
const manualTokenInput = document.getElementById("manualTokenInput");

const positionsContainer = document.getElementById("positionsContainer");
const activePositionsBadge = document.getElementById("activePositionsBadge");
const scannedTokensTableBody = document.getElementById("scannedTokensTableBody");
const scannedTokensBadge = document.getElementById("scannedTokensBadge");
const tradeHistoryTableBody = document.getElementById("tradeHistoryTableBody");
const tradeHistoryBadge = document.getElementById("tradeHistoryBadge");
const terminalBody = document.getElementById("terminalBody");
const btnClearLogs = document.getElementById("btnClearLogs");

// AI Copilot Elements
const btnOpenAiChat = document.getElementById("btnOpenAiChat");
const aiCopilotDrawer = document.getElementById("aiCopilotDrawer");
const btnCloseAiChat = document.getElementById("btnCloseAiChat");
const copilotMessages = document.getElementById("copilotMessages");
const copilotInput = document.getElementById("copilotInput");
const btnSendCopilot = document.getElementById("btnSendCopilot");
const copilotSentimentText = document.getElementById("copilotSentimentText");

// Modals
const btnOpenSettings = document.getElementById("btnOpenSettings");
const settingsModal = document.getElementById("settingsModal");
const btnCloseSettings = document.getElementById("btnCloseSettings");
const btnCancelSettings = document.getElementById("btnCancelSettings");
const btnSaveSettings = document.getElementById("btnSaveSettings");
const btnResetBalance = document.getElementById("btnResetBalance");

const inspectorModal = document.getElementById("inspectorModal");
const btnCloseInspector = document.getElementById("btnCloseInspector");
const inspectorModalBody = document.getElementById("inspectorModalBody");

// Initialize Application
document.addEventListener("DOMContentLoaded", async () => {
    setupEventListeners();
    await fetchInitialState();
    await fetchMarketSentiment();
    await fetchPerformanceAnalytics(activeTimeframe);
    connectWebSocket();
    setInterval(fetchMarketSentiment, 15000);
    setInterval(() => { fetchPerformanceAnalytics(activeTimeframe); }, 10000);
});

// Setup Event Listeners
function setupEventListeners() {
    // Buttons
    btnToggleAutoBuy.addEventListener("click", toggleAutoBuy);
    btnToggleAiFilter.addEventListener("click", toggleAiFilter);
    btnPanicSell.addEventListener("click", handlePanicSell);
    btnManualSnipe.addEventListener("click", handleManualSnipe);
    btnClearLogs.addEventListener("click", () => { terminalBody.innerHTML = ""; });

    // Timeframe Switcher Tabs
    document.querySelectorAll(".tf-tab-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll(".tf-tab-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            activeTimeframe = btn.getAttribute("data-tf");
            fetchPerformanceAnalytics(activeTimeframe);
        });
    });

    // AI Copilot Chat
    btnOpenAiChat.addEventListener("click", () => {
        aiCopilotDrawer.classList.toggle("show");
        if (aiCopilotDrawer.classList.contains("show")) {
            copilotInput.focus();
        }
    });
    btnCloseAiChat.addEventListener("click", () => { aiCopilotDrawer.classList.remove("show"); });
    btnSendCopilot.addEventListener("click", sendCopilotMessage);
    copilotInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") sendCopilotMessage();
    });

    document.querySelectorAll(".prompt-pill").forEach(pill => {
        pill.addEventListener("click", () => {
            const prompt = pill.getAttribute("data-prompt");
            copilotInput.value = prompt;
            sendCopilotMessage();
        });
    });

    // Settings Modal
    btnOpenSettings.addEventListener("click", openSettingsModal);
    btnCloseSettings.addEventListener("click", closeSettingsModal);
    btnCancelSettings.addEventListener("click", closeSettingsModal);
    btnSaveSettings.addEventListener("click", saveSettings);
    btnResetBalance.addEventListener("click", handleResetBalance);

    const btnToggleKeyVisibility = document.getElementById("btnToggleKeyVisibility");
    if (btnToggleKeyVisibility) {
        btnToggleKeyVisibility.addEventListener("click", () => {
            const input = document.getElementById("cfgSolanaPrivateKey");
            if (input.type === "password") {
                input.type = "text";
                btnToggleKeyVisibility.textContent = "🔒";
            } else {
                input.type = "password";
                btnToggleKeyVisibility.textContent = "👁️";
            }
        });
    }


    // Inspector Modal
    btnCloseInspector.addEventListener("click", () => {
        inspectorModal.classList.remove("show");
    });

    // Chain Filter Chips
    document.querySelectorAll(".chain-chip").forEach(chip => {
        chip.addEventListener("click", (e) => {
            document.querySelectorAll(".chain-chip").forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            activeChainFilter = chip.getAttribute("data-chain");
            renderScannedTokens();
        });
    });
}

// Initial Fetch
async function fetchInitialState() {
    try {
        const res = await fetch("/api/state");
        if (res.ok) {
            const data = await res.json();
            botState = data;
            renderAll();
        }
    } catch (err) {
        console.error("Failed fetching initial state:", err);
    }
}

async function fetchMarketSentiment() {
    try {
        const res = await fetch("/api/ai/market-sentiment");
        if (res.ok) {
            const data = await res.json();
            navAiSentiment.textContent = data.sentiment || "NEUTRAL";
            copilotSentimentText.textContent = `Sentiment: ${data.sentiment} (${data.bullish_pct}% Bullish)`;
        }
    } catch (e) {
        console.debug("Sentiment fetch error:", e);
    }
}

async function fetchPerformanceAnalytics(tf = "all") {
    try {
        const res = await fetch(`/api/analytics/performance?timeframe=${tf}`);
        if (res.ok) {
            const result = await res.json();
            if (result.analytics) {
                renderPerformanceMetrics(result.analytics);
                renderEquityChart(result.analytics.equity_series || []);
            }
        }
    } catch (e) {
        console.error("Performance fetch error:", e);
    }
}

// Real-Time WebSocket Connection
function connectWebSocket() {
    if (wsSocket) {
        try { wsSocket.close(); } catch (e) {}
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    wsSocket = new WebSocket(wsUrl);

    wsSocket.onopen = () => {
        wsStatusDot.className = "status-dot connected";
        wsStatusText.textContent = "24/7 STREAM";
        if (reconnectTimer) {
            clearInterval(reconnectTimer);
            reconnectTimer = null;
        }
    };

    wsSocket.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === "STATE_UPDATE" && msg.data) {
                botState.state = { ...botState.state, ...msg.data };
                if (msg.data.config) {
                    botState.config = { ...botState.config, ...msg.data.config };
                }
                renderAll();
                if (msg.data.performance) {
                    renderPerformanceMetrics(msg.data.performance);
                    renderEquityChart(msg.data.performance.equity_series || []);
                }
            } else if (msg.type === "AUTO_BUY_TOGGLED") {
                botState.config.auto_buy_enabled = msg.auto_buy_enabled;
                renderControlButtons();
            } else if (msg.type === "AI_TOGGLED") {
                botState.config.ai_filtering_enabled = msg.ai_filtering_enabled;
                renderControlButtons();
            } else if (msg.type === "FULL_RESET" || msg.type === "BALANCE_RESET") {
                fetchInitialState();
                fetchPerformanceAnalytics(activeTimeframe);
            }
        } catch (err) {
            console.error("Error parsing WS message:", err);
        }
    };

    wsSocket.onclose = () => {
        wsStatusDot.className = "status-dot disconnected";
        wsStatusText.textContent = "RECONNECTING";
        if (!reconnectTimer) {
            reconnectTimer = setInterval(connectWebSocket, 3000);
        }
    };

    wsSocket.onerror = () => {
        wsSocket.close();
    };
}

// Master Render Method
function renderAll() {
    renderNavbar();
    renderKpis();
    renderControlButtons();
    renderPositions();
    renderScannedTokens();
    renderTradeHistory();
    renderLogs();
}

function renderNavbar() {
    const s = botState.state;
    const c = botState.config;

    navTradingMode.textContent = c.trading_mode === "LIVE" ? "LIVE TRADING" : "PAPER TRADING";
    navTradingMode.className = `chip-value mode-badge ${c.trading_mode === "LIVE" ? "live" : "paper"}`;

    const solBal = (c.trading_mode === "LIVE" && s.live_balance_sol !== undefined) ? s.live_balance_sol : (s.paper_balance_sol || 0);
    const usdBal = (c.trading_mode === "LIVE" && s.live_balance_usd !== undefined) ? s.live_balance_usd : (s.paper_balance_usd || 0);

    navSolBalance.textContent = `${Number(solBal).toFixed(2)} SOL`;
    navUsdBalance.textContent = `$${Number(usdBal).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    const stats = s.stats || {};
    const totalProfit = stats.total_profit_usd || 0;
    const sign = totalProfit >= 0 ? "+" : "";
    navNetPnl.textContent = `${sign}$${totalProfit.toFixed(2)}`;
    navNetPnl.style.color = totalProfit >= 0 ? "var(--neon-green)" : "var(--neon-red)";
}


function renderKpis() {
    const s = botState.state;
    const c = botState.config;
    const stats = s.stats || {};

    const profitUsd = stats.total_profit_usd || 0;
    const sign = profitUsd >= 0 ? "+" : "";
    kpiTotalProfitUsd.textContent = `${sign}$${profitUsd.toFixed(2)}`;
    kpiTotalProfitUsd.className = `kpi-value ${profitUsd >= 0 ? "text-green" : "text-red"}`;

    const totalTrades = stats.total_trades || 0;
    const wins = stats.winning_trades || 0;
    const winRate = totalTrades > 0 ? ((wins / totalTrades) * 100).toFixed(1) : "0.0";
    kpiWinRate.textContent = `${winRate}% Win Rate (${wins}/${totalTrades})`;
    kpiTradesCount.textContent = `${totalTrades} Closed Trades`;

    const positions = Object.values(s.positions || {});
    kpiOpenPositionsCount.textContent = `${positions.length} / ${c.max_open_positions || 30}`;

    let unrealizedPnlUsd = 0;
    positions.forEach(p => { unrealizedPnlUsd += (p.pnl_usd || 0); });
    const uSign = unrealizedPnlUsd >= 0 ? "+" : "";
    kpiOpenPnlUsd.textContent = `${uSign}$${unrealizedPnlUsd.toFixed(2)} Unrealized`;
    kpiOpenPnlUsd.style.color = unrealizedPnlUsd >= 0 ? "var(--neon-green)" : "var(--neon-red)";

    kpiMinScore.textContent = c.min_safety_score || 80;
    kpiMinAiConf.textContent = `${c.min_ai_confidence || 80}%`;
}

function renderPerformanceMetrics(perf) {
    if (!perf) return;

    metricStartingCapital.textContent = `$${(perf.initial_capital_usd || 1500.0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    metricCurrentEquity.textContent = `$${(perf.current_equity_usd || 1500.0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    
    const roi = perf.period_roi_pct || 0.0;
    const rSign = roi >= 0 ? "+" : "";
    metricPeriodRoi.textContent = `${rSign}${roi.toFixed(2)}%`;
    metricPeriodRoi.className = `m-value font-mono ${roi >= 0 ? "text-green" : "text-red"}`;

    const profitUsd = perf.period_profit_usd || 0.0;
    const pSign = profitUsd >= 0 ? "+" : "";
    metricPeriodProfitUsd.textContent = `${pSign}$${profitUsd.toFixed(2)}`;
    metricPeriodProfitUsd.className = `m-value font-mono ${profitUsd >= 0 ? "text-green" : "text-red"}`;

    metricWinRateFactor.textContent = `${(perf.win_rate_pct || 0).toFixed(1)}% (${perf.winning_trades || 0}W/${perf.losing_trades || 0}L) | PF: ${perf.profit_factor || 1.0}x`;

    const tfLabel = {
        "1H": "1 ORĂ ROI (%)",
        "24H": "24 ORE ROI (%)",
        "7D": "7 ZILE ROI (%)",
        "30D": "30 ZILE ROI (%)",
        "ALL": "ALL-TIME GROWTH (%)"
    }[perf.timeframe || "ALL"] || "TIMEFRAME ROI (%)";
    metricPeriodRoiLabel.textContent = tfLabel;
}

function renderEquityChart(series) {
    const ctx = document.getElementById("equityGrowthChart");
    if (!ctx) return;

    if (!series || series.length === 0) {
        series = [{
            time_str: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            total_equity_usd: 1500.0,
            roi_pct: 0.0
        }];
    }

    const labels = series.map(pt => pt.time_str || pt.date_str || "");
    const dataValues = series.map(pt => pt.total_equity_usd || 1500.0);

    if (equityChart) {
        equityChart.data.labels = labels;
        equityChart.data.datasets[0].data = dataValues;
        equityChart.update("none");
        return;
    }

    const chartCtx = ctx.getContext("2d");
    const gradient = chartCtx.createLinearGradient(0, 0, 0, 240);
    gradient.addColorStop(0, "rgba(0, 240, 255, 0.35)");
    gradient.addColorStop(0.5, "rgba(0, 255, 163, 0.15)");
    gradient.addColorStop(1, "rgba(0, 240, 255, 0.0)");

    equityChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [{
                label: "Portfolio Equity (USD)",
                data: dataValues,
                borderColor: "#00f0ff",
                borderWidth: 2.5,
                backgroundColor: gradient,
                fill: true,
                tension: 0.35,
                pointBackgroundColor: "#00ffa3",
                pointBorderColor: "#fff",
                pointRadius: series.length > 30 ? 0 : 3.5,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "rgba(14, 18, 30, 0.95)",
                    titleColor: "#00f0ff",
                    bodyColor: "#fff",
                    borderColor: "rgba(0, 240, 255, 0.4)",
                    borderWidth: 1,
                    padding: 10,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            const val = context.parsed.y;
                            const init = botState.state.initial_capital_usd || 1500.0;
                            const roi = ((val - init) / init) * 100.0;
                            const sign = roi >= 0 ? "+" : "";
                            return `Capital: $${val.toFixed(2)} (${sign}${roi.toFixed(2)}% ROI)`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: "rgba(255, 255, 255, 0.04)" },
                    ticks: {
                        color: "#6b7280",
                        font: { family: "JetBrains Mono", size: 10 },
                        maxTicksLimit: 8
                    }
                },
                y: {
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: {
                        color: "#6b7280",
                        font: { family: "JetBrains Mono", size: 10 },
                        callback: function(value) { return "$" + value; }
                    }
                }
            }
        }
    });
}

function renderControlButtons() {
    const c = botState.config;
    if (c.auto_buy_enabled) {
        btnToggleAutoBuy.textContent = "AUTO-BUY: ON";
        btnToggleAutoBuy.className = "btn-toggle active";
    } else {
        btnToggleAutoBuy.textContent = "AUTO-BUY: PAUSED";
        btnToggleAutoBuy.className = "btn-toggle paused";
    }

    if (c.ai_filtering_enabled) {
        btnToggleAiFilter.textContent = "AI SMART: ON";
        btnToggleAiFilter.className = "btn-toggle active";
    } else {
        btnToggleAiFilter.textContent = "AI SMART: OFF";
        btnToggleAiFilter.className = "btn-toggle paused";
    }
}

function renderPositions() {
    const positions = Object.values(botState.state.positions || {});
    activePositionsBadge.textContent = positions.length;

    if (positions.length === 0) {
        positionsContainer.innerHTML = `
            <div class="empty-state glass-panel">
                <div class="empty-icon">🛰️</div>
                <h3>No Active Positions</h3>
                <p>Scanner is monitoring new pairs 24/7. AI Assistant will auto-snipe tokens with High Momentum & Safety Score ≥ ${botState.config.min_safety_score || 80}.</p>
            </div>
        `;
        return;
    }

    positionsContainer.innerHTML = positions.map(pos => {
        const pnlPct = pos.pnl_pct || 0;
        const pnlUsd = pos.pnl_usd || 0;
        const isProfit = pnlPct >= 0;
        const sign = isProfit ? "+" : "";
        const chainClass = (pos.chain || "solana").toLowerCase();

        return `
            <div class="position-card glass-panel ${isProfit ? 'profit' : 'loss'}">
                <div class="pos-header">
                    <div class="pos-token-meta">
                        <span class="pos-symbol">${escapeHtml(pos.symbol || 'TOKEN')}</span>
                        <span class="chain-tag ${chainClass}">${escapeHtml(pos.chain || 'SOL')}</span>
                        <span class="ai-badge buy">🤖 AI ${pos.ai_signal || 'SMART'}</span>
                        ${pos.break_even_activated ? '<span class="badge-win" style="background: rgba(0, 240, 255, 0.2); border-color: var(--neon-cyan); color: var(--neon-cyan);">🔒 BE LOCKED (+1%)</span>' : ''}
                        <a href="${escapeHtml(pos.url || '#')}" target="_blank" class="btn-text-sm" title="View Chart on DexScreener">📊 Chart</a>
                    </div>
                    <div class="pos-pnl-chip ${isProfit ? 'gain' : 'drop'}">
                        ${sign}${pnlPct.toFixed(2)}% (${sign}$${pnlUsd.toFixed(2)})
                    </div>
                </div>

                <div class="pos-metrics-grid">
                    <div class="pos-metric">
                        <span class="metric-label">Entry Price</span>
                        <span class="metric-val">$${formatPrice(pos.entry_price)}</span>
                    </div>
                    <div class="pos-metric">
                        <span class="metric-label">Current Price</span>
                        <span class="metric-val text-cyan">$${formatPrice(pos.current_price)}</span>
                    </div>
                    <div class="pos-metric">
                        <span class="metric-label">Invested</span>
                        <span class="metric-val">$${(pos.invested_usd || 0).toFixed(2)}</span>
                    </div>
                    <div class="pos-metric">
                        <span class="metric-label">TP Target</span>
                        <span class="metric-val text-green">$${formatPrice(pos.take_profit_target_price)}</span>
                    </div>
                </div>

                <div class="ai-thesis-box">
                    <strong>AI Smart Exit Watch:</strong> ${escapeHtml(pos.ai_thesis || 'Monitorizare dinamică activă pe volum și momentum.')}
                </div>

                <div class="pos-footer">
                    <div class="pos-trailing-bar">
                        Peak: <strong>$${formatPrice(pos.peak_price)}</strong> | Stop: <strong>$${formatPrice(pos.stop_loss_target_price || pos.trailing_stop_price)}</strong>
                    </div>
                    <button class="btn-sell-single" onclick="handleSellPosition('${escapeHtml(pos.token_address)}')">
                        SELL NOW
                    </button>
                </div>
            </div>
        `;
    }).join("");
}

function renderScannedTokens() {
    const tokens = botState.state.scanned_tokens || [];
    scannedTokensBadge.textContent = tokens.length;

    let filtered = tokens;
    if (activeChainFilter !== "all") {
        filtered = tokens.filter(t => (t.chain || "").toLowerCase() === activeChainFilter);
    }

    if (filtered.length === 0) {
        scannedTokensTableBody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted py-6">No discovered tokens match current filter (${activeChainFilter.toUpperCase()}).</td>
            </tr>
        `;
        return;
    }

    scannedTokensTableBody.innerHTML = filtered.map(t => {
        const safety = t.safety || {};
        const score = safety.safety_score !== undefined ? safety.safety_score : 100;
        let scoreClass = "score-safe";
        if (score < 60) scoreClass = "score-risk";
        else if (score < 80) scoreClass = "score-mod";

        const ai = t.ai || {};
        const aiSignal = ai.signal || "WAIT";
        const aiConf = ai.confidence_score !== undefined ? ai.confidence_score : 60;
        let aiBadgeClass = "skip";
        if (aiSignal === "STRONG_BUY") aiBadgeClass = "strong-buy";
        else if (aiSignal === "BUY") aiBadgeClass = "buy";
        else if (aiSignal === "WATCH") aiBadgeClass = "watch";

        const chainClass = (t.chain || "solana").toLowerCase();

        return `
            <tr>
                <td>
                    <div style="font-weight: 700;">${escapeHtml(t.symbol || 'TOKEN')}</div>
                    <div class="text-muted" style="font-size: 10px;">${escapeHtml((t.token_address || '').substring(0, 10))}...</div>
                </td>
                <td><span class="chain-tag ${chainClass}">${escapeHtml(t.chain || 'SOL')}</span></td>
                <td>$${formatPrice(t.price_usd)}</td>
                <td>$${formatNumber(t.liquidity_usd)}</td>
                <td>
                    <span class="ai-badge ${aiBadgeClass}" title="${escapeHtml(ai.thesis || '')}">
                        🤖 ${aiSignal} (${aiConf}%)
                    </span>
                </td>
                <td>
                    <span class="score-pill ${scoreClass}">
                        🛡️ ${score}/100
                    </span>
                </td>
                <td>
                    <div class="table-actions">
                        <button class="btn-table-action" onclick="handleInspectToken('${escapeHtml(t.chain)}', '${escapeHtml(t.token_address)}')">Audit & AI</button>
                        <button class="btn-table-action text-cyan" onclick="handleQuickSnipe('${escapeHtml(t.chain)}', '${escapeHtml(t.token_address)}')">Snipe</button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");
}

function renderTradeHistory() {
    const history = botState.state.trade_history || [];
    tradeHistoryBadge.textContent = history.length;

    if (history.length === 0) {
        tradeHistoryTableBody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted py-6">No closed trades recorded yet.</td>
            </tr>
        `;
        return;
    }

    tradeHistoryTableBody.innerHTML = history.map(t => {
        const isWin = (t.profit_usd || 0) >= 0;
        const sign = isWin ? "+" : "";
        const timeStr = t.closed_at ? new Date(t.closed_at * 1000).toLocaleTimeString() : "--:--";

        let reasonBadge = `<span class="text-muted" style="font-size: 11px;">${escapeHtml(t.exit_reason || 'MANUAL')}</span>`;
        const reason = t.exit_reason || '';
        if (reason.includes('RUG_PULL') || reason.includes('LP Drained')) {
            reasonBadge = `<span class="badge-status-rug" style="background: rgba(255, 0, 85, 0.2); color: #ff0055; border: 1px solid rgba(255, 0, 85, 0.6); font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px; display: inline-block;">💀 RUG-PULL (LP $0)</span>`;
        } else if (reason.includes('TAKE_PROFIT')) {
            reasonBadge = `<span class="badge-status-tp" style="background: rgba(0, 255, 163, 0.15); color: #00ffa3; border: 1px solid rgba(0, 255, 163, 0.5); font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px; display: inline-block;">🎯 TAKE PROFIT</span>`;
        } else if (reason.includes('BREAK_EVEN')) {
            reasonBadge = `<span class="badge-status-be" style="background: rgba(0, 240, 255, 0.15); color: #00f0ff; border: 1px solid rgba(0, 240, 255, 0.5); font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px; display: inline-block;">🔒 BREAK-EVEN</span>`;
        } else if (reason.includes('STOP_LOSS')) {
            reasonBadge = `<span class="badge-status-sl" style="background: rgba(255, 77, 77, 0.15); color: #ff4d4d; border: 1px solid rgba(255, 77, 77, 0.5); font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px; display: inline-block;">🛑 STOP LOSS</span>`;
        } else if (reason.includes('TRAILING_STOP')) {
            reasonBadge = `<span class="badge-status-trailing" style="background: rgba(255, 184, 0, 0.15); color: #ffb800; border: 1px solid rgba(255, 184, 0, 0.5); font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px; display: inline-block;">🛡️ TRAILING STOP</span>`;
        }

        return `
            <tr>
                <td class="text-muted">${timeStr}</td>
                <td><strong>${escapeHtml(t.symbol || 'TOKEN')}</strong> <span class="text-muted" style="font-size: 10px;">(${escapeHtml(t.chain || 'SOL')})</span></td>
                <td>$${formatPrice(t.entry_price)}</td>
                <td>$${formatPrice(t.exit_price)}</td>
                <td class="${isWin ? 'text-green' : 'text-red'}" style="font-weight: 700;">${sign}$${(t.profit_usd || 0).toFixed(2)}</td>
                <td class="${isWin ? 'text-green' : 'text-red'}" style="font-weight: 700;">${sign}${(t.profit_pct || 0).toFixed(2)}%</td>
                <td>${reasonBadge}</td>
            </tr>
        `;
    }).join("");
}


function renderLogs() {
    const logs = botState.state.activity_logs || [];
    if (logs.length === 0) return;

    terminalBody.innerHTML = logs.map(log => {
        let levelClass = "log-info";
        if (log.level === "SUCCESS") levelClass = "log-success";
        else if (log.level === "WARN") levelClass = "log-warn";
        else if (log.level === "ERROR") levelClass = "log-error";

        return `
            <div class="terminal-row ${levelClass}">
                <span class="text-muted">[${escapeHtml(log.timestamp || '')}]</span> ${escapeHtml(log.message || '')}
            </div>
        `;
    }).join("");
}

// User Actions
async function toggleAutoBuy() {
    try {
        const res = await fetch("/api/bot/toggle-auto-buy", { method: "POST" });
        if (res.ok) {
            const data = await res.json();
            botState.config.auto_buy_enabled = data.auto_buy_enabled;
            renderControlButtons();
        }
    } catch (e) {
        console.error(e);
    }
}

async function toggleAiFilter() {
    try {
        const res = await fetch("/api/ai/toggle-ai-sniper", { method: "POST" });
        if (res.ok) {
            const data = await res.json();
            botState.config.ai_filtering_enabled = data.ai_filtering_enabled;
            renderControlButtons();
        }
    } catch (e) {
        console.error(e);
    }
}

async function sendCopilotMessage() {
    const msg = copilotInput.value.trim();
    if (!msg) return;

    const userBubble = document.createElement("div");
    userBubble.className = "copilot-msg user-msg";
    userBubble.textContent = msg;
    copilotMessages.appendChild(userBubble);
    copilotInput.value = "";
    copilotMessages.scrollTop = copilotMessages.scrollHeight;

    const thinkingBubble = document.createElement("div");
    thinkingBubble.className = "copilot-msg ai-msg";
    thinkingBubble.innerHTML = "<em>AI Copilot analizează datele pieței...</em>";
    copilotMessages.appendChild(thinkingBubble);
    copilotMessages.scrollTop = copilotMessages.scrollHeight;

    try {
        const res = await fetch("/api/ai/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: msg })
        });
        if (res.ok) {
            const data = await res.json();
            thinkingBubble.innerHTML = data.reply || "Răspuns indisponibil.";
        } else {
            thinkingBubble.textContent = "Eroare la procesarea cererii AI.";
        }
    } catch (e) {
        thinkingBubble.textContent = `Eroare: ${e.message}`;
    }
    copilotMessages.scrollTop = copilotMessages.scrollHeight;
}

async function handlePanicSell() {
    if (!confirm("🚨 ARE YOU SURE? This will emergency market sell all active positions!")) return;
    try {
        btnPanicSell.disabled = true;
        btnPanicSell.textContent = "CLOSING...";
        const res = await fetch("/api/bot/panic-sell-all", { method: "POST" });
        if (res.ok) {
            await fetchInitialState();
            await fetchPerformanceAnalytics(activeTimeframe);
        }
    } catch (e) {
        console.error(e);
    } finally {
        btnPanicSell.disabled = false;
        btnPanicSell.textContent = "🚨 PANIC SELL ALL";
    }
}

async function handleManualSnipe() {
    const address = manualTokenInput.value.trim();
    const chain = manualChainSelect.value;
    if (!address) {
        alert("Please enter a token contract address.");
        return;
    }

    try {
        btnManualSnipe.disabled = true;
        btnManualSnipe.textContent = "SNIPING...";
        const res = await fetch("/api/trade/buy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                token_address: address,
                chain: chain,
                amount_usd: botState.config.buy_amount_usd || 15.0
            })
        });

        if (!res.ok) {
            const err = await res.json();
            alert(`Snipe Failed: ${err.detail || "Unknown error"}`);
        } else {
            manualTokenInput.value = "";
            await fetchInitialState();
            await fetchPerformanceAnalytics(activeTimeframe);
        }
    } catch (e) {
        alert(`Error executing snipe: ${e.message}`);
    } finally {
        btnManualSnipe.disabled = false;
        btnManualSnipe.textContent = "SNIPE";
    }
}

window.handleQuickSnipe = async function(chain, address) {
    if (!confirm(`Confirm snipe for ${address} on ${chain.toUpperCase()} ($${botState.config.buy_amount_usd || 15})?`)) return;
    try {
        const res = await fetch("/api/trade/buy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                token_address: address,
                chain: chain,
                amount_usd: botState.config.buy_amount_usd || 15.0
            })
        });
        if (!res.ok) {
            const err = await res.json();
            alert(`Snipe Failed: ${err.detail}`);
        } else {
            await fetchInitialState();
            await fetchPerformanceAnalytics(activeTimeframe);
        }
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
};

window.handleSellPosition = async function(tokenAddress) {
    if (!confirm(`Sell position for ${tokenAddress}?`)) return;
    try {
        const res = await fetch("/api/trade/sell", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token_address: tokenAddress })
        });
        if (!res.ok) {
            const err = await res.json();
            alert(`Sell Failed: ${err.detail}`);
        } else {
            await fetchInitialState();
            await fetchPerformanceAnalytics(activeTimeframe);
        }
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
};

window.handleInspectToken = async function(chain, address) {
    inspectorModal.classList.add("show");
    inspectorModalBody.innerHTML = `
        <div style="text-align: center; padding: 40px;">
            <div style="font-size: 28px; margin-bottom: 12px;">🧠</div>
            <h3>Running Deep Anti-Rug & AI Momentum Audit...</h3>
            <p class="text-muted">Evaluating Buy/Sell Pressure, Mint/Freeze Authorities, and Synthesizing AI Trade Thesis...</p>
        </div>
    `;

    try {
        const res = await fetch(`/api/token/inspect/${chain}/${address}`);
        if (res.ok) {
            const data = await res.json();
            renderInspectionReport(data);
        } else {
            inspectorModalBody.innerHTML = `<div class="text-red">Failed to audit token: Unable to retrieve contract metadata.</div>`;
        }
    } catch (e) {
        inspectorModalBody.innerHTML = `<div class="text-red">Inspection error: ${e.message}</div>`;
    }
};

function renderInspectionReport(data) {
    const t = data.token || {};
    const s = data.safety || {};
    const ai = data.ai || {};
    const score = s.safety_score !== undefined ? s.safety_score : 100;
    const aiSignal = ai.signal || "WAIT";
    const aiConf = ai.confidence_score || 70;

    inspectorModalBody.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border-glass); padding-bottom: 16px;">
            <div>
                <h2 style="font-size: 20px;">${escapeHtml(t.name || 'Token')} (${escapeHtml(t.symbol || 'SYM')})</h2>
                <div class="text-muted font-mono" style="font-size: 11px;">${escapeHtml(s.token_address || '')}</div>
            </div>
            <div style="display: flex; gap: 8px; align-items: center;">
                <span class="ai-badge ${aiSignal === 'STRONG_BUY' ? 'strong-buy' : (aiSignal === 'BUY' ? 'buy' : 'watch')}" style="font-size: 14px; padding: 6px 12px;">
                    🤖 AI: ${aiSignal} (${aiConf}%)
                </span>
                <span class="score-pill ${score >= 80 ? 'score-safe' : (score >= 60 ? 'score-mod' : 'score-risk')}" style="font-size: 14px; padding: 6px 12px;">
                    🛡️ Safety: ${score}/100
                </span>
            </div>
        </div>

        <div style="background: rgba(0, 240, 255, 0.06); border: 1px solid rgba(0, 240, 255, 0.2); border-radius: 8px; padding: 14px; margin-bottom: 20px;">
            <h4 style="font-size: 12px; color: var(--neon-cyan); margin-bottom: 4px; text-transform: uppercase; font-family: var(--font-mono);">💡 AI Trade Thesis & Momentum Analysis</h4>
            <p style="font-size: 13px; color: #f0f6fc; line-height: 1.5;">${escapeHtml(ai.thesis || 'Momentum de piață în analiză.')}</p>
        </div>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 20px;">
            <div class="pos-metric glass-panel" style="padding: 10px;">
                <span class="metric-label">Buy / Sell Pressure</span>
                <span class="metric-val text-green">${(ai.buy_ratio_pct || 50).toFixed(0)}% Buys</span>
            </div>
            <div class="pos-metric glass-panel" style="padding: 10px;">
                <span class="metric-label">Volume Velocity</span>
                <span class="metric-val text-cyan">${(ai.volume_spike_ratio || 1.0).toFixed(1)}x Normal</span>
            </div>
            <div class="pos-metric glass-panel" style="padding: 10px;">
                <span class="metric-label">Liquidity</span>
                <span class="metric-val text-cyan">$${formatNumber(s.liquidity_usd || t.liquidity_usd)}</span>
            </div>
            <div class="pos-metric glass-panel" style="padding: 10px;">
                <span class="metric-label">LP Burned / Locked</span>
                <span class="metric-val text-green">${(s.lp_burned_pct || 100).toFixed(1)}%</span>
            </div>
            <div class="pos-metric glass-panel" style="padding: 10px;">
                <span class="metric-label">Mint Authority</span>
                <span class="metric-val ${s.mint_auth_disabled ? 'text-green' : 'text-red'}">${s.mint_auth_disabled ? 'DISABLED (Safe)' : 'ACTIVE (Risky)'}</span>
            </div>
            <div class="pos-metric glass-panel" style="padding: 10px;">
                <span class="metric-label">Freeze Authority</span>
                <span class="metric-val ${s.freeze_auth_disabled ? 'text-green' : 'text-red'}">${s.freeze_auth_disabled ? 'DISABLED (Safe)' : 'ACTIVE (Risky)'}</span>
            </div>
        </div>

        <div style="margin-bottom: 20px;">
            <h4 style="font-size: 13px; color: var(--text-secondary); margin-bottom: 8px;">SECURITY AUDIT WARNINGS & FLAGS</h4>
            ${s.warnings && s.warnings.length > 0 ? `
                <ul style="list-style: none; display: flex; flex-direction: column; gap: 6px;">
                    ${s.warnings.map(w => `<li style="background: rgba(255, 51, 102, 0.12); border-left: 3px solid var(--neon-red); padding: 6px 12px; font-size: 12px; border-radius: 4px; color: #ffb8c6;">⚠️ ${escapeHtml(w)}</li>`).join("")}
                </ul>
            ` : `<div style="background: rgba(0, 255, 163, 0.1); border-left: 3px solid var(--neon-green); padding: 8px 12px; font-size: 12px; border-radius: 4px; color: #a7f3d0;">✅ No critical security threats or honeypot indicators detected.</div>`}
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 10px;">
            <a href="${escapeHtml(t.url || '#')}" target="_blank" class="btn-secondary" style="text-decoration: none;">View DexScreener</a>
            <button class="btn-cyber-primary" onclick="handleQuickSnipe('${escapeHtml(s.chain || 'solana')}', '${escapeHtml(s.token_address)}'); inspectorModal.classList.remove('show');">SNIPE THIS TOKEN</button>
        </div>
    `;
}

// Settings Modal Management
function openSettingsModal() {
    const c = botState.config;
    document.getElementById("cfgTradingMode").value = c.trading_mode || "PAPER";
    document.getElementById("cfgAiFiltering").value = c.ai_filtering_enabled !== false ? "true" : "false";
    document.getElementById("cfgMinAiConfidence").value = c.min_ai_confidence || 80;
    document.getElementById("cfgAiSmartExit").value = c.ai_smart_exit_enabled !== false ? "true" : "false";
    document.getElementById("cfgBreakEvenEnabled").value = c.break_even_enabled !== false ? "true" : "false";
    document.getElementById("cfgBreakEvenTriggerPct").value = c.break_even_trigger_percent || 6.0;
    document.getElementById("cfgBuyAmountUsd").value = c.buy_amount_usd || 15.0;
    document.getElementById("cfgMaxOpenPositions").value = c.max_open_positions || 30;
    document.getElementById("cfgTakeProfitPct").value = c.take_profit_percent || 18.0;
    document.getElementById("cfgTrailingStopOffsetPct").value = c.trailing_stop_offset_percent || 5.0;
    document.getElementById("cfgStopLossPct").value = c.stop_loss_percent || 12.0;
    document.getElementById("cfgMinSafetyScore").value = c.min_safety_score || 60;
    document.getElementById("cfgMinLiquidityUsd").value = c.min_liquidity_usd || 3500;
    document.getElementById("cfgMaxDevHoldingPct").value = c.max_dev_holding_percent || 20.0;

    const keyInput = document.getElementById("cfgSolanaPrivateKey");
    if (keyInput) {
        keyInput.value = "";
        keyInput.placeholder = c.has_solana_private_key ? "•••••••• (Cheia Solana este activă și securizată)" : "Base58 Private Key sau 12 cuvinte recovery phrase...";
    }

    settingsModal.classList.add("show");
}

function closeSettingsModal() {
    settingsModal.classList.remove("show");
}

async function saveSettings() {
    const keyVal = document.getElementById("cfgSolanaPrivateKey") ? document.getElementById("cfgSolanaPrivateKey").value.trim() : "";
    const updated = {
        trading_mode: document.getElementById("cfgTradingMode").value,
        auto_buy_enabled: botState.config.auto_buy_enabled,
        scanner_active: botState.config.scanner_active,
        ai_filtering_enabled: document.getElementById("cfgAiFiltering").value === "true",
        min_ai_confidence: parseInt(document.getElementById("cfgMinAiConfidence").value) || 65,
        ai_smart_exit_enabled: document.getElementById("cfgAiSmartExit").value === "true",
        break_even_enabled: document.getElementById("cfgBreakEvenEnabled").value === "true",
        break_even_trigger_percent: parseFloat(document.getElementById("cfgBreakEvenTriggerPct").value) || 6.0,
        break_even_offset_percent: 1.0,
        buy_amount_usd: parseFloat(document.getElementById("cfgBuyAmountUsd").value) || 8.0,
        buy_amount_sol: 0.08,
        max_open_positions: parseInt(document.getElementById("cfgMaxOpenPositions").value) || 30,
        take_profit_percent: parseFloat(document.getElementById("cfgTakeProfitPct").value) || 18.0,
        trailing_stop_enabled: true,
        trailing_stop_offset_percent: parseFloat(document.getElementById("cfgTrailingStopOffsetPct").value) || 5.0,
        stop_loss_percent: parseFloat(document.getElementById("cfgStopLossPct").value) || 12.0,
        max_hold_time_minutes: botState.config.max_hold_time_minutes || 60,
        min_liquidity_usd: parseFloat(document.getElementById("cfgMinLiquidityUsd").value) || 3500.0,
        min_volume_usd: botState.config.min_volume_usd || 500.0,
        max_dev_holding_percent: parseFloat(document.getElementById("cfgMaxDevHoldingPct").value) || 20.0,
        max_buy_tax_percent: botState.config.max_buy_tax_percent || 5.0,
        max_sell_tax_percent: botState.config.max_sell_tax_percent || 5.0,
        min_safety_score: parseInt(document.getElementById("cfgMinSafetyScore").value) || 60
    };

    if (keyVal) {
        updated.solana_private_key = keyVal;
    }


    try {
        const res = await fetch("/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(updated)
        });
        if (res.ok) {
            botState.config = { ...botState.config, ...updated };
            closeSettingsModal();
            renderAll();
            fetchPerformanceAnalytics(activeTimeframe);
        }
    } catch (e) {
        alert(`Error saving config: ${e.message}`);
    }
}

async function handleResetBalance() {
    const sol = parseFloat(document.getElementById("resetSolInput").value) || 10.0;
    const usd = parseFloat(document.getElementById("resetUsdInput").value) || 1500.0;

    if (!confirm(`Are you sure you want to perform a FULL RESET? This will clear all open positions, reset all trade history, and reset balances to ${sol} SOL / $${usd} USD (PnL = $0.00).`)) {
        return;
    }

    try {
        const res = await fetch("/api/bot/full-reset", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sol, usd })
        });
        if (res.ok) {
            await fetchInitialState();
            await fetchPerformanceAnalytics(activeTimeframe);
            closeSettingsModal();
            alert("Full system reset executed successfully! Balances and PnL reset to 0.");
        }
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

// Helpers
function formatPrice(val) {
    if (val === undefined || val === null || isNaN(val)) return "0.00";
    const num = Number(val);
    if (num >= 1) return num.toFixed(4);
    if (num >= 0.0001) return num.toFixed(6);
    return num.toFixed(8);
}

function formatNumber(val) {
    if (!val) return "0";
    const num = Number(val);
    if (num >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
    if (num >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
    return num.toFixed(0);
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
