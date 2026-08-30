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
        self.is_warmed_up: bool = False
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
        """2 günden eski kayıtları temizler."""
        now = time.time()
        max_age = 86400 * 2
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
        print("🔔 [TELEGRAM RADAR SERVICE] Akıllı Anti-Spam & Tazelik Filtreli Alarm Servisi Başlatıldı.")
        
        while self.is_running:
            try:
                config = load_telegram_config()
                if config.get("enabled", False) and (config.get("notify_retest") or config.get("notify_confirmed")):
                    # Always run warmup first if not yet warmed up
                    if not self.is_warmed_up:
                        print("⏳ [TELEGRAM] Başlangıç ısınması yapılıyor (Eski sinyaller önbelleğe alınıyor)...")
                        try:
                            await self.check_and_notify_radars(config, is_warmup=True)
                            self.is_warmed_up = True
                            print("✅ [TELEGRAM] Başlangıç ısınması tamamlandı. Yalnızca YENİ CANLI sinyaller iletilecektir.")
                        except Exception as e:
                            print(f"⚠️ Isınma hatası: {e}")
                            self.is_warmed_up = True
                    else:
                        await self.check_and_notify_radars(config, is_warmup=False)
            except Exception as e:
                print(f"⚠️ [TELEGRAM RADAR SERVICE] Hata: {e}")
                
            await asyncio.sleep(self.interval_seconds)

    async def check_and_notify_radars(self, config: Dict[str, Any], is_warmup: bool = False):
        timeframes = config.get("timeframes", ["1h"])
        strategies = config.get("strategies", ["PDH_PDL", "SWING_HL", "CHART_PATTERNS"])

        for tf in timeframes:
            # 1. Strateji: PDH / PDL
            if "PDH_PDL" in strategies:
                try:
                    pdh_res = await asyncio.to_thread(run_pdh_pdl_radar, timeframe=tf, limit_coins=30)
                    if pdh_res.get("status") == "success":
                        await asyncio.to_thread(self._process_stage_alerts, pdh_res.get("stages", {}), "PDH_PDL", tf, config, is_warmup)
                except Exception as e:
                    print(f"⚠️ PDH/PDL Radar check error: {e}")

            # 2. Strateji: Swing High / Low
            if "SWING_HL" in strategies:
                try:
                    swing_res = await asyncio.to_thread(run_swing_radar, timeframe=tf, limit_coins=30, swing_lookback=3)
                    if swing_res.get("status") == "success":
                        await asyncio.to_thread(self._process_stage_alerts, swing_res.get("stages", {}), "SWING_HL", tf, config, is_warmup)
                except Exception as e:
                    print(f"⚠️ Swing Radar check error: {e}")

            # 3. Strateji: Formasyon Radarı
            if "CHART_PATTERNS" in strategies:
                try:
                    pat_res = await asyncio.to_thread(run_pattern_radar, timeframe=tf, limit_coins=30)
                    if pat_res.get("status") == "success":
                        await asyncio.to_thread(self._process_stage_alerts, pat_res.get("stages", {}), "CHART_PATTERNS", tf, config, is_warmup)
                except Exception as e:
                    print(f"⚠️ Pattern Radar check error: {e}")

        await asyncio.to_thread(self._cleanup_old_history)

    def _get_setup_identifier(self, coin: Dict[str, Any], strat_type: str, tf: str) -> str:
        symbol = coin.get("symbol", "")
        direction = coin.get("direction", "")
        # Round to 2 decimal places to avoid float precision spam (94.0 vs 94.00001)
        raw_level = coin.get("breakout_level") or coin.get("pdh") or coin.get("pdl") or coin.get("swing_level", 0.0)
        bo_level = round(float(raw_level or 0.0), 2)
        bo_bar = coin.get("breakout_bar") or {}
        bo_time = bo_bar.get("time_str") or bo_bar.get("iso_time") or str(bo_bar.get("timestamp", ""))
        pat_name = coin.get("strategy_name", "")
        return f"{strat_type}_{tf}_{symbol}_{direction}_{bo_level}_{bo_time}_{pat_name}"

    def _process_stage_alerts(self, stages: Dict[str, Any], strat_type: str, tf: str, config: Dict[str, Any], is_warmup: bool = False):
        now = time.time()
        updated = False
        should_notify_retest = config.get("notify_retest", False)
        should_notify_confirmed = config.get("notify_confirmed", True)
        enabled_patterns = config.get("enabled_patterns", ["ALL"]) # Formasyon filtre listesi

        # A. 2. Aşama: Retesting Yapanlar (Erken Uyarı)
        if should_notify_retest:
            for coin in stages.get("retesting", []):
                # Formasyon filtresi kontrolü
                if strat_type == "CHART_PATTERNS" and "ALL" not in enabled_patterns:
                    pat_cat = coin.get("pattern_category", "TRENDLINE")
                    if pat_cat not in enabled_patterns:
                        continue

                # Tazelik Filtresi (Son 2 saat = 7200 sn içinde olmalı)
                rt_bar = coin.get("retest_bar") or {}
                rt_ts = rt_bar.get("timestamp", 0) if isinstance(rt_bar, dict) else 0
                if rt_ts > 0 and (now - rt_ts) > 7200:
                    continue # Eski bar, bildirim atma

                setup_id = self._get_setup_identifier(coin, strat_type, tf)
                record = self.history.get(setup_id, {
                    "retest_sent": False,
                    "confirmed_sent": False,
                    "created_at": now,
                    "last_updated": now
                })

                if is_warmup:
                    record["retest_sent"] = True
                    self.history[setup_id] = record
                    updated = True
                    continue

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
        if should_notify_confirmed:
            for coin in stages.get("confirmed", []):
                # Formasyon filtresi kontrolü
                if strat_type == "CHART_PATTERNS" and "ALL" not in enabled_patterns:
                    pat_cat = coin.get("pattern_category", "TRENDLINE")
                    if pat_cat not in enabled_patterns:
                        continue

                # Tazelik Filtresi (Son 2 saat = 7200 sn içinde olmalı)
                conf_bar = coin.get("confirmed_bar") or {}
                conf_ts = conf_bar.get("timestamp", 0) if isinstance(conf_bar, dict) else 0
                if conf_ts > 0 and (now - conf_ts) > 7200:
                    continue # Eski bar, bildirim atma

                setup_id = self._get_setup_identifier(coin, strat_type, tf)
                record = self.history.get(setup_id, {
                    "retest_sent": False,
                    "confirmed_sent": False,
                    "created_at": now,
                    "last_updated": now
                })

                if is_warmup:
                    record["confirmed_sent"] = True
                    self.history[setup_id] = record
                    updated = True
                    continue

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
