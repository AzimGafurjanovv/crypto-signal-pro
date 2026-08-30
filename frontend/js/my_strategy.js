// CryptoSignalPro AI - Özel Stratejiler Radarı (PDH/PDL & Swing High/Low) Frontend Mantığı (v6.7)

let activeStrategy = 'PDH_PDL'; // 'PDH_PDL' | 'SWING_HL'
let currentRadarData = null;
let radarChartInstance = null;
let autoRefreshTimer = null;
let autoRefreshCountdown = 30;
let isFetchingInProgress = false;
let currentFetchId = 0;

document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();

    setInterval(updateRadarClock, 1000);
    updateRadarClock();

    const tfSelect = document.getElementById('timeframeSelect');
    const dirFilter = document.getElementById('directionFilter');
    const searchInput = document.getElementById('coinSearchInput');
    const runBtn = document.getElementById('runRadarBtn');
    const swingLookback = document.getElementById('swingLookbackSelect');
    const autoRefreshIntervalSelect = document.getElementById('autoRefreshIntervalSelect');

    if (runBtn) {
        runBtn.addEventListener('click', () => fetchActiveRadarData(false));
    }

    if (tfSelect) {
        tfSelect.addEventListener('change', () => fetchActiveRadarData(false));
    }

    if (swingLookback) {
        swingLookback.addEventListener('change', () => fetchActiveRadarData(false));
    }

    const patternCatSelect = document.getElementById('patternCategorySelect');
    if (patternCatSelect) {
        patternCatSelect.addEventListener('change', () => applyRadarFiltersAndRender());
    }

    if (dirFilter) {
        dirFilter.addEventListener('change', () => applyRadarFiltersAndRender());
    }

    if (searchInput) {
        searchInput.addEventListener('input', () => applyRadarFiltersAndRender());
    }

    if (autoRefreshIntervalSelect) {
        autoRefreshIntervalSelect.addEventListener('change', (e) => {
            setupAutoRefresh(parseInt(e.target.value) || 0);
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeRadarChartModal();
        }
    });

    // Otomatik yenilemeyi 30 saniye ile başlat
    setupAutoRefresh(30);

    // İlk açılışta verileri çek
    fetchActiveRadarData(true);
});

function updateRadarClock() {
    const clockEl = document.getElementById('radarLiveClock');
    if (clockEl) {
        const now = new Date();
        clockEl.textContent = now.toLocaleTimeString('tr-TR', { hour12: false }) + ' UTC+3';
    }
}

// 🔀 STRATEJİLER ARASINDA GEÇİŞ YAP
function switchStrategy(newStrat) {
    if (activeStrategy === newStrat) return;
    activeStrategy = newStrat;

    const tabPdh = document.getElementById('tabPdhPdlBtn');
    const tabSwing = document.getElementById('tabSwingBtn');
    const tabPattern = document.getElementById('tabPatternBtn');
    const swingWrapper = document.getElementById('swingLookbackWrapper');
    const patternGuide = document.getElementById('patternGuideWrapper');
    const patternFilter = document.getElementById('patternFilterWrapper');
    const heroBadge = document.getElementById('heroStrategyBadge');
    const heroSub = document.getElementById('heroStrategySub');
    const heroTitle = document.getElementById('heroStrategyTitle');
    const heroDesc = document.getElementById('heroStrategyDesc');

    // Tab stillerini sıfırla
    const inactiveClass = "flex-1 sm:flex-none px-3.5 py-2 rounded-xl bg-gray-900 text-gray-400 hover:text-white hover:bg-gray-800 font-bold text-xs flex items-center justify-center gap-1.5 transition cursor-pointer border border-transparent hover:border-gray-700";
    if (tabPdh) tabPdh.className = inactiveClass;
    if (tabSwing) tabSwing.className = inactiveClass;
    if (tabPattern) tabPattern.className = inactiveClass;
    if (swingWrapper) swingWrapper.classList.add('hidden');
    if (patternGuide) patternGuide.classList.add('hidden');
    if (patternFilter) patternFilter.classList.add('hidden');

    if (activeStrategy === 'PDH_PDL') {
        if (tabPdh) tabPdh.className = "flex-1 sm:flex-none px-3.5 py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition shadow-md shadow-cyan-600/20 cursor-pointer";
        if (heroBadge) heroBadge.textContent = "⭐ 1. STRATEJİ (GÜNLÜK LİKİDİTE)";
        if (heroSub) heroSub.textContent = "UTC 00:00–24:00 Daily Boundary";
        if (heroTitle) heroTitle.textContent = "Önceki Gün Zirve / Dip Kırılımı + Retest & Onay (PDH / PDL)";
        if (heroDesc) heroDesc.innerHTML = "Bu radar, Binance canlı piyasasındaki tüm coinleri 24 saatlik UTC döngüsünde mikroskop altına alır. <strong>1. Aşama (Kırılım)</strong>, <strong>2. Aşama (0.3xATR Retest)</strong> ve <strong>3. Aşama (Hacimli Onay Mumu ile Kesin Giriş)</strong> olarak 3 ayrı bölmede canlı kategorize eder.";
    } else if (activeStrategy === 'SWING_HL') {
        if (tabSwing) tabSwing.className = "flex-1 sm:flex-none px-3.5 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition shadow-md shadow-indigo-600/20 cursor-pointer";
        if (swingWrapper) swingWrapper.classList.remove('hidden');
        if (heroBadge) heroBadge.textContent = "🌊 2. STRATEJİ (YAPISAL DÖNÜŞLER)";
        if (heroSub) heroSub.textContent = "Lookback(3) Confirmed Swing Structure";
        if (heroTitle) heroTitle.textContent = "Yapısal Swing High / Low Kırılımı + Retest & Onay";
        if (heroDesc) heroDesc.innerHTML = "Bu radar, piyasanın kendi iç dönüş noktalarını (Swing High/Low) takip eder. Sabit gün döngüsü yerine gün içinde oluşan yeni teyitli tepelerin/dipların kırılımını, <strong>0.3xATR retestini</strong> ve <strong>hacimli yönlü onay mumunu</strong> canlı tespit eder.";
    } else { // CHART_PATTERNS
        if (tabPattern) tabPattern.className = "flex-1 sm:flex-none px-3.5 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition shadow-md shadow-amber-500/20 cursor-pointer";
        if (patternGuide) patternGuide.classList.remove('hidden');
        if (patternFilter) patternFilter.classList.remove('hidden');
        if (heroBadge) heroBadge.textContent = "📐 3. STRATEJİ (FORMASYON SCANNER)";
        if (heroSub) heroSub.textContent = "10 Klasik & Modern Formasyon Motoru";
        if (heroTitle) heroTitle.textContent = "Klasik & Modern Grafik Formasyonları Radarı";
        if (heroDesc) heroDesc.innerHTML = "Düşen/Yükselen Trend Çizgileri, Simetrik/Yükselen/Alçalan Üçgenler, Destek-Direnç Flip, Range ve İkili Dip (W) / Tepe (M) formasyonlarının <strong>kırılımını</strong>, <strong>retestini</strong> ve <strong>onaylı kesin giriş seviyelerini</strong> canlı tarar.";
    }

    lucide.createIcons();
    fetchActiveRadarData(true);
}

// 🔄 OTOMATİK YENİLEME VE ARKA PLAN CANLI TARAMA
function setupAutoRefresh(seconds) {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
    }

    const badge = document.getElementById('autoRefreshBadge');
    if (seconds <= 0) {
        if (badge) {
            badge.textContent = "Kapalı";
            badge.className = "text-[11px] font-mono font-bold px-2 py-0.5 rounded bg-gray-800 text-gray-500 border border-gray-700";
        }
        return;
    }

    autoRefreshCountdown = seconds;
    if (badge) {
        badge.textContent = `${autoRefreshCountdown}s`;
        badge.className = "text-[11px] font-mono font-bold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30";
    }

    autoRefreshTimer = setInterval(() => {
        autoRefreshCountdown--;
        if (autoRefreshCountdown <= 0) {
            autoRefreshCountdown = seconds;
            // Arka planda donmadan sessizce tara
            fetchActiveRadarData(false, true);
        }
        if (badge) badge.textContent = `${autoRefreshCountdown}s`;
    }, 1000);
}

async function fetchActiveRadarData(showLoadingFull = false, isSilentBackground = false) {
    const fetchId = ++currentFetchId;
    const stratAtRequest = activeStrategy;

    const tfSelect = document.getElementById('timeframeSelect');
    const swingLookback = document.getElementById('swingLookbackSelect');
    const runBtn = document.getElementById('runRadarBtn');
    const loadingState = document.getElementById('radarLoadingState');
    const content = document.getElementById('radarContent');

    const tf = tfSelect ? tfSelect.value : '1h';
    const lookback = swingLookback ? swingLookback.value : '3';

    if (!isSilentBackground && runBtn) {
        runBtn.disabled = true;
        runBtn.innerHTML = `<div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div> <span>PİYASA TARANIYOR...</span>`;
    }

    if (showLoadingFull) {
        if (loadingState) loadingState.classList.remove('hidden');
        if (content) content.classList.add('hidden');
    }

    try {
        let url = `/api/pdh-pdl-radar?timeframe=${tf}&limit_coins=50`;
        if (activeStrategy === 'SWING_HL') {
            url = `/api/swing-radar?timeframe=${tf}&limit_coins=50&swing_lookback=${lookback}`;
        } else if (activeStrategy === 'CHART_PATTERNS') {
            url = `/api/pattern-radar?timeframe=${tf}&limit_coins=50`;
        }

        const res = await fetch(url);
        const data = await res.json();

        // Race condition guard: ignore response if user already switched strategy or triggered a newer fetch
        if (fetchId !== currentFetchId || stratAtRequest !== activeStrategy) return;

        if (data.status === 'success') {
            currentRadarData = data;
            
            // Sayaçları Güncelle
            if (document.getElementById('statBreakoutCount')) document.getElementById('statBreakoutCount').textContent = data.stats.breakout_count || 0;
            if (document.getElementById('statRetestCount')) document.getElementById('statRetestCount').textContent = data.stats.retesting_count || 0;
            if (document.getElementById('statConfirmedCount')) document.getElementById('statConfirmedCount').textContent = data.stats.confirmed_count || 0;

            applyRadarFiltersAndRender();

            if (loadingState) loadingState.classList.add('hidden');
            if (content) content.classList.remove('hidden');
        }
    } catch (e) {
        console.error('Fetch radar error:', e);
    } finally {
        if (fetchId === currentFetchId) {
            isFetchingInProgress = false;
            if (runBtn) {
                runBtn.disabled = false;
                runBtn.innerHTML = `<i data-lucide="refresh-cw" class="w-4 h-4"></i> <span>RADARI CANLI TARA</span>`;
                lucide.createIcons();
            }
        }
    }
}

function applyRadarFiltersAndRender() {
    if (!currentRadarData || !currentRadarData.stages) return;

    const patternCatSelect = document.getElementById('patternCategorySelect');
    const dirFilter = document.getElementById('directionFilter');
    const searchInput = document.getElementById('coinSearchInput');

    const catVal = patternCatSelect ? patternCatSelect.value : 'ALL';
    const dirVal = dirFilter ? dirFilter.value : 'ALL';
    const query = searchInput ? searchInput.value.trim().toUpperCase() : '';

    const filterFn = (c) => {
        if (query && !c.symbol.toUpperCase().includes(query)) return false;
        if (dirVal !== 'ALL' && c.direction !== dirVal) return false;
        if (activeStrategy === 'CHART_PATTERNS' && catVal !== 'ALL' && c.pattern_category !== catVal) return false;
        return true;
    };

    const boFiltered = (currentRadarData.stages.breakout || []).filter(filterFn);
    const rtFiltered = (currentRadarData.stages.retesting || []).filter(filterFn);
    const cfFiltered = (currentRadarData.stages.confirmed || []).filter(filterFn);

    renderColumnList('colBreakoutList', boFiltered, 'breakout');
    renderColumnList('colRetestList', rtFiltered, 'retest');
    renderColumnList('colConfirmedList', cfFiltered, 'confirmed');

    if (document.getElementById('col1BadgeCount')) document.getElementById('col1BadgeCount').textContent = boFiltered.length;
    if (document.getElementById('col2BadgeCount')) document.getElementById('col2BadgeCount').textContent = rtFiltered.length;
    if (document.getElementById('col3BadgeCount')) document.getElementById('col3BadgeCount').textContent = cfFiltered.length;

    if (document.getElementById('mobBadgeBreakout')) document.getElementById('mobBadgeBreakout').textContent = boFiltered.length;
    if (document.getElementById('mobBadgeRetest')) document.getElementById('mobBadgeRetest').textContent = rtFiltered.length;
    if (document.getElementById('mobBadgeConfirmed')) document.getElementById('mobBadgeConfirmed').textContent = cfFiltered.length;

    // Apply current mobile filter state
    applyMobileStageFilter();

    lucide.createIcons();
}

let activeMobileStage = 'all';

function setMobileStageFilter(stage) {
    activeMobileStage = stage;
    applyMobileStageFilter();
}

function applyMobileStageFilter() {
    const colBreakout = document.getElementById('colBreakoutWrapper');
    const colRetest = document.getElementById('colRetestWrapper');
    const colConfirmed = document.getElementById('colConfirmedWrapper');
    if (!colBreakout || !colRetest || !colConfirmed) return;

    const isMobile = window.innerWidth < 1024;
    if (isMobile) {
        colBreakout.style.display = (activeMobileStage === 'all' || activeMobileStage === 'breakout') ? 'block' : 'none';
        colRetest.style.display = (activeMobileStage === 'all' || activeMobileStage === 'retest') ? 'block' : 'none';
        colConfirmed.style.display = (activeMobileStage === 'all' || activeMobileStage === 'confirmed') ? 'block' : 'none';
    } else {
        colBreakout.style.display = 'block';
        colRetest.style.display = 'block';
        colConfirmed.style.display = 'block';
    }

    // Update active tab buttons style
    const tabs = {
        'confirmed': document.getElementById('mobTabConfirmed'),
        'retest': document.getElementById('mobTabRetest'),
        'breakout': document.getElementById('mobTabBreakout'),
        'all': document.getElementById('mobTabAll')
    };

    Object.keys(tabs).forEach(k => {
        const el = tabs[k];
        if (!el) return;
        if (k === activeMobileStage) {
            el.className = 'flex-1 py-2 px-2.5 rounded-xl bg-cyan-500/20 text-cyan-300 font-bold text-xs flex items-center justify-center gap-1.5 transition border border-cyan-500/40 shadow-sm';
        } else {
            el.className = 'flex-1 py-2 px-2.5 rounded-xl bg-gray-900 text-gray-400 font-bold text-xs flex items-center justify-center gap-1.5 transition border border-transparent';
        }
    });
}

window.addEventListener('resize', applyMobileStageFilter);

function renderColumnList(containerId, coins, type) {
    const el = document.getElementById(containerId);
    if (!el) return;

    if (!coins || coins.length === 0) {
        el.innerHTML = `
            <div class="p-6 text-center text-gray-500 rounded-2xl border border-dashed border-gray-800 text-xs">
                Bu aşamada eşleşen kripto para bulunamadı.
            </div>
        `;
        return;
    }

    const curTf = document.getElementById('timeframeSelect')?.value || '1h';
    el.innerHTML = '';
    coins.forEach(c => {
        const isLong = c.direction === 'LONG';
        const levelLabel = activeStrategy === 'PDH_PDL' 
            ? (isLong ? 'PDH' : 'PDL')
            : (activeStrategy === 'SWING_HL' ? (isLong ? 'Swing High' : 'Swing Low') : (c.strategy_name || 'Formasyon'));
        const levelName = levelLabel;

        const levelPrice = c.breakout_level || (isLong ? (c.pdh || c.swing_level) : (c.pdl || c.swing_level));

        const dirBadge = isLong 
            ? `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 text-[10px] font-mono">🟢 LONG</span>`
            : `<span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-bold border border-rose-500/30 text-[10px] font-mono">🔴 SHORT</span>`;

        const tfBadge = c.timeframe_badge 
            ? `<span class="px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-bold border border-indigo-500/30 text-[9px] font-mono">${c.timeframe_badge}</span>`
            : `<span class="px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 font-bold border border-gray-700 text-[9px] font-mono">${(c.timeframe || curTf).toUpperCase()}</span>`;

        const qualityBadge = c.quality_score 
            ? `<span class="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30 text-[9px] font-mono">%${c.quality_score} Kalite</span>`
            : '';

        const card = document.createElement('div');
        card.className = `glass-card p-4 rounded-2xl border transition cursor-pointer group hover:scale-[1.01] ${
            type === 'confirmed' ? 'border-emerald-500/40 hover:border-emerald-400' : (type === 'retest' ? 'border-amber-500/40 hover:border-amber-400' : 'border-cyan-500/30 hover:border-cyan-400')
        }`;
        card.onclick = () => openRadarChartModal(c);

        if (type === 'confirmed') {
            card.innerHTML = `
                <div class="flex items-center justify-between pb-2 border-b border-gray-800/80">
                    <div class="flex items-center gap-2">
                        <span class="font-extrabold text-sm text-white">${c.symbol}</span>
                        ${dirBadge}
                        ${tfBadge}
                        ${qualityBadge}
                    </div>
                    <span class="text-xs font-bold text-emerald-400 font-mono flex items-center gap-1">
                        <i data-lucide="check-circle-2" class="w-3.5 h-3.5"></i>
                        <span>ONAYLANDI</span>
                    </span>
                </div>

                <div class="mt-2.5 grid grid-cols-2 gap-2 text-xs font-mono">
                    <div class="bg-gray-950/60 p-2 rounded-xl border border-gray-800">
                        <span class="text-[10px] text-gray-500 block font-sans">GİRİŞ</span>
                        <span class="font-bold text-yellow-400">$${formatPrice(c.entry_price)}</span>
                    </div>
                    <div class="bg-gray-950/60 p-2 rounded-xl border border-gray-800">
                        <span class="text-[10px] text-gray-500 block font-sans">STOP (0.2xATR)</span>
                        <span class="font-bold text-rose-400">$${formatPrice(c.stop_loss)}</span>
                    </div>
                    <div class="bg-gray-950/60 p-2 rounded-xl border border-gray-800">
                        <span class="text-[10px] text-gray-500 block font-sans">HEDEF (S/R)</span>
                        <span class="font-bold text-emerald-400">$${formatPrice(c.take_profit || c.tp1)}</span>
                    </div>
                    <div class="bg-gray-950/60 p-2 rounded-xl border border-gray-800">
                        <span class="text-[10px] text-gray-500 block font-sans">R:R ORANI</span>
                        <span class="font-bold text-cyan-300">${c.risk_reward ? c.risk_reward + ' R' : '1:2+'}</span>
                    </div>
                </div>

                <div class="mt-2.5 bg-emerald-500/10 border border-emerald-500/20 p-2 rounded-lg text-[11px] text-emerald-300">
                    <div class="font-bold flex items-center gap-1">
                        <i data-lucide="sparkles" class="w-3 h-3 text-emerald-400"></i>
                        <span>${c.confirmed_bar ? `Saat ${c.confirmed_bar.time_str} barında Onaylandı` : 'Hacimli Onay Mumu Kapandı'}</span>
                    </div>
                </div>

                <div class="mt-3 flex items-center justify-between pt-2 border-t border-gray-800/60">
                    <span class="text-[10px] text-gray-400 truncate max-w-[180px]">${levelLabel}: $${formatPrice(levelPrice)}</span>
                    <button class="px-2.5 py-1 rounded-lg bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 text-[10px] font-bold font-mono transition flex items-center gap-1">
                        <i data-lucide="line-chart" class="w-3 h-3"></i>
                        <span>Grafiği Aç & Doğrula</span>
                    </button>
                </div>
            `;
        } else if (type === 'retest') {
            card.innerHTML = `
                <div class="flex items-center justify-between pb-2 border-b border-gray-800/80">
                    <div class="flex items-center gap-2">
                        <span class="font-extrabold text-sm text-white">${c.symbol}</span>
                        ${dirBadge}
                    </div>
                    <span class="text-xs font-bold text-amber-400 font-mono">RETEST 🎯</span>
                </div>

                <div class="mt-2.5 space-y-2 text-xs font-mono">
                    <div class="flex justify-between items-center bg-gray-950/60 p-2 rounded-xl border border-gray-800">
                        <span class="text-[10px] text-gray-400 font-sans">Güncel Fiyat:</span>
                        <span class="font-bold text-white">$${formatPrice(c.current_price)}</span>
                    </div>
                    <div class="flex justify-between items-center bg-gray-950/60 p-2 rounded-xl border border-gray-800">
                        <span class="text-[10px] text-gray-400 font-sans">Seviye (${levelLabel}):</span>
                        <span class="font-bold text-cyan-400">$${formatPrice(levelPrice)}</span>
                    </div>
                </div>

                <div class="mt-2.5 bg-amber-500/10 border border-amber-500/20 p-2 rounded-lg text-[11px] text-amber-300">
                    <div class="flex items-center gap-1 font-semibold">
                        <i data-lucide="clock" class="w-3 h-3 text-amber-400"></i>
                        <span>${c.retest_bar ? `Saat ${c.retest_bar.time_str} barında 0.3xATR toleransla test edildi` : 'Seviye test ediliyor'}</span>
                    </div>
                </div>

                <div class="mt-3 flex items-center justify-between pt-2 border-t border-gray-800/60">
                    <span class="text-[10px] text-gray-400 font-sans">2 Bar İçinde Onay Bekleniyor</span>
                    <button class="px-2.5 py-1 rounded-lg bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 text-[10px] font-bold font-mono transition flex items-center gap-1">
                        <i data-lucide="line-chart" class="w-3 h-3"></i>
                        <span>İncele</span>
                    </button>
                </div>
            `;
        } else { // breakout
            card.innerHTML = `
                <div class="flex items-center justify-between pb-2 border-b border-gray-800/80">
                    <div class="flex items-center gap-2">
                        <span class="font-extrabold text-sm text-white">${c.symbol}</span>
                        ${dirBadge}
                    </div>
                    <span class="text-xs font-bold text-cyan-400 font-mono">KIRILIM ⚡</span>
                </div>

                <div class="mt-2.5 space-y-2 text-xs font-mono">
                    <div class="flex justify-between items-center bg-gray-950/60 p-2 rounded-xl border border-gray-800">
                        <span class="text-[10px] text-gray-400 font-sans">Güncel Fiyat:</span>
                        <span class="font-bold text-white">$${formatPrice(c.current_price)}</span>
                    </div>
                    <div class="flex justify-between items-center bg-gray-950/60 p-2 rounded-xl border border-gray-800">
                        <span class="text-[10px] text-gray-400 font-sans">Kırılan Seviye (${levelLabel}):</span>
                        <span class="font-bold text-cyan-400">$${formatPrice(levelPrice)}</span>
                    </div>
                </div>

                <div class="mt-3 flex items-center justify-between pt-2 border-t border-gray-800/60">
                    <span class="text-[10px] text-gray-400 font-sans">Retest için geri çekilme bekleniyor</span>
                    <button class="px-2.5 py-1 rounded-lg bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 text-[10px] font-bold font-mono transition flex items-center gap-1">
                        <i data-lucide="line-chart" class="w-3 h-3"></i>
                        <span>İncele</span>
                    </button>
                </div>
            `;
        }

        el.appendChild(card);
    });
}

// -------------------------------------------------------------
// 🔍 RADAR İNTERAKTİF GRAFİK MODALİ
// -------------------------------------------------------------
async function openRadarChartModal(coin) {
    if (!coin) return;

    const modal = document.getElementById('radarChartModal');
    if (!modal) return;

    const isLong = coin.direction === 'LONG';
    const isSwing = activeStrategy === 'SWING_HL';
    const levelName = isSwing ? (isLong ? 'SWING HIGH' : 'SWING LOW') : (isLong ? 'PDH ZİRVE' : 'PDL DİP');
    const levelPrice = coin.breakout_level || (isLong ? (coin.pdh || coin.swing_level) : (coin.pdl || coin.swing_level));

    // Header Bilgileri
    const dirBadge = document.getElementById('modalDirBadge');
    if (dirBadge) {
        dirBadge.textContent = isLong ? `🟢 LONG (${levelName} KIRILIMI)` : `🔴 SHORT (${levelName} KIRILIMI)`;
        dirBadge.className = isLong 
            ? 'px-2.5 py-1 rounded-lg bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/40 text-xs font-mono'
            : 'px-2.5 py-1 rounded-lg bg-rose-500/20 text-rose-400 font-bold border border-rose-500/40 text-xs font-mono';
    }

    const coinTf = (coin.timeframe || '1h').toUpperCase();
    if (document.getElementById('modalSymbolTitle')) document.getElementById('modalSymbolTitle').textContent = `${coin.symbol} (${coinTf})`;
    if (document.getElementById('modalStageSubtitle')) {
        document.getElementById('modalStageSubtitle').innerHTML = `
            <span class="text-amber-400 font-bold">${coin.strategy_name || 'Formasyon'}</span> • 
            <span class="text-white">${coin.stage_name}</span> • 
            <span class="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-bold border border-indigo-500/40">Zaman Dilimi: ${coinTf}</span>
        `;
    }

    const modalBacktestBtn = document.getElementById('modalBacktestBtn');
    if (modalBacktestBtn) {
        modalBacktestBtn.href = `/backtest.html?symbol=${encodeURIComponent(coin.symbol)}&timeframe=${encodeURIComponent(coin.timeframe || '1h')}`;
    }

    const pdhLabelEl = document.getElementById('badgePdhLabel');
    const pdlLabelEl = document.getElementById('badgePdlLabel');
    if (pdhLabelEl && pdlLabelEl) {
        if (activeStrategy === 'PDH_PDL') {
            pdhLabelEl.textContent = 'DÜNKÜ ZİRVE (PDH)';
            pdlLabelEl.textContent = 'DÜNKÜ DİP (PDL)';
        } else if (activeStrategy === 'SWING_HL') {
            pdhLabelEl.textContent = 'SWING SEVİYESİ';
            pdlLabelEl.textContent = 'ONAY ZAMANI';
        } else {
            pdhLabelEl.textContent = 'KIRILAN SEVİYE';
            pdlLabelEl.textContent = 'FORMASYON HEDEFİ';
        }
    }

    if (document.getElementById('badgePdh')) document.getElementById('badgePdh').textContent = `$${formatPrice(coin.pdh || coin.swing_level || levelPrice)}`;
    if (document.getElementById('badgePdl')) {
        const pdlVal = activeStrategy === 'CHART_PATTERNS' ? (coin.take_profit || coin.tp1) : (coin.pdl || coin.swing_level || levelPrice);
        document.getElementById('badgePdl').textContent = pdlVal ? `$${formatPrice(pdlVal)}` : (coin.swing_confirmed_time || '$0.00');
    }
    if (document.getElementById('badgeEntry')) document.getElementById('badgeEntry').textContent = `$${formatPrice(coin.entry_price || coin.current_price)}`;
    if (document.getElementById('badgeSl')) document.getElementById('badgeSl').textContent = `$${formatPrice(coin.stop_loss)}`;
    const tpPrice = coin.take_profit || coin.tp1;
    if (document.getElementById('badgeTp')) document.getElementById('badgeTp').textContent = tpPrice ? `$${formatPrice(tpPrice)}` : '$0.00';

    // 📋 CHECKLIST (KONTROL LİSTESİ) DOLDUR
    const checklistItemsEl = document.getElementById('modalChecklistItems');
    const verdictEl = document.getElementById('modalChecklistVerdict');
    
    if (checklistItemsEl && coin.checklist) {
        checklistItemsEl.innerHTML = '';
        let passedCount = 0;

        coin.checklist.forEach(chk => {
            if (chk.passed) passedCount++;
            const itemDiv = document.createElement('div');
            itemDiv.className = `p-2.5 rounded-xl border flex items-start gap-2.5 ${
                chk.passed ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-gray-900 border-gray-800 text-gray-400'
            }`;
            itemDiv.innerHTML = `
                <div class="mt-0.5 ${chk.passed ? 'text-emerald-400' : 'text-gray-500'}">
                    <i data-lucide="${chk.passed ? 'check-circle' : 'circle-dashed'}" class="w-4 h-4"></i>
                </div>
                <div>
                    <div class="font-bold text-xs ${chk.passed ? 'text-emerald-300' : 'text-gray-300'}">${chk.title}</div>
                    <div class="text-[11px] mt-0.5 ${chk.passed ? 'text-gray-300' : 'text-gray-500'}">${chk.detail}</div>
                </div>
            `;
            checklistItemsEl.appendChild(itemDiv);
        });

        if (verdictEl) {
            verdictEl.textContent = `${passedCount} / ${coin.checklist.length} ŞART SAĞLANDI`;
            verdictEl.className = passedCount === coin.checklist.length
                ? 'text-[11px] font-mono px-2.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold'
                : 'text-[11px] font-mono px-2.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold';
        }
    }

    // Açıklama Metni
    const explEl = document.getElementById('modalRadarExplanationText');
    if (explEl) {
        const boStr = coin.breakout_bar ? `Saat ${coin.breakout_bar.time_str} barında $${formatPrice(coin.breakout_bar.close)} ile kırıldı` : 'Kırılım bekleniyor';
        const rtStr = coin.retest_bar ? `Saat ${coin.retest_bar.time_str} barında seviyeye fitil değdirildi` : 'Retest henüz gerçekleşmedi';
        const cfStr = coin.confirmed_bar ? `Saat ${coin.confirmed_bar.time_str} barında hacimli yönlü mum ile onaylandı` : 'Onay mumu bekleniyor';

        explEl.innerHTML = `
            <div class="space-y-1.5 font-mono text-xs">
                <div class="text-amber-300 font-bold font-sans">${coin.explanation || ''}</div>
                <div class="p-2.5 rounded-lg bg-gray-950/80 border border-gray-800 space-y-1">
                    <div><span class="text-cyan-400 font-bold">1. Kırılım Mumu:</span> ${boStr}</div>
                    <div><span class="text-amber-400 font-bold">2. Retest Mumu:</span> ${rtStr}</div>
                    <div><span class="text-emerald-400 font-bold">3. Onay Mumu:</span> ${cfStr}</div>
                </div>
                <div class="text-[11px] text-gray-400 font-sans">
                    💡 <strong>Not:</strong> Bu analiz <strong>${coinTf} (${coin.timeframe_label || coinTf})</strong> zaman dilimi mumlarıyla yapılmıştır. TradingView üzerinde incelerken grafiğinizi <strong>${coinTf}</strong> zaman dilimine ayarlayınız.
                </div>
            </div>
        `;
    }

    modal.classList.remove('hidden');
    lucide.createIcons();

    setTimeout(() => {
        loadAndRenderRadarChart(coin);
    }, 100);
}

function closeRadarChartModal() {
    const modal = document.getElementById('radarChartModal');
    if (modal) modal.classList.add('hidden');
    if (window._radarChartInstance) {
        try { window._radarChartInstance.remove(); } catch(e) {}
        window._radarChartInstance = null;
    }
}

async function loadAndRenderRadarChart(coin) {
    const container = document.getElementById('radarModalChartArea');
    if (!container) return;

    // Cleanup previous chart instance
    if (window._radarChartInstance) {
        try { window._radarChartInstance.remove(); } catch(e) {}
        window._radarChartInstance = null;
    }
    if (container) container.innerHTML = '';

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
            vertLine: { color: '#06b6d4', width: 1, style: 3 },
            horzLine: { color: '#06b6d4', width: 1, style: 3 },
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

    radarChartInstance = LightweightCharts.createChart(container, chartOptions);
    window._radarChartInstance = radarChartInstance;

    const candleSeries = radarChartInstance.addCandlestickSeries({
        upColor: '#10b981',
        downColor: '#ef4444',
        borderUpColor: '#10b981',
        borderDownColor: '#ef4444',
        wickUpColor: '#10b981',
        wickDownColor: '#ef4444',
    });

    try {
        const tf = coin.timeframe || '1h';
        const res = await fetch(`/api/chart-data/${encodeURIComponent(coin.symbol)}?timeframe=${tf}`);
        const data = await res.json();

        if (data.status === 'success' && data.candles) {
            const formattedCandles = data.candles.map(c => ({
                time: c.time,
                open: c.open,
                high: c.high,
                low: c.low,
                close: c.close
            })).sort((a, b) => a.time - b.time);

            candleSeries.setData(formattedCandles);

            // 1. Kırılan Seviye Çizgisi
            const refLevel = coin.breakout_level || coin.swing_level || (coin.direction === 'LONG' ? coin.pdh : coin.pdl);
            if (refLevel) {
                candleSeries.createPriceLine({
                    price: refLevel,
                    color: coin.direction === 'LONG' ? '#10b981' : '#ef4444',
                    lineWidth: 2,
                    lineStyle: 0,
                    axisLabelVisible: true,
                    title: `SEVİYE ($${formatPrice(refLevel)})`,
                });
            }

            // 2. Giriş Çizgisi
            if (coin.entry_price) {
                candleSeries.createPriceLine({
                    price: coin.entry_price,
                    color: '#fbbf24',
                    lineWidth: 2,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: `GİRİŞ ($${formatPrice(coin.entry_price)})`,
                });
            }

            // 3. Stop Loss (0.2 x ATR)
            if (coin.stop_loss) {
                candleSeries.createPriceLine({
                    price: coin.stop_loss,
                    color: '#ef4444',
                    lineWidth: 1,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: `STOP (0.2xATR: $${formatPrice(coin.stop_loss)})`,
                });
            }

            // 4. Take Profit (Dinamik S/R Hedefi)
            const tpTarget = coin.take_profit || coin.tp1;
            if (tpTarget) {
                candleSeries.createPriceLine({
                    price: tpTarget,
                    color: '#34d399',
                    lineWidth: 1,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: `HEDEF (S/R: $${formatPrice(tpTarget)})`,
                });
            }

            // 📍 5. GRAFİK ÜZERİNDE MUM ETİKETLERİ VE OKLAR (MARKERS)
            const candleTimes = formattedCandles.map(c => c.time);
            const candleTimeSet = new Set(candleTimes);

            function findClosestTs(ts) {
                if (!ts || candleTimes.length === 0) return null;
                let closest = candleTimes[0];
                let minDiff = Math.abs(candleTimes[0] - ts);
                for (let i = 1; i < candleTimes.length; i++) {
                    const diff = Math.abs(candleTimes[i] - ts);
                    if (diff < minDiff) {
                        minDiff = diff;
                        closest = candleTimes[i];
                    }
                }
                return closest;
            }

            const markers = [];
            const boTs = coin.breakout_bar ? (coin.breakout_bar.timestamp || coin.breakout_bar.time) : null;
            const rtTs = coin.retest_bar ? (coin.retest_bar.timestamp || coin.retest_bar.time) : null;
            const confTs = coin.confirmed_bar ? (coin.confirmed_bar.timestamp || coin.confirmed_bar.time) : null;

            if (boTs) {
                const matchedTime = candleTimeSet.has(boTs) ? boTs : findClosestTs(boTs);
                if (matchedTime) {
                    markers.push({
                        time: matchedTime,
                        position: coin.direction === 'LONG' ? 'belowBar' : 'aboveBar',
                        color: '#06b6d4',
                        shape: coin.direction === 'LONG' ? 'arrowUp' : 'arrowDown',
                        text: '⚡ KIRILIM'
                    });
                }
            }
            if (rtTs) {
                const matchedTime = candleTimeSet.has(rtTs) ? rtTs : findClosestTs(rtTs);
                if (matchedTime) {
                    markers.push({
                        time: matchedTime,
                        position: coin.direction === 'LONG' ? 'belowBar' : 'aboveBar',
                        color: '#f59e0b',
                        shape: 'circle',
                        text: '🎯 RETEST'
                    });
                }
            }
            if (confTs) {
                const matchedTime = candleTimeSet.has(confTs) ? confTs : findClosestTs(confTs);
                if (matchedTime) {
                    markers.push({
                        time: matchedTime,
                        position: coin.direction === 'LONG' ? 'belowBar' : 'aboveBar',
                        color: '#10b981',
                        shape: coin.direction === 'LONG' ? 'arrowUp' : 'arrowDown',
                        text: '🔥 ONAY (GİRİŞ)'
                    });
                }
            }

            if (markers.length > 0) {
                try {
                    markers.sort((a, b) => a.time - b.time);
                    candleSeries.setMarkers(markers);
                } catch (mErr) {
                    console.warn('Marker render warning:', mErr);
                }
            }

            // 6. ÖZEL FORMASYON TRENDLİNE & BOYUN ÇİZGİLERİ (TradingView Alt+T Standardı)
            const patternLines = (coin.lines && Array.isArray(coin.lines) && coin.lines.length > 0)
                ? coin.lines
                : ((data.patterns && data.patterns[0] && data.patterns[0].lines) ? data.patterns[0].lines : []);

            if (patternLines && Array.isArray(patternLines)) {
                patternLines.forEach(lineDef => {
                    if (lineDef.points && lineDef.points.length > 0) {
                        try {
                            const patLine = radarChartInstance.addLineSeries({
                                color: lineDef.color || '#fbbf24',
                                lineWidth: lineDef.lineWidth || 2,
                                lineStyle: lineDef.lineStyle !== undefined ? lineDef.lineStyle : 0,
                                priceLineVisible: false,
                                lastValueVisible: true,
                                crosshairMarkerVisible: true,
                                title: lineDef.name || 'Trendline'
                            });

                            const validPoints = [];
                            const seenTimes = new Set();

                            lineDef.points.forEach(p => {
                                const ptTime = candleTimeSet.has(p.time) ? p.time : findClosestTs(p.time);
                                if (ptTime && !seenTimes.has(ptTime)) {
                                    seenTimes.add(ptTime);
                                    validPoints.push({
                                        time: ptTime,
                                        value: Number(p.value)
                                    });
                                }
                            });

                            validPoints.sort((a, b) => a.time - b.time);

                            if (validPoints.length >= 2) {
                                patLine.setData(validPoints);
                            }
                        } catch (lineErr) {
                            console.error('Line series render error:', lineErr);
                        }
                    }
                });
            }

            radarChartInstance.timeScale().fitContent();
        }
    } catch (err) {
        console.error('Error fetching chart data for radar:', err);
    }
}

function formatPrice(val) {
    if (val === undefined || val === null) return '0.00';
    if (val >= 1000) return val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (val >= 1) return val.toFixed(4);
    return val.toFixed(6);
}
