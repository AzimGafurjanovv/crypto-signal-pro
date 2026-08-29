"""
CryptoSignalPro AI - 7/24 Akıllı Anti-Spam Radar Alarm Servisi (strategy_alert_service.py)

Özellikler:
1. Her coin ve kurulum (setup) için YALNIZCA BİR KEZ alarm gönderir.
2. Fiyat aynı kurulum içinde kaldığı sürece ASLA mükerrer (spam) bildirim göndermez.
3. Ancak o işlem tamamlanır, stop olur veya geçersiz kılınır ve DAHA SONRA YENİ BİR KURULUM (yeni kırılım döngüsü) oluşursa tekrar alarm gönderir.
4. Gönderilen alarmları diskte (alert_history.json) saklar, sunucu yeniden başlasa bile eski alarmları tekrar atmaz.
"""

import os
import json
import time
import asyncio
from typing import Dict, Any
from engine.pdh_pdl_radar import run_pdh_pdl_radar
from engine.swing_radar import run_swing_radar
from engine.pattern_radar import run_pattern_radar
from engine.telegram_notifier import load_telegram_config, send_retest_alert, send_confirmed_alert

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "alert_history.json")

class StrategyAlertService:
    def __init__(self):
        self.is_running: bool = False
        self.interval_seconds: int = 60 # Her 60 saniyede bir tara
        self.history: Dict[str, Dict[str, Any]] = self._load_history()

    def _load_history(self) -> Dict[str, Dict[str, Any]]:
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Alert history okuma hatası: {e}")
        return {}

    def _save_history(self):
        try:
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR, exist_ok=True)
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Alert history kaydetme hatası: {e}")

    def _cleanup_old_history(self):
        """3 günden eski tamamlanmış veya aktif olmayan kayıtları temizler."""
        now = time.time()
        max_age = 86400 * 3 # 3 gün
        keys_to_delete = []
        for k, v in self.history.items():
            last_ts = v.get("last_updated", 0)
            if now - last_ts > max_age:
                keys_to_delete.append(k)
        for k in keys_to_delete:
            del self.history[k]
        if keys_to_delete:
            self._save_history()

    async def start_loop(self):
        self.is_running = True
        print("🔔 [TELEGRAM RADAR SERVICE] Akıllı Anti-Spam Alarm Servisi Başlatıldı.")
        
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

            # 3. Strateji: Formasyon Radarı (Trendline, Üçgen, S/R Flip, İkili Dip)
            if "CHART_PATTERNS" in strategies or True:
                try:
                    pat_res = run_pattern_radar(timeframe=tf, limit_coins=30)
                    if pat_res.get("status") == "success":
                        self._process_stage_alerts(pat_res.get("stages", {}), "CHART_PATTERNS", tf)
                except Exception as e:
                    print(f"⚠️ Pattern Radar check error: {e}")

        self._cleanup_old_history()

    def _get_setup_identifier(self, coin: Dict[str, Any], strat_type: str, tf: str) -> str:
        """
        Her bir işlem döngüsünü benzersiz kılan kimlik (Setup Key).
        Kırılan seviye + Kırılma zamanı (bo_time) + Parite + Yön kombinasyonu ile üretilir.
        Aynı kırılma döngüsü içinde asla tekrar alarm üretmez.
        """
        symbol = coin.get("symbol", "")
        direction = coin.get("direction", "")
        bo_level = coin.get("breakout_level") or coin.get("pdh") or coin.get("pdl") or coin.get("swing_level", 0.0)
        bo_bar = coin.get("breakout_bar", {})
        bo_time = bo_bar.get("time_str") or bo_bar.get("iso_time") or str(bo_bar.get("timestamp", ""))

        return f"{strat_type}_{tf}_{symbol}_{direction}_{bo_level}_{bo_time}"

    def _process_stage_alerts(self, stages: Dict[str, Any], strat_type: str, tf: str):
        now = time.time()
        updated = False

        # A. 2. Aşama: Retesting Yapanlar (Erken Uyarı)
        for coin in stages.get("retesting", []):
            setup_id = self._get_setup_identifier(coin, strat_type, tf)
            record = self.history.get(setup_id, {
                "retest_sent": False,
                "confirmed_sent": False,
                "created_at": now,
                "last_updated": now
            })

            # Bu kurulum için Retest veya Onay alarmı daha önce ATILMADIYSA gönder
            if not record.get("retest_sent", False) and not record.get("confirmed_sent", False):
                print(f"📢 [TELEGRAM] 2. Aşama RETEST Alarmı İletiliyor: {coin.get('symbol')} ({strat_type})")
                success = send_retest_alert(coin, strategy_type=strat_type)
                if success:
                    record["retest_sent"] = True
                    record["retest_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    record["last_updated"] = now
                    self.history[setup_id] = record
                    updated = True

        # B. 3. Aşama: Onaylananlar (Kesin Giriş Sinyali)
        for coin in stages.get("confirmed", []):
            setup_id = self._get_setup_identifier(coin, strat_type, tf)
            record = self.history.get(setup_id, {
                "retest_sent": False,
                "confirmed_sent": False,
                "created_at": now,
                "last_updated": now
            })

            # Bu kurulum için Onaylandı alarmı daha önce ATILMADIYSA gönder
            if not record.get("confirmed_sent", False):
                print(f"🔥 [TELEGRAM] 3. Aşama KESİN GİRİŞ Alarmı İletiliyor: {coin.get('symbol')} ({strat_type})")
                success = send_confirmed_alert(coin, strategy_type=strat_type)
                if success:
                    record["confirmed_sent"] = True
                    record["confirmed_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    record["last_updated"] = now
                    self.history[setup_id] = record
                    updated = True

        if updated:
            self._save_history()

telegram_alert_service = StrategyAlertService()
