"""
CryptoSignalPro AI - 7/24 Arka Plan Radar Bildirim Servisi (strategy_alert_service.py)
Kullanıcının 1. ve 2. stratejilerini arka planda tarar, yeni Retest veya Onaylanan coin tespit ettiğinde Telegram'a gönderir.
"""

import time
import asyncio
from typing import Set, Dict, Any
from engine.pdh_pdl_radar import run_pdh_pdl_radar
from engine.swing_radar import run_swing_radar
from engine.telegram_notifier import load_telegram_config, send_retest_alert, send_confirmed_alert

class StrategyAlertService:
    def __init__(self):
        self.is_running: bool = False
        self.sent_alert_keys: Set[str] = set()
        self.last_scan_time: float = 0.0
        self.interval_seconds: int = 60 # 60 saniyede bir kontrol et

    async def start_loop(self):
        self.is_running = True
        print("🔔 [TELEGRAM RADAR SERVICE] 7/24 Arka Plan Alarm Servisi Başlatıldı.")
        
        while self.is_running:
            try:
                config = load_telegram_config()
                if config.get("enabled", False) and (config.get("notify_retest") or config.get("notify_confirmed")):
                    await self.check_and_notify_radars(config)
            except Exception as e:
                print(f"⚠️ [TELEGRAM RADAR SERVICE] Hata: {e}")
                
            await asyncio.sleep(self.interval_seconds)

    async def check_and_notify_radars(self, config: Dict[str, Any]):
        timeframes = config.get("timeframes", ["1h"])
        strategies = config.get("strategies", ["PDH_PDL", "SWING_HL"])

        for tf in timeframes:
            # 1. Strateji: PDH / PDL
            if "PDH_PDL" in strategies:
                try:
                    pdh_res = run_pdh_pdl_radar(timeframe=tf, limit_coins=30)
                    if pdh_res.get("status") == "success":
                        self._process_stage_alerts(pdh_res.get("stages", {}), "PDH_PDL", tf)
                except Exception as e:
                    print(f"⚠️ PDH/PDL Radar check error: {e}")

            # 2. Strateji: Swing High / Low
            if "SWING_HL" in strategies:
                try:
                    swing_res = run_swing_radar(timeframe=tf, limit_coins=30, swing_lookback=3)
                    if swing_res.get("status") == "success":
                        self._process_stage_alerts(swing_res.get("stages", {}), "SWING_HL", tf)
                except Exception as e:
                    print(f"⚠️ Swing Radar check error: {e}")

    def _process_stage_alerts(self, stages: Dict[str, Any], strat_type: str, tf: str):
        # A. 2. Aşama: Retesting Yapanlar
        for coin in stages.get("retesting", []):
            sym = coin.get("symbol")
            direction = coin.get("direction")
            retest_time = coin.get("retest_bar", {}).get("time_str", "now")
            alert_key = f"{strat_type}:{tf}:{sym}:{direction}:RETEST:{retest_time}"

            if alert_key not in self.sent_alert_keys:
                print(f"📢 [TELEGRAM] 2. Aşama RETEST Alarmı Gönderiliyor: {sym} ({strat_type})")
                success = send_retest_alert(coin, strategy_type=strat_type)
                if success:
                    self.sent_alert_keys.add(alert_key)

        # B. 3. Aşama: Onaylananlar (Kesin Giriş)
        for coin in stages.get("confirmed", []):
            sym = coin.get("symbol")
            direction = coin.get("direction")
            conf_time = coin.get("confirmed_bar", {}).get("time_str", "now")
            alert_key = f"{strat_type}:{tf}:{sym}:{direction}:CONFIRMED:{conf_time}"

            if alert_key not in self.sent_alert_keys:
                print(f"🔥 [TELEGRAM] 3. Aşama KESİN GİRİŞ Alarmı Gönderiliyor: {sym} ({strat_type})")
                success = send_confirmed_alert(coin, strategy_type=strat_type)
                if success:
                    self.sent_alert_keys.add(alert_key)

        # Bellek temizliği (1000'den fazla kayıt birikirse en eskileri temizle)
        if len(self.sent_alert_keys) > 2000:
            self.sent_alert_keys = set(list(self.sent_alert_keys)[-1000:])

telegram_alert_service = StrategyAlertService()
