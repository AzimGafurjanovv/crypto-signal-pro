// CryptoSignalPro AI - Trade Günlüğü & Trade Notları ve Fiyat Alarmı Masası Frontend Mantığı (v1.1.0)

let currentJournalTrades = [];
let currentTradeNotes = [];
let availablePairs = [];
let activeJournalStatusFilter = 'ALL';
let activeNoteStatusFilter = 'ALL';
let livePriceCache = {};

// Popüler varsayılan Binance çiftleri (Fallback)
const DEFAULT_TOP_PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT", "ADA/USDT",
    "AVAX/USDT", "SUI/USDT", "PEPE/USDT", "NEAR/USDT", "APT/USDT", "ARB/USDT", "OP/USDT",
    "LINK/USDT", "TIA/USDT", "FET/USDT", "RENDER/USDT", "DOT/USDT", "MATIC/USDT", "LTC/USDT",
    "INJ/USDT", "SHIB/USDT", "TRX/USDT", "BCH/USDT", "UNI/USDT", "FIL/USDT", "KAS/USDT"
];

document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    initJournalPage();
});

async function initJournalPage() {
    await Promise.all([
        fetchAvailablePairs(),
        fetchJournalTrades(),
        fetchJournalStats(),
        fetchTradeNotes()
    ]);

    // Her 30 saniyede bir notlardaki canlı fiyatları güncelle
    setInterval(updateLivePricesForNotes, 30000);
}

// -------------------------------------------------------------
// 🪙 COİN VE PARİTE LİSTESİ (AUTOCOMPLETE DATALIST)
// -------------------------------------------------------------
async function fetchAvailablePairs() {
    try {
        const res = await fetch('/api/pairs');
        if (res.ok) {
            const data = await res.json();
            if (data.pairs && data.pairs.length > 0) {
                availablePairs = data.pairs;
            } else {
                availablePairs = DEFAULT_TOP_PAIRS;
            }
        } else {
            availablePairs = DEFAULT_TOP_PAIRS;
        }
    } catch (e) {
        console.warn('Pairs API fallback to default list:', e);
        availablePairs = DEFAULT_TOP_PAIRS;
    }

    populatePairsDatalist();
}

function populatePairsDatalist() {
    const datalist = document.getElementById('availablePairsList');
    if (!datalist) return;
    datalist.innerHTML = availablePairs.map(p => `<option value="${p}">`).join('');
}

// 🪙 Hızlı Çip veya Dropdown'dan Coin Seçildiğinde
async function selectSymbol(symbol, context) {
    if (context === 'trade') {
        const input = document.getElementById('tradeFormSymbol');
        if (input) input.value = symbol;
        await fetchAndAutofillPrice(symbol, 'trade');
    } else if (context === 'note') {
        const input = document.getElementById('noteFormSymbol');
        if (input) input.value = symbol;
        await fetchAndAutofillPrice(symbol, 'note');
    }
}

// Input alanına yazıldığında veya datalistten seçildiğinde
let symbolDebounceTimer = null;
function onSymbolInput(context) {
    clearTimeout(symbolDebounceTimer);
    symbolDebounceTimer = setTimeout(() => {
        onSymbolSelected(context);
    }, 400);
}

async function onSymbolSelected(context) {
    let inputId = context === 'trade' ? 'tradeFormSymbol' : 'noteFormSymbol';
    let input = document.getElementById(inputId);
    if (!input) return;

    let val = input.value.toUpperCase().trim();
    if (!val) return;

    // Otomatik /USDT tamamlama (örn: BTC yazılırsa BTC/USDT yapar)
    if (!val.includes('/') && !val.endsWith('USDT')) {
        const found = availablePairs.find(p => p.startsWith(val + '/') || p.split('/')[0] === val);
        if (found) {
            val = found;
            input.value = val;
        } else if (val.length >= 2) {
            val = `${val}/USDT`;
            input.value = val;
        }
    }

    await fetchAndAutofillPrice(val, context);
}

// Seçilen coinin Binance anlık canlı fiyatını çekip ilgili kutulara otomatik doldurur
async function fetchAndAutofillPrice(symbol, context) {
    const cleanSym = symbol.toUpperCase().trim();
    const livePriceEl = document.getElementById(context === 'trade' ? 'tradeLivePriceText' : 'noteLivePriceText');
    if (livePriceEl) livePriceEl.textContent = '⏳ Fiyat çekiliyor...';

    try {
        const res = await fetch(`/api/chart-data?symbol=${encodeURIComponent(cleanSym)}&timeframe=15m&limit=2`);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        
        if (data.candles && data.candles.length > 0) {
            const currentPrice = data.candles[data.candles.length - 1].close;
            livePriceCache[cleanSym] = currentPrice;

            if (livePriceEl) {
                livePriceEl.textContent = `🪙 Canlı: $${formatPrice(currentPrice)}`;
            }

            if (context === 'trade') {
                const entryInput = document.getElementById('tradeFormEntry');
                const slInput = document.getElementById('tradeFormStopLoss');
                const tpInput = document.getElementById('tradeFormTarget');
                const dir = document.getElementById('tradeFormDirection')?.value || 'LONG';

                // Giriş fiyatını anlık fiyatla doldur
                if (entryInput) entryInput.value = currentPrice;

                // Akıllı TP / SL önerisi hesapla (%2 Stop, %4 Hedef)
                if (dir === 'LONG') {
                    if (slInput) slInput.value = (currentPrice * 0.98).toFixed(currentPrice >= 1 ? 4 : 8);
                    if (tpInput) tpInput.value = (currentPrice * 1.04).toFixed(currentPrice >= 1 ? 4 : 8);
                } else {
                    if (slInput) slInput.value = (currentPrice * 1.02).toFixed(currentPrice >= 1 ? 4 : 8);
                    if (tpInput) tpInput.value = (currentPrice * 0.96).toFixed(currentPrice >= 1 ? 4 : 8);
                }
            } else if (context === 'note') {
                const targetInput = document.getElementById('noteFormTarget');
                if (targetInput && (!targetInput.value || parseFloat(targetInput.value) === 0)) {
                    targetInput.value = currentPrice;
                }
            }
        } else {
            if (livePriceEl) livePriceEl.textContent = '';
        }
    } catch (e) {
        if (livePriceEl) livePriceEl.textContent = '';
    }
}

// Yön (LONG/SHORT) değiştiğinde TP/SL seviyelerini otomatik güncelle
function onDirectionChanged(context) {
    if (context === 'trade') {
        const entryInput = document.getElementById('tradeFormEntry');
        const slInput = document.getElementById('tradeFormStopLoss');
        const tpInput = document.getElementById('tradeFormTarget');
        const dir = document.getElementById('tradeFormDirection')?.value || 'LONG';
        const entryPrice = parseFloat(entryInput?.value) || 0;

        if (entryPrice > 0) {
            if (dir === 'LONG') {
                if (slInput) slInput.value = (entryPrice * 0.98).toFixed(entryPrice >= 1 ? 4 : 8);
                if (tpInput) tpInput.value = (entryPrice * 1.04).toFixed(entryPrice >= 1 ? 4 : 8);
            } else {
                if (slInput) slInput.value = (entryPrice * 1.02).toFixed(entryPrice >= 1 ? 4 : 8);
                if (tpInput) tpInput.value = (entryPrice * 0.96).toFixed(entryPrice >= 1 ? 4 : 8);
            }
        }
    }
}

// -------------------------------------------------------------
// 🎛️ ANA SEKME DEĞİŞTİRME (JOURNAL / NOTES)
// -------------------------------------------------------------
function switchMainTab(tab) {
    const secJournal = document.getElementById('sectionJournal');
    const secNotes = document.getElementById('sectionNotes');
    const btnJournal = document.getElementById('tabJournalBtn');
    const btnNotes = document.getElementById('tabNotesBtn');

    if (tab === 'journal') {
        secJournal.classList.remove('hidden');
        secNotes.classList.add('hidden');
        btnJournal.className = 'flex-1 py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 text-white font-bold text-xs flex items-center justify-center gap-2 transition shadow-md border border-indigo-400/40';
        btnNotes.className = 'flex-1 py-2.5 px-4 rounded-xl text-gray-400 hover:text-white font-bold text-xs flex items-center justify-center gap-2 transition border border-transparent';
    } else {
        secJournal.classList.add('hidden');
        secNotes.classList.remove('hidden');
        btnNotes.className = 'flex-1 py-2.5 px-4 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 text-white font-bold text-xs flex items-center justify-center gap-2 transition shadow-md border border-amber-400/40';
        btnJournal.className = 'flex-1 py-2.5 px-4 rounded-xl text-gray-400 hover:text-white font-bold text-xs flex items-center justify-center gap-2 transition border border-transparent';
        updateLivePricesForNotes();
    }
    lucide.createIcons();
}

// =============================================================
// 📖 1. TRADE GÜNLÜĞÜ (JOURNAL) FONKSİYONLARI
// =============================================================
async function fetchJournalTrades() {
    try {
        const res = await fetch('/api/journal');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        currentJournalTrades = data.trades || [];
        renderJournalTable();
    } catch (e) {
        console.error('Fetch journal error:', e);
    }
}

async function fetchJournalStats() {
    try {
        const res = await fetch('/api/journal/stats');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        const stats = data.stats || {};

        document.getElementById('statTotalTrades').textContent = stats.total_trades || 0;
        document.getElementById('statOpenTrades').textContent = stats.open_trades || 0;
        document.getElementById('statWinRate').textContent = `%${stats.win_rate || 0}`;
        document.getElementById('statWinCount').textContent = `${stats.winning_trades || 0} Kazanç / ${stats.losing_trades || 0} Kayıp`;
        
        const pnlPct = stats.total_pnl_pct || 0;
        const elPnlPct = document.getElementById('statTotalPnlPct');
        elPnlPct.textContent = `${pnlPct > 0 ? '+' : ''}%${pnlPct}`;
        elPnlPct.className = `text-xl sm:text-2xl font-black font-mono mt-0.5 ${pnlPct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`;

        const pnlAmount = stats.total_pnl_amount || 0;
        document.getElementById('statTotalPnlAmount').textContent = `${pnlAmount >= 0 ? '+$' : '-$'}${Math.abs(pnlAmount).toFixed(2)} Net`;
        
        document.getElementById('statProfitFactor').textContent = stats.profit_factor || '0.00';
        document.getElementById('statAvgRR').textContent = `${stats.avg_rr || 0} R`;
    } catch (e) {
        console.error('Fetch stats error:', e);
    }
}

function filterJournalByStatus(status) {
    activeJournalStatusFilter = status;
    document.querySelectorAll('.journal-filter-btn').forEach(btn => {
        if (btn.getAttribute('data-status') === status) {
            btn.className = 'journal-filter-btn px-3 py-1.5 rounded-lg bg-indigo-600 text-white transition';
        } else {
            btn.className = 'journal-filter-btn px-3 py-1.5 rounded-lg text-gray-400 hover:text-white transition';
        }
    });
    renderJournalTable();
}

function applyJournalFilters() {
    renderJournalTable();
}

function renderJournalTable() {
    const searchVal = document.getElementById('journalSearchInput')?.value.toUpperCase().trim() || '';
    
    let list = currentJournalTrades;
    if (activeJournalStatusFilter !== 'ALL') {
        list = list.filter(t => t.status === activeJournalStatusFilter);
    }
    if (searchVal) {
        list = list.filter(t => (t.symbol || '').includes(searchVal) || (t.strategy || '').toUpperCase().includes(searchVal));
    }

    const tbody = document.getElementById('journalTableBody');
    const mobList = document.getElementById('journalMobileCardList');
    const emptyState = document.getElementById('journalEmptyState');

    if (!tbody || !mobList) return;

    if (list.length === 0) {
        tbody.innerHTML = '';
        mobList.innerHTML = '';
        if (emptyState) emptyState.classList.remove('hidden');
        return;
    }

    if (emptyState) emptyState.classList.add('hidden');

    // Desktop Table HTML
    tbody.innerHTML = list.map(t => {
        const isLong = t.direction === 'LONG';
        const dirBadge = isLong 
            ? `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 text-[10px]">🟢 LONG</span>`
            : `<span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-bold border border-rose-500/30 text-[10px]">🔴 SHORT</span>`;

        let statusBadge = '';
        if (t.status === 'OPEN') statusBadge = `<span class="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/30 text-[10px]">🟢 AÇIK</span>`;
        else if (t.status === 'WIN_TP') statusBadge = `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 text-[10px]">🎯 TP KÂR</span>`;
        else if (t.status === 'LOSS_SL') statusBadge = `<span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-bold border border-rose-500/30 text-[10px]">🛑 SL STOP</span>`;
        else statusBadge = `<span class="px-2 py-0.5 rounded bg-gray-800 text-gray-400 font-bold border border-gray-700 text-[10px]">⚪ KAPATILDI</span>`;

        const pnlVal = t.pnl_percent || 0;
        const pnlColor = pnlVal > 0 ? 'text-emerald-400' : (pnlVal < 0 ? 'text-rose-400' : 'text-gray-400');
        const pnlText = t.status === 'OPEN' ? '<span class="text-gray-500 font-sans text-[11px]">Pozisyon Açık</span>' : `<span class="font-bold ${pnlColor}">${pnlVal > 0 ? '+' : ''}%${pnlVal}</span>`;

        return `
            <tr class="hover:bg-gray-800/40 transition">
                <td class="p-3.5">
                    <div class="font-bold text-white text-sm">${t.symbol}</div>
                    <div class="text-[10px] text-gray-500 font-sans">${t.entry_date_str || ''}</div>
                </td>
                <td class="p-3.5">${dirBadge}</td>
                <td class="p-3.5 space-y-0.5 text-[11px]">
                    <div>Giriş: <b class="text-yellow-400">$${formatPrice(t.entry_price)}</b></div>
                    <div class="text-rose-400/80">SL: $${formatPrice(t.stop_loss)}</div>
                    <div class="text-emerald-400/80">TP: $${formatPrice(t.target_price)}</div>
                </td>
                <td class="p-3.5 text-cyan-300 font-bold text-[11px]">${t.exit_price ? '$' + formatPrice(t.exit_price) : '<span class="text-gray-600">-</span>'}</td>
                <td class="p-3.5 font-bold text-purple-300">${t.risk_reward ? t.risk_reward + ' R' : '-'}</td>
                <td class="p-3.5">${pnlText}</td>
                <td class="p-3.5">${statusBadge}</td>
                <td class="p-3.5 max-w-[200px] truncate">
                    <div class="text-gray-300 font-sans font-semibold">${t.strategy || 'Kişisel'}</div>
                    <div class="text-[10px] text-gray-500 truncate font-sans">${t.notes || ''}</div>
                </td>
                <td class="p-3.5 text-right space-x-1">
                    ${t.status === 'OPEN' ? `
                        <button onclick="quickSetTradeStatus('${t.id}', 'WIN_TP')" title="Kârla Kapat (TP)" class="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 transition cursor-pointer">
                            <i data-lucide="check" class="w-3.5 h-3.5"></i>
                        </button>
                        <button onclick="quickSetTradeStatus('${t.id}', 'LOSS_SL')" title="Zararla Kapat (SL)" class="p-1.5 rounded-lg bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 transition cursor-pointer">
                            <i data-lucide="x" class="w-3.5 h-3.5"></i>
                        </button>
                    ` : ''}
                    <button onclick="openEditTradeModal('${t.id}')" title="Düzenle" class="p-1.5 rounded-lg bg-gray-800 text-gray-300 hover:bg-gray-700 transition cursor-pointer">
                        <i data-lucide="edit-3" class="w-3.5 h-3.5"></i>
                    </button>
                    <button onclick="deleteJournalTrade('${t.id}')" title="Sil" class="p-1.5 rounded-lg bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 transition cursor-pointer">
                        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');

    // Mobile Cards HTML
    mobList.innerHTML = list.map(t => {
        const isLong = t.direction === 'LONG';
        const dirBadge = isLong 
            ? `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 text-[10px]">🟢 LONG</span>`
            : `<span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-bold border border-rose-500/30 text-[10px]">🔴 SHORT</span>`;

        let statusBadge = '';
        if (t.status === 'OPEN') statusBadge = `<span class="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-bold text-[10px]">🟢 AÇIK</span>`;
        else if (t.status === 'WIN_TP') statusBadge = `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold text-[10px]">🎯 TP KÂR</span>`;
        else if (t.status === 'LOSS_SL') statusBadge = `<span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-bold text-[10px]">🛑 SL STOP</span>`;
        else statusBadge = `<span class="px-2 py-0.5 rounded bg-gray-800 text-gray-400 font-bold text-[10px]">⚪ KAPATILDI</span>`;

        const pnlVal = t.pnl_percent || 0;
        const pnlColor = pnlVal > 0 ? 'text-emerald-400' : (pnlVal < 0 ? 'text-rose-400' : 'text-gray-400');

        return `
            <div class="glass-card p-4 rounded-2xl border border-gray-800 space-y-3 font-mono">
                <div class="flex items-center justify-between pb-2 border-b border-gray-800/80">
                    <div class="flex items-center gap-2">
                        <span class="font-extrabold text-sm text-white">${t.symbol}</span>
                        ${dirBadge}
                    </div>
                    ${statusBadge}
                </div>

                <div class="grid grid-cols-3 gap-2 text-xs">
                    <div class="bg-gray-950/60 p-2 rounded-xl border border-gray-800">
                        <span class="text-[9px] text-gray-500 block font-sans">GİRİŞ</span>
                        <span class="font-bold text-yellow-400">$${formatPrice(t.entry_price)}</span>
                    </div>
                    <div class="bg-gray-950/60 p-2 rounded-xl border border-gray-800">
                        <span class="text-[9px] text-gray-500 block font-sans">STOP (SL)</span>
                        <span class="font-bold text-rose-400">$${formatPrice(t.stop_loss)}</span>
                    </div>
                    <div class="bg-gray-950/60 p-2 rounded-xl border border-gray-800">
                        <span class="text-[9px] text-gray-500 block font-sans">HEDEF (TP)</span>
                        <span class="font-bold text-emerald-400">$${formatPrice(t.target_price)}</span>
                    </div>
                </div>

                <div class="flex items-center justify-between bg-gray-950/40 p-2 rounded-xl text-xs">
                    <div>
                        <span class="text-[10px] text-gray-500 font-sans block">Net PnL:</span>
                        <span class="font-black ${pnlColor}">${t.status === 'OPEN' ? 'Pozisyon Açık' : (pnlVal > 0 ? '+' : '') + '%' + pnlVal}</span>
                    </div>
                    <div>
                        <span class="text-[10px] text-gray-500 font-sans block">R:R Oranı:</span>
                        <span class="font-bold text-purple-300">${t.risk_reward ? t.risk_reward + ' R' : '-'}</span>
                    </div>
                    <div>
                        <span class="text-[10px] text-gray-500 font-sans block">Strateji:</span>
                        <span class="text-gray-300 truncate max-w-[90px] block font-sans">${t.strategy || 'Kişisel'}</span>
                    </div>
                </div>

                ${t.notes ? `<div class="text-[11px] text-gray-400 font-sans italic bg-gray-900/50 p-2 rounded-lg border border-gray-800/60">"${t.notes}"</div>` : ''}

                <div class="flex items-center justify-between pt-2 border-t border-gray-800/80">
                    <span class="text-[10px] text-gray-500">${t.entry_date_str || ''}</span>
                    <div class="flex items-center gap-1.5">
                        ${t.status === 'OPEN' ? `
                            <button onclick="quickSetTradeStatus('${t.id}', 'WIN_TP')" class="px-2.5 py-1 rounded-lg bg-emerald-500/20 text-emerald-300 text-xs font-bold font-sans">Kâr (TP)</button>
                            <button onclick="quickSetTradeStatus('${t.id}', 'LOSS_SL')" class="px-2.5 py-1 rounded-lg bg-rose-500/20 text-rose-300 text-xs font-bold font-sans">Zarar (SL)</button>
                        ` : ''}
                        <button onclick="openEditTradeModal('${t.id}')" class="p-1.5 rounded-lg bg-gray-800 text-gray-300"><i data-lucide="edit-3" class="w-3.5 h-3.5"></i></button>
                        <button onclick="deleteJournalTrade('${t.id}')" class="p-1.5 rounded-lg bg-rose-500/20 text-rose-400"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    lucide.createIcons();
}

function getNowLocalDateTimeString() {
    const now = new Date();
    const pad = n => String(n).padStart(2, '0');
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

function formatDateForDisplay(dtStr) {
    if (!dtStr) return '';
    return dtStr.replace('T', ' ').slice(0, 16);
}

function formatIsoToInput(dtStr) {
    if (!dtStr) return '';
    return dtStr.replace(' ', 'T').slice(0, 16);
}

function openNewTradeModal() {
    document.getElementById('tradeFormId').value = '';
    document.getElementById('tradeModalTitle').textContent = 'Yeni İşlem Kaydı Ekle';
    document.getElementById('tradeForm').reset();
    document.getElementById('tradeLivePriceText').textContent = '';
    document.getElementById('tradeFormEntryDate').value = getNowLocalDateTimeString();
    document.getElementById('tradeFormExitDate').value = '';
    document.getElementById('tradeModal').classList.remove('hidden');
    document.getElementById('tradeModal').classList.add('flex');

    // Varsayılan olarak ilk pariteyi seç
    if (availablePairs.length > 0) {
        selectSymbol('BTC/USDT', 'trade');
    }
}

function openEditTradeModal(tradeId) {
    const trade = currentJournalTrades.find(t => t.id === tradeId);
    if (!trade) return;

    document.getElementById('tradeFormId').value = trade.id;
    document.getElementById('tradeModalTitle').textContent = `İşlemi Düzenle: ${trade.symbol}`;
    document.getElementById('tradeFormSymbol').value = trade.symbol;
    document.getElementById('tradeFormDirection').value = trade.direction;
    document.getElementById('tradeFormEntry').value = trade.entry_price || '';
    document.getElementById('tradeFormStopLoss').value = trade.stop_loss || '';
    document.getElementById('tradeFormTarget').value = trade.target_price || '';
    document.getElementById('tradeFormSize').value = trade.position_size || '';
    document.getElementById('tradeFormStatus').value = trade.status || 'OPEN';
    document.getElementById('tradeFormExit').value = trade.exit_price || '';
    document.getElementById('tradeFormStrategy').value = trade.strategy || 'Kişisel Analiz';
    document.getElementById('tradeFormNotes').value = trade.notes || '';
    document.getElementById('tradeFormEntryDate').value = formatIsoToInput(trade.entry_date_str) || getNowLocalDateTimeString();
    document.getElementById('tradeFormExitDate').value = formatIsoToInput(trade.exit_date_str) || '';
    document.getElementById('tradeLivePriceText').textContent = '';

    document.getElementById('tradeModal').classList.remove('hidden');
    document.getElementById('tradeModal').classList.add('flex');
}

function closeTradeModal() {
    document.getElementById('tradeModal').classList.add('hidden');
    document.getElementById('tradeModal').classList.remove('flex');
}

async function handleTradeFormSubmit(e) {
    e.preventDefault();
    const tradeId = document.getElementById('tradeFormId').value;
    
    const entryDateInput = document.getElementById('tradeFormEntryDate').value;
    const exitDateInput = document.getElementById('tradeFormExitDate').value;

    const payload = {
        symbol: document.getElementById('tradeFormSymbol').value.toUpperCase().trim(),
        direction: document.getElementById('tradeFormDirection').value,
        entry_price: parseFloat(document.getElementById('tradeFormEntry').value) || 0,
        stop_loss: parseFloat(document.getElementById('tradeFormStopLoss').value) || 0,
        target_price: parseFloat(document.getElementById('tradeFormTarget').value) || 0,
        position_size: parseFloat(document.getElementById('tradeFormSize').value) || 0,
        status: document.getElementById('tradeFormStatus').value,
        exit_price: parseFloat(document.getElementById('tradeFormExit').value) || null,
        strategy: document.getElementById('tradeFormStrategy').value,
        notes: document.getElementById('tradeFormNotes').value,
        entry_date_str: formatDateForDisplay(entryDateInput) || new Date().toISOString().slice(0, 16).replace('T', ' '),
        exit_date_str: formatDateForDisplay(exitDateInput) || null
    };

    try {
        let res;
        if (tradeId) {
            res = await fetch(`/api/journal/${tradeId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } else {
            res = await fetch('/api/journal', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        }

        if (!res.ok) throw new Error('HTTP ' + res.status);
        closeTradeModal();
        await Promise.all([fetchJournalTrades(), fetchJournalStats()]);
    } catch (err) {
        alert('İşlem kaydedilirken hata oluştu: ' + err.message);
    }
}

async function quickSetTradeStatus(tradeId, newStatus) {
    const trade = currentJournalTrades.find(t => t.id === tradeId);
    if (!trade) return;

    let exitPrice = trade.exit_price;
    if (!exitPrice) {
        if (newStatus === 'WIN_TP') exitPrice = trade.target_price;
        else if (newStatus === 'LOSS_SL') exitPrice = trade.stop_loss;
        else exitPrice = trade.entry_price;
    }

    try {
        const res = await fetch(`/api/journal/${tradeId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                status: newStatus,
                exit_price: exitPrice,
                exit_date_str: new Date().toISOString().slice(0, 16).replace('T', ' ')
            })
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        await Promise.all([fetchJournalTrades(), fetchJournalStats()]);
    } catch (e) {
        console.error('Quick status error:', e);
    }
}

async function deleteJournalTrade(tradeId) {
    if (!confirm('Bu işlemi günlükten silmek istediğinize emin misiniz?')) return;
    try {
        const res = await fetch(`/api/journal/${tradeId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        await Promise.all([fetchJournalTrades(), fetchJournalStats()]);
    } catch (e) {
        console.error('Delete error:', e);
    }
}

// =============================================================
// 📝 2. TRADE NOTLARI & ÖZEL FİYAT ALARMLARI FONKSİYONLARI
// =============================================================
async function fetchTradeNotes() {
    try {
        const res = await fetch('/api/trade-notes');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        currentTradeNotes = data.notes || [];
        renderTradeNotes();
    } catch (e) {
        console.error('Fetch notes error:', e);
    }
}

function filterNotesByStatus(status) {
    activeNoteStatusFilter = status;
    document.querySelectorAll('.note-filter-btn').forEach(btn => {
        if (btn.getAttribute('data-status') === status) {
            btn.className = 'note-filter-btn px-3 py-1.5 rounded-xl bg-amber-500/20 text-amber-300 font-bold text-xs border border-amber-500/40 transition';
        } else {
            btn.className = 'note-filter-btn px-3 py-1.5 rounded-xl text-gray-400 font-bold text-xs hover:text-white transition';
        }
    });
    renderTradeNotes();
}

async function updateLivePricesForNotes() {
    const activeSymbols = [...new Set(currentTradeNotes.map(n => n.symbol))];
    for (const sym of activeSymbols) {
        try {
            const res = await fetch(`/api/chart-data?symbol=${encodeURIComponent(sym)}&timeframe=15m&limit=2`);
            if (res.ok) {
                const d = await res.json();
                if (d.candles && d.candles.length > 0) {
                    livePriceCache[sym] = d.candles[d.candles.length - 1].close;
                }
            }
        } catch (e) {}
    }
    renderTradeNotes();
}

function renderTradeNotes() {
    let list = currentTradeNotes;
    if (activeNoteStatusFilter === 'ACTIVE') {
        list = list.filter(n => n.is_active && !n.is_triggered);
    } else if (activeNoteStatusFilter === 'TRIGGERED') {
        list = list.filter(n => n.is_triggered);
    }

    const grid = document.getElementById('notesCardGrid');
    const empty = document.getElementById('notesEmptyState');
    const badge = document.getElementById('activeNotesCount');

    const activeCount = currentTradeNotes.filter(n => n.is_active && !n.is_triggered).length;
    if (badge) badge.textContent = activeCount;

    if (!grid) return;

    if (list.length === 0) {
        grid.innerHTML = '';
        if (empty) empty.classList.remove('hidden');
        return;
    }

    if (empty) empty.classList.add('hidden');

    grid.innerHTML = list.map(n => {
        const currPrice = livePriceCache[n.symbol] || n.created_price || 0;
        const targetPrice = n.target_price || 0;
        
        let distPct = 0;
        if (currPrice > 0 && targetPrice > 0) {
            distPct = Math.abs((currPrice - targetPrice) / currPrice * 100.0).toFixed(2);
        }

        let statusBadge = '';
        if (n.is_triggered) {
            statusBadge = `<span class="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 text-[10px] flex items-center gap-1 font-mono">🟢 HEDEFE ULAŞILDI</span>`;
        } else if (n.is_active) {
            statusBadge = `<span class="px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30 text-[10px] flex items-center gap-1 font-mono animate-pulse">🔴 CANLI İZLENİYOR</span>`;
        } else {
            statusBadge = `<span class="px-2.5 py-0.5 rounded-full bg-gray-800 text-gray-400 font-bold border border-gray-700 text-[10px] font-mono">⚪ PASİF</span>`;
        }

        const dirBadge = n.direction_bias === 'LONG' 
            ? `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold text-[10px] font-mono">🟢 LONG</span>`
            : (n.direction_bias === 'SHORT' ? `<span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-bold text-[10px] font-mono">🔴 SHORT</span>` : '');

        const condLabel = n.condition_type === 'CROSS_ABOVE' 
            ? '🔺 Fiyat Üstüne Çıkarsa' 
            : (n.condition_type === 'CROSS_BELOW' ? '🔻 Fiyat Altına Düşerse' : '🎯 Fiyat Yaklaşırsa');

        return `
            <div class="glass-card p-4 rounded-2xl border ${n.is_triggered ? 'border-emerald-500/40' : (n.is_active ? 'border-amber-500/30' : 'border-gray-800')} space-y-3 flex flex-col justify-between">
                <div class="space-y-2">
                    <div class="flex items-center justify-between pb-2 border-b border-gray-800/80">
                        <div class="flex items-center gap-2">
                            <span class="font-black text-sm text-white">${n.symbol}</span>
                            ${dirBadge}
                        </div>
                        ${statusBadge}
                    </div>

                    <div>
                        <h4 class="font-bold text-xs text-amber-300 font-sans">${n.note_title}</h4>
                        <div class="text-[10px] text-gray-400 font-mono mt-0.5">${condLabel}</div>
                    </div>

                    <div class="grid grid-cols-2 gap-2 text-xs font-mono">
                        <div class="bg-gray-950/70 p-2 rounded-xl border border-gray-800">
                            <span class="text-[9px] text-gray-500 block font-sans">HEDEF FİYAT</span>
                            <span class="font-black text-amber-400">$${formatPrice(targetPrice)}</span>
                        </div>
                        <div class="bg-gray-950/70 p-2 rounded-xl border border-gray-800">
                            <span class="text-[9px] text-gray-500 block font-sans">CANLI FİYAT</span>
                            <span class="font-bold text-white">$${formatPrice(currPrice)}</span>
                        </div>
                    </div>

                    ${!n.is_triggered ? `
                        <div class="bg-amber-500/10 border border-amber-500/20 p-2 rounded-xl text-[11px] text-amber-300 flex items-center justify-between font-mono">
                            <span>Hedefe Kalan Mesafe:</span>
                            <span class="font-black font-mono text-white">%${distPct}</span>
                        </div>
                    ` : `
                        <div class="bg-emerald-500/10 border border-emerald-500/20 p-2 rounded-xl text-[11px] text-emerald-300 font-mono">
                            Saat <b>${n.triggered_at || ''}</b> itibarıyla $${formatPrice(n.triggered_price || targetPrice)} fiyatında tetiklendi.
                        </div>
                    `}

                    ${n.note_text ? `
                        <div class="bg-gray-950/60 p-2.5 rounded-xl border border-gray-800 text-[11px] text-gray-300 font-sans italic">
                            "${n.note_text}"
                        </div>
                    ` : ''}
                </div>

                <div class="flex items-center justify-between pt-2 border-t border-gray-800/80 text-[10px] text-gray-500 font-mono">
                    <span>${n.created_at_str || ''}</span>
                    <div class="flex items-center gap-1.5">
                        <button onclick="toggleNoteActive('${n.id}')" title="${n.is_active ? 'Alarmı Duraklat' : 'Alarmı Yeniden Başlat'}" class="px-2.5 py-1 rounded-lg ${n.is_active ? 'bg-amber-500/20 text-amber-300 hover:bg-amber-500/30' : 'bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30'} font-bold transition cursor-pointer">
                            ${n.is_active ? 'Duraklat' : 'Yeniden Başlat'}
                        </button>
                        <button onclick="deleteTradeNote('${n.id}')" title="Sil" class="p-1.5 rounded-lg bg-rose-500/20 text-rose-400 hover:bg-rose-500/30 transition cursor-pointer">
                            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    lucide.createIcons();
}

function openNewNoteModal() {
    document.getElementById('noteFormId').value = '';
    document.getElementById('noteForm').reset();
    document.getElementById('noteLivePriceText').textContent = '';
    const dateInput = document.getElementById('noteFormDate');
    if (dateInput) dateInput.value = getNowLocalDateTimeString();
    document.getElementById('noteModal').classList.remove('hidden');
    document.getElementById('noteModal').classList.add('flex');

    if (availablePairs.length > 0) {
        selectSymbol('ETH/USDT', 'note');
    }
}

function closeNoteModal() {
    document.getElementById('noteModal').classList.add('hidden');
    document.getElementById('noteModal').classList.remove('flex');
}

async function handleNoteFormSubmit(e) {
    e.preventDefault();
    const dateInput = document.getElementById('noteFormDate')?.value;
    const payload = {
        symbol: document.getElementById('noteFormSymbol').value.toUpperCase().trim(),
        direction_bias: document.getElementById('noteFormDirection').value,
        target_price: parseFloat(document.getElementById('noteFormTarget').value) || 0,
        condition_type: document.getElementById('noteFormCondition').value,
        note_title: document.getElementById('noteFormTitle').value,
        note_text: document.getElementById('noteFormText').value,
        telegram_notify: document.getElementById('noteFormTelegram').checked,
        created_at_str: formatDateForDisplay(dateInput) || new Date().toISOString().slice(0, 16).replace('T', ' ')
    };

    try {
        const res = await fetch('/api/trade-notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        closeNoteModal();
        await fetchTradeNotes();
    } catch (err) {
        alert('Not kaydedilirken hata oluştu: ' + err.message);
    }
}

async function toggleNoteActive(noteId) {
    try {
        const res = await fetch(`/api/trade-notes/${noteId}/toggle`, { method: 'POST' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        await fetchTradeNotes();
    } catch (e) {
        console.error('Toggle error:', e);
    }
}

async function deleteTradeNote(noteId) {
    if (!confirm('Bu notu ve fiyat alarmını silmek istediğinize emin misiniz?')) return;
    try {
        const res = await fetch(`/api/trade-notes/${noteId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        await fetchTradeNotes();
    } catch (e) {
        console.error('Delete error:', e);
    }
}

// -------------------------------------------------------------
// 🛠️ YARDIMCI FİYAT FORMATLAYICI
// -------------------------------------------------------------
function formatPrice(p) {
    if (p === null || p === undefined || isNaN(p)) return '0.00';
    const num = Number(p);
    if (num >= 1000) return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (num >= 1) return num.toFixed(4);
    if (num >= 0.0001) return num.toFixed(6);
    return num.toFixed(8);
}
