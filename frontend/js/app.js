// CryptoSignalPro AI Frontend Uygulama Mantığı (v5.3.0 Sağdan Açılan İnteraktif AI Chat & Model Seçimi)
let currentSetups = [];
let selectedSetupForModal = null;
let selectedSetupForRawModal = null;
let selectedBacktestSymbol = null;
let currentModalTimeframe = '1h';

let nextScanRemainingSeconds = 300;
let autoRefreshIntervalTimer = null;

// İnteraktif AI Chat Durum Değişkenleri
let currentChatSymbol = null;
let currentChatHistory = [];
let originalSetupPrompt = "";
let isChatSending = false;

// Gemini API Key Yönetimi (localStorage)
function getStoredGeminiKey() {
    return localStorage.getItem('gemini_api_key') || '';
}

function setStoredGeminiKey(key) {
    if (key) {
        localStorage.setItem('gemini_api_key', key.trim());
    } else {
        localStorage.removeItem('gemini_api_key');
    }
    updateGeminiStatusBadge();
}

function updateGeminiStatusBadge() {
    const dot = document.getElementById('geminiStatusDot');
    const hasKey = !!getStoredGeminiKey();
    if (dot) {
        if (hasKey) {
            dot.className = 'w-2 h-2 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/50 animate-pulse';
            dot.title = 'Gemini AI Aktif';
        } else {
            dot.className = 'w-2 h-2 rounded-full bg-gray-500';
            dot.title = 'API Anahtarı Girilmedi';
        }
    }
}

function openGeminiModal() {
    const modal = document.getElementById('geminiSettingsModal');
    const input = document.getElementById('geminiApiKeyInput');
    const statusMsg = document.getElementById('geminiKeyStatusMsg');
    if (modal) {
        modal.classList.remove('hidden');
        if (input) input.value = getStoredGeminiKey();
        if (statusMsg) statusMsg.classList.add('hidden');
    }
}

function closeGeminiModal() {
    const modal = document.getElementById('geminiSettingsModal');
    if (modal) modal.classList.add('hidden');
}

function saveGeminiKey() {
    const input = document.getElementById('geminiApiKeyInput');
    const statusMsg = document.getElementById('geminiKeyStatusMsg');
    const val = input ? input.value.trim() : '';

    if (!val) {
        if (statusMsg) {
            statusMsg.className = 'p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-semibold';
            statusMsg.textContent = 'Lütfen geçerli bir Gemini API Anahtarı girin.';
            statusMsg.classList.remove('hidden');
        }
        return;
    }

    setStoredGeminiKey(val);
    if (statusMsg) {
        statusMsg.className = 'p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold';
        statusMsg.textContent = '✓ Gemini API Anahtarınız başarıyla kaydedildi!';
        statusMsg.classList.remove('hidden');
    }

    showToast('Gemini AI Aktif', 'API anahtarınız kaydedildi. Artık tek tıkla canlı yapay zeka analizi alabilirsiniz.');
    setTimeout(() => {
        closeGeminiModal();
    }, 1200);
}

function clearGeminiKey() {
    setStoredGeminiKey('');
    const input = document.getElementById('geminiApiKeyInput');
    const statusMsg = document.getElementById('geminiKeyStatusMsg');
    if (input) input.value = '';
    if (statusMsg) {
        statusMsg.className = 'p-2.5 rounded-xl bg-gray-800 text-gray-400 text-xs font-semibold';
        statusMsg.textContent = 'API anahtarı silindi.';
        statusMsg.classList.remove('hidden');
    }
    showToast('Bilgi', 'Gemini API anahtarı temizlendi.');
}

// -------------------------------------------------------------
// 🔄 OTOMATİK GÜNCELLEME VE ZAMANLAYICI YÖNETİMİ
// -------------------------------------------------------------
function getStoredAutoRefreshMinutes() {
    return parseInt(localStorage.getItem('auto_refresh_minutes') || '5');
}

function setStoredAutoRefreshMinutes(min) {
    localStorage.setItem('auto_refresh_minutes', min.toString());
}

async function updateAutoRefreshConfig(min) {
    setStoredAutoRefreshMinutes(min);
    const intervalSelect = document.getElementById('autoRefreshIntervalSelect');
    if (intervalSelect) intervalSelect.value = min.toString();

    if (min > 0) {
        nextScanRemainingSeconds = min * 60;
        showToast('Otomatik Güncelleme', `Piyasa verileri her ${min} dakikada bir otomatik güncellenecek.`);
    } else {
        nextScanRemainingSeconds = 0;
        showToast('Otomatik Güncelleme', 'Otomatik tarama kapatıldı (Manuel mod).');
    }
    updateCountdownDisplay();

    try {
        await fetch('/api/auto-scan-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ interval_minutes: min })
        });
    } catch (e) {
        console.error('Config sync error:', e);
    }
}

function updateCountdownDisplay() {
    const countdownEl = document.getElementById('nextUpdateCountdownText');
    const wrapper = document.getElementById('nextUpdateCountdownWrapper');
    const intervalMin = getStoredAutoRefreshMinutes();

    if (!countdownEl) return;

    if (intervalMin === 0) {
        if (wrapper) wrapper.classList.add('hidden');
        return;
    }

    if (wrapper) wrapper.classList.remove('hidden');
    const mins = Math.floor(nextScanRemainingSeconds / 60);
    const secs = nextScanRemainingSeconds % 60;
    countdownEl.textContent = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function startAutoRefreshTicker() {
    if (autoRefreshIntervalTimer) clearInterval(autoRefreshIntervalTimer);
    autoRefreshIntervalTimer = setInterval(() => {
        const intervalMin = getStoredAutoRefreshMinutes();
        if (intervalMin > 0) {
            nextScanRemainingSeconds--;
            if (nextScanRemainingSeconds <= 0) {
                // Sessizce arka planda taze verileri çek
                fetchLatestCachedSetups(true);
                nextScanRemainingSeconds = intervalMin * 60;
            }
            updateCountdownDisplay();
        }
    }, 1000);
}

function updateLastScanBadge(timeStr) {
    const badge = document.getElementById('lastUpdateTimeText');
    if (badge && timeStr) {
        badge.textContent = timeStr;
    }
}

// -------------------------------------------------------------
// 💬 SAĞDAN AÇILAN İNTERAKTİF AI CHAT & PROMPT DÜZENLEME PANELİ
function autoResizeChatInput() {
    const inputEl = document.getElementById('chatPromptInput');
    if (!inputEl) return;
    inputEl.style.height = 'auto';
    const newH = Math.max(120, Math.min(inputEl.scrollHeight + 6, 380));
    inputEl.style.height = newH + 'px';
}

async function openAiChatDrawer(symbol, customPrompt = null) {
    currentChatSymbol = symbol;
    const drawer = document.getElementById('aiChatDrawer');
    const backdrop = document.getElementById('aiChatDrawerBackdrop');
    const symbolEl = document.getElementById('chatDrawerSymbol');
    const inputEl = document.getElementById('chatPromptInput');

    if (!drawer) return;

    if (symbolEl) symbolEl.textContent = symbol;

    // Coinin teknik setup ve prompt verisini bul
    let setup = currentSetups.find(s => s.symbol === symbol);
    if (setup && setup.ai_prompt) {
        originalSetupPrompt = setup.ai_prompt;
    } else {
        originalSetupPrompt = `[ROLE: Senior Institutional Crypto Trader]\n[TASK: Evaluate chart data for ${symbol} & render executive trade decision]\n\nLütfen bu coin için 2 aşamalı saf veri doğrulaması ve strateji analizi yap.`;
    }

    if (inputEl) {
        inputEl.value = customPrompt || originalSetupPrompt;
        setTimeout(autoResizeChatInput, 50);
    }

    // Paneli kaydırarak aç
    if (backdrop) backdrop.classList.remove('hidden');
    drawer.classList.remove('translate-x-full');

    setTimeout(() => {
        if (inputEl) {
            inputEl.focus();
            autoResizeChatInput();
        }
    }, 300);
    lucide.createIcons();
}

function toggleOrOpenAiChatDrawer() {
    const drawer = document.getElementById('aiChatDrawer');
    if (!drawer) return;
    const isClosed = drawer.classList.contains('translate-x-full');
    if (isClosed) {
        const sym = currentChatSymbol || (currentSetups && currentSetups.length > 0 ? currentSetups[0].symbol : 'BTC/USDT');
        openAiChatDrawer(sym);
    } else {
        closeAiChatDrawer();
    }
}

function closeAiChatDrawer() {
    const drawer = document.getElementById('aiChatDrawer');
    const backdrop = document.getElementById('aiChatDrawerBackdrop');
    if (drawer) drawer.classList.add('translate-x-full');
    if (backdrop) backdrop.classList.add('hidden');
}

function resetToOriginalPrompt() {
    const inputEl = document.getElementById('chatPromptInput');
    if (inputEl && originalSetupPrompt) {
        inputEl.value = originalSetupPrompt;
        autoResizeChatInput();
        showToast('Sıfırlandı', 'İstem orijinal haline getirildi.');
    }
}

function appendQuickPrompt(text) {
    const inputEl = document.getElementById('chatPromptInput');
    if (!inputEl) return;
    if (!inputEl.value.trim()) {
        inputEl.value = text;
    } else {
        inputEl.value = inputEl.value.trim() + "\n\n" + text;
    }
    autoResizeChatInput();
    inputEl.focus();
}

function clearChatHistory() {
    currentChatHistory = [];
    const container = document.getElementById('chatMessagesContainer');
    if (container) {
        container.innerHTML = `
            <div class="flex items-start gap-2.5">
                <div class="w-7 h-7 rounded-lg bg-indigo-600/30 border border-indigo-500/40 text-indigo-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <i data-lucide="bot" class="w-4 h-4"></i>
                </div>
                <div class="flex-1 p-3 rounded-2xl bg-gray-800/80 border border-gray-700 text-gray-200 leading-relaxed shadow-sm space-y-1.5">
                    <div class="font-bold text-indigo-300 flex items-center gap-1.5">
                        <i data-lucide="sparkles" class="w-3.5 h-3.5"></i> Sohbet Temizlendi
                    </div>
                    <p class="text-[11px] text-gray-300">
                        Yeni soru sormak veya analiz istemini düzenleyip göndermek için aşağıdaki metin kutusunu kullanabilirsiniz.
                    </p>
                </div>
            </div>
        `;
        lucide.createIcons();
    }
    showToast('Temizlendi', 'Sohbet geçmişi sıfırlandı.');
}

async function sendChatMessage() {
    if (isChatSending) return;
    const inputEl = document.getElementById('chatPromptInput');
    const container = document.getElementById('chatMessagesContainer');
    const sendBtn = document.getElementById('sendChatBtn');
    const modelSelect = document.getElementById('chatModelSelect');

    const msg = inputEl ? inputEl.value.trim() : '';
    if (!msg) {
        showToast('Boş İstem', 'Lütfen bir analiz sorusu veya istem girin.', true);
        return;
    }

    const storedKey = getStoredGeminiKey();
    if (!storedKey) {
        openGeminiModal();
        showToast('Gemini API Anahtarı Gerekli', 'Lütfen ücretsiz API anahtarınızı girin.', true);
        return;
    }

    const selectedModel = modelSelect ? modelSelect.value : 'gemini-2.0-flash';

    // 1. Kullanıcı Baloncuğunu Ekle
    const userBubble = document.createElement('div');
    userBubble.className = 'flex items-start gap-2.5 justify-end';
    userBubble.innerHTML = `
        <div class="max-w-[85%] p-3 rounded-2xl bg-indigo-600/30 border border-indigo-500/40 text-gray-100 text-xs leading-relaxed shadow-sm font-sans whitespace-pre-wrap">${escapeHtml(msg)}</div>
        <div class="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center flex-shrink-0 mt-0.5 shadow">
            <i data-lucide="user" class="w-4 h-4"></i>
        </div>
    `;
    container.appendChild(userBubble);
    container.scrollTop = container.scrollHeight;

    // 2. Yükleniyor Baloncuğu
    const loadingBubble = document.createElement('div');
    loadingBubble.className = 'flex items-start gap-2.5';
    loadingBubble.id = 'chatLoadingBubble';
    loadingBubble.innerHTML = `
        <div class="w-7 h-7 rounded-lg bg-indigo-600/30 border border-indigo-500/40 text-indigo-400 flex items-center justify-center flex-shrink-0 mt-0.5">
            <i data-lucide="bot" class="w-4 h-4"></i>
        </div>
        <div class="p-3 rounded-2xl bg-gray-800/80 border border-gray-700 text-gray-300 text-xs flex items-center gap-2">
            <div class="w-3.5 h-3.5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin"></div>
            <span>${selectedModel} piyasa verilerini ve isteminizi inceliyor...</span>
        </div>
    `;
    container.appendChild(loadingBubble);
    container.scrollTop = container.scrollHeight;

    isChatSending = true;
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.innerHTML = `<div class="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div> <span>Yorumlanıyor...</span>`;
    }
    if (inputEl) inputEl.value = '';

    try {
        const res = await fetch('/api/ai-chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                symbol: currentChatSymbol || 'BTC/USDT',
                message: msg,
                history: currentChatHistory,
                model_name: selectedModel,
                api_key: storedKey
            })
        });

        const data = await res.json();
        const loader = document.getElementById('chatLoadingBubble');
        if (loader) loader.remove();

        if (data.status === 'success' && data.reply) {
            // Geçmişe ekle
            currentChatHistory.push({ role: 'user', content: msg });
            currentChatHistory.push({ role: 'model', content: data.reply });

            // AI Baloncuğunu Ekle
            const aiBubble = document.createElement('div');
            aiBubble.className = 'flex items-start gap-2.5';
            aiBubble.innerHTML = `
                <div class="w-7 h-7 rounded-lg bg-gradient-to-tr from-indigo-600 to-purple-500 text-white flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm">
                    <i data-lucide="bot" class="w-4 h-4"></i>
                </div>
                <div class="flex-1 p-3.5 rounded-2xl bg-gray-900 border border-gray-800 text-gray-200 text-xs leading-relaxed shadow space-y-2">
                    <div class="flex items-center justify-between border-b border-gray-800 pb-1.5 text-[10px]">
                        <span class="font-bold text-indigo-400 uppercase tracking-wider">${data.model_used || selectedModel}</span>
                        <button onclick="copyToClipboard(\`${escapeHtmlForJs(data.reply)}\`, 'Yanıt Kopyalandı!')" class="text-gray-400 hover:text-white flex items-center gap-1">
                            <i data-lucide="copy" class="w-3 h-3"></i> Kopyala
                        </button>
                    </div>
                    <div class="prose prose-invert prose-xs max-w-none space-y-1.5 leading-relaxed font-sans">${formatMarkdownText(data.reply)}</div>
                </div>
            `;
            container.appendChild(aiBubble);
        } else {
            const errBubble = document.createElement('div');
            errBubble.className = 'flex items-start gap-2.5';
            errBubble.innerHTML = `
                <div class="w-7 h-7 rounded-lg bg-rose-500/20 text-rose-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <i data-lucide="alert-circle" class="w-4 h-4"></i>
                </div>
                <div class="p-3 rounded-2xl bg-rose-950/40 border border-rose-500/40 text-rose-300 text-xs">
                    <div class="font-bold">Analiz Hatası:</div>
                    <div class="text-[11px] mt-0.5 text-gray-300">${data.message || 'Yanıt alınamadı.'}</div>
                </div>
            `;
            container.appendChild(errBubble);
        }
    } catch (e) {
        console.error('Chat error:', e);
        const loader = document.getElementById('chatLoadingBubble');
        if (loader) loader.remove();
        const errBubble = document.createElement('div');
        errBubble.className = 'flex items-start gap-2.5';
        errBubble.innerHTML = `
            <div class="w-7 h-7 rounded-lg bg-rose-500/20 text-rose-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                <i data-lucide="alert-circle" class="w-4 h-4"></i>
            </div>
            <div class="p-3 rounded-2xl bg-rose-950/40 border border-rose-500/40 text-rose-300 text-xs">
                Sunucuya veya Gemini servisine ulaşılamadı.
            </div>
        `;
        container.appendChild(errBubble);
    } finally {
        isChatSending = false;
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.innerHTML = `<i data-lucide="send" class="w-3.5 h-3.5"></i> <span>Gönder & Analiz Et</span>`;
        }
        container.scrollTop = container.scrollHeight;
        lucide.createIcons();
    }
}

function escapeHtml(text) {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function escapeHtmlForJs(text) {
    return text.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$');
}

function formatMarkdownText(text) {
    if (!text) return '';
    let html = escapeHtml(text);
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-bold">$1</strong>');
    // Bullet points
    html = html.replace(/^\s*-\s+(.*)$/gm, '<li class="ml-4 list-disc text-gray-300">$1</li>');
    html = html.replace(/^\s*\*\s+(.*)$/gm, '<li class="ml-4 list-disc text-gray-300">$1</li>');
    // Headings
    html = html.replace(/^### (.*$)/gm, '<h4 class="text-xs font-bold text-indigo-300 mt-2 uppercase tracking-wide">$1</h4>');
    html = html.replace(/^## (.*$)/gm, '<h3 class="text-sm font-bold text-white mt-2.5">$1</h3>');
    // Code blocks
    html = html.replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded bg-gray-950 text-amber-300 font-mono text-[11px]">$1</code>');
    // Newlines
    html = html.replace(/\n\n/g, '<div class="h-1.5"></div>');
    html = html.replace(/\n/g, '<br/>');
    return html;
}

document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    updateGeminiStatusBadge();

    setInterval(updateClock, 1000);
    updateClock();

    const minConfRange = document.getElementById('minConfidenceRange');
    const minConfVal = document.getElementById('minConfidenceVal');
    const enableMinConfToggle = document.getElementById('enableMinConfidenceToggle');
    const sliderWrapper = document.getElementById('sliderWrapper');
    const sortBySelect = document.getElementById('sortBySelect');
    const strategySelect = document.getElementById('strategySelect');
    const directionSelect = document.getElementById('directionSelect');
    const limitCoinsSelect = document.getElementById('limitCoinsSelect');
    const timeframeSelect = document.getElementById('timeframeSelect');
    const symbolSearchInput = document.getElementById('symbolSearchInput');
    const clearSearchBtn = document.getElementById('clearSearchBtn');
    const scanBtn = document.getElementById('scanBtn');
    const autoRefreshSelect = document.getElementById('autoRefreshIntervalSelect');
    const chatPromptInput = document.getElementById('chatPromptInput');

    // Chat Prompt Input Klavye Kısayolu (Enter = Gönder, Shift+Enter = Yeni Satır) & Otomatik Boyutlandırma
    if (chatPromptInput) {
        chatPromptInput.addEventListener('input', autoResizeChatInput);
        chatPromptInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    }

    // Otomatik Yenileme Seçici Dinleyicisi
    if (autoRefreshSelect) {
        const savedMin = getStoredAutoRefreshMinutes();
        autoRefreshSelect.value = savedMin.toString();
        autoRefreshSelect.addEventListener('change', (e) => {
            const min = parseInt(e.target.value);
            updateAutoRefreshConfig(min);
        });
    }

    // 1. Min Güvenlik Toggle Değişimi
    if (enableMinConfToggle) {
        enableMinConfToggle.addEventListener('change', (e) => {
            const isEnabled = e.target.checked;
            if (minConfRange) minConfRange.disabled = !isEnabled;
            if (sliderWrapper) {
                if (isEnabled) {
                    sliderWrapper.classList.remove('opacity-40');
                    minConfRange.classList.remove('cursor-not-allowed');
                    minConfRange.classList.add('cursor-pointer');
                    minConfVal.textContent = `%${minConfRange.value}`;
                    minConfVal.className = 'text-xs font-bold text-indigo-400';
                } else {
                    sliderWrapper.classList.add('opacity-40');
                    minConfRange.classList.add('cursor-not-allowed');
                    minConfRange.classList.remove('cursor-pointer');
                    minConfVal.textContent = 'Kapalı (Tümü)';
                    minConfVal.className = 'text-xs font-bold text-gray-400';
                }
            }
            applyAllFiltersAndRender();
        });
    }

    // 2. Min Güvenlik Slider Kaydırma (Canlı 60fps dinamik filtreleme)
    if (minConfRange) {
        minConfRange.addEventListener('input', (e) => {
            if (enableMinConfToggle && enableMinConfToggle.checked) {
                minConfVal.textContent = `%${e.target.value}`;
                applyAllFiltersAndRender();
            }
        });
    }

    // 3. Sıralama Seçici (Sort By) Değişimi
    if (sortBySelect) {
        sortBySelect.addEventListener('change', () => {
            applyAllFiltersAndRender();
        });
    }

    // 4. Strateji Filtresi Değişimi (Anında dinamik filtreleme)
    if (strategySelect) {
        strategySelect.addEventListener('change', () => {
            applyAllFiltersAndRender();
        });
    }

    // 5. İşlem Yönü (Direction) Değişimi (Anında dinamik filtreleme)
    if (directionSelect) {
        directionSelect.addEventListener('change', () => {
            applyAllFiltersAndRender();
        });
    }

    // 6. Gösterilecek Coin Limiti Değişimi (10, 20, 30, 40, 50)
    if (limitCoinsSelect) {
        limitCoinsSelect.addEventListener('change', () => {
            applyAllFiltersAndRender();
        });
    }

    // 7. Zaman Dilimi Değişimi
    if (timeframeSelect) {
        timeframeSelect.addEventListener('change', () => {
            performScan();
        });
    }

    // 8. Taramayı Başlat Butonu (Manuel Zorlamalı Canlı Tarama)
    if (scanBtn) {
        scanBtn.addEventListener('click', () => performScan());
    }

    // 🔍 9. Canlı Coin Arama Çubuğu (Her harfte anında dinamik filtreleme)
    if (symbolSearchInput) {
        symbolSearchInput.addEventListener('input', (e) => {
            const query = e.target.value.trim().toLowerCase();
            if (clearSearchBtn) {
                if (query.length > 0) {
                    clearSearchBtn.classList.remove('hidden');
                } else {
                    clearSearchBtn.classList.add('hidden');
                }
            }
            applyAllFiltersAndRender();
        });

        symbolSearchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                performScan();
            }
        });
    }

    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            symbolSearchInput.value = '';
            clearSearchBtn.classList.add('hidden');
            applyAllFiltersAndRender();
        });
    }

    // Chart Modal Kapatma
    const closeModalBtn = document.getElementById('closeModalBtn');
    const chartModal = document.getElementById('chartModal');
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', () => {
            chartModal.classList.add('hidden');
        });
    }

    if (chartModal) {
        chartModal.addEventListener('click', (e) => {
            if (e.target === chartModal) {
                chartModal.classList.add('hidden');
            }
        });
    }

    // Ham Veri Pop-up Modal Kapatma
    const rawDataModal = document.getElementById('rawDataModal');
    const closeRawModalBtn = document.getElementById('closeRawModalBtn');
    const cancelRawModalBtn = document.getElementById('cancelRawModalBtn');
    
    if (closeRawModalBtn) {
        closeRawModalBtn.addEventListener('click', () => rawDataModal.classList.add('hidden'));
    }
    if (cancelRawModalBtn) {
        cancelRawModalBtn.addEventListener('click', () => rawDataModal.classList.add('hidden'));
    }
    if (rawDataModal) {
        rawDataModal.addEventListener('click', (e) => {
            if (e.target === rawDataModal) {
                rawDataModal.classList.add('hidden');
            }
        });
    }

    // Gemini Modal Kapatma
    const geminiModal = document.getElementById('geminiSettingsModal');
    if (geminiModal) {
        geminiModal.addEventListener('click', (e) => {
            if (e.target === geminiModal) {
                geminiModal.classList.add('hidden');
            }
        });
    }

    // Modal içi AI Prompt Kopyalama
    const modalCopyBtn = document.getElementById('modalCopyBtn');
    if (modalCopyBtn) {
        modalCopyBtn.addEventListener('click', () => {
            if (selectedSetupForModal) {
                const text = selectedSetupForModal.ai_prompt || "AI Prompt hazırlanıyor...";
                copyToClipboard(text, `${selectedSetupForModal.symbol} AI Promptu Kopyalandı!`);
            }
        });
    }

    // Modal içi Ham Veri Pop-up Açma
    const modalCopyRawBtn = document.getElementById('modalCopyRawBtn');
    if (modalCopyRawBtn) {
        modalCopyRawBtn.addEventListener('click', () => {
            if (selectedSetupForModal) {
                openRawDataModal(selectedSetupForModal);
            }
        });
    }

    // Pop-up içi Değişim Dinleyicileri
    const rawModalTimeframe = document.getElementById('rawModalTimeframe');
    const rawModalCandleLimit = document.getElementById('rawModalCandleLimit');
    if (rawModalTimeframe) {
        rawModalTimeframe.addEventListener('change', updateRawModalPreview);
    }
    if (rawModalCandleLimit) {
        rawModalCandleLimit.addEventListener('change', updateRawModalPreview);
    }

    // Pop-up içi Kopyalama Butonu
    const doCopyRawModalBtn = document.getElementById('doCopyRawModalBtn');
    if (doCopyRawModalBtn) {
        doCopyRawModalBtn.addEventListener('click', () => {
            const previewEl = document.getElementById('rawModalPreview');
            if (previewEl && selectedSetupForRawModal) {
                copyToClipboard(previewEl.textContent, `${selectedSetupForRawModal.symbol} Ham Verisi Kopyalandı!`);
            }
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const drawer = document.getElementById('aiChatDrawer');
            if (drawer && !drawer.classList.contains('translate-x-full')) {
                closeAiChatDrawer();
            } else if (geminiModal && !geminiModal.classList.contains('hidden')) {
                geminiModal.classList.add('hidden');
            } else if (rawDataModal && !rawDataModal.classList.contains('hidden')) {
                rawDataModal.classList.add('hidden');
            } else if (chartModal && !chartModal.classList.contains('hidden')) {
                chartModal.classList.add('hidden');
            }
        }
    });

    // ⚡ İLK AÇILIŞ: Sayfayı dondurmadan sunucudaki hazır önbelleği 0ms hızında anında getir!
    fetchLatestCachedSetups();
    startAutoRefreshTicker();
});

function updateClock() {
    const clockEl = document.getElementById('liveClock');
    if (clockEl) {
        const now = new Date();
        clockEl.textContent = now.toLocaleTimeString('tr-TR', { hour12: false }) + ' UTC+3';
    }
}

/**
 * ⚡ SUNUCU ÖNBELLEĞİNDEN ANINDA ÇEKME (0ms Gecikme & Sıfır Donma)
 */
async function fetchLatestCachedSetups(isSilent = false) {
    const loadingState = document.getElementById('loadingState');
    const resultsGrid = document.getElementById('resultsGrid');
    const statsSection = document.getElementById('statsSection');

    if (!isSilent && (!currentSetups || currentSetups.length === 0)) {
        if (loadingState) loadingState.classList.remove('hidden');
    }

    try {
        const res = await fetch('/api/latest-setups');
        const data = await res.json();

        if (data.status === 'success' && data.setups) {
            currentSetups = data.setups;
            if (data.last_scan_time) {
                updateLastScanBadge(data.last_scan_time);
            }
            const storedMin = getStoredAutoRefreshMinutes();
            if (storedMin === 0) {
                nextScanRemainingSeconds = 0;
            } else if (data.next_scan_seconds !== undefined && data.next_scan_seconds > 0) {
                nextScanRemainingSeconds = data.next_scan_seconds;
            } else {
                nextScanRemainingSeconds = storedMin * 60;
            }
            updateCountdownDisplay();
            if (statsSection) statsSection.classList.remove('hidden');
            applyAllFiltersAndRender();
        }
    } catch (e) {
        console.error('Fetch latest cached setups error:', e);
    } finally {
        if (loadingState) loadingState.classList.add('hidden');
    }
}

/**
 * ⚡ ANINDA DİNAMİK İSTEMCİ FİLTRELEME & SIRALAMA MOTORU (0ms Gecikme)
 */
function applyAllFiltersAndRender() {
    if (!currentSetups || currentSetups.length === 0) {
        return;
    }

    const searchInput = document.getElementById('symbolSearchInput');
    const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
    
    const directionSelect = document.getElementById('directionSelect');
    const direction = directionSelect ? directionSelect.value : 'ALL';

    const strategySelect = document.getElementById('strategySelect');
    const strategy = strategySelect ? strategySelect.value : 'ALL';

    const enableMinConfToggle = document.getElementById('enableMinConfidenceToggle');
    const isMinConfEnabled = enableMinConfToggle ? enableMinConfToggle.checked : false;
    const minConfRange = document.getElementById('minConfidenceRange');
    const minConfidence = (isMinConfEnabled && minConfRange) ? parseInt(minConfRange.value) : 1;

    const sortBySelect = document.getElementById('sortBySelect');
    const sortBy = sortBySelect ? sortBySelect.value : 'CONF_DESC';

    const limitCoinsSelect = document.getElementById('limitCoinsSelect');
    const limitVal = limitCoinsSelect ? limitCoinsSelect.value : '10';
    const limit = parseInt(limitVal) || 10;

    // 1. Filtreleme
    let filtered = currentSetups.filter(s => {
        if (query && !s.symbol.toLowerCase().includes(query)) {
            return false;
        }
        if (direction !== 'ALL' && s.direction !== direction) {
            return false;
        }
        if (isMinConfEnabled && s.confidence_score < minConfidence) {
            return false;
        }
        if (strategy !== 'ALL') {
            const stratLower = strategy.toLowerCase();
            const allStrats = (s.strategies || []).slice();
            if (s.primary_strategy) allStrats.push(s.primary_strategy);
            if (s.patterns) allStrats.push(...s.patterns);

            let matched = false;
            if (stratLower === 'pdh' || stratLower === 'benim') {
                matched = allStrats.some(st => {
                    const l = st.toLowerCase();
                    return l.includes('pdh') || l.includes('pdl') || l.includes('benim') || l.includes('önceki gün');
                });
            } else {
                matched = allStrats.some(st => st.toLowerCase().includes(stratLower));
            }
            if (!matched) return false;
        }
        return true;
    });

    // 2. Sıralama (Sorting)
    if (sortBy === 'CONF_ASC') {
        filtered.sort((a, b) => a.confidence_score - b.confidence_score);
    } else if (sortBy === 'RR_DESC') {
        filtered.sort((a, b) => b.rr_ratio - a.rr_ratio);
    } else if (sortBy === 'CHANGE_DESC') {
        filtered.sort((a, b) => ((b.indicators && b.indicators.price_change_24h) || 0) - ((a.indicators && a.indicators.price_change_24h) || 0));
    } else if (sortBy === 'CHANGE_ASC') {
        filtered.sort((a, b) => ((a.indicators && a.indicators.price_change_24h) || 0) - ((b.indicators && b.indicators.price_change_24h) || 0));
    } else if (sortBy === 'SYMBOL_ASC') {
        filtered.sort((a, b) => a.symbol.localeCompare(b.symbol));
    } else { // CONF_DESC
        filtered.sort((a, b) => (b.confidence_score * 1.5 + b.rr_ratio * 10) - (a.confidence_score * 1.5 + a.rr_ratio * 10));
    }

    if (query) {
        filtered.sort((a, b) => (a.symbol.toLowerCase() === query || a.symbol.toLowerCase().startsWith(query) ? -1 : 1));
    }

    // 3. Limit Uygulama
    const displaySetups = filtered.slice(0, limit);

    // 4. İstatistikleri Güncelle
    updateStats({
        long_count: filtered.filter(s => s.direction === 'LONG').length,
        short_count: filtered.filter(s => s.direction === 'SHORT').length,
        avg_rr: filtered.length > 0 ? round(filtered.reduce((acc, s) => acc + s.rr_ratio, 0) / filtered.length, 2) : 0,
        top_score: filtered.length > 0 ? Math.max(...filtered.map(s => s.confidence_score)) : 0
    }, currentSetups.length);

    // 5. Izgarayı Çiz
    if (displaySetups.length > 0) {
        renderSetupsGrid(displaySetups);
    } else {
        const resultsGrid = document.getElementById('resultsGrid');
        const emptyState = document.getElementById('emptyState');
        resultsGrid.classList.add('hidden');
        emptyState.classList.remove('hidden');
        emptyState.innerHTML = `
            <div class="w-16 h-16 mx-auto rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4">
                <i data-lucide="search" class="w-8 h-8"></i>
            </div>
            <h3 class="text-lg font-bold text-gray-200">${query ? `"${query.toUpperCase()}" Mevcut Listede Bulunamadı` : 'Filtre Kriterlerine Uygun Coin Bulunamadı'}</h3>
            <p class="text-sm text-gray-400 max-w-md mx-auto mt-1 mb-6">
                ${query ? `Aşağıdaki butona tıklayarak "${query.toUpperCase()}" için Binance sunucularından canlı çekim yapabilirsiniz.` : 'Min Güvenlik filtresini esnetebilir veya yönü "Tümü" olarak seçebilirsiniz.'}
            </p>
            <button onclick="performScan()" class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm transition shadow-lg shadow-emerald-600/30">
                <i data-lucide="search" class="w-4 h-4"></i> ${query ? `"${query.toUpperCase()}" Canlı Tara` : 'Tüm Piyasayı Yeniden Tara'}
            </button>
        `;
        lucide.createIcons();
    }
}

function round(val, dec = 2) {
    return Number(Math.round(val + 'e' + dec) + 'e-' + dec);
}

/**
 * 🔍 MANUEL ZORLAMALI CANLI TARAMA (Butona basıldığında çalışır)
 */
async function performScan() {
    const scanBtn = document.getElementById('scanBtn');
    const loadingState = document.getElementById('loadingState');
    const emptyState = document.getElementById('emptyState');
    const resultsGrid = document.getElementById('resultsGrid');
    const statsSection = document.getElementById('statsSection');

    const timeframe = document.getElementById('timeframeSelect').value;
    const limitCoinsSelect = document.getElementById('limitCoinsSelect');
    const limitCoins = limitCoinsSelect ? (parseInt(limitCoinsSelect.value) || 10) : 10;
    const searchSymbol = document.getElementById('symbolSearchInput') ? document.getElementById('symbolSearchInput').value.trim() : null;

    scanBtn.disabled = true;
    scanBtn.innerHTML = `<div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div> <span>Piyasa Çekiliyor (${limitCoins} Coin)...</span>`;
    
    emptyState.classList.add('hidden');
    resultsGrid.classList.add('hidden');
    loadingState.classList.remove('hidden');

    try {
        const response = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                timeframe: timeframe,
                raw_candle_limit: 30,
                limit_coins: limitCoins,
                direction: "ALL",
                strategy: "ALL",
                enable_min_confidence: false,
                min_confidence: 1,
                min_rr: 1.0,
                sort_by: "CONF_DESC",
                search_symbol: searchSymbol || null
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            currentSetups = data.setups || [];
            if (data.last_scan_time) {
                updateLastScanBadge(data.last_scan_time);
            }
            statsSection.classList.remove('hidden');
            applyAllFiltersAndRender();
        } else {
            showToast('Hata', 'Tarama yapılırken bir sorun oluştu.', true);
        }
    } catch (err) {
        console.error('Scan error:', err);
        showToast('Bağlantı Hatası', 'API sunucusuna erişilemedi.', true);
    } finally {
        loadingState.classList.add('hidden');
        scanBtn.disabled = false;
        scanBtn.innerHTML = `<i data-lucide="search" class="w-4 h-4"></i> <span>TÜM COİNLERİ TARA VE LİSTELE (SCAN & SORT ALL COINS)</span>`;
        lucide.createIcons();
    }
}

function updateStats(stats, scannedTotal) {
    document.getElementById('statScanned').textContent = scannedTotal || 0;
    document.getElementById('statLong').textContent = stats.long_count || 0;
    document.getElementById('statShort').textContent = stats.short_count || 0;
    document.getElementById('statAvgRR').textContent = `1 : ${stats.avg_rr || 0}`;
    document.getElementById('statTopScore').textContent = `%${stats.top_score || 0}`;
}

function renderSetupsGrid(setups) {
    const resultsGrid = document.getElementById('resultsGrid');
    const emptyState = document.getElementById('emptyState');

    resultsGrid.innerHTML = '';

    if (!setups || setups.length === 0) {
        resultsGrid.classList.add('hidden');
        emptyState.classList.remove('hidden');
        emptyState.innerHTML = `
            <div class="w-16 h-16 mx-auto rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-4">
                <i data-lucide="filter" class="w-8 h-8"></i>
            </div>
            <h3 class="text-lg font-bold text-gray-200">Kriterlere Uygun Setup Bulunamadı</h3>
            <p class="text-sm text-gray-400 max-w-md mx-auto mt-1 mb-6">
                Filtre ayarlarınızı (Güven Puanı veya Yön) esneterek yeniden deneyebilirsiniz.
            </p>
        `;
        lucide.createIcons();
        return;
    }

    setups.forEach((s, idx) => {
        const isLong = s.direction === 'LONG';
        const cardBorder = isLong ? 'hover:border-emerald-500/50' : 'hover:border-rose-500/50';
        const directionBg = isLong ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border-rose-500/30';
        const scoreColor = s.confidence_score >= 80 ? 'text-emerald-400' : (s.confidence_score >= 65 ? 'text-indigo-400' : (s.confidence_score >= 50 ? 'text-amber-400' : 'text-gray-400'));
        const safeSym = s.symbol.replace(/[^a-zA-Z0-9]/g, '_');

        const reasonsHtml = s.reasons.map(r => `
            <li class="flex items-start gap-2 text-xs text-gray-300">
                <i data-lucide="check-circle-2" class="w-3.5 h-3.5 text-indigo-400 flex-shrink-0 mt-0.5"></i>
                <span>${r}</span>
            </li>
        `).join('');

        const primaryStrat = s.primary_strategy || (s.strategies ? s.strategies[0] : 'SMC & Trend Analizi');

        // MTF Mini Radar
        let mtfHtml = '';
        if (s.mtf && s.mtf.timeframes) {
            const tfs = s.mtf.timeframes;
            mtfHtml = `
                <div class="mt-2 p-2 bg-gray-950/70 rounded-xl border border-gray-800/80 flex items-center justify-between text-[11px] font-mono">
                    <span class="text-gray-400 text-[10px] font-sans font-semibold">MTF Trend:</span>
                    <div class="flex items-center gap-1.5 font-bold">
                        <span class="px-1.5 py-0.5 rounded ${tfs['15m'].signal.includes('LONG') ? 'bg-emerald-950 text-emerald-400' : (tfs['15m'].signal.includes('SHORT') ? 'bg-rose-950 text-rose-400' : 'bg-gray-800 text-gray-400')}">15m</span>
                        <span class="px-1.5 py-0.5 rounded ${tfs['1h'].signal.includes('LONG') ? 'bg-emerald-950 text-emerald-400' : (tfs['1h'].signal.includes('SHORT') ? 'bg-rose-950 text-rose-400' : 'bg-gray-800 text-gray-400')}">1h</span>
                        <span class="px-1.5 py-0.5 rounded ${tfs['4h'].signal.includes('LONG') ? 'bg-emerald-950 text-emerald-400' : (tfs['4h'].signal.includes('SHORT') ? 'bg-rose-950 text-rose-400' : 'bg-gray-800 text-gray-400')}">4h</span>
                        <span class="px-1.5 py-0.5 rounded ${tfs['1d'].signal.includes('LONG') ? 'bg-emerald-950 text-emerald-400' : (tfs['1d'].signal.includes('SHORT') ? 'bg-rose-950 text-rose-400' : 'bg-gray-800 text-gray-400')}">1d</span>
                    </div>
                </div>
            `;
        }

        const card = document.createElement('div');
        card.className = `glass-card rounded-2xl p-5 border border-gray-800 transition-all duration-300 flex flex-col justify-between ${cardBorder}`;
        card.innerHTML = `
            <div>
                <!-- Kart Başlığı & Fiyat -->
                <div class="flex items-center justify-between pb-3 border-b border-gray-800">
                    <div>
                        <div class="flex items-center gap-2">
                            <h3 class="text-lg font-extrabold text-white">${s.symbol}</h3>
                            <span class="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 uppercase font-mono">${s.timeframe}</span>
                        </div>
                        <div class="text-xs text-gray-400 mt-0.5">
                            Fiyat: <span class="font-mono font-semibold text-gray-200">$${formatPrice(s.current_price)}</span>
                        </div>
                    </div>
                    
                    <!-- Güven Skoru & R:R Rozetleri -->
                    <div class="text-right">
                        <div class="text-xs font-bold ${scoreColor} flex items-center justify-end gap-1">
                            <i data-lucide="shield-check" class="w-3.5 h-3.5"></i> %${s.confidence_score} Güven
                        </div>
                        <div class="text-[11px] font-mono font-semibold text-amber-400 mt-0.5">
                            R:R 1 : ${s.rr_ratio}
                        </div>
                    </div>
                </div>

                <!-- 🎯 EN UYGUN STRATEJİ VURGULAMA KUTUSU (ÇİFT DİLLİ TR / EN) -->
                <div class="mt-2.5 p-2 bg-indigo-950/40 rounded-xl border border-indigo-800/50 flex items-center gap-2">
                    <div class="w-7 h-7 rounded-lg bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center flex-shrink-0">
                        <i data-lucide="target" class="w-4 h-4"></i>
                    </div>
                    <div>
                        <div class="text-[10px] font-extrabold text-indigo-400 uppercase tracking-wider">🎯 En Uygun Strateji (Best Suited Strategy):</div>
                        <div class="text-xs font-bold text-white leading-tight">${primaryStrat}</div>
                    </div>
                </div>

                <!-- Yön Rozeti -->
                <div class="py-2 flex items-center gap-1.5">
                    <span class="text-xs font-bold px-2.5 py-1 rounded-lg border ${directionBg}">
                        ${s.direction_label}
                    </span>
                </div>

                <!-- MTF Mini Radar -->
                ${mtfHtml}

                <!-- Seviyeler Matrisi (Giriş, SL, TP2) -->
                <div class="grid grid-cols-3 gap-2 p-3 bg-gray-950/60 rounded-xl border border-gray-800/80 my-2 text-xs font-mono">
                    <div>
                        <div class="text-cyan-400 text-[10px] font-semibold">🎯 GİRİŞ (ENTRY)</div>
                        <div class="font-bold text-white mt-0.5">$${formatPrice(s.entry_price)}</div>
                    </div>
                    <div>
                        <div class="text-rose-400 text-[10px] font-semibold">🛑 STOP LOSS</div>
                        <div class="font-bold text-rose-400 mt-0.5">$${formatPrice(s.stop_loss)}</div>
                        <div class="text-[9px] text-rose-500">-%${s.risk_percent}</div>
                    </div>
                    <div>
                        <div class="text-emerald-400 text-[10px] font-semibold">🚀 HEDEF 2 (TP2)</div>
                        <div class="font-bold text-emerald-400 mt-0.5">$${formatPrice(s.tp2)}</div>
                        <div class="text-[9px] text-emerald-500">+%${s.reward_tp2_percent}</div>
                    </div>
                </div>

                <!-- 🤖 CANLI GEMINI AI ANALİZ ALANI (2 AŞAMALI DENETİM KUTUSU) -->
                <div id="aiVerdictBox-${safeSym}" class="hidden my-2.5 p-3 rounded-xl border transition-all duration-300"></div>

                <!-- Neden Bu Sinyal? (Teknik Gerekçeler) -->
                <div class="mt-3 space-y-1.5">
                    <div class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Neden Bu Sinyal? (Reasons)</div>
                    <ul class="space-y-1.5">
                        ${reasonsHtml}
                    </ul>
                </div>
            </div>

            <!-- Kart Alt Butonları (5 Kilit Eylem: 💬 AI Chat & Analiz, Ham Veri, Grafik, 🧪 Test) -->
            <div class="pt-3.5 mt-3.5 border-t border-gray-800/80 space-y-2">
                <!-- 1. Satır: 💬 SAĞDAN AÇILAN AI CHAT & ANALİZ BUTONU (Düzenlenebilir & Model Seçimli) -->
                <button onclick="openAiChatDrawer('${s.symbol}')" class="w-full py-2 px-3 rounded-xl bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-500 hover:from-indigo-500 hover:to-purple-400 text-white text-xs font-bold transition shadow-md shadow-indigo-500/20 flex items-center justify-center gap-1.5 active:scale-98">
                    <i data-lucide="sparkles" class="w-3.5 h-3.5 text-yellow-300"></i>
                    <span>🤖 AI ANALİZ & CHAT (DÜZENLE & SOR)</span>
                </button>

                <!-- 2. Satır: 4 Hızlı Eylem Butonu -->
                <div class="grid grid-cols-4 gap-1">
                    <button onclick="handleCopyPrompt('${s.symbol}')" title="AI Analiz Promptunu Kopyala" class="flex items-center justify-center gap-1 py-1.5 px-1 rounded-xl bg-gray-800/90 hover:bg-gray-700 text-indigo-300 border border-indigo-500/20 text-[10px] font-semibold transition active:scale-95">
                        <i data-lucide="copy" class="w-3 h-3"></i>
                        <span>Prompt</span>
                    </button>

                    <button onclick="handleOpenRawModal('${s.symbol}')" title="İnteraktif Seçenekli Ham Piyasa Verisi Pop-up Aç" class="flex items-center justify-center gap-1 py-1.5 px-1 rounded-xl bg-gray-800/90 hover:bg-gray-700 text-emerald-300 border border-emerald-500/20 text-[10px] font-semibold transition active:scale-95">
                        <i data-lucide="file-spreadsheet" class="w-3 h-3"></i>
                        <span>Ham Veri</span>
                    </button>

                    <button onclick="openChartModal('${s.symbol}')" title="İnteraktif TradingView Grafiğinde Gör" class="flex items-center justify-center gap-1 py-1.5 px-1 rounded-xl bg-gray-800/90 hover:bg-gray-700 text-gray-200 border border-gray-700 text-[10px] font-semibold transition active:scale-95">
                        <i data-lucide="line-chart" class="w-3 h-3 text-emerald-400"></i>
                        <span>Grafik</span>
                    </button>

                    <button onclick="openBacktestTab('${s.symbol}')" title="Bu Koin İçin 11 Stratejiyi Yeni Sekmede Test Et ve En İyisini Bul" class="flex items-center justify-center gap-1 py-1.5 px-1 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/30 text-[10px] font-bold transition active:scale-95">
                        <i data-lucide="flask-conical" class="w-3 h-3 text-amber-400"></i>
                        <span>🧪 Test</span>
                    </button>
                </div>
            </div>
        `;

        resultsGrid.appendChild(card);
    });

    resultsGrid.classList.remove('hidden');
    lucide.createIcons();
}

/**
 * 🧪 YENİ SEKMEDE STRATEJİ TEST LABORATUVARINI AÇ
 */
function openBacktestTab(symbol) {
    if (!symbol) return;
    const cleanSym = encodeURIComponent(symbol);
    const tf = document.getElementById('timeframeSelect') ? document.getElementById('timeframeSelect').value : '1h';
    window.open(`/backtest.html?symbol=${cleanSym}&timeframe=${tf}`, '_blank');
}

function handleCopyPrompt(symbol) {
    const setup = currentSetups.find(s => s.symbol === symbol);
    if (!setup) return;
    const text = setup.ai_prompt || "AI Prompt hazırlanıyor...";
    copyToClipboard(text, `${setup.symbol} AI Promptu Kopyalandı!`);
}

function handleOpenRawModal(symbol) {
    const setup = currentSetups.find(s => s.symbol === symbol);
    if (!setup) return;
    openRawDataModal(setup);
}

function openRawDataModal(setup) {
    selectedSetupForRawModal = setup;
    const rawDataModal = document.getElementById('rawDataModal');
    const symbolEl = document.getElementById('rawModalSymbol');
    const timeframeEl = document.getElementById('rawModalTimeframe');
    const limitEl = document.getElementById('rawModalCandleLimit');

    if (!rawDataModal || !setup) return;

    symbolEl.textContent = setup.symbol;
    if (timeframeEl) timeframeEl.value = setup.timeframe || '1h';
    if (limitEl) limitEl.value = '30';

    rawDataModal.classList.remove('hidden');
    updateRawModalPreview();
}

async function updateRawModalPreview() {
    if (!selectedSetupForRawModal) return;

    const previewEl = document.getElementById('rawModalPreview');
    const statusEl = document.getElementById('rawModalStatus');
    const timeframeEl = document.getElementById('rawModalTimeframe');
    const limitEl = document.getElementById('rawModalCandleLimit');

    const symbol = selectedSetupForRawModal.symbol;
    const timeframe = timeframeEl ? timeframeEl.value : (selectedSetupForRawModal.timeframe || '1h');
    const limit = limitEl ? parseInt(limitEl.value) : 30;

    if (previewEl) previewEl.textContent = "Veriler Binance sunucularından çekiliyor ve zaman damgaları formatlanıyor...";
    if (statusEl) statusEl.textContent = "⏳ Canlı Veri Yükleniyor...";

    try {
        const res = await fetch(`/api/raw-data/${encodeURIComponent(symbol)}?timeframe=${timeframe}&limit=${limit}`);
        const data = await res.json();

        if (data.status === 'success' && data.raw_text) {
            if (previewEl) previewEl.textContent = data.raw_text;
            if (statusEl) statusEl.textContent = `✓ ${symbol} (${timeframe}) - Son ${limit} Mum Verisi Yerel Saatle Hazır`;
        } else {
            if (previewEl) previewEl.textContent = selectedSetupForRawModal.raw_market_data || "Veri alınamadı.";
            if (statusEl) statusEl.textContent = "⚠️ Varsayılan veriler gösteriliyor.";
        }
    } catch (err) {
        console.error("Raw modal preview fetch error:", err);
        if (previewEl) previewEl.textContent = selectedSetupForRawModal.raw_market_data || "Veri yüklenemedi.";
    }
}

function copyToClipboard(text, successTitle) {
    if (!text) {
        showToast('Hata', 'Kopyalanacak metin bulunamadı.', true);
        return;
    }

    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
            showToast(successTitle || 'Kopyalandı!', 'Panoya kopyalama başarılı.');
        }).catch(err => {
            fallbackCopyToClipboard(text, successTitle);
        });
    } else {
        fallbackCopyToClipboard(text, successTitle);
    }
}

function fallbackCopyToClipboard(text, successTitle) {
    try {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        textArea.style.top = "-999999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);

        if (successful) {
            showToast(successTitle || 'Kopyalandı!', 'Panoya kopyalama başarılı.');
        } else {
            showToast('Kopyalama Başarısız', 'Panoya yazma izni verilemedi.', true);
        }
    } catch (err) {
        console.error('Fallback copy failed:', err);
        showToast('Kopyalama Başarısız', 'Lütfen manuel kopyalayın.', true);
    }
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
    toast.classList.add('translate-y-0', 'opacity-100');

    setTimeout(() => {
        toast.classList.remove('translate-y-0', 'opacity-100');
        toast.classList.add('translate-y-20', 'opacity-0');
    }, 3500);
}

async function openChartModal(symbol) {
    const setup = currentSetups.find(s => s.symbol === symbol);
    if (!setup) return;
    selectedSetupForModal = setup;
    currentModalTimeframe = setup.timeframe || '1h';

    const modal = document.getElementById('chartModal');
    const chartLoader = document.getElementById('chartLoader');
    
    document.getElementById('modalTitle').textContent = setup.symbol;
    document.getElementById('modalDirectionBadge').textContent = setup.direction_label;
    document.getElementById('modalDirectionBadge').className = setup.direction === 'LONG' 
        ? 'text-xs font-bold px-2.5 py-1 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' 
        : 'text-xs font-bold px-2.5 py-1 rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/30';
        
    document.getElementById('modalScoreBadge').textContent = `%${setup.confidence_score} Güven`;
    document.getElementById('modalRRBadge').textContent = `1 : ${setup.rr_ratio} R:R`;
    
    document.getElementById('modalEntry').textContent = `$${formatPrice(setup.entry_price)}`;
    document.getElementById('modalSL').textContent = `$${formatPrice(setup.stop_loss)} (-%${setup.risk_percent})`;
    document.getElementById('modalTP1').textContent = `$${formatPrice(setup.tp1)} (+%${setup.reward_tp1_percent})`;
    document.getElementById('modalTP2').textContent = `$${formatPrice(setup.tp2)} (+%${setup.reward_tp2_percent})`;
    document.getElementById('modalTP3').textContent = `$${formatPrice(setup.tp3)} (+%${setup.reward_tp3_percent})`;

    document.getElementById('hudSymbol').textContent = `${setup.symbol} (${currentModalTimeframe})`;
    document.getElementById('hudPrice').textContent = `$${formatPrice(setup.current_price)}`;
    const changeEl = document.getElementById('hudChange');
    if (setup.indicators && setup.indicators.price_change_24h !== undefined) {
        changeEl.textContent = `${setup.indicators.price_change_24h > 0 ? '+' : ''}${setup.indicators.price_change_24h}%`;
        changeEl.className = setup.indicators.price_change_24h >= 0 ? 'text-[11px] font-mono text-emerald-400 font-bold' : 'text-[11px] font-mono text-rose-400 font-bold';
    }
    
    if (setup.indicators) {
        document.getElementById('hudEma20').textContent = `$${formatPrice(setup.indicators.ema20)}`;
        document.getElementById('hudEma50').textContent = `$${formatPrice(setup.indicators.ema50)}`;
        document.getElementById('hudEma200').textContent = `$${formatPrice(setup.indicators.ema200)}`;
    }

    const primaryStrat = setup.primary_strategy || (setup.strategies ? setup.strategies[0] : 'SMC & Trend Analizi');
    document.getElementById('hudStrategy').textContent = `🎯 En Uygun Strateji (Best Suited Strategy): ${primaryStrat}`;

    renderModalMtfGrid(setup.mtf);

    const reasonsListEl = document.getElementById('modalReasonsList');
    reasonsListEl.innerHTML = setup.reasons.map(r => `
        <li class="flex items-start gap-1.5">
            <span class="text-emerald-400 font-bold">✓</span>
            <span>${r}</span>
        </li>
    `).join('');

    updateModalTimeframeButtons(currentModalTimeframe);

    modal.classList.remove('hidden');
    chartLoader.classList.remove('hidden');
    lucide.createIcons();

    setTimeout(async () => {
        initTradingViewChart('tvChartArea');
        await loadModalChartData(setup.symbol, currentModalTimeframe);
    }, 40);
}

function renderModalMtfGrid(mtf) {
    const mtfStatusEl = document.getElementById('modalMtfStatus');
    const mtfGridEl = document.getElementById('modalMtfGrid');
    if (!mtf || !mtf.timeframes) {
        mtfStatusEl.textContent = 'Analiz Yapılıyor...';
        mtfGridEl.innerHTML = '<div class="col-span-4 text-gray-500">MTF verisi yükleniyor...</div>';
        return;
    }

    mtfStatusEl.textContent = mtf.alignment_status;
    const tfs = mtf.timeframes;

    const cards = Object.keys(tfs).map(key => {
        const item = tfs[key];
        const isLong = item.signal.includes('LONG');
        const isShort = item.signal.includes('SHORT');
        const borderClass = isLong ? 'border-emerald-800/40 bg-emerald-950/20' : (isShort ? 'border-rose-800/40 bg-rose-950/20' : 'border-gray-800 bg-gray-900/50');
        const textClass = isLong ? 'text-emerald-400' : (isShort ? 'text-rose-400' : 'text-gray-400');
        
        return `
            <div class="p-2 rounded-lg border ${borderClass}">
                <div class="text-[10px] text-gray-400 font-semibold">${item.name}</div>
                <div class="font-bold text-xs ${textClass} mt-0.5">${item.signal}</div>
                <div class="text-[10px] text-gray-400 mt-0.5">RSI: <span class="font-mono text-gray-300 font-semibold">${item.rsi}</span></div>
            </div>
        `;
    }).join('');

    mtfGridEl.innerHTML = cards;
}

async function loadModalChartData(symbol, timeframe) {
    const chartLoader = document.getElementById('chartLoader');
    chartLoader.classList.remove('hidden');

    try {
        const res = await fetch(`/api/chart-data/${encodeURIComponent(symbol)}?timeframe=${timeframe}`);
        const chartData = await res.json();

        if (chartData.status === 'success') {
            if (chartData.setup) {
                selectedSetupForModal = chartData.setup;
            }
            if (chartData.mtf) {
                renderModalMtfGrid(chartData.mtf);
            }
            renderChartData(chartData);
        } else {
            showToast('Hata', 'Grafik verisi yüklenemedi.', true);
        }
    } catch (e) {
        console.error('Error fetching chart:', e);
    } finally {
        chartLoader.classList.add('hidden');
    }
}

async function changeModalTimeframe(tf) {
    if (!selectedSetupForModal) return;
    currentModalTimeframe = tf;
    updateModalTimeframeButtons(tf);
    document.getElementById('hudSymbol').textContent = `${selectedSetupForModal.symbol} (${tf})`;
    await loadModalChartData(selectedSetupForModal.symbol, tf);
}

function updateModalTimeframeButtons(activeTf) {
    ['15m', '1h', '4h', '1d'].forEach(tf => {
        const btn = document.getElementById(`tfBtn-${tf}`);
        if (btn) {
            if (tf === activeTf) {
                btn.className = 'px-2 py-1 rounded-md text-[11px] font-semibold bg-indigo-600 text-white shadow';
            } else {
                btn.className = 'px-2 py-1 rounded-md text-[11px] font-semibold text-gray-400 hover:text-white transition';
            }
        }
    });
}

function formatPrice(val) {
    if (val === undefined || val === null) return '0.00';
    if (val >= 1000) return val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (val >= 1) return val.toFixed(4);
    return val.toFixed(6);
}
