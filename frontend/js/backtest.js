// CryptoSignalPro AI - Strateji Backtest Laboratuvarı JS Mantığı (v5.0.0)
let currentBacktestData = null;
let currentCandlesData = [];
let selectedStrategyTrades = [];

document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();

    setInterval(updateClock, 1000);
    updateClock();

    // URL parametrelerini oku (örn: /backtest.html?symbol=BTC/USDT&timeframe=1h)
    const urlParams = new URLSearchParams(window.location.search);
    const urlSym = urlParams.get('symbol');
    const initialTf = urlParams.get('timeframe') || '1h';

    const symbolInput = document.getElementById('symbolInput');
    const tfSelect = document.getElementById('timeframeSelect');
    const lookbackSelect = document.getElementById('lookbackSelect');
    const runBtn = document.getElementById('runBacktestBtn');

    if (symbolInput && urlSym) {
        symbolInput.value = urlSym.replace('/', '');
    }
    if (tfSelect) tfSelect.value = initialTf;

    if (runBtn) {
        runBtn.addEventListener('click', () => {
            fetchAndRenderBacktest();
        });
    }

    if (symbolInput) {
        symbolInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                fetchAndRenderBacktest();
            }
        });
    }

    if (tfSelect) {
        tfSelect.addEventListener('change', () => {
            fetchAndRenderBacktest();
        });
    }

    if (lookbackSelect) {
        lookbackSelect.addEventListener('change', () => {
            fetchAndRenderBacktest();
        });
    }

    // Escape tuşu ile modali kapat
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeTradeDetailModal();
        }
    });

    // İlk yüklemede otomatik testi başlat
    fetchAndRenderBacktest();
});

function updateClock() {
    const clockEl = document.getElementById('labLiveClock');
    if (clockEl) {
        const now = new Date();
        clockEl.textContent = now.toLocaleTimeString('tr-TR', { hour12: false }) + ' UTC+3';
    }
}

function switchSymbol(sym) {
    const symbolInput = document.getElementById('symbolInput');
    if (symbolInput) {
        symbolInput.value = sym.replace('/', '');
        fetchAndRenderBacktest();
    }
}

async function fetchAndRenderBacktest() {
    const symbolInput = document.getElementById('symbolInput');
    const tfSelect = document.getElementById('timeframeSelect');
    const lookbackSelect = document.getElementById('lookbackSelect');
    const runBtn = document.getElementById('runBacktestBtn');
    const loadingState = document.getElementById('loadingState');
    const resultsContent = document.getElementById('resultsContent');

    let symbol = symbolInput ? symbolInput.value.trim().toUpperCase() : 'BTC';
    if (!symbol) symbol = 'BTC';
    if (!symbol.endsWith('USDT')) symbol = `${symbol}USDT`;
    
    const formattedSym = symbol.endsWith('/USDT') ? symbol : `${symbol.replace('USDT', '')}/USDT`;
    const tf = tfSelect ? tfSelect.value : '1h';
    const lookback = lookbackSelect ? parseInt(lookbackSelect.value) : 500;

    if (runBtn) {
        runBtn.disabled = true;
        runBtn.innerHTML = `<div class="w-4 h-4 border-2 border-gray-950 border-t-transparent rounded-full animate-spin"></div> <span>TEST EDİLİYOR...</span>`;
    }

    if (loadingState) loadingState.classList.remove('hidden');
    if (resultsContent) resultsContent.classList.add('hidden');

    try {
        const res = await fetch(`/api/backtest/${encodeURIComponent(formattedSym)}?timeframe=${tf}&limit=${lookback}`);
        const data = await res.json();

        if (data.status === 'success') {
            currentBacktestData = data;
            currentCandlesData = data.candles || [];
            renderAllResults(data);
            if (loadingState) loadingState.classList.add('hidden');
            if (resultsContent) resultsContent.classList.remove('hidden');
            lucide.createIcons();
        } else {
            showToast('Hata', 'Strateji testi verisi alınamadı.', true);
            if (loadingState) loadingState.classList.add('hidden');
        }
    } catch (err) {
        console.error('Backtest error:', err);
        showToast('Bağlantı Hatası', 'API sunucusuna ulaşılamadı.', true);
        if (loadingState) loadingState.classList.add('hidden');
    } finally {
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.innerHTML = `<i data-lucide="play" class="w-4 h-4 text-gray-950 fill-current"></i> <span>TÜM 12 STRATEJİYİ TEST ET (RUN BACKTEST)</span>`;
            lucide.createIcons();
        }
    }
}

// Equity curve chart instance
let equityChartInstance = null;
// State for show-all vs recent trades toggle
let showingAllTrades = false;
let currentStrategyForTrades = null;

function renderAllResults(data) {
    const champ = data.champion_strategy || (data.leaderboard && data.leaderboard[0]);
    const leaderboard = data.leaderboard || [];

    // 1. Şampiyon Strateji Afişi
    const heroName = document.getElementById('heroStrategyName') || document.getElementById('heroChampName');
    const heroCat = document.getElementById('heroStrategyCategory') || document.getElementById('heroChampCategory');
    const heroDesc = document.getElementById('heroStrategyDesc') || document.getElementById('heroChampCategory');
    const heroWin = document.getElementById('heroWinRate');
    const heroNet = document.getElementById('heroNetProfit');
    const heroPf = document.getElementById('heroPF');
    const heroTrades = document.getElementById('heroTrades');
    const heroTp1 = document.getElementById('heroTp1Rate');
    const heroTp2 = document.getElementById('heroTp2Rate');
    const heroTp3 = document.getElementById('heroTp3Rate');
    const heroSharpe = document.getElementById('heroSharpe');
    const heroMaxConsec = document.getElementById('heroMaxConsecLoss');

    if (champ) {
        if (heroName) heroName.textContent = `${champ.name} (${champ.name_en || ''})`;
        if (heroCat) heroCat.textContent = `${champ.category} • Son ${data.lookback_candles || 500} Mum`;
        if (heroDesc) heroDesc.textContent = `Geçmiş ${data.lookback_candles || 500} mum boyunca en yüksek başarı oranı ve getiri sağlayan şampiyon strateji.`;
        // Fix: Use strict comparison to prevent 0 being treated as falsy
        if (heroWin) heroWin.textContent = `%${champ.tp2_win_rate != null ? champ.tp2_win_rate : (champ.win_rate || 0)}`;
        if (heroNet) {
            heroNet.textContent = `${champ.net_profit_pct > 0 ? '+' : ''}%${champ.net_profit_pct || 0}`;
            heroNet.className = (champ.net_profit_pct || 0) >= 0 ? 'text-lg font-black text-emerald-400 mt-0.5' : 'text-lg font-black text-rose-400 mt-0.5';
        }
        if (heroPf) heroPf.textContent = `${champ.profit_factor || 0.0}`;
        if (heroTrades) heroTrades.textContent = `${champ.total_trades || 0} (${champ.wins || 0}W / ${champ.losses || 0}L)`;
        if (heroTp1) heroTp1.textContent = `%${champ.tp1_win_rate || 0}`;
        if (heroTp2) heroTp2.textContent = `%${champ.tp2_win_rate != null ? champ.tp2_win_rate : (champ.win_rate || 0)}`;
        if (heroTp3) heroTp3.textContent = `%${champ.tp3_win_rate || 0}`;
        // NEW: Sharpe & Max Consecutive Loss
        if (heroSharpe) heroSharpe.textContent = `${champ.sharpe_ratio != null ? champ.sharpe_ratio : '—'}`;
        if (heroMaxConsec) heroMaxConsec.textContent = `${champ.max_consecutive_losses != null ? champ.max_consecutive_losses : '—'}`;

        // Equity Curve
        const equityCurve = champ.equity_curve || [];
        renderEquityCurve(equityCurve, champ.net_profit_pct || 0, champ.max_drawdown_pct || 0);

        // Avg hold badge
        const avgHoldBadge = document.getElementById('avgHoldBadge');
        if (avgHoldBadge && champ.avg_hold_bars != null) {
            avgHoldBadge.textContent = `⏱️ Ort. Hold: ${champ.avg_hold_bars} bar`;
            avgHoldBadge.classList.remove('hidden');
        }
    } else {
        if (heroName) heroName.textContent = "Yeterli İşlem Örneği Bulunamadı";
        if (heroCat) heroCat.textContent = "Mum aralığını veya zaman dilimini artırmayı deneyin.";
        if (heroWin) heroWin.textContent = "%0";
        if (heroNet) heroNet.textContent = "%0";
        if (heroPf) heroPf.textContent = "0.0";
        if (heroTrades) heroTrades.textContent = "0";
        if (heroTp1) heroTp1.textContent = "%0";
        if (heroTp2) heroTp2.textContent = "%0";
        if (heroTp3) heroTp3.textContent = "%0";
        if (heroSharpe) heroSharpe.textContent = "—";
        if (heroMaxConsec) heroMaxConsec.textContent = "—";
    }

    renderLeaderboardRows(leaderboard);

    // Varsayılan olarak şampiyon stratejinin son 15 işlemini göster
    showingAllTrades = false;
    currentStrategyForTrades = champ;
    if (champ && champ.recent_trades && champ.recent_trades.length > 0) {
        renderTradesTable(champ.recent_trades, champ.name);
        updateTradesCountInfo(champ.recent_trades.length, (champ.all_trades || []).length);
    } else if (leaderboard.length > 0 && leaderboard[0].recent_trades) {
        currentStrategyForTrades = leaderboard[0];
        renderTradesTable(leaderboard[0].recent_trades, leaderboard[0].name);
        updateTradesCountInfo(leaderboard[0].recent_trades.length, (leaderboard[0].all_trades || []).length);
    } else {
        renderTradesTable([], "Strateji");
    }
}

function updateTradesCountInfo(showing, total) {
    const el = document.getElementById('tradesCountInfo');
    if (el) {
        el.textContent = showing < total ? `Son ${showing} işlem (Toplam ${total})` : `Tüm ${total} işlem`;
    }
}

function toggleAllTrades() {
    if (!currentStrategyForTrades) return;
    showingAllTrades = !showingAllTrades;
    const btn = document.getElementById('showAllTradesBtn');
    const trades = showingAllTrades 
        ? (currentStrategyForTrades.all_trades || currentStrategyForTrades.recent_trades || [])
        : (currentStrategyForTrades.recent_trades || []);
    const total = (currentStrategyForTrades.all_trades || currentStrategyForTrades.recent_trades || []).length;
    renderTradesTable(trades, currentStrategyForTrades.name);
    updateTradesCountInfo(trades.length, total);
    if (btn) {
        const span = btn.querySelector('span');
        if (span) span.textContent = showingAllTrades ? 'Son 15\'i Göster' : 'Tümünü Göster';
    }
    lucide.createIcons();
}

function exportTradesToCSV() {
    if (!currentStrategyForTrades) { showToast('Uyarı', 'Önce bir strateji seçin.', true); return; }
    const trades = currentStrategyForTrades.all_trades || currentStrategyForTrades.recent_trades || [];
    if (!trades.length) { showToast('Uyarı', 'Export edilecek işlem bulunamadı.', true); return; }
    
    const headers = ['Giriş Zamanı', 'Çıkış Zamanı', 'Yön', 'Giriş Fiyatı', 'Stop Loss', 'TP1', 'TP2', 'TP3', 'Çıkış Fiyatı', 'Kâr/Zarar %', 'Sonuç', 'Çıkış Nedeni'];
    const rows = trades.map(t => [
        t.entry_time, t.exit_time, t.direction,
        t.entry_price, t.stop_loss, t.tp1 || '', t.tp2 || '', t.tp3 || '',
        t.exit_price, t.pnl_pct, t.is_win ? 'KÂR' : 'ZARAR', t.exit_reason
    ]);
    
    const csvContent = [headers, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' }); // BOM for Excel
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backtest_${currentStrategyForTrades.id || 'strategy'}_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('CSV İndirildi', `${trades.length} işlem kaydı Excel'e uyumlu CSV formatında indirildi.`);
}

function renderEquityCurve(equityPoints, finalPnl, maxDD) {
    const canvas = document.getElementById('equityCurveChart');
    if (!canvas) return;

    // Destroy previous chart
    if (equityChartInstance) {
        equityChartInstance.destroy();
        equityChartInstance = null;
    }

    const finalPnlEl = document.getElementById('equityFinalPnl');
    const maxDDEl = document.getElementById('equityMaxDD');
    if (finalPnlEl) {
        finalPnlEl.textContent = `${finalPnl >= 0 ? '+' : ''}%${finalPnl}`;
        finalPnlEl.className = finalPnl >= 0
            ? 'px-2.5 py-1 rounded-lg bg-emerald-500/15 text-emerald-400 font-bold border border-emerald-500/30 font-mono'
            : 'px-2.5 py-1 rounded-lg bg-rose-500/15 text-rose-400 font-bold border border-rose-500/30 font-mono';
    }
    if (maxDDEl) maxDDEl.textContent = `DD: -%${maxDD}`;

    if (!equityPoints || equityPoints.length < 2) {
        document.getElementById('equityChartEmpty')?.classList.remove('hidden');
        return;
    }
    document.getElementById('equityChartEmpty')?.classList.add('hidden');

    const labels = equityPoints.map((_, i) => i === 0 ? 'Başlangıç' : `İşlem ${i}`);
    const isPositive = equityPoints[equityPoints.length - 1] >= 0;
    const lineColor = isPositive ? '#10b981' : '#ef4444';
    const fillColor = isPositive ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)';

    equityChartInstance = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Kümülatif Kâr/Zarar (%)',
                data: equityPoints,
                borderColor: lineColor,
                backgroundColor: fillColor,
                borderWidth: 2,
                fill: true,
                tension: 0.3,
                pointRadius: equityPoints.length > 50 ? 0 : 3,
                pointBackgroundColor: lineColor,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#0f141f',
                    borderColor: '#1e293b',
                    borderWidth: 1,
                    titleColor: '#94a3b8',
                    bodyColor: '#e2e8f0',
                    callbacks: {
                        label: ctx => ` ${ctx.parsed.y >= 0 ? '+' : ''}%${ctx.parsed.y.toFixed(2)}`
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#4b5563', maxTicksLimit: 10, font: { family: 'JetBrains Mono', size: 10 } },
                    grid: { color: 'rgba(30, 41, 59, 0.4)' }
                },
                y: {
                    ticks: {
                        color: '#4b5563',
                        font: { family: 'JetBrains Mono', size: 10 },
                        callback: v => `%${v}`
                    },
                    grid: { color: 'rgba(30, 41, 59, 0.4)' }
                }
            },
            interaction: { mode: 'index', intersect: false }
        }
    });
}



let activeCategoryFilter = 'ALL';

function filterLeaderboard(cat) {
    activeCategoryFilter = cat;
    ['ALL', 'PATTERNS', 'CUSTOM', 'SMC'].forEach(c => {
        const btn = document.getElementById(`filterBtn${c}`);
        if (btn) {
            if (c === cat) {
                btn.className = "px-2.5 py-1 rounded-lg bg-amber-500 text-gray-950 font-bold text-[11px] cursor-pointer transition";
            } else {
                btn.className = "px-2.5 py-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 font-bold text-[11px] cursor-pointer transition";
            }
        }
    });
    if (currentBacktestData && currentBacktestData.leaderboard) {
        renderLeaderboardRows(currentBacktestData.leaderboard);
    }
}

function renderLeaderboardRows(leaderboard) {
    const tbody = document.getElementById('leaderboardTbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    const filtered = leaderboard.filter(s => {
        if (activeCategoryFilter === 'ALL') return true;
        if (activeCategoryFilter === 'PATTERNS') {
            return s.id.includes('trendline') || s.id.includes('triangle') || s.id.includes('sr_flip') || s.id.includes('range') || s.id.includes('double') || s.id.includes('chart_patterns');
        }
        if (activeCategoryFilter === 'CUSTOM') {
            return s.id.includes('pdh_pdl') || s.id.includes('swing_hl');
        }
        if (activeCategoryFilter === 'SMC') {
            return s.id.includes('smc');
        }
        return true;
    });

    filtered.forEach((s, idx) => {
        const isChamp = idx === 0 && s.total_trades >= 1 && activeCategoryFilter === 'ALL';
        const rankBadge = isChamp 
            ? '<span class="px-2.5 py-1 rounded-lg bg-amber-500/20 text-amber-300 font-extrabold border border-amber-500/40 shadow-sm flex items-center gap-1">🏆 #1 ŞAMPİYON</span>'
            : `<span class="text-gray-400 font-bold text-sm">#${idx + 1}</span>`;

        const netColor = s.net_profit_pct >= 0 ? 'text-emerald-400' : 'text-rose-400';

        let customBadge = '';
        if (s.id === 'pdh_pdl_breakout_retest_user') customBadge = '<span class="px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-[9px] font-bold">⭐ 1. STRATEJİ</span>';
        else if (s.id === 'swing_hl_breakout_retest') customBadge = '<span class="px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 text-[9px] font-bold">🌊 2. STRATEJİ</span>';
        else if (s.id === 'chart_patterns_all') customBadge = '<span class="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[9px] font-bold">📐 3. STRATEJİ</span>';
        else if (s.category.includes('Formasyon') || s.category.includes('Kilit')) customBadge = '<span class="px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-300 border border-orange-500/40 text-[9px] font-bold">📐 FORMASYON</span>';

        const tr = document.createElement('tr');
        tr.className = `cursor-pointer transition ${isChamp ? 'bg-amber-500/10 hover:bg-amber-500/15' : 'hover:bg-gray-800/40'}`;
        tr.title = "Bu stratejinin geçmiş işlemlerini listelemek için tıklayın";
        tr.onclick = () => {
            selectStrategyForTradesView(s);
            // Tablodaki seçili satırı vurgula
            document.querySelectorAll('#leaderboardTbody tr').forEach(r => r.classList.remove('ring-2', 'ring-indigo-500'));
            tr.classList.add('ring-2', 'ring-indigo-500');
        };

        tr.innerHTML = `
            <td class="p-3.5 font-sans">
                <div class="flex items-center gap-3">
                    <div class="w-8 text-center flex-shrink-0">${rankBadge}</div>
                    <div>
                        <div class="font-bold text-white text-sm flex items-center gap-1.5">
                            <span>${s.name}</span>
                            ${customBadge}
                        </div>
                        <div class="text-[11px] text-gray-400 font-mono">${s.name_en}</div>
                    </div>
                </div>
            </td>
            <td class="p-3.5 font-sans text-gray-400 text-xs">${s.category}</td>
            <td class="p-3.5 text-center">
                <div class="flex items-center justify-center gap-1 font-mono text-[10px]">
                    <span class="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 font-bold border border-emerald-500/30" title="TP1 (1:1 R:R) Başarı Oranı">TP1: %${s.tp1_win_rate || 0}</span>
                    <span class="px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-400 font-bold border border-indigo-500/30" title="TP2 (1:2 R:R) Başarı Oranı">TP2: %${s.tp2_win_rate || s.win_rate}</span>
                    <span class="px-2 py-0.5 rounded bg-purple-500/15 text-purple-400 font-bold border border-purple-500/30" title="TP3 (1:3.5 R:R) Başarı Oranı">TP3: %${s.tp3_win_rate || 0}</span>
                </div>
            </td>
            <td class="p-3.5 text-center font-bold text-sm text-gray-200">
                ${s.total_trades} <span class="text-xs text-gray-400 font-normal">(${s.wins}W / ${s.losses}L)</span>
            </td>
            <td class="p-3.5 text-right font-bold text-sm ${netColor}">
                ${s.net_profit_pct > 0 ? '+' : ''}%${s.net_profit_pct}
            </td>
            <td class="p-3.5 text-right font-bold text-sm text-amber-400">${s.profit_factor}</td>
            <td class="p-3.5 text-right font-bold text-sm text-rose-400">-%${s.max_drawdown_pct}</td>
            <td class="p-3.5 text-right font-bold text-sm text-sky-400">${s.sharpe_ratio != null ? s.sharpe_ratio : '—'}</td>
            <td class="p-3.5 text-right font-bold text-sm text-orange-400">${s.max_consecutive_losses != null ? s.max_consecutive_losses : '—'}</td>
        `;
        tbody.appendChild(tr);
    });
}

function selectStrategyForTradesView(strategy) {
    const trades = strategy.recent_trades || [];
    currentStrategyForTrades = strategy;
    showingAllTrades = false;
    const btn = document.getElementById('showAllTradesBtn');
    if (btn) { const span = btn.querySelector('span'); if (span) span.textContent = 'Tümünü Göster'; }
    renderTradesTable(trades, strategy.name);
    updateTradesCountInfo(trades.length, (strategy.all_trades || []).length);
    // Update equity curve for selected strategy
    renderEquityCurve(strategy.equity_curve || [], strategy.net_profit_pct || 0, strategy.max_drawdown_pct || 0);
    // Update avg hold badge
    const avgHoldBadge = document.getElementById('avgHoldBadge');
    if (avgHoldBadge && strategy.avg_hold_bars != null) {
        avgHoldBadge.textContent = `⏱️ Ort. Hold: ${strategy.avg_hold_bars} bar`;
        avgHoldBadge.classList.remove('hidden');
    }
    showToast(strategy.name, `${trades.length} adet geçmiş işlem kaydı listelendi.`);
}

function renderTradesTable(trades, strategyName) {
    const tradesTbody = document.getElementById('tradesTbody');
    if (!tradesTbody) return;
    tradesTbody.innerHTML = '';

    if (!trades || trades.length === 0) {
        tradesTbody.innerHTML = `<tr><td colspan="9" class="text-center py-6 text-gray-500 font-sans">${strategyName} için simüle edilmiş işlem örneği bulunamadı.</td></tr>`;
        return;
    }

    trades.forEach((t, i) => {
        const isWin = t.is_win;
        const outcomeBadge = isWin 
            ? '<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 text-[10px]">✓ TP ALINDI</span>'
            : '<span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-bold border border-rose-500/30 text-[10px]">✗ STOP OLDU</span>';
        const dirBadge = t.direction === 'LONG'
            ? '<span class="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/30 text-[10px]">🟢 LONG</span>'
            : '<span class="px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 font-bold border border-rose-500/30 text-[10px]">🔴 SHORT</span>';
        const pnlColor = t.pnl_pct >= 0 ? 'text-emerald-400' : 'text-rose-400';

        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-800/40 transition cursor-pointer group';
        row.title = "Grafik üzerinde çizgilerle detaylı incelemek için tıklayın";
        row.onclick = () => openTradeDetailModal(t);

        row.innerHTML = `
            <td class="py-2.5 px-3 text-gray-300">${t.entry_time}</td>
            <td class="py-2.5 px-3">${dirBadge}</td>
            <td class="py-2.5 px-3 font-bold text-white">$${formatPrice(t.entry_price)}</td>
            <td class="py-2.5 px-3 text-rose-400 font-semibold">$${formatPrice(t.stop_loss)}</td>
            <td class="py-2.5 px-3 text-emerald-400 font-semibold">$${formatPrice(t.take_profit || t.tp2)}</td>
            <td class="py-2.5 px-3 text-gray-200">$${formatPrice(t.exit_price)} <span class="text-[10px] text-gray-500 font-normal">(${t.exit_time})</span></td>
            <td class="py-2.5 px-3 text-right font-bold text-xs ${pnlColor}">${t.pnl_pct > 0 ? '+' : ''}%${t.pnl_pct}</td>
            <td class="py-2.5 px-3 text-center">${outcomeBadge}</td>
            <td class="py-2.5 px-3 text-right">
                <button onclick="event.stopPropagation(); openTradeDetailModal(${JSON.stringify(t).replace(/"/g, '&quot;')})" class="px-2.5 py-1 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/25 border border-indigo-500/30 text-indigo-300 text-[11px] font-bold transition flex items-center gap-1 ml-auto">
                    <i data-lucide="line-chart" class="w-3.5 h-3.5"></i>
                    <span>Grafiği Aç</span>
                </button>
            </td>
        `;
        tradesTbody.appendChild(row);
    });

    lucide.createIcons();
}

// -------------------------------------------------------------
// 🔍 İŞLEM GRAFİK VE DETAYLI ÇİZGİ ANALİZİ MODALİ
// -------------------------------------------------------------
let tradeModalChart = null;

function openTradeDetailModal(trade) {
    if (!trade) return;

    const modal = document.getElementById('tradeDetailModal');
    if (!modal) return;

    // 1. Header Bilgileri
    const dirBadge = document.getElementById('modalTradeDirBadge');
    if (dirBadge) {
        dirBadge.textContent = trade.direction === 'LONG' ? '🟢 LONG İŞLEM' : '🔴 SHORT İŞLEM';
        dirBadge.className = trade.direction === 'LONG'
            ? 'px-2.5 py-1 rounded-lg bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/40 text-xs font-mono'
            : 'px-2.5 py-1 rounded-lg bg-rose-500/20 text-rose-400 font-bold border border-rose-500/40 text-xs font-mono';
    }

    const titleEl = document.getElementById('modalTradeStratTitle');
    if (titleEl) titleEl.textContent = trade.strategy_name || "Strateji İşlem Detayı";

    const subtitleEl = document.getElementById('modalTradeSubtitle');
    if (subtitleEl) subtitleEl.textContent = `İşleme Giriş: ${trade.entry_time} • Pozisyon Çıkışı: ${trade.exit_time} (${trade.exit_reason || 'Bilinmiyor'})`;

    const outcomeBadge = document.getElementById('modalTradeOutcomeBadge');
    if (outcomeBadge) {
        outcomeBadge.textContent = trade.is_win ? `✓ TP ALINDI (+%${trade.pnl_pct})` : `✗ STOP OLDU (%${trade.pnl_pct})`;
        outcomeBadge.className = trade.is_win
            ? 'px-3 py-1 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 font-bold font-mono text-xs'
            : 'px-3 py-1 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/40 font-bold font-mono text-xs';
    }

    // 2. Fiyat Rozetleri
    if (document.getElementById('badgeEntryPrice')) document.getElementById('badgeEntryPrice').textContent = `$${formatPrice(trade.entry_price)}`;
    if (document.getElementById('badgeStopLoss')) document.getElementById('badgeStopLoss').textContent = `$${formatPrice(trade.stop_loss)}`;
    if (document.getElementById('badgeTp1')) document.getElementById('badgeTp1').textContent = `$${formatPrice(trade.tp1 || trade.take_profit)}`;
    if (document.getElementById('badgeTp2')) document.getElementById('badgeTp2').textContent = `$${formatPrice(trade.tp2 || trade.take_profit)}`;
    if (document.getElementById('badgeTp3')) document.getElementById('badgeTp3').textContent = `$${formatPrice(trade.tp3 || trade.take_profit * 1.5)}`;

    // 3. Açıklama Metni
    const explEl = document.getElementById('modalTradeExplanationText');
    if (explEl) {
        explEl.innerHTML = trade.explanation 
            ? `${trade.explanation}<br/><br/><span class="text-indigo-300 font-semibold">• Sarı Kesikli Çizgi:</span> İşleme giriş fiyatı ($${formatPrice(trade.entry_price)})<br/><span class="text-rose-400 font-semibold">• Kırmızı Çizgi:</span> Stop Loss seviyesi ($${formatPrice(trade.stop_loss)})<br/><span class="text-emerald-400 font-semibold">• Yeşil Çizgiler:</span> TP1, TP2 ve TP3 Kâr Alma Seviyeleri`
            : `Bu işlem ${trade.entry_time} tarihinde $${formatPrice(trade.entry_price)} seviyesinden açıldı. Sonuç: ${trade.is_win ? 'KÂR İLE KAPANDI' : 'ZARAR/STOP İLE KAPANDI'}.`;
    }

    // Modali Göster
    modal.classList.remove('hidden');
    lucide.createIcons();

    // 4. Grafiği Çiz (TradingView Lightweight Chart)
    setTimeout(() => {
        renderModalTradeChart(trade);
    }, 100);
}

function closeTradeDetailModal() {
    const modal = document.getElementById('tradeDetailModal');
    if (modal) modal.classList.add('hidden');
    if (tradeModalChart) {
        try {
            tradeModalChart.remove();
        } catch (e) {}
        tradeModalChart = null;
    }
}

function renderModalTradeChart(trade) {
    const container = document.getElementById('modalTradeChartArea');
    if (!container) return;

    if (tradeModalChart) {
        try {
            tradeModalChart.remove();
        } catch (e) {}
        tradeModalChart = null;
    }
    container.innerHTML = '';

    const width = container.clientWidth || 850;
    const height = container.clientHeight || 400;

    const chartOptions = {
        width: width,
        height: height,
        layout: {
            background: { type: 'solid', color: '#080c14' },
            textColor: '#94a3b8',
            fontSize: 12,
            fontFamily: "'JetBrains Mono', monospace",
        },
        grid: {
            vertLines: { color: 'rgba(30, 41, 59, 0.45)' },
            horzLines: { color: 'rgba(30, 41, 59, 0.45)' },
        },
        crosshair: {
            mode: 1,
            vertLine: { color: '#6366f1', width: 1, style: 3 },
            horzLine: { color: '#6366f1', width: 1, style: 3 },
        },
        rightPriceScale: {
            borderColor: '#1e293b',
            autoScale: true,
        },
        timeScale: {
            borderColor: '#1e293b',
            timeVisible: true,
            secondsVisible: false,
        },
    };

    tradeModalChart = LightweightCharts.createChart(container, chartOptions);

    const candleSeries = tradeModalChart.addCandlestickSeries({
        upColor: '#10b981',
        downColor: '#ef4444',
        borderUpColor: '#10b981',
        borderDownColor: '#ef4444',
        wickUpColor: '#10b981',
        wickDownColor: '#ef4444',
    });

    if (currentCandlesData && currentCandlesData.length > 0) {
        // Mumları yükle
        const formattedCandles = currentCandlesData.map(c => ({
            time: c.time,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close
        })).sort((a, b) => a.time - b.time);

        candleSeries.setData(formattedCandles);

        // Çizgileri Ekle:
        // 1. Giriş Çizgisi
        candleSeries.createPriceLine({
            price: trade.entry_price,
            color: '#fbbf24',
            lineWidth: 2,
            lineStyle: 2,
            axisLabelVisible: true,
            title: `GİRİŞ ($${formatPrice(trade.entry_price)})`,
        });

        // 2. Stop Loss Çizgisi
        candleSeries.createPriceLine({
            price: trade.stop_loss,
            color: '#ef4444',
            lineWidth: 2,
            lineStyle: 0,
            axisLabelVisible: true,
            title: `STOP LOSS ($${formatPrice(trade.stop_loss)})`,
        });

        // 3. TP1 Çizgisi
        if (trade.tp1) {
            candleSeries.createPriceLine({
                price: trade.tp1,
                color: '#34d399',
                lineWidth: 1,
                lineStyle: 2,
                axisLabelVisible: true,
                title: `TP1 (1:1: $${formatPrice(trade.tp1)})`,
            });
        }

        // 4. TP2 Çizgisi
        if (trade.tp2 || trade.take_profit) {
            candleSeries.createPriceLine({
                price: trade.tp2 || trade.take_profit,
                color: '#10b981',
                lineWidth: 2,
                lineStyle: 0,
                axisLabelVisible: true,
                title: `TP2 (1:2: $${formatPrice(trade.tp2 || trade.take_profit)})`,
            });
        }

        // 5. TP3 Çizgisi
        if (trade.tp3) {
            candleSeries.createPriceLine({
                price: trade.tp3,
                color: '#8b5cf6',
                lineWidth: 1,
                lineStyle: 2,
                axisLabelVisible: true,
                title: `TP3 (1:3.5: $${formatPrice(trade.tp3)})`,
            });
        }

        // 6. Kırılan Seviye Çizgisi (varsa)
        if (trade.breakout_level) {
            candleSeries.createPriceLine({
                price: trade.breakout_level,
                color: '#06b6d4',
                lineWidth: 1,
                lineStyle: 0,
                axisLabelVisible: true,
                title: `KIRILAN SEVİYE ($${formatPrice(trade.breakout_level)})`,
            });
        }

        // 📍 7. GRAFİK ÜZERİNDE MUM İŞARETÇİLERİ VE SEMBOLLER (MARKERS)
        const markers = [];
        const isLong = trade.direction === 'LONG';

        // A. Kırılma ve Retest İşaretçileri
        if (trade.breakout_timestamp) {
            markers.push({
                time: trade.breakout_timestamp,
                position: isLong ? 'belowBar' : 'aboveBar',
                color: '#06b6d4',
                shape: isLong ? 'arrowUp' : 'arrowDown',
                text: '⚡ KIRILMA'
            });
        }
        if (trade.retest_timestamp) {
            markers.push({
                time: trade.retest_timestamp,
                position: isLong ? 'belowBar' : 'aboveBar',
                color: '#f59e0b',
                shape: 'circle',
                text: '🎯 RETEST'
            });
        }

        // B. Giriş Mumu İşaretçisi
        if (trade.entry_timestamp) {
            markers.push({
                time: trade.entry_timestamp,
                position: isLong ? 'belowBar' : 'aboveBar',
                color: '#fbbf24',
                shape: isLong ? 'arrowUp' : 'arrowDown',
                text: `🟡 GİRİŞ ($${formatPrice(trade.entry_price)})`
            });
        }

        // C. Çıkış Mumu İşaretçisi (TP / SL / TIMEOUT)
        if (trade.exit_timestamp) {
            const isWin = trade.is_win;
            const exitText = isWin 
                ? `🟢 TP ALINDI (+%${trade.pnl_pct})`
                : (trade.exit_reason === 'SL' ? `🔴 STOP OLDU (%${trade.pnl_pct})` : `⏳ ÇIKIŞ (%${trade.pnl_pct})`);

            markers.push({
                time: trade.exit_timestamp,
                position: isLong ? 'aboveBar' : 'belowBar',
                color: isWin ? '#10b981' : '#ef4444',
                shape: isLong ? 'arrowDown' : 'arrowUp',
                text: exitText
            });
        }

        if (markers.length > 0) {
            markers.sort((a, b) => a.time - b.time);
            candleSeries.setMarkers(markers);
        }

        // 🔍 Otomatik Odaklanma: İşlemin gerçekleştiği aralığa kamerayı yaklaştır
        if (trade.entry_timestamp && trade.exit_timestamp) {
            const marginSeconds = 3600 * 20; // 20 bar öncesi ve sonrası
            const fromT = trade.entry_timestamp - marginSeconds;
            const toT = trade.exit_timestamp + marginSeconds;
            try {
                tradeModalChart.timeScale().setVisibleRange({ from: fromT, to: toT });
            } catch (e) {
                tradeModalChart.timeScale().fitContent();
            }
        } else {
            tradeModalChart.timeScale().fitContent();
        }
    }
}

function formatPrice(val) {
    if (val === undefined || val === null) return '0.00';
    if (val >= 1000) return val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (val >= 1) return val.toFixed(4);
    return val.toFixed(6);
}

function showToast(title, message, isError = false) {
    const toast = document.getElementById('toastNotification');
    const toastTitle = document.getElementById('toastTitle');
    const toastMsg = document.getElementById('toastMsg');

    if (!toast) return;

    toastTitle.textContent = title;
    toastMsg.textContent = message;

    if (isError) {
        toast.className = toast.className.replace('border-indigo-500/40', 'border-rose-500/40');
    } else {
        toast.className = toast.className.replace('border-rose-500/40', 'border-indigo-500/40');
    }

    toast.classList.remove('translate-y-20', 'opacity-0');
    setTimeout(() => {
        toast.classList.add('translate-y-20', 'opacity-0');
    }, 3500);
}
