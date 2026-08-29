// CryptoSignalPro AI - Özel Stratejiler Radarı (PDH/PDL & Swing High/Low) Frontend Mantığı (v6.7)

let activeStrategy = 'PDH_PDL'; // 'PDH_PDL' | 'SWING_HL'
let currentRadarData = null;
let radarChartInstance = null;
let autoRefreshTimer = null;
let autoRefreshCountdown = 30;
let isFetchingInProgress = false;

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
    if (isFetchingInProgress) return;
    isFetchingInProgress = true;

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
        isFetchingInProgress = false;
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.innerHTML = `<i data-lucide="refresh-cw" class="w-4 h-4"></i> <span>RADARI CANLI TARA</span>`;
            lucide.createIcons();
        }
    }
}

function applyRadarFiltersAndRender() {
    if (!currentRadarData || !currentRadarData.stages) return;

    const dirFilter = document.getElementById('directionFilter') ? document.getElementById('directionFilter').value : 'ALL';
    const query = document.getElementById('coinSearchInput') ? document.getElementById('coinSearchInput').value.trim().toLowerCase() : '';

    const filterFn = (item) => {
        if (dirFilter !== 'ALL' && item.direction !== dirFilter) return false;
        if (query && !item.symbol.toLowerCase().includes(query)) return false;
        return true;
    };

    const breakoutList = (currentRadarData.stages.breakout || []).filter(filterFn);
    const retestList = (currentRadarData.stages.retesting || []).filter(filterFn);
    const confirmedList = (currentRadarData.stages.confirmed || []).filter(filterFn);

    // Kolon Badge Sayıları
    if (document.getElementById('col1BadgeCount')) document.getElementById('col1BadgeCount').textContent = breakoutList.length;
    if (document.getElementById('col2BadgeCount')) document.getElementById('col2BadgeCount').textContent = retestList.length;
    if (document.getElementById('col3BadgeCount')) document.getElementById('col3BadgeCount').textContent = confirmedList.length;

    // Kolonları Doldur
    renderColumnList('colBreakoutList', breakoutList, 'breakout');
    renderColumnList('colRetestList', retestList, 'retest');
    renderColumnList('colConfirmedList', confirmedList, 'confirmed');

    lucide.createIcons();
}

function renderColumnList(containerId, list, type) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';

    if (!list || list.length === 0) {
        container.innerHTML = `
            <div class="p-6 rounded-2xl bg-gray-950/40 border border-gray-800/60 text-center space-y-2">
                <div class="text-xs text-gray-500 font-medium">Bu kriterde aktif coin bulunamadı</div>
            </div>
        `;
        return;
    }

    list.forEach(c => {
        const isLong = c.direction === 'LONG';
        const levelLabel = activeStrategy === 'PDH_PDL'
            ? (isLong ? 'PDH' : 'PDL')
            : (isLong ? 'Swing High' : 'Swing Low');

        const levelPrice = c.breakout_level || (isLong ? (c.pdh || c.swing_level) : (c.pdl || c.swing_level));

        const dirBadge = isLong 
            ? `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 text-[10px] font-mono">🟢 LONG (${levelLabel})</span>`
            : `<span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-bold border border-rose-500/30 text-[10px] font-mono">🔴 SHORT (${levelLabel})</span>`;

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

        container.appendChild(card);
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

    if (document.getElementById('modalSymbolTitle')) document.getElementById('modalSymbolTitle').textContent = `${coin.symbol} (${coin.timeframe || '1h'})`;
    if (document.getElementById('modalStageSubtitle')) document.getElementById('modalStageSubtitle').textContent = coin.stage_name;

    // Rozetler
    if (document.getElementById('badgePdh')) document.getElementById('badgePdh').textContent = `$${formatPrice(coin.pdh || coin.swing_level || levelPrice)}`;
    if (document.getElementById('badgePdl')) document.getElementById('badgePdl').textContent = `$${formatPrice(coin.pdl || coin.swing_level || levelPrice)}`;
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
        explEl.innerHTML = `
            ${coin.explanation}<br/><br/>
            <span class="text-cyan-400 font-bold">• Seviye Çizgisi (${levelName}):</span> $${formatPrice(levelPrice)}<br/>
            <span class="text-yellow-400 font-bold">• Giriş Seviyesi:</span> $${formatPrice(coin.entry_price || coin.current_price)}<br/>
            <span class="text-rose-400 font-bold">• Stop Loss (0.2xATR):</span> $${formatPrice(coin.stop_loss)}<br/>
            <span class="text-emerald-400 font-bold">• Dinamik Hedef (S/R):</span> ${tpPrice ? '$' + formatPrice(tpPrice) : 'S/R Takip Ediliyor'}
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
    if (radarChartInstance) {
        try {
            radarChartInstance.remove();
        } catch (e) {}
        radarChartInstance = null;
    }
}

async function loadAndRenderRadarChart(coin) {
    const container = document.getElementById('radarModalChartArea');
    if (!container) return;

    if (radarChartInstance) {
        try {
            radarChartInstance.remove();
        } catch (e) {}
        radarChartInstance = null;
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
            const markers = [];
            const boTime = coin.breakout_bar ? (coin.breakout_bar.timestamp || coin.breakout_bar.time) : null;
            const rtTime = coin.retest_bar ? (coin.retest_bar.timestamp || coin.retest_bar.time) : null;
            const confTime = coin.confirmed_bar ? (coin.confirmed_bar.timestamp || coin.confirmed_bar.time) : null;

            if (boTime) {
                markers.push({
                    time: boTime,
                    position: coin.direction === 'LONG' ? 'belowBar' : 'aboveBar',
                    color: '#06b6d4',
                    shape: coin.direction === 'LONG' ? 'arrowUp' : 'arrowDown',
                    text: '⚡ KIRILIM'
                });
            }
            if (rtTime) {
                markers.push({
                    time: rtTime,
                    position: coin.direction === 'LONG' ? 'belowBar' : 'aboveBar',
                    color: '#f59e0b',
                    shape: 'circle',
                    text: '🎯 RETEST'
                });
            }
            if (confTime) {
                markers.push({
                    time: confTime,
                    position: coin.direction === 'LONG' ? 'belowBar' : 'aboveBar',
                    color: '#10b981',
                    shape: coin.direction === 'LONG' ? 'arrowUp' : 'arrowDown',
                    text: '🔥 ONAY (GİRİŞ)'
                });
            }

            if (markers.length > 0) {
                markers.sort((a, b) => a.time - b.time);
                candleSeries.setMarkers(markers);
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
