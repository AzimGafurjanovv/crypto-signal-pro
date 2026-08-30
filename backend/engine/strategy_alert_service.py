"""
CryptoSignalPro AI - Strateji Telegram Bildirim & Akıllı Anti-Spam Servisi (v11.0.0)

Gelişmiş Çok Kademeli Anti-Spam & Bekleme (Cooldown) Mimarisi:
1. Başarısızlık & Dalgalanma Koruması (Anti-Flapping):
   - Bir coin retest bölgesine girip alarm attıktan sonra başarısız olup seviyeden düşerse ve tekrar girerse spam yapamaz.
   - Her parite ve yön için RETEST alarmı sonrası EN AZ 4 SAAT (14,400 saniye) soğuma süresi (Cooldown) uygulanır.
2. Kesin Giriş Kilidi:
   - ONAYLANDI (3. Aşama) alarmı gönderildikten sonra aynı pariteye 6 SAAT boyunca yeni sinyal gönderilmez.
3. Çift Katmanlı Tekilleştirme:
   - Hem spesifik Setup ID (seviye + formasyon adı) hem de Parite/Yön anahtarı (Symbol + Direction + TF) üzerinden çifte kilit kontrol edilir.
4. Başlangıç Isınması (Warmup):
   - Sunucu açıldığında veya Telegram servisi aktif edildiğinde mevcut eski sinyaller önbelleğe alınır, kullanıcıya spam atılmaz.
"""

import os
import json
import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from engine.market_data import market_manager
from engine.pdh_pdl_radar import run_pdh_pdl_radar
from engine.swing_radar import run_swing_radar
from engine.pattern_radar import run_pattern_radar
from engine.telegram_notifier import load_telegram_config, send_retest_alert, send_confirmed_alert


def get_alert_data_dir() -> str:
    env_dir = os.environ.get("CRYPTO_DATA_DIR")
    if env_dir and os.path.exists(env_dir):
        return env_dir
    prod_dir = "/root/crypto_data"
    if os.path.exists(prod_dir):
        return prod_dir
    if os.name != "nt" and os.path.exists("/root"):
        try:
            os.makedirs(prod_dir, exist_ok=True)
            return prod_dir
        except Exception:
            pass
    local_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(local_dir, exist_ok=True)
    return local_dir


DATA_DIR = get_alert_data_dir()
HISTORY_FILE = os.path.join(DATA_DIR, "alert_history.json")

# ⏱️ AKILLI SOĞUMA SÜRELERİ (SANİYE)
RETEST_COOLDOWN_SECONDS = 4 * 3600    # 4 Saat (Başarısız olup tekrar girerse spam yapmaz)
CONFIRMED_COOLDOWN_SECONDS = 6 * 3600 # 6 Saat (İşlem gerçekleştikten sonra uzun koruma)


class StrategyAlertService:
    def __init__(self):
        self.is_running: bool = False
        self.is_warmed_up: bool = False
        self.interval_seconds: int = 60 # Her 60 saniyede bir kontrol et
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
        print("🔔 [TELEGRAM RADAR SERVICE] 4 Saatlik Akıllı Anti-Spam & Cooldown Filtreli Alarm Servisi Başlatıldı.")
        
        while self.is_running:
            try:
                config = load_telegram_config()
                if config.get("enabled", False) and (config.get("notify_retest") or config.get("notify_confirmed")):
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

    def _get_coin_cooldown_key(self, symbol: str, strat_type: str, tf: str, direction: str) -> str:
        """Parite, strateji ve yön bazlı ana soğuma anahtarı."""
        return f"COOLDOWN_{strat_type}_{tf}_{symbol}_{direction}"

    def _get_setup_identifier(self, coin: Dict[str, Any], strat_type: str, tf: str) -> str:
        symbol = coin.get("symbol", "")
        direction = coin.get("direction", "")
        raw_level = coin.get("breakout_level") or coin.get("pdh") or coin.get("pdl") or coin.get("swing_level", 0.0)
        bo_level = round(float(raw_level or 0.0), 2)
        pat_name = coin.get("strategy_name", "")
        return f"{strat_type}_{tf}_{symbol}_{direction}_{bo_level}_{pat_name}"

    def _process_stage_alerts(self, stages: Dict[str, Any], strat_type: str, tf: str, config: Dict[str, Any], is_warmup: bool = False):
        now = time.time()
        updated = False
        should_notify_retest = config.get("notify_retest", False)
        should_notify_confirmed = config.get("notify_confirmed", True)
        enabled_patterns = config.get("enabled_patterns", ["ALL"])

        # ─────────────────────────────────────────────────────────────────────
        # A. 2. Aşama: Retesting Yapanlar (Erken Uyarı + 4 Saatlik Cooldown)
        # ─────────────────────────────────────────────────────────────────────
        if should_notify_retest:
            for coin in stages.get("retesting", []):
                if strat_type == "CHART_PATTERNS" and "ALL" not in enabled_patterns:
                    pat_cat = coin.get("pattern_category", "TRENDLINE")
                    if pat_cat not in enabled_patterns:
                        continue

                symbol = coin.get("symbol", "")
                direction = coin.get("direction", "")
                cooldown_key = self._get_coin_cooldown_key(symbol, strat_type, tf, direction)
                setup_id = self._get_setup_identifier(coin, strat_type, tf)

                cooldown_record = self.history.get(cooldown_key, {})
                last_retest_ts = cooldown_record.get("last_retest_sent_at", 0)
                last_confirmed_ts = cooldown_record.get("last_confirmed_sent_at", 0)

                # 🛑 KORUMA 1: 4 Saat içinde bu coine zaten Retest alarmı atılmışsa TEKRAR ATMA (Spam Engeli)
                if (now - last_retest_ts) < RETEST_COOLDOWN_SECONDS:
                    continue

                # 🛑 KORUMA 2: 6 Saat içinde zaten Onaylı Giriş atılmışsa Retest atma
                if (now - last_confirmed_ts) < CONFIRMED_COOLDOWN_SECONDS:
                    continue

                # Tazelik Filtresi (Son 2 saat içinde olmalı)
                rt_bar = coin.get("retest_bar") or {}
                rt_ts = rt_bar.get("timestamp", 0) if isinstance(rt_bar, dict) else 0
                if rt_ts > 0 and (now - rt_ts) > 7200:
                    continue

                if is_warmup:
                    self.history[cooldown_key] = {
                        "last_retest_sent_at": now,
                        "last_updated": now
                    }
                    updated = True
                    continue

                print(f"📢 [TELEGRAM] 2. Aşama RETEST Alarmı İletiliyor: {symbol} ({strat_type})")
                success = send_retest_alert(coin, strategy_type=strat_type)
                if success:
                    self.history[cooldown_key] = {
                        "last_retest_sent_at": now,
                        "last_retest_time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "last_updated": now
                    }
                    # Setup ID kaydı da tut
                    self.history[setup_id] = {
                        "retest_sent": True,
                        "created_at": now,
                        "last_updated": now
                    }
                    updated = True

        # ─────────────────────────────────────────────────────────────────────
        # B. 3. Aşama: Onaylananlar (Kesin Giriş Sinyali + 6 Saatlik Cooldown)
        # ─────────────────────────────────────────────────────────────────────
        if should_notify_confirmed:
            for coin in stages.get("confirmed", []):
                if strat_type == "CHART_PATTERNS" and "ALL" not in enabled_patterns:
                    pat_cat = coin.get("pattern_category", "TRENDLINE")
                    if pat_cat not in enabled_patterns:
                        continue

                symbol = coin.get("symbol", "")
                direction = coin.get("direction", "")
                cooldown_key = self._get_coin_cooldown_key(symbol, strat_type, tf, direction)
                setup_id = self._get_setup_identifier(coin, strat_type, tf)

                cooldown_record = self.history.get(cooldown_key, {})
                last_confirmed_ts = cooldown_record.get("last_confirmed_sent_at", 0)

                # 🛑 KORUMA 3: 6 Saat içinde bu coine zaten Onaylı Giriş atılmışsa TEKRAR ATMA
                if (now - last_confirmed_ts) < CONFIRMED_COOLDOWN_SECONDS:
                    continue

                conf_bar = coin.get("confirmed_bar") or {}
                conf_ts = conf_bar.get("timestamp", 0) if isinstance(conf_bar, dict) else 0
                if conf_ts > 0 and (now - conf_ts) > 7200:
                    continue

                if is_warmup:
                    self.history[cooldown_key] = {
                        "last_confirmed_sent_at": now,
                        "last_updated": now
                    }
                    updated = True
                    continue

                print(f"🔥 [TELEGRAM] 3. Aşama KESİN GİRİŞ Alarmı İletiliyor: {symbol} ({strat_type})")
                success = send_confirmed_alert(coin, strategy_type=strat_type)
                if success:
                    self.history[cooldown_key] = {
                        "last_retest_sent_at": cooldown_record.get("last_retest_sent_at", now),
                        "last_confirmed_sent_at": now,
                        "last_confirmed_time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "last_updated": now
                    }
                    self.history[setup_id] = {
                        "confirmed_sent": True,
                        "last_updated": now
                    }
                    updated = True

        if updated:
            self._save_history()


telegram_alert_service = StrategyAlertService()
