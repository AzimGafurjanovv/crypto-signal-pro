"""
CryptoSignalPro AI - Telegram Bildirim Motoru (telegram_notifier.py)
Kullanıcının özel stratejileri için Telegram Bot üzerinden anlık sinyal ve erken uyarı gönderir.
"""

import os
import json
import requests
from typing import Dict, Any, Optional

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CONFIG_FILE = os.path.join(CONFIG_DIR, "telegram_config.json")

def load_telegram_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        
    default_config = {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
        "notify_retest": True,      # 2. Aşama (Retest Yapanlar)
        "notify_confirmed": True,   # 3. Aşama (Onaylanan Kesin Girişler)
        "timeframes": ["1h", "15m", "4h"],
        "strategies": ["PDH_PDL", "SWING_HL"]
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception as e:
            print(f"⚠️ Telegram config okuma hatası: {e}")
            
    return default_config

def save_telegram_config(config: Dict[str, Any]) -> bool:
    try:
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Telegram config kaydetme hatası: {e}")
        return False

def send_telegram_raw_message(bot_token: str, chat_id: str, text: str) -> Dict[str, Any]:
    if not bot_token or not chat_id:
        return {"status": "error", "message": "Bot Token veya Chat ID eksik."}
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        if data.get("ok"):
            return {"status": "success", "message": "Mesaj başarıyla iletildi."}
        else:
            return {"status": "error", "message": data.get("description", "Telegram API hatası")}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def send_retest_alert(coin_data: Dict[str, Any], strategy_type: str = "PDH_PDL") -> bool:
    """2. Aşama: Retest Yapanlar (Erken Uyarı Alarmı)"""
    config = load_telegram_config()
    if not config.get("enabled") or not config.get("notify_retest"):
        return False
        
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")
    if not bot_token or not chat_id:
        return False

    symbol = coin_data.get("symbol", "COIN")
    tf = coin_data.get("timeframe", "1h")
    direction = coin_data.get("direction", "LONG")
    curr_price = coin_data.get("current_price", 0.0)
    level_price = coin_data.get("breakout_level") or coin_data.get("pdh") or coin_data.get("pdl") or coin_data.get("swing_level", 0.0)
    retest_bar = coin_data.get("retest_bar", {})
    retest_time = retest_bar.get("time_str", "Şimdi")

    dir_icon = "🟢" if direction == "LONG" else "🔴"
    
    if strategy_type == "PDH_PDL":
        strat_badge = "📅 1. STRATEJİ: PDH / PDL (Dünün Zirve/Dibi)"
        header_tag = "[1. STRATEJİ: PDH/PDL]"
        level_name = "Dünün Zirvesi (PDH)" if direction == "LONG" else "Dünün Dibi (PDL)"
        strat_desc = "UTC 00:00–24:00 Günlük seviye kırılımı sonrası 0.3xATR retesti yapıldı."
    else:
        strat_badge = "🌊 2. STRATEJİ: SWING HIGH / LOW (Yapısal Dönüşler)"
        header_tag = "[2. STRATEJİ: SWING H/L]"
        level_name = "Onaylı Swing High" if direction == "LONG" else "Onaylı Swing Low"
        strat_desc = "Lookback(3) Yapısal dönüş noktası kırılımı sonrası 0.3xATR retesti yapıldı."

    text = f"""<b>⚠️ {header_tag} RETEST ERKEN UYARISI!</b> 🎯

<b>📐 KULLANILAN STRATEJİ:</b>
👉 <b>{strat_badge}</b>

━━━━━━━━━━━━━━━━━━━━
<b>🪙 Parite:</b> <code>{symbol}</code> ({tf})
<b>{dir_icon} Yön:</b> <b>{direction}</b>
<b>📍 Kırılan Seviye ({level_name}):</b> <code>${level_price:,.4f}</code>
<b>📊 Güncel Fiyat:</b> <code>${curr_price:,.4f}</code>
<b>⏰ Retest Zamanı:</b> {retest_time}
━━━━━━━━━━━━━━━━━━━━

💡 <b>Durum:</b> {strat_desc}
⏳ <i>Sonraki 1-2 bar içinde Hacimli Onay Mumu gelirse KESİN GİRİŞ gerçekleşecektir.</i>

🔗 <a href="http://47.251.110.202/my_strategy.html">Radarda Canlı Grafiği Aç</a>"""

    res = send_telegram_raw_message(bot_token, chat_id, text)
    return res.get("status") == "success"

def send_confirmed_alert(coin_data: Dict[str, Any], strategy_type: str = "PDH_PDL") -> bool:
    """3. Aşama: Kesin Onaylananlar (Giriş Sinyali Alarmı)"""
    config = load_telegram_config()
    if not config.get("enabled") or not config.get("notify_confirmed"):
        return False
        
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")
    if not bot_token or not chat_id:
        return False

    symbol = coin_data.get("symbol", "COIN")
    tf = coin_data.get("timeframe", "1h")
    direction = coin_data.get("direction", "LONG")
    entry_price = coin_data.get("entry_price") or coin_data.get("current_price", 0.0)
    stop_loss = coin_data.get("stop_loss", 0.0)
    take_profit = coin_data.get("take_profit") or coin_data.get("tp1", 0.0)
    rr = coin_data.get("risk_reward", "1:2.0+")
    conf_bar = coin_data.get("confirmed_bar", {})
    conf_time = conf_bar.get("time_str", "Şimdi")

    dir_icon = "🟢" if direction == "LONG" else "🔴"
    
    if strategy_type == "PDH_PDL":
        strat_badge = "📅 1. STRATEJİ: PDH / PDL (Dünün Zirve/Dibi)"
        header_tag = "[1. STRATEJİ: PDH/PDL]"
    else:
        strat_badge = "🌊 2. STRATEJİ: SWING HIGH / LOW (Yapısal Dönüşler)"
        header_tag = "[2. STRATEJİ: SWING H/L]"

    text = f"""<b>🚀 {header_tag} 🔥 KESİN GİRİŞ ONAYLANDI!</b>

<b>📐 KULLANILAN STRATEJİ:</b>
👉 <b>{strat_badge}</b>

━━━━━━━━━━━━━━━━━━━━
<b>🪙 Parite:</b> <code>{symbol}</code> ({tf})
<b>{dir_icon} Sinyal Yönü:</b> <b>{direction}</b>
━━━━━━━━━━━━━━━━━━━━

🟡 <b>Giriş Seviyesi (Entry):</b> <code>${entry_price:,.4f}</code>
🛑 <b>Stop Loss (0.2xATR):</b> <code>${stop_loss:,.4f}</code>
🎯 <b>Hedef (Dinamik S/R):</b> <code>${take_profit:,.4f}</code>
⚖️ <b>Risk / Kazanç (R:R):</b> <code>{rr} R</code>
━━━━━━━━━━━━━━━━━━━━

✅ <b>Onay Kuralı:</b> Retest sonrası Yutan Mum (Engulfing) veya %60+ Gövdeli Mum, 20 SMA üzeri Hacim ile kapandı.
⏰ <b>Onay Saati:</b> {conf_time}

🔗 <a href="http://47.251.110.202/my_strategy.html">Grafiği İnteraktif İncele</a>"""

    res = send_telegram_raw_message(bot_token, chat_id, text)
    return res.get("status") == "success"
