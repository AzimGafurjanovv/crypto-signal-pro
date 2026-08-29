// CryptoSignalPro AI - Telegram Bildirimleri Yönetim Modülü (telegram.js)

document.addEventListener('DOMContentLoaded', () => {
    loadTelegramSettings();
});

async function loadTelegramSettings() {
    try {
        const res = await fetch('/api/telegram/settings');
        const data = await res.json();
        if (data.status === 'success' && data.config) {
            const cfg = data.config;
            const tokenInput = document.getElementById('tgBotTokenInput');
            const chatIdInput = document.getElementById('tgChatIdInput');
            const enabledToggle = document.getElementById('tgEnabledToggle');
            const retestToggle = document.getElementById('tgRetestToggle');
            const confirmedToggle = document.getElementById('tgConfirmedToggle');
            const statusBadge = document.getElementById('tgStatusBadge');

            if (tokenInput && cfg.masked_token) tokenInput.value = cfg.masked_token;
            if (chatIdInput && cfg.chat_id) chatIdInput.value = cfg.chat_id;
            if (enabledToggle) enabledToggle.checked = cfg.enabled;
            if (retestToggle) retestToggle.checked = cfg.notify_retest;
            if (confirmedToggle) confirmedToggle.checked = cfg.notify_confirmed;

            if (statusBadge) {
                if (cfg.enabled && cfg.has_token && cfg.chat_id) {
                    statusBadge.textContent = "● Telegram Canlı";
                    statusBadge.className = "text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
                } else {
                    statusBadge.textContent = "○ Telegram Kapalı";
                    statusBadge.className = "text-[10px] font-mono px-2 py-0.5 rounded-full bg-gray-800 text-gray-400 border border-gray-700";
                }
            }
        }
    } catch (e) {
        console.error('Telegram settings error:', e);
    }
}

function openTelegramModal() {
    const modal = document.getElementById('telegramSettingsModal');
    if (modal) {
        modal.classList.remove('hidden');
        lucide.createIcons();
    }
}

function closeTelegramModal() {
    const modal = document.getElementById('telegramSettingsModal');
    if (modal) modal.classList.add('hidden');
}

async function saveTelegramSettings() {
    const tokenInput = document.getElementById('tgBotTokenInput');
    const chatIdInput = document.getElementById('tgChatIdInput');
    const enabledToggle = document.getElementById('tgEnabledToggle');
    const retestToggle = document.getElementById('tgRetestToggle');
    const confirmedToggle = document.getElementById('tgConfirmedToggle');
    const saveBtn = document.getElementById('tgSaveBtn');

    if (!tokenInput || !chatIdInput) return;

    const payload = {
        enabled: Boolean(enabledToggle && enabledToggle.checked),
        bot_token: tokenInput.value.trim(),
        chat_id: chatIdInput.value.trim(),
        notify_retest: Boolean(retestToggle && retestToggle.checked),
        notify_confirmed: Boolean(confirmedToggle && confirmedToggle.checked),
        timeframes: ["1h", "15m", "4h"],
        strategies: ["PDH_PDL", "SWING_HL", "CHART_PATTERNS"]
    };

    if (!payload.bot_token || !payload.chat_id) {
        alert("Lütfen hem Bot Token hem de Chat ID alanlarını doldurunuz.");
        return;
    }

    if (saveBtn) saveBtn.innerHTML = `<div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div> <span>Kaydediliyor...</span>`;

    try {
        const res = await fetch('/api/telegram/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.status === 'success') {
            alert("✅ Telegram bildirim ayarları başarıyla kaydedildi! Sistem 7/24 sinyalleri Telegram'a iletecektir.");
            closeTelegramModal();
            loadTelegramSettings();
        } else {
            alert("❌ Hata: " + (data.message || "Kaydedilemedi."));
        }
    } catch (e) {
        alert("Bağlantı hatası: " + e.message);
    } finally {
        if (saveBtn) saveBtn.innerHTML = `<i data-lucide="check" class="w-4 h-4"></i> <span>Ayarları Kaydet & Aktif Et</span>`;
        lucide.createIcons();
    }
}

async function sendTelegramTestMessage() {
    const tokenInput = document.getElementById('tgBotTokenInput');
    const chatIdInput = document.getElementById('tgChatIdInput');
    const testBtn = document.getElementById('tgTestBtn');

    const bot_token = tokenInput ? tokenInput.value.trim() : "";
    const chat_id = chatIdInput ? chatIdInput.value.trim() : "";

    if (testBtn) testBtn.innerHTML = `<div class="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div> <span>İletiliyor...</span>`;

    try {
        const res = await fetch('/api/telegram/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bot_token, chat_id, enabled: true, notify_retest: true, notify_confirmed: true, timeframes: ["1h"], strategies: ["PDH_PDL"] })
        });
        const data = await res.json();

        if (data.status === 'success') {
            alert("🎉 Harika! Telegram botunuzdan test mesajı başarıyla telefonunuza iletildi!");
        } else {
            alert("❌ Telegram Hatası: " + (data.message || "Bilinmeyen hata. Lütfen Token ve Chat ID'nizi kontrol edin."));
        }
    } catch (e) {
        alert("Bağlantı hatası: " + e.message);
    } finally {
        if (testBtn) testBtn.innerHTML = `<i data-lucide="send" class="w-4 h-4"></i> <span>🔔 Test Bildirimi Gönder</span>`;
        lucide.createIcons();
    }
}
