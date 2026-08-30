/**
 * CryptoSignalPro AI - Trade Günlüğü & Not Alarm Masası Frontend v2.0
 * 
 * Özellikler:
 * 1. Kasa / Bakiye & Başlangıç Depozitosu Takibi.
 * 2. 1x - 100x Kaldıraç & Marjin / Pozisyon Kullanım Oranları.
 * 3. 2 Ayrı Görünüm:
 *    - 📋 1. Liste & Tablo Görünümü (Detaylı filtreler, mobil kartlar, hızlı aksiyonlar)
 *    - 📅 2. Takvim Bazlı Günlük Görünüm (TradeZella tarzı interaktif ay takvimi ve günlük PnL karnesi)
 * 4. Flatpickr İnteraktif Takvim & Saat Seçici.
 * 5. Trade Notları & 7/24 Fiyat Takip Alarmları.
 */

let activeMainTab = 'journal'; // 'journal' veya 'notes'
let activeJournalView = 'list'; // 'list' veya 'calendar'
let activeJournalStatusFilter = 'ALL';
let activeNoteStatusFilter = 'ALL';

let currentJournalTrades = [];
let currentTradeNotes = [];
let currentStats = {};
let availablePairs = [];
let livePriceCache = {};

let fpEntryDate = null;
let fpExitDate = null;
let fpNoteDate = null;

// Takvim Gezinme Değişkenleri
let calendarDate = new Date(); // Şu anki seçili takvim ayı

document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    initFlatpickrInstances();
    initJournalPage();
});

function initFlatpickrInstances() {
    if (typeof flatpickr === 'undefined') return;

    const commonConfig = {
        enableTime: true,
        time_24hr: true,
        dateFormat: "Y-m-d H:i",
        theme: "dark",
        disableMobile: "true"
    };

    try {
        if (flatpickr.l10ns && flatpickr.l10ns.tr) {
            commonConfig.locale = flatpickr.l10ns.tr;
        }
    } catch(e) {}

    const elEntry = document.getElementById('tradeFormEntryDate');
    if (elEntry) {
        fpEntryDate = flatpickr(elEntry, {
            ...commonConfig,
            defaultDate: new Date()
        });
    }

    const elExit = document.getElementById('tradeFormExitDate');
    if (elExit) {
        fpExitDate = flatpickr(elExit, {
            ...commonConfig,
            defaultDate: null
        });
    }

    const elNote = document.getElementById('noteFormDate');
    if (elNote) {
        fpNoteDate = flatpickr(elNote, {
            ...commonConfig,
            defaultDate: new Date()
        });
    }
}

function setQuickDate(daysAgo, inputId) {
    const d = new Date();
    d.setDate(d.getDate() - daysAgo);
    
    const pad = n => String(n).padStart(2, '0');
    const formatted = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;

    const input = document.getElementById(inputId);
    if (input) {
        input.value = formatted;
        if (input._flatpickr) {
            input._flatpickr.setDate(d, true);
        }
    }
}

function clearDateField(inputId) {
    const input = document.getElementById(inputId);
    if (input) {
        input.value = '';
        if (input._flatpickr) {
            input._flatpickr.clear();
        }
    }
}

async function initJournalPage() {
    await fetchAvailablePairs();
    await fetchJournalStats();
    await fetchJournalTrades();
    await fetchTradeNotes();

    // 30 saniyede bir canlı fiyatları ve notları güncelle
    setInterval(() => {
        if (activeMainTab === 'notes') {
            updateLivePricesForNotes();
        }
    }, 30000);
}

// =========================================================================
// 🎛️ SEKME & GÖRÜNÜM YÖNETİMİ
// =========================================================================

function switchMainTab(tab) {
    activeMainTab = tab;
    const tabJournalBtn = document.getElementById('tabJournalBtn');
    const tabNotesBtn = document.getElementById('tabNotesBtn');
    const secJournal = document.getElementById('sectionJournal');
    const secNotes = document.getElementById('sectionNotes');

    if (tab === 'journal') {
        tabJournalBtn.className = 'flex-1 py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 text-white font-bold text-xs flex items-center justify-center gap-2 transition shadow-md border border-indigo-400/40';
        tabNotesBtn.className = 'flex-1 py-2.5 px-4 rounded-xl text-gray-400 hover:text-white font-bold text-xs flex items-center justify-center gap-2 transition border border-transparent';
        secJournal.classList.remove('hidden');
        secNotes.classList.add('hidden');
        fetchJournalStats();
        fetchJournalTrades();
    } else {
        tabNotesBtn.className = 'flex-1 py-2.5 px-4 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 text-white font-bold text-xs flex items-center justify-center gap-2 transition shadow-md border border-amber-400/40';
        tabJournalBtn.className = 'flex-1 py-2.5 px-4 rounded-xl text-gray-400 hover:text-white font-bold text-xs flex items-center justify-center gap-2 transition border border-transparent';
        secNotes.classList.remove('hidden');
        secJournal.classList.add('hidden');
        fetchTradeNotes();
        updateLivePricesForNotes();
    }
    lucide.createIcons();
}

function switchJournalView(view) {
    activeJournalView = view;
    const btnList = document.getElementById('viewListBtn');
    const btnCal = document.getElementById('viewCalendarBtn');
    const viewList = document.getElementById('journalListView');
    const viewCal = document.getElementById('journalCalendarView');
    const filterGroup = document.getElementById('journalStatusFilterGroup');

    if (view === 'list') {
        btnList.className = 'px-3.5 py-2 rounded-lg bg-indigo-600 text-white transition flex items-center gap-1.5 shadow-sm';
        btnCal.className = 'px-3.5 py-2 rounded-lg text-gray-400 hover:text-white transition flex items-center gap-1.5';
        viewList.classList.remove('hidden');
        viewCal.classList.add('hidden');
        if (filterGroup) filterGroup.classList.remove('hidden');
    } else {
        btnCal.className = 'px-3.5 py-2 rounded-lg bg-indigo-600 text-white transition flex items-center gap-1.5 shadow-sm';
        btnList.className = 'px-3.5 py-2 rounded-lg text-gray-400 hover:text-white transition flex items-center gap-1.5';
        viewCal.classList.remove('hidden');
        viewList.classList.add('hidden');
        if (filterGroup) filterGroup.classList.add('hidden');
        renderTradingCalendar();
    }
    lucide.createIcons();
}

// =========================================================================
// 🪙 PARİTE VE CANLI FİYAT DOLDURMA (AUTO-COMPLETE & AUTOFILL)
// =========================================================================

async function fetchAvailablePairs() {
    try {
        const res = await fetch('/api/pairs');
        if (res.ok) {
            const data = await res.json();
            availablePairs = data.pairs || [];
            
            const datalist = document.getElementById('availablePairsList');
            if (datalist && availablePairs.length > 0) {
                datalist.innerHTML = availablePairs.map(p => `<option value="${p}">`).join('');
            }
        }
    } catch (e) {
        console.error('Pairs fetch error:', e);
    }
}

function selectSymbol(sym, modalType) {
    const inputId = modalType === 'trade' ? 'tradeFormSymbol' : 'noteFormSymbol';
    const input = document.getElementById(inputId);
    if (input) {
        input.value = sym;
        fetchAndAutofillPrice(sym, modalType);
    }
}

function onSymbolSelected(modalType) {
    const inputId = modalType === 'trade' ? 'tradeFormSymbol' : 'noteFormSymbol';
    const sym = document.getElementById(inputId).value.toUpperCase().trim();
    if (sym) {
        fetchAndAutofillPrice(sym, modalType);
    }
}

function onSymbolInput(modalType) {
    const inputId = modalType === 'trade' ? 'tradeFormSymbol' : 'noteFormSymbol';
    const val = document.getElementById(inputId).value.toUpperCase().trim();
    if (availablePairs.includes(val)) {
        fetchAndAutofillPrice(val, modalType);
    }
}

async function fetchAndAutofillPrice(symbol, modalType) {
    const textId = modalType === 'trade' ? 'tradeLivePriceText' : 'noteLivePriceText';
    const textEl = document.getElementById(textId);
    if (textEl) textEl.textContent = '⏳ Fiyat alınıyor...';

    try {
        const res = await fetch(`/api/chart-data?symbol=${encodeURIComponent(symbol)}&timeframe=15m&limit=2`);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        
        if (data.candles && data.candles.length > 0) {
            const lastCandle = data.candles[data.candles.length - 1];
            const price = parseFloat(lastCandle.close);
            livePriceCache[symbol] = price;

            if (textEl) {
                textEl.textContent = `🪙 Canlı: $${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`;
            }

            if (modalType === 'trade') {
                const entryInput = document.getElementById('tradeFormEntry');
                if (entryInput && !entryInput.value) {
                    entryInput.value = price;
                }
                const dir = document.getElementById('tradeFormDirection').value;
                const slInput = document.getElementById('tradeFormStopLoss');
                const tpInput = document.getElementById('tradeFormTarget');

                if (slInput && !slInput.value) {
                    slInput.value = dir === 'LONG' ? roundPrice(price * 0.98) : roundPrice(price * 1.02);
                }
                if (tpInput && !tpInput.value) {
                    tpInput.value = dir === 'LONG' ? roundPrice(price * 1.04) : roundPrice(price * 0.96);
                }
            } else if (modalType === 'note') {
                const targetInput = document.getElementById('noteFormTarget');
                if (targetInput && !targetInput.value) {
                    targetInput.value = roundPrice(price * 1.03);
                }
            }
        }
    } catch (e) {
        if (textEl) textEl.textContent = '';
    }
}

function onDirectionChanged(modalType) {
    if (modalType === 'trade') {
        const entry = parseFloat(document.getElementById('tradeFormEntry').value);
        if (entry > 0) {
            const dir = document.getElementById('tradeFormDirection').value;
            document.getElementById('tradeFormStopLoss').value = dir === 'LONG' ? roundPrice(entry * 0.98) : roundPrice(entry * 1.02);
            document.getElementById('tradeFormTarget').value = dir === 'LONG' ? roundPrice(entry * 1.04) : roundPrice(entry * 0.96);
        }
    }
}

function roundPrice(p) {
    if (p >= 1000) return p.toFixed(1);
    if (p >= 1) return p.toFixed(2);
    return p.toFixed(4);
}

// =========================================================================
// ⚡ KALDIRAÇ & MARJİN VE POZİSYON HESAPLAMALARI
// =========================================================================

function setTradeLeverage(lev) {
    document.getElementById('tradeFormLeverage').value = lev;
    onLeverageOrMarginChange();
}

function onLeverageOrMarginChange() {
    const lev = Math.max(1, parseInt(document.getElementById('tradeFormLeverage').value) || 1);
    const margin = parseFloat(document.getElementById('tradeFormMargin').value) || 0;
    
    if (margin > 0) {
        const totalSize = roundPrice(margin * lev);
        document.getElementById('tradeFormSize').value = totalSize;
    }
    updateDepositUsageHint();
}

function onMarginInputChange() {
    const lev = Math.max(1, parseInt(document.getElementById('tradeFormLeverage').value) || 1);
    const margin = parseFloat(document.getElementById('tradeFormMargin').value) || 0;
    
    if (margin > 0) {
        document.getElementById('tradeFormSize').value = roundPrice(margin * lev);
    }
    updateDepositUsageHint();
}

function onPositionSizeInputChange() {
    const lev = Math.max(1, parseInt(document.getElementById('tradeFormLeverage').value) || 1);
    const totalSize = parseFloat(document.getElementById('tradeFormSize').value) || 0;
    
    if (totalSize > 0) {
        document.getElementById('tradeFormMargin').value = roundPrice(totalSize / lev);
    }
    updateDepositUsageHint();
}

function updateDepositUsageHint() {
    const margin = parseFloat(document.getElementById('tradeFormMargin').value) || 0;
    const lev = Math.max(1, parseInt(document.getElementById('tradeFormLeverage').value) || 1);
    const totalSize = parseFloat(document.getElementById('tradeFormSize').value) || (margin * lev);
    const initDeposit = currentStats.initial_deposit || 1000.0;
    const defaultFeeRate = currentStats.default_fee_pct !== undefined ? currentStats.default_fee_pct : 0.05;

    // Otomatik komisyon hesapla (Giriş + Çıkış = 2 işlem)
    const feeInput = document.getElementById('tradeFormFee');
    if (feeInput && !feeInput.dataset.manual) {
        const estFee = (totalSize * (defaultFeeRate / 100.0) * 2).toFixed(2);
        feeInput.value = estFee;
    }

    const badge = document.getElementById('tradeDepositUsageBadge');
    if (!badge) return;

    if (margin > 0) {
        const riskPct = ((margin / initDeposit) * 100.0).toFixed(1);
        const curFee = feeInput ? feeInput.value : '0.00';
        badge.textContent = `Kasa Payı: %${riskPct} ($${margin}) | ${lev}x | Poz: $${totalSize} | Kom: $${curFee}`;
    } else {
        badge.textContent = '';
    }
}

// =========================================================================
// 💰 KASA / BAŞLANGIÇ DEPOZİTOSU YÖNETİMİ (DEPOSIT MODAL)
// =========================================================================

function openDepositModal() {
    const initDep = currentStats.initial_deposit || 1000;
    const defFee = currentStats.default_fee_pct !== undefined ? currentStats.default_fee_pct : 0.05;
    document.getElementById('depositInput').value = initDep;
    const feeInp = document.getElementById('defaultFeeInput');
    if (feeInp) feeInp.value = defFee;
    document.getElementById('depositModal').classList.remove('hidden');
    document.getElementById('depositModal').classList.add('flex');
}

function closeDepositModal() {
    document.getElementById('depositModal').classList.add('hidden');
    document.getElementById('depositModal').classList.remove('flex');
}

function setDepositValue(val) {
    document.getElementById('depositInput').value = val;
}

async function handleDepositFormSubmit(e) {
    e.preventDefault();
    const newDeposit = parseFloat(document.getElementById('depositInput').value) || 1000;
    const newFee = parseFloat(document.getElementById('defaultFeeInput')?.value) || 0.05;

    try {
        const res = await fetch('/api/journal/deposit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ deposit: newDeposit, default_fee_pct: newFee })
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        
        closeDepositModal();
        await fetchJournalStats();
        await fetchJournalTrades();
    } catch (e) {
        alert('Depozito güncellenirken hata oluştu: ' + e.message);
    }
}

// =========================================================================
// 📊 STATS & LİSTE GÖRÜNÜMÜ RENDER
// =========================================================================

async function fetchJournalStats() {
    try {
        const res = await fetch('/api/journal/stats');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        currentStats = data.stats || {};
        renderJournalStats(currentStats);
    } catch (e) {
        console.error('Journal stats error:', e);
    }
}

function renderJournalStats(s) {
    const curBalEl = document.getElementById('statCurrentBalance');
    const initDepHint = document.getElementById('statInitialDepositHint');
    const growthEl = document.getElementById('statAccountGrowth');
    const totTrades = document.getElementById('statTotalTrades');
    const openTradesHint = document.getElementById('statOpenTradesHint');
    const winRateEl = document.getElementById('statWinRate');
    const winCountEl = document.getElementById('statWinCount');
    const pnlAmtEl = document.getElementById('statTotalPnlAmount');
    const avgLevEl = document.getElementById('statAvgLeverage');
    const avgRREl = document.getElementById('statAvgRR');
    const pfEl = document.getElementById('statProfitFactor');

    const curBal = s.current_balance !== undefined ? s.current_balance : 1000;
    const initDep = s.initial_deposit !== undefined ? s.initial_deposit : 1000;
    const growth = s.account_growth_pct || 0;
    const pnlAmt = s.total_pnl_amount || 0;

    if (curBalEl) curBalEl.textContent = `$${curBal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (initDepHint) initDepHint.textContent = `Depozito: $${initDep.toLocaleString('en-US')}`;

    if (growthEl) {
        const sign = growth > 0 ? '+' : '';
        growthEl.textContent = `${sign}%${growth.toFixed(1)}`;
        growthEl.className = growth >= 0 
            ? 'text-xl sm:text-2xl font-black text-emerald-400 font-mono mt-0.5' 
            : 'text-xl sm:text-2xl font-black text-rose-400 font-mono mt-0.5';
    }

    if (pnlAmtEl) {
        const sign = pnlAmt > 0 ? '+' : '';
        pnlAmtEl.textContent = `${sign}$${pnlAmt.toFixed(2)} Net`;
        pnlAmtEl.className = pnlAmt >= 0 ? 'text-[9px] text-emerald-400/80 font-mono' : 'text-[9px] text-rose-400/80 font-mono';
    }

    if (totTrades) totTrades.textContent = s.total_trades || 0;
    if (openTradesHint) openTradesHint.textContent = `${s.open_trades || 0} Açık Pozisyon`;
    if (winRateEl) winRateEl.textContent = `%${(s.win_rate || 0).toFixed(1)}`;
    if (winCountEl) winCountEl.textContent = `${s.winning_trades || 0} Kazanç / ${s.losing_trades || 0} Kayıp`;
    
    const feesEl = document.getElementById('statTotalFees');
    if (feesEl) {
        const feeTotal = s.total_fees_paid || 0;
        feesEl.textContent = `-$${feeTotal.toFixed(2)}`;
    }
    if (avgLevEl) avgLevEl.textContent = `${s.avg_leverage || 1.0}x Ort. Kaldıraç`;
    if (avgRREl) avgRREl.textContent = `${s.avg_rr || 0} R Ortalama`;
    if (pfEl) pfEl.textContent = (s.profit_factor || 0).toFixed(2);
}

async function fetchJournalTrades() {
    try {
        const res = await fetch(`/api/journal?status=${activeJournalStatusFilter}`);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        currentJournalTrades = data.trades || [];
        applyJournalFilters();
        if (activeJournalView === 'calendar') {
            renderTradingCalendar();
        }
    } catch (e) {
        console.error('Fetch journal error:', e);
    }
}

function filterJournalByStatus(status) {
    activeJournalStatusFilter = status;
    document.querySelectorAll('.journal-filter-btn').forEach(btn => {
        if (btn.getAttribute('data-status') === status) {
            btn.className = 'journal-filter-btn px-2.5 py-1 rounded-lg bg-indigo-600 text-white transition';
        } else {
            btn.className = 'journal-filter-btn px-2.5 py-1 rounded-lg text-gray-400 hover:text-white transition';
        }
    });
    fetchJournalTrades();
}

function applyJournalFilters() {
    const q = (document.getElementById('journalSearchInput')?.value || '').toUpperCase().trim();
    let filtered = currentJournalTrades;
    if (q) {
        filtered = filtered.filter(t => t.symbol.includes(q) || (t.notes && t.notes.toUpperCase().includes(q)));
    }
    renderJournalTable(filtered);
}

function renderJournalTable(trades) {
    const tbody = document.getElementById('journalTableBody');
    const mobileList = document.getElementById('journalMobileCardList');
    const empty = document.getElementById('journalEmptyState');

    if (!tbody) return;

    if (trades.length === 0) {
        tbody.innerHTML = '';
        if (mobileList) mobileList.innerHTML = '';
        if (empty) empty.classList.remove('hidden');
        return;
    }

    if (empty) empty.classList.add('hidden');

    // Desktop Tablo
    tbody.innerHTML = trades.map(t => {
        const isLong = t.direction === 'LONG';
        const dirBadge = isLong 
            ? '<span class="px-2 py-0.5 rounded-lg bg-emerald-500/20 text-emerald-400 font-bold text-[10px] border border-emerald-500/30">LONG</span>'
            : '<span class="px-2 py-0.5 rounded-lg bg-rose-500/20 text-rose-400 font-bold text-[10px] border border-rose-500/30">SHORT</span>';

        const levBadge = `<span class="px-1.5 py-0.5 rounded-md bg-purple-500/20 text-purple-300 font-bold text-[10px] border border-purple-500/30">${t.leverage || 1}x</span>`;

        let statusBadge = '<span class="px-2 py-0.5 rounded-lg bg-cyan-500/20 text-cyan-400 font-bold text-[10px]">AÇIK</span>';
        if (t.status === 'WIN_TP') statusBadge = '<span class="px-2 py-0.5 rounded-lg bg-emerald-500/20 text-emerald-400 font-bold text-[10px]">KÂR (TP)</span>';
        if (t.status === 'LOSS_SL') statusBadge = '<span class="px-2 py-0.5 rounded-lg bg-rose-500/20 text-rose-400 font-bold text-[10px]">ZARAR (SL)</span>';
        if (t.status === 'CLOSED') statusBadge = '<span class="px-2 py-0.5 rounded-lg bg-gray-700 text-gray-300 font-bold text-[10px]">KAPANDI</span>';

        const pnlPct = t.pnl_percent || 0;
        const pnlAmt = t.pnl_amount || 0;
        const sign = pnlAmt > 0 ? '+' : '';
        const pnlColor = pnlAmt > 0 ? 'text-emerald-400 font-bold' : (pnlAmt < 0 ? 'text-rose-400 font-bold' : 'text-gray-400');

        return `
            <tr class="hover:bg-gray-900/50 transition">
                <td class="p-3.5">
                    <div class="font-bold text-white">${t.symbol}</div>
                    <div class="text-[10px] text-gray-400 font-sans">${t.entry_date_str || ''}</div>
                </td>
                <td class="p-3.5">
                    <div class="flex items-center gap-1.5">
                        ${dirBadge}
                        ${levBadge}
                    </div>
                </td>
                <td class="p-3.5">
                    <div class="text-gray-200">$${(t.margin || 0).toLocaleString()} <span class="text-[10px] text-gray-500">Marjin</span></div>
                    <div class="text-[10px] text-gray-400">Poz: $${(t.position_size || 0).toLocaleString()}</div>
                </td>
                <td class="p-3.5">
                    <div class="text-yellow-400 font-bold">$${t.entry_price || '-'}</div>
                    <div class="text-[10px] text-gray-400">SL: <span class="text-rose-400">$${t.stop_loss || '-'}</span> | TP: <span class="text-emerald-400">$${t.target_price || '-'}</span></div>
                </td>
                <td class="p-3.5">
                    <div class="text-white">${t.exit_price ? '$' + t.exit_price : '<span class="text-gray-600">-</span>'}</div>
                </td>
                <td class="p-3.5">
                    <div class="${pnlColor}">${sign}$${pnlAmt.toFixed(2)} <span class="text-[9px] text-gray-500 font-sans">(-$${(t.fee || 0).toFixed(2)})</span></div>
                    <div class="text-[10px] ${pnlColor}">${sign}%${pnlPct.toFixed(1)} Net ROE</div>
                </td>
                <td class="p-3.5">${statusBadge}</td>
                <td class="p-3.5 font-sans">
                    <div class="text-[11px] text-indigo-300 font-medium">${t.strategy || 'Kişisel'}</div>
                    ${t.notes ? `<div class="text-[10px] text-gray-400 italic truncate max-w-[140px]" title="${t.notes}">"${t.notes}"</div>` : ''}
                </td>
                <td class="p-3.5 text-right font-sans">
                    <div class="flex items-center justify-end gap-1.5">
                        ${t.status === 'OPEN' ? `
                            <button onclick="quickSetTradeStatus('${t.id}', 'WIN_TP')" title="Kâr Alındı (TP)" class="px-2 py-1 rounded-lg bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 text-xs font-bold transition">TP</button>
                            <button onclick="quickSetTradeStatus('${t.id}', 'LOSS_SL')" title="Stop Oldu (SL)" class="px-2 py-1 rounded-lg bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 text-xs font-bold transition">SL</button>
                        ` : ''}
                        <button onclick="openEditTradeModal('${t.id}')" title="Düzenle" class="p-1.5 rounded-lg bg-gray-800 text-gray-300 hover:text-white transition">
                            <i data-lucide="edit-3" class="w-3.5 h-3.5"></i>
                        </button>
                        <button onclick="deleteJournalTrade('${t.id}')" title="Sil" class="p-1.5 rounded-lg bg-rose-500/20 text-rose-400 hover:bg-rose-500/30 transition">
                            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    // Mobil Kartlar
    if (mobileList) {
        mobileList.innerHTML = trades.map(t => {
            const isLong = t.direction === 'LONG';
            const dirBadge = isLong 
                ? '<span class="px-2 py-0.5 rounded-lg bg-emerald-500/20 text-emerald-400 font-bold text-[10px] border border-emerald-500/30">LONG</span>'
                : '<span class="px-2 py-0.5 rounded-lg bg-rose-500/20 text-rose-400 font-bold text-[10px] border border-rose-500/30">SHORT</span>';

            const levBadge = `<span class="px-1.5 py-0.5 rounded-md bg-purple-500/20 text-purple-300 font-bold text-[10px] border border-purple-500/30">${t.leverage || 1}x</span>`;

            let statusBadge = '<span class="px-2 py-0.5 rounded-lg bg-cyan-500/20 text-cyan-400 font-bold text-[10px]">AÇIK</span>';
            if (t.status === 'WIN_TP') statusBadge = '<span class="px-2 py-0.5 rounded-lg bg-emerald-500/20 text-emerald-400 font-bold text-[10px]">KÂR (TP)</span>';
            if (t.status === 'LOSS_SL') statusBadge = '<span class="px-2 py-0.5 rounded-lg bg-rose-500/20 text-rose-400 font-bold text-[10px]">ZARAR (SL)</span>';
            if (t.status === 'CLOSED') statusBadge = '<span class="px-2 py-0.5 rounded-lg bg-gray-700 text-gray-300 font-bold text-[10px]">KAPANDI</span>';

            const pnlPct = t.pnl_percent || 0;
            const pnlAmt = t.pnl_amount || 0;
            const sign = pnlAmt > 0 ? '+' : '';
            const pnlColor = pnlAmt > 0 ? 'text-emerald-400' : (pnlAmt < 0 ? 'text-rose-400' : 'text-gray-400');

            return `
                <div class="glass-panel p-3.5 rounded-2xl border border-gray-800/80 space-y-2.5 font-mono">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-1.5">
                            <span class="font-black text-white text-sm">${t.symbol}</span>
                            ${dirBadge}
                            ${levBadge}
                        </div>
                        <div>${statusBadge}</div>
                    </div>

                    <div class="grid grid-cols-2 gap-2 text-[11px] bg-gray-950/60 p-2.5 rounded-xl border border-gray-800/60">
                        <div>
                            <span class="text-gray-500 block text-[9px]">GİRİŞ / MARJİN:</span>
                            <span class="text-yellow-400 font-bold">$${t.entry_price}</span> <span class="text-gray-400">($${t.margin || 0})</span>
                        </div>
                        <div>
                            <span class="text-gray-500 block text-[9px]">NET KÂR / ROE:</span>
                            <span class="${pnlColor} font-bold text-xs">${sign}$${pnlAmt.toFixed(2)} (${sign}%${pnlPct.toFixed(1)})</span>
                            <span class="text-[9px] text-gray-500 block">Kom: -$${(t.fee || 0).toFixed(2)}</span>
                        </div>
                        <div>
                            <span class="text-gray-500 block text-[9px]">STOP LOSS:</span>
                            <span class="text-rose-400">$${t.stop_loss || '-'}</span>
                        </div>
                        <div>
                            <span class="text-gray-500 block text-[9px]">HEDEF (TP):</span>
                            <span class="text-emerald-400">$${t.target_price || '-'}</span>
                        </div>
                    </div>

                    ${t.notes ? `<div class="text-[11px] text-gray-400 font-sans italic bg-gray-900/50 p-2 rounded-lg border border-gray-800/60">"${t.notes}"</div>` : ''}

                    <div class="flex items-center justify-between pt-2 border-t border-gray-800/80">
                        <span class="text-[10px] text-gray-500 font-sans">${t.entry_date_str || ''}</span>
                        <div class="flex items-center gap-1.5 font-sans">
                            ${t.status === 'OPEN' ? `
                                <button onclick="quickSetTradeStatus('${t.id}', 'WIN_TP')" class="px-2.5 py-1 rounded-lg bg-emerald-500/20 text-emerald-300 text-xs font-bold">Kâr</button>
                                <button onclick="quickSetTradeStatus('${t.id}', 'LOSS_SL')" class="px-2.5 py-1 rounded-lg bg-rose-500/20 text-rose-300 text-xs font-bold">Zarar</button>
                            ` : ''}
                            <button onclick="openEditTradeModal('${t.id}')" class="p-1.5 rounded-lg bg-gray-800 text-gray-300"><i data-lucide="edit-3" class="w-3.5 h-3.5"></i></button>
                            <button onclick="deleteJournalTrade('${t.id}')" class="p-1.5 rounded-lg bg-rose-500/20 text-rose-400"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    lucide.createIcons();
}

// =========================================================================
// 📅 TAKVİM BAZLI GÜNLÜK GÖRÜNÜMÜ MOTORU (TRADING CALENDAR)
// =========================================================================

const MONTH_NAMES = [
    'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
    'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'
];

function changeCalendarMonth(delta) {
    calendarDate.setMonth(calendarDate.getMonth() + delta);
    renderTradingCalendar();
}

function goToCurrentMonth() {
    calendarDate = new Date();
    renderTradingCalendar();
}

function renderTradingCalendar() {
    const year = calendarDate.getFullYear();
    const month = calendarDate.getMonth(); // 0-indexed

    const titleEl = document.getElementById('calendarMonthTitle');
    if (titleEl) {
        titleEl.textContent = `${MONTH_NAMES[month]} ${year}`;
    }

    const grid = document.getElementById('calendarGridDays');
    if (!grid) return;

    // Ayın ilk gününün haftanın hangi günü olduğu (Pazartesi = 0, Pazar = 6)
    const firstDay = new Date(year, month, 1);
    let startDayOfWeek = firstDay.getDay() - 1;
    if (startDayOfWeek === -1) startDayOfWeek = 6; // Pazar günü

    // Bu aydaki gün sayısı
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    // Önceki aydaki gün sayısı
    const daysInPrevMonth = new Date(year, month, 0).getDate();

    const dailyMap = currentStats.daily_calendar || {};

    let monthTotalPnl = 0;
    let monthTotalTrades = 0;
    let html = '';

    // Önceki aydan taşan günler
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
        const prevDayNum = daysInPrevMonth - i;
        html += `
            <div class="min-h-[90px] sm:min-h-[110px] p-2 rounded-2xl bg-gray-950/40 border border-gray-800/40 opacity-30 text-gray-600 font-mono text-xs flex flex-col justify-between">
                <span class="text-[11px]">${prevDayNum}</span>
            </div>
        `;
    }

    // Bu ayın günleri
    const todayStr = new Date().toISOString().slice(0, 10);
    const pad = n => String(n).padStart(2, '0');

    for (let d = 1; d <= daysInMonth; d++) {
        const dateKey = `${year}-${pad(month + 1)}-${pad(d)}`;
        const isToday = dateKey === todayStr;
        const dayData = dailyMap[dateKey];

        if (dayData && dayData.trade_count > 0) {
            monthTotalPnl += dayData.net_pnl_amount;
            monthTotalTrades += dayData.trade_count;

            const pnl = dayData.net_pnl_amount;
            const sign = pnl > 0 ? '+' : '';
            const isProfit = pnl > 0;
            const isLoss = pnl < 0;

            const cardStyle = isProfit 
                ? 'bg-emerald-950/20 border-emerald-500/40 hover:border-emerald-400 hover:bg-emerald-950/40 shadow-emerald-500/10'
                : (isLoss ? 'bg-rose-950/20 border-rose-500/40 hover:border-rose-400 hover:bg-rose-950/40 shadow-rose-500/10' : 'bg-gray-900/60 border-gray-700/60');

            const pnlTextClass = isProfit ? 'text-emerald-400' : (isLoss ? 'text-rose-400' : 'text-gray-300');

            html += `
                <div onclick="openDayDetailsModal('${dateKey}')" class="min-h-[90px] sm:min-h-[110px] p-2 rounded-2xl border ${cardStyle} shadow-lg transition flex flex-col justify-between cursor-pointer group active:scale-95">
                    <div class="flex items-center justify-between">
                        <span class="text-xs font-black ${isToday ? 'text-indigo-400 px-1.5 py-0.5 rounded-md bg-indigo-500/20 border border-indigo-500/40' : 'text-gray-300'}">${d}</span>
                        <span class="text-[10px] font-sans px-1.5 py-0.5 rounded-md bg-gray-900/80 text-gray-400 border border-gray-800">${dayData.trade_count} İşlem</span>
                    </div>

                    <div class="my-auto text-center py-1">
                        <div class="text-xs sm:text-sm font-black font-mono ${pnlTextClass}">${sign}$${pnl.toFixed(2)}</div>
                        <div class="text-[9px] text-gray-400 font-sans">${dayData.win_count}W / ${dayData.loss_count}L</div>
                    </div>

                    <div class="text-[9px] text-indigo-300 font-sans flex items-center justify-between opacity-80 group-hover:opacity-100">
                        <span>Detaylar</span>
                        <i data-lucide="arrow-up-right" class="w-3 h-3"></i>
                    </div>
                </div>
            `;
        } else {
            // İşlem olmayan gün
            html += `
                <div class="min-h-[90px] sm:min-h-[110px] p-2 rounded-2xl bg-gray-950/60 border ${isToday ? 'border-indigo-500/50 bg-indigo-950/10' : 'border-gray-800/60'} text-gray-500 font-mono text-xs flex flex-col justify-between">
                    <div class="flex items-center justify-between">
                        <span class="text-xs font-bold ${isToday ? 'text-indigo-400 px-1.5 py-0.5 rounded-md bg-indigo-500/20 border border-indigo-500/40' : 'text-gray-400'}">${d}</span>
                    </div>
                    <div class="text-center text-[10px] text-gray-700 font-sans my-auto">-</div>
                    <div class="text-[9px] text-transparent">-</div>
                </div>
            `;
        }
    }

    // Gelecek aydan taşan günler
    const totalCells = startDayOfWeek + daysInMonth;
    const remainingCells = (7 - (totalCells % 7)) % 7;
    for (let i = 1; i <= remainingCells; i++) {
        html += `
            <div class="min-h-[90px] sm:min-h-[110px] p-2 rounded-2xl bg-gray-950/40 border border-gray-800/40 opacity-30 text-gray-600 font-mono text-xs flex flex-col justify-between">
                <span class="text-[11px]">${i}</span>
            </div>
        `;
    }

    grid.innerHTML = html;

    // Ay Özeti Rozeti Güncelle
    const monthPnlEl = document.getElementById('calendarMonthPnlText');
    const monthTradesEl = document.getElementById('calendarMonthTradesText');
    if (monthPnlEl) {
        const sign = monthTotalPnl > 0 ? '+' : '';
        monthPnlEl.textContent = `${sign}$${monthTotalPnl.toFixed(2)}`;
        monthPnlEl.className = monthTotalPnl >= 0 ? 'font-black text-sm text-emerald-400' : 'font-black text-sm text-rose-400';
    }
    if (monthTradesEl) {
        monthTradesEl.textContent = `(${monthTotalTrades} İşlem)`;
    }

    lucide.createIcons();
}

// 🪟 GÜNLÜK DETAY MODALI (DAY DETAILS POPUP)
function openDayDetailsModal(dateKey) {
    const dayData = currentStats.daily_calendar ? currentStats.daily_calendar[dateKey] : null;
    if (!dayData) return;

    document.getElementById('dayModalDateTitle').textContent = `📅 ${dateKey} Tarihli İşlem Karnesi`;
    
    const pnl = dayData.net_pnl_amount;
    const sign = pnl > 0 ? '+' : '';
    const sumEl = document.getElementById('dayModalPnlSummary');
    sumEl.textContent = `Net Kâr: ${sign}$${pnl.toFixed(2)} (${dayData.win_count} Kazanç / ${dayData.loss_count} Kayıp)`;
    sumEl.className = pnl >= 0 ? 'text-[11px] font-mono text-emerald-400 font-bold' : 'text-[11px] font-mono text-rose-400 font-bold';

    const list = document.getElementById('dayModalTradeList');
    list.innerHTML = dayData.trades.map(t => {
        const isLong = t.direction === 'LONG';
        const dirBadge = isLong 
            ? '<span class="px-2 py-0.5 rounded-lg bg-emerald-500/20 text-emerald-400 font-bold text-[10px]">LONG</span>'
            : '<span class="px-2 py-0.5 rounded-lg bg-rose-500/20 text-rose-400 font-bold text-[10px]">SHORT</span>';

        const pnlAmt = t.pnl_amount || 0;
        const pnlPct = t.pnl_percent || 0;
        const tSign = pnlAmt > 0 ? '+' : '';
        const pColor = pnlAmt > 0 ? 'text-emerald-400' : (pnlAmt < 0 ? 'text-rose-400' : 'text-gray-400');

        return `
            <div class="glass-panel p-3 rounded-2xl border border-gray-800 space-y-2">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-1.5">
                        <span class="font-bold text-white text-sm">${t.symbol}</span>
                        ${dirBadge}
                        <span class="px-1.5 py-0.5 rounded-md bg-purple-500/20 text-purple-300 font-bold text-[10px]">${t.leverage || 1}x</span>
                    </div>
                    <span class="${pColor} font-bold text-xs">${tSign}$${pnlAmt.toFixed(2)} (${tSign}%${pnlPct.toFixed(1)})</span>
                </div>
                <div class="flex items-center justify-between text-[11px] text-gray-400 font-sans">
                    <span>Marjin: $${t.margin || 0} (Poz: $${t.position_size || 0})</span>
                    <span class="text-indigo-300">${t.strategy || 'Kişisel'}</span>
                </div>
                <div class="flex items-center justify-end gap-2 pt-2 border-t border-gray-800/60 font-sans">
                    <button onclick="closeDayDetailsModal(); openEditTradeModal('${t.id}');" class="px-2.5 py-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-bold transition">Düzenle</button>
                    <button onclick="deleteJournalTrade('${t.id}'); closeDayDetailsModal();" class="px-2.5 py-1 rounded-lg bg-rose-500/20 text-rose-400 hover:bg-rose-500/30 text-xs font-bold transition">Sil</button>
                </div>
            </div>
        `;
    }).join('');

    document.getElementById('dayDetailsModal').classList.remove('hidden');
    document.getElementById('dayDetailsModal').classList.add('flex');
}

function closeDayDetailsModal() {
    document.getElementById('dayDetailsModal').classList.add('hidden');
    document.getElementById('dayDetailsModal').classList.remove('flex');
}

// =========================================================================
// 🪟 TRADE MODAL AÇMA / DÜZENLEME / KAYDETME
// =========================================================================

function openNewTradeModal() {
    document.getElementById('tradeFormId').value = '';
    document.getElementById('tradeModalTitle').textContent = 'Yeni İşlem Kaydı Ekle';
    document.getElementById('tradeForm').reset();
    document.getElementById('tradeLivePriceText').textContent = '';
    document.getElementById('tradeFormLeverage').value = '1';
    document.getElementById('tradeFormMargin').value = '';
    document.getElementById('tradeFormSize').value = '';
    const feeInp = document.getElementById('tradeFormFee');
    if (feeInp) {
        feeInp.value = '';
        delete feeInp.dataset.manual;
    }
    
    setQuickDate(0, 'tradeFormEntryDate');
    clearDateField('tradeFormExitDate');
    updateDepositUsageHint();
    
    document.getElementById('tradeModal').classList.remove('hidden');
    document.getElementById('tradeModal').classList.add('flex');

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
    document.getElementById('tradeFormLeverage').value = trade.leverage || 1;
    document.getElementById('tradeFormMargin').value = trade.margin || '';
    document.getElementById('tradeFormSize').value = trade.position_size || '';
    const feeInp = document.getElementById('tradeFormFee');
    if (feeInp) {
        feeInp.value = trade.fee !== undefined ? trade.fee : '';
        feeInp.dataset.manual = 'true';
    }
    document.getElementById('tradeFormEntry').value = trade.entry_price || '';
    document.getElementById('tradeFormStopLoss').value = trade.stop_loss || '';
    document.getElementById('tradeFormTarget').value = trade.target_price || '';
    document.getElementById('tradeFormStatus').value = trade.status || 'OPEN';
    document.getElementById('tradeFormExit').value = trade.exit_price || '';
    document.getElementById('tradeFormStrategy').value = trade.strategy || 'Kişisel Analiz';
    document.getElementById('tradeFormNotes').value = trade.notes || '';
    
    if (trade.entry_date_str) {
        const inp = document.getElementById('tradeFormEntryDate');
        inp.value = trade.entry_date_str;
        if (inp._flatpickr) inp._flatpickr.setDate(trade.entry_date_str, true);
    } else {
        setQuickDate(0, 'tradeFormEntryDate');
    }

    if (trade.exit_date_str) {
        const inp = document.getElementById('tradeFormExitDate');
        inp.value = trade.exit_date_str;
        if (inp._flatpickr) inp._flatpickr.setDate(trade.exit_date_str, true);
    } else {
        clearDateField('tradeFormExitDate');
    }

    document.getElementById('tradeLivePriceText').textContent = '';
    updateDepositUsageHint();
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

    const feeVal = document.getElementById('tradeFormFee')?.value;
    const payload = {
        symbol: document.getElementById('tradeFormSymbol').value.toUpperCase().trim(),
        direction: document.getElementById('tradeFormDirection').value,
        leverage: parseInt(document.getElementById('tradeFormLeverage').value) || 1,
        margin: parseFloat(document.getElementById('tradeFormMargin').value) || 0,
        position_size: parseFloat(document.getElementById('tradeFormSize').value) || 0,
        fee: feeVal !== undefined && feeVal !== '' ? parseFloat(feeVal) : null,
        entry_price: parseFloat(document.getElementById('tradeFormEntry').value) || 0,
        stop_loss: parseFloat(document.getElementById('tradeFormStopLoss').value) || 0,
        target_price: parseFloat(document.getElementById('tradeFormTarget').value) || 0,
        status: document.getElementById('tradeFormStatus').value,
        exit_price: parseFloat(document.getElementById('tradeFormExit').value) || null,
        strategy: document.getElementById('tradeFormStrategy').value,
        notes: document.getElementById('tradeFormNotes').value,
        entry_date_str: entryDateInput || new Date().toISOString().slice(0, 16).replace('T', ' '),
        exit_date_str: exitDateInput || null
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
        await fetchJournalStats();
        await fetchJournalTrades();
    } catch (e) {
        alert('İşlem kaydedilirken hata oluştu: ' + e.message);
    }
}

async function quickSetTradeStatus(tradeId, status) {
    const trade = currentJournalTrades.find(t => t.id === tradeId);
    if (!trade) return;

    let exitPrice = trade.exit_price;
    if (status === 'WIN_TP' && trade.target_price) {
        exitPrice = trade.target_price;
    } else if (status === 'LOSS_SL' && trade.stop_loss) {
        exitPrice = trade.stop_loss;
    }

    try {
        const res = await fetch(`/api/journal/${tradeId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                status: status,
                exit_price: exitPrice,
                exit_date_str: new Date().toISOString().slice(0, 16).replace('T', ' ')
            })
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        await fetchJournalStats();
        await fetchJournalTrades();
    } catch (e) {
        console.error('Quick status update error:', e);
    }
}

async function deleteJournalTrade(tradeId) {
    if (!confirm('Bu işlemi günlükten silmek istediğinize emin misiniz?')) return;
    try {
        const res = await fetch(`/api/journal/${tradeId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        await fetchJournalStats();
        await fetchJournalTrades();
    } catch (e) {
        alert('İşlem silinirken hata oluştu: ' + e.message);
    }
}

// =========================================================================
// 📝 TRADE NOTLARI & FİYAT ALARMLARI MOTORU
// =========================================================================

async function fetchTradeNotes() {
    try {
        const res = await fetch('/api/trade-notes');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        currentTradeNotes = data.notes || [];
        renderTradeNotes();
    } catch (e) {
        console.error('Fetch trade notes error:', e);
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
            distPct = ((targetPrice - currPrice) / currPrice * 100.0);
        }

        let condLabel = 'Hedefe Yaklaşma';
        if (n.condition_type === 'CROSS_ABOVE') condLabel = '🔺 Üstüne Çıkış';
        if (n.condition_type === 'CROSS_BELOW') condLabel = '🔻 Altına Düşüş';

        const isTriggered = n.is_triggered;
        const isActive = n.is_active && !isTriggered;

        let statusBadge = '<span class="px-2 py-0.5 rounded-lg bg-gray-700 text-gray-300 font-bold text-[10px]">DURAKLATILDI</span>';
        if (isActive) statusBadge = '<span class="px-2 py-0.5 rounded-lg bg-amber-500/20 text-amber-300 font-bold text-[10px] border border-amber-500/30 glow-amber">🔴 CANLI TAKİP</span>';
        if (isTriggered) statusBadge = '<span class="px-2 py-0.5 rounded-lg bg-emerald-500/20 text-emerald-300 font-bold text-[10px] border border-emerald-500/30 glow-emerald">🎯 HEDEFE ULAŞTI</span>';

        return `
            <div class="glass-panel p-4 rounded-3xl border ${isActive ? 'border-amber-500/30' : (isTriggered ? 'border-emerald-500/30' : 'border-gray-800')} space-y-3 shadow-xl">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="font-black text-white text-base font-mono">${n.symbol}</span>
                        <span class="px-2 py-0.5 rounded-md bg-gray-900 border border-gray-800 text-[10px] text-gray-400 font-mono">${n.direction_bias}</span>
                    </div>
                    <div>${statusBadge}</div>
                </div>

                <div class="text-xs font-bold text-white font-sans">${n.note_title}</div>

                <div class="grid grid-cols-2 gap-2 bg-gray-950/80 p-3 rounded-2xl border border-gray-800/80 font-mono text-[11px]">
                    <div>
                        <span class="text-gray-500 block text-[9px]">HEDEF FİYAT:</span>
                        <span class="text-amber-400 font-bold text-sm">$${targetPrice.toLocaleString()}</span>
                    </div>
                    <div>
                        <span class="text-gray-500 block text-[9px]">GÜNCEL FİYAT:</span>
                        <span class="text-white font-bold text-sm">$${currPrice ? currPrice.toLocaleString() : '-'}</span>
                    </div>
                    <div class="col-span-2 pt-1 border-t border-gray-800/60 flex items-center justify-between text-[10px]">
                        <span class="text-gray-400 font-sans">${condLabel}</span>
                        <span class="${distPct >= 0 ? 'text-cyan-400' : 'text-orange-400'} font-bold">Mesafe: %${Math.abs(distPct).toFixed(2)}</span>
                    </div>
                </div>

                ${n.note_text ? `
                    <div class="bg-gray-950/60 p-2.5 rounded-xl border border-gray-800 text-[11px] text-gray-300 font-sans italic">
                        "${n.note_text}"
                    </div>
                ` : ''}

                <div class="flex items-center justify-between pt-2 border-t border-gray-800/80 text-[10px] text-gray-500 font-mono">
                    <span>${n.created_at_str || ''}</span>
                    <div class="flex items-center gap-1.5 font-sans">
                        <button onclick="toggleNoteActive('${n.id}')" class="px-2.5 py-1 rounded-lg ${n.is_active ? 'bg-amber-500/20 text-amber-300' : 'bg-emerald-500/20 text-emerald-300'} font-bold transition cursor-pointer">
                            ${n.is_active ? 'Duraklat' : 'Yeniden Başlat'}
                        </button>
                        <button onclick="deleteTradeNote('${n.id}')" class="p-1.5 rounded-lg bg-rose-500/20 text-rose-400 hover:bg-rose-500/30 transition cursor-pointer">
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
    setQuickDate(0, 'noteFormDate');
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
        created_at_str: dateInput || new Date().toISOString().slice(0, 16).replace('T', ' ')
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
    } catch (e) {
        alert('Not kaydedilirken hata oluştu: ' + e.message);
    }
}

async function toggleNoteActive(noteId) {
    try {
        const res = await fetch(`/api/trade-notes/${noteId}/toggle`, { method: 'POST' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        await fetchTradeNotes();
    } catch (e) {
        console.error('Toggle note error:', e);
    }
}

async function deleteTradeNote(noteId) {
    if (!confirm('Bu not ve alarmı silmek istediğinize emin misiniz?')) return;
    try {
        const res = await fetch(`/api/trade-notes/${noteId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        await fetchTradeNotes();
    } catch (e) {
        alert('Not silinirken hata oluştu: ' + e.message);
    }
}
