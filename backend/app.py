import os
import sys
import json
import math
import time
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
import numpy as np
import pandas as pd
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from engine.market_data import market_manager
from engine.setup_calculator import calculate_crypto_setup
from engine.ai_prompt_generator import generate_ai_prompt
from engine.raw_data_formatter import format_raw_market_data
from engine.mtf_analysis import analyze_all_timeframes
from engine.patterns import detect_chart_patterns
from engine.smc import analyze_smc
from engine.indicators import enrich_all_indicators
from engine.backtest_engine import run_strategy_backtest
from engine.pdh_pdl_radar import run_pdh_pdl_radar
from engine.swing_radar import run_swing_radar
from engine.pattern_radar import run_pattern_radar
from engine.telegram_notifier import load_telegram_config, save_telegram_config, send_telegram_raw_message, send_trade_note_alert
from engine.trade_journal_service import trade_journal_manager, trade_notes_manager
from engine.strategy_alert_service import telegram_alert_service
from engine.gemini_engine import analyze_with_gemini, get_active_gemini_key, chat_with_gemini, discover_available_gemini_models

# -------------------------------------------------------------
# 🔄 ARKA PLAN SUNUCU OTOMATİK TARAMA & AKILLI ÖNBELLEK SERVİSİ
# -------------------------------------------------------------
class ServerBackgroundScanner:
    def __init__(self):
        self.cached_setups: List[Dict[str, Any]] = []
        self.last_scan_time: Optional[str] = None
        self.last_scan_timestamp: float = 0.0
        self.interval_minutes: int = 5 # Varsayılan: 5 dakika
        self.is_scanning: bool = False
        self.total_scanned: int = 0
        self.stats: Dict[str, Any] = {
            "long_count": 0,
            "short_count": 0,
            "avg_rr": 0.0,
            "top_score": 0
        }
        self._task: Optional[asyncio.Task] = None

    def execute_scan(self, limit_coins: int = 50, timeframe: str = "1h") -> List[Dict[str, Any]]:
        """Sunucu hafızasındaki önbelleği tazeleyen çekirdek tarama motoru."""
        self.is_scanning = True
        try:
            pairs = market_manager.get_top_pairs(limit=limit_coins)
            raw_results = []

            with ThreadPoolExecutor(max_workers=15) as executor:
                futures = {
                    executor.submit(
                        scan_single_pair,
                        symbol,
                        timeframe,
                        "ALL",
                        "ALL",
                        False,
                        1,
                        1.0,
                        30
                    ): symbol for symbol in pairs
                }
                for future in as_completed(futures):
                    res = future.result()
                    if res:
                        raw_results.append(res)

            # Güven skoruna göre sırala
            raw_results.sort(key=lambda x: (x['confidence_score'] * 1.5 + x['rr_ratio'] * 10), reverse=True)

            # MTF Zenginleştirmesi
            with ThreadPoolExecutor(max_workers=8) as mtf_executor:
                mtf_futures = {mtf_executor.submit(analyze_all_timeframes, s['symbol']): s for s in raw_results}
                for future in as_completed(mtf_futures):
                    s = mtf_futures[future]
                    try:
                        mtf_res = future.result()
                        s['mtf'] = mtf_res
                        s['ai_prompt'] = generate_ai_prompt(s)
                    except Exception:
                        s['ai_prompt'] = generate_ai_prompt(s)

            self.cached_setups = raw_results
            self.total_scanned = len(raw_results)
            self.last_scan_timestamp = time.time()
            self.last_scan_time = datetime.now().strftime("%H:%M:%S")

            long_count = sum(1 for s in raw_results if s['direction'] == 'LONG')
            short_count = sum(1 for s in raw_results if s['direction'] == 'SHORT')
            avg_rr = round(sum(s['rr_ratio'] for s in raw_results) / len(raw_results), 2) if raw_results else 0.0
            top_score = max([s['confidence_score'] for s in raw_results], default=0)

            self.stats = {
                "long_count": long_count,
                "short_count": short_count,
                "avg_rr": avg_rr,
                "top_score": top_score
            }
            return raw_results
        finally:
            self.is_scanning = False

    async def background_loop(self):
        """Kullanıcının belirlediği dakika aralığında arka planda sessizce çalışan dinamik işçi."""
        # İlk açılışta hemen bir kez tarama yap
        await asyncio.to_thread(self.execute_scan, 50, "1h")
        
        while True:
            try:
                if self.interval_minutes > 0 and not self.is_scanning:
                    now = time.time()
                    elapsed = now - self.last_scan_timestamp
                    if elapsed >= (self.interval_minutes * 60):
                        await asyncio.to_thread(self.execute_scan, 50, "1h")
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[BackgroundScanner Error]: {e}")
                await asyncio.sleep(5)
                print(f"[BackgroundScanner Error]: {e}")
                await asyncio.sleep(30)

bg_scanner = ServerBackgroundScanner()

async def trade_notes_monitoring_loop():
    """Arka planda her 30 saniyede bir kullanıcının özel trade notları ve fiyat alarmlarını kontrol eder."""
    while True:
        try:
            triggered = await asyncio.to_thread(trade_notes_manager.check_and_trigger_alerts)
            for item in triggered:
                note = item.get("note", {})
                curr_p = item.get("current_price", 0.0)
                if note.get("telegram_notify", True):
                    print(f"📢 [TRADE NOTE ALARM] {note.get('symbol')} hedefine (${note.get('target_price')}) ulaştı! Telegram gönderiliyor...")
                    try:
                        send_trade_note_alert(note, curr_p)
                    except Exception as te:
                        print(f"⚠️ Telegram trade note alert error: {te}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"⚠️ Trade note monitor loop error: {e}")
        await asyncio.sleep(30)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sunucu başlatıldığında arka plan işçilerini başlat
    scan_task = asyncio.create_task(bg_scanner.background_loop())
    telegram_task = asyncio.create_task(telegram_alert_service.start_loop())
    notes_task = asyncio.create_task(trade_notes_monitoring_loop())
    yield
    # Sunucu kapatılırken iptal et
    scan_task.cancel()
    telegram_task.cancel()
    notes_task.cancel()
    try:
        await scan_task
    except asyncio.CancelledError:
        pass
    try:
        await telegram_task
    except asyncio.CancelledError:
        pass
    try:
        await notes_task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="CryptoSignalPro AI API", version="5.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(os.path.dirname(current_dir), "frontend")

if os.path.exists(os.path.join(frontend_dir, "css")):
    app.mount("/static/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
if os.path.exists(os.path.join(frontend_dir, "js")):
    app.mount("/static/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")

class ScanRequest(BaseModel):
    timeframe: str = "1h"
    raw_candle_limit: int = 30
    limit_coins: int = 10 # İlk açılışta 10, kullanıcı isterse 50'ye kadar artırabilir (Max 50)
    direction: str = "ALL" # ALL, LONG, SHORT
    strategy: str = "ALL"
    enable_min_confidence: bool = False # Kullanıcı min güvenlik filtresini açıp kapatabilir
    min_confidence: int = 1
    min_rr: float = 1.0
    sort_by: str = "CONF_DESC" # CONF_DESC, CONF_ASC, RR_DESC, CHANGE_DESC, CHANGE_ASC, SYMBOL_ASC
    search_symbol: Optional[str] = None # Özel coin araması (örn: TRX, SOL)

class AutoScanConfigRequest(BaseModel):
    interval_minutes: int = 5 # 0 = Manuel, 1, 3, 5, 10, 15

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/backtest")
@app.get("/backtest.html")
async def serve_backtest():
    return FileResponse(os.path.join(frontend_dir, "backtest.html"))

@app.get("/my-strategy")
@app.get("/my_strategy.html")
@app.get("/pdh-pdl-radar")
async def serve_my_strategy():
    return FileResponse(os.path.join(frontend_dir, "my_strategy.html"))

@app.get("/api/pdh-pdl-radar")
async def get_pdh_pdl_radar(timeframe: str = Query("1h"), limit_coins: int = Query(50)):
    """Kullanıcının 1. Özel Stratejisi (PDH / PDL Günlük Likidite Breakout-Retest) canlı taraması."""
    report = await asyncio.to_thread(run_pdh_pdl_radar, timeframe=timeframe, limit_coins=limit_coins)
    return sanitize_json(report)

@app.get("/api/swing-radar")
async def get_swing_radar(timeframe: str = Query("1h"), limit_coins: int = Query(50), swing_lookback: int = Query(3)):
    """Kullanıcının 2. Özel Stratejisi (Yapısal Swing High/Low Breakout-Retest) canlı taraması."""
    report = await asyncio.to_thread(run_swing_radar, timeframe=timeframe, limit_coins=limit_coins, swing_lookback=swing_lookback)
    return sanitize_json(report)

@app.get("/api/pattern-radar")
async def get_pattern_radar(timeframe: str = Query("1h"), limit_coins: int = Query(50)):
    """Kullanıcının 3. Özel Stratejisi (Klasik ve Modern Formasyon Radarı - Trendline, Üçgen, S/R Flip, İkili Dip)."""
    report = await asyncio.to_thread(run_pattern_radar, timeframe=timeframe, limit_coins=limit_coins)
    return sanitize_json(report)

@app.get("/api/pairs")
async def get_pairs():
    pairs = market_manager.get_top_pairs(limit=50)
    return {"status": "success", "count": len(pairs), "pairs": pairs}

def scan_single_pair(symbol: str, timeframe: str, direction: str, strategy: str, enable_min_conf: bool, min_confidence: int, min_rr: float, raw_candle_limit: int = 30) -> Optional[Dict[str, Any]]:
    try:
        df = market_manager.get_market_data(symbol, timeframe=timeframe, limit=max(300, raw_candle_limit + 50))
        if df is None or len(df) < 50:
            return None
            
        effective_min_conf = min_confidence if enable_min_conf else 1
        setup = calculate_crypto_setup(symbol, df, timeframe=timeframe, min_confidence=effective_min_conf)
        if not setup:
            setup = build_raw_setup_fallback(symbol, df, timeframe=timeframe)
            
        if direction != "ALL" and setup['direction'] != direction:
            return None
            
        if enable_min_conf and setup['confidence_score'] < min_confidence:
            return None
            
        if setup['rr_ratio'] < min_rr:
            return None
            
        if strategy != "ALL":
            strat_lower = strategy.lower()
            all_strats = [s.lower() for s in setup['strategies'] + setup.get('patterns', [])]
            if setup.get('primary_strategy'):
                all_strats.append(setup['primary_strategy'].lower())
                
            matched = any(strat_lower in s for s in all_strats)
            if not matched:
                return None
                
        setup['raw_market_data'] = format_raw_market_data(setup, df, candle_limit=raw_candle_limit)
        return setup
    except Exception:
        return None

# -------------------------------------------------------------
# ⚡ 0ms SIFIR GECİKMELİ ÖNBELLEK ENDPOINT'LERİ
# -------------------------------------------------------------
@app.get("/api/latest-setups")
async def get_latest_cached_setups():
    """Sayfa açıldığında veya yenilendiğinde hiç beklemeden önbellekteki taze verileri anında döner."""
    if not bg_scanner.cached_setups and not bg_scanner.is_scanning:
        # Önbellek henüz boşsa ilk taramayı çalıştır
        await asyncio.to_thread(bg_scanner.execute_scan, 50, "1h")

    now = time.time()
    next_seconds = 0
    if bg_scanner.interval_minutes > 0 and bg_scanner.last_scan_timestamp > 0:
        elapsed = now - bg_scanner.last_scan_timestamp
        target = bg_scanner.interval_minutes * 60
        next_seconds = max(0, int(target - elapsed))

    return sanitize_json({
        "status": "success",
        "setups": bg_scanner.cached_setups,
        "total_scanned": bg_scanner.total_scanned,
        "last_scan_time": bg_scanner.last_scan_time or datetime.now().strftime("%H:%M:%S"),
        "interval_minutes": bg_scanner.interval_minutes,
        "next_scan_seconds": next_seconds,
        "is_scanning": bg_scanner.is_scanning,
        "stats": bg_scanner.stats
    })

@app.post("/api/auto-scan-config")
async def set_auto_scan_config(req: AutoScanConfigRequest):
    """Kullanıcının belirlediği otomatik güncelleme aralığını (dakika) ayarlar."""
    bg_scanner.interval_minutes = max(0, min(60, req.interval_minutes))
    bg_scanner.last_scan_timestamp = time.time()
    return {
        "status": "success",
        "interval_minutes": bg_scanner.interval_minutes,
        "message": f"Otomatik güncelleme aralığı {bg_scanner.interval_minutes} dakika olarak ayarlandı." if bg_scanner.interval_minutes > 0 else "Otomatik güncelleme kapatıldı (Manuel mod)."
    }

@app.post("/api/scan")
async def scan_market(req: ScanRequest):
    """Kullanıcı 'TÜM COİNLERİ TARA' butonuna bastığında zorlamalı taze tarama yapar ve önbelleği günceller."""
    if bg_scanner.is_scanning:
        return sanitize_json({
            "status": "success",
            "total_scanned": bg_scanner.total_scanned,
            "found_count": len(bg_scanner.cached_setups),
            "last_scan_time": bg_scanner.last_scan_time or datetime.now().strftime("%H:%M:%S"),
            "stats": bg_scanner.stats,
            "setups": bg_scanner.cached_setups,
            "message": "Arka planda tarama devam ediyor, önbellekteki son sonuçlar getirildi."
        })

    scan_limit = min(50, max(5, req.limit_coins))
    pairs = market_manager.get_top_pairs(limit=scan_limit)
    
    if req.search_symbol:
        clean_search = req.search_symbol.upper().strip()
        if not clean_search.endswith("/USDT") and not clean_search.endswith("USDT"):
            clean_search = f"{clean_search}/USDT"
        elif clean_search.endswith("USDT") and not clean_search.endswith("/USDT"):
            clean_search = f"{clean_search[:-4]}/USDT"
        if clean_search not in pairs:
            pairs.insert(0, clean_search)

    raw_results = []
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {
            executor.submit(
                scan_single_pair,
                symbol,
                req.timeframe,
                req.direction,
                req.strategy,
                req.enable_min_confidence,
                req.min_confidence,
                req.min_rr,
                req.raw_candle_limit
            ): symbol for symbol in pairs
        }
        
        for future in as_completed(futures):
            res = future.result()
            if res:
                raw_results.append(res)
            
    # Sıralama Mantığı
    if req.sort_by == "CONF_ASC":
        raw_results.sort(key=lambda x: x['confidence_score'])
    elif req.sort_by == "RR_DESC":
        raw_results.sort(key=lambda x: x['rr_ratio'], reverse=True)
    elif req.sort_by == "CHANGE_DESC":
        raw_results.sort(key=lambda x: x.get('indicators', {}).get('price_change_24h', 0.0), reverse=True)
    elif req.sort_by == "CHANGE_ASC":
        raw_results.sort(key=lambda x: x.get('indicators', {}).get('price_change_24h', 0.0))
    elif req.sort_by == "SYMBOL_ASC":
        raw_results.sort(key=lambda x: x['symbol'])
    else: # CONF_DESC
        raw_results.sort(key=lambda x: (x['confidence_score'] * 1.5 + x['rr_ratio'] * 10), reverse=True)
    
    if req.search_symbol:
        clean_search = req.search_symbol.upper().strip().replace("/USDT", "")
        raw_results.sort(key=lambda x: 0 if clean_search in x['symbol'] else 1)
        
    final_setups = raw_results[:req.limit_coins] if not req.search_symbol else raw_results[:max(req.limit_coins, 40)]
    
    with ThreadPoolExecutor(max_workers=8) as mtf_executor:
        mtf_futures = {mtf_executor.submit(analyze_all_timeframes, s['symbol']): s for s in final_setups}
        for future in as_completed(mtf_futures):
            s = mtf_futures[future]
            try:
                mtf_res = future.result()
                s['mtf'] = mtf_res
                s['ai_prompt'] = generate_ai_prompt(s)
            except Exception:
                s['ai_prompt'] = generate_ai_prompt(s)
    
    # Sunucu önbelleğini de güncelle
    if len(final_setups) > 0 and not req.search_symbol:
        bg_scanner.cached_setups = final_setups
        bg_scanner.total_scanned = len(final_setups)
        bg_scanner.last_scan_timestamp = time.time()
        bg_scanner.last_scan_time = datetime.now().strftime("%H:%M:%S")

    long_count = sum(1 for s in final_setups if s['direction'] == 'LONG')
    short_count = sum(1 for s in final_setups if s['direction'] == 'SHORT')
    avg_rr = round(sum(s['rr_ratio'] for s in final_setups) / len(final_setups), 2) if final_setups else 0.0
    avg_conf = round(sum(s['confidence_score'] for s in final_setups) / len(final_setups), 1) if final_setups else 0.0
    
    return sanitize_json({
        "status": "success",
        "total_scanned": len(pairs),
        "found_count": len(final_setups),
        "last_scan_time": bg_scanner.last_scan_time or datetime.now().strftime("%H:%M:%S"),
        "stats": {
            "long_count": long_count,
            "short_count": short_count,
            "avg_rr": avg_rr,
            "avg_confidence": avg_conf,
            "top_score": max([s['confidence_score'] for s in final_setups], default=0)
        },
        "setups": final_setups
    })

def build_raw_setup_fallback(symbol: str, df: pd.DataFrame, timeframe: str = "1h") -> Dict[str, Any]:
    """Herhangi bir formasyon oluşmasa dahi ham piyasa verilerini ve EMA/RSI indikatörlerini eksiksiz oluşturan yedek motor."""
    df_enriched = enrich_all_indicators(df)
    last_row = df_enriched.iloc[-1]
    prev_row = df_enriched.iloc[-2] if len(df_enriched) > 1 else last_row
    
    current_price = float(last_row['close'])
    atr = float(last_row.get('atr', current_price * 0.02))
    rsi = float(last_row.get('rsi', 50.0))
    ema20 = float(last_row.get('ema20', current_price))
    ema50 = float(last_row.get('ema50', current_price))
    ema200 = float(last_row.get('ema200', current_price))
    supertrend = str(last_row.get('supertrend', 'NEUTRAL'))
    
    # Yön Belirleme
    is_bullish = current_price >= ema50 and rsi >= 48
    direction = "LONG" if is_bullish else "SHORT"
    direction_label = "🟢 NÖTR / BOĞA EĞİLİMİ (LONG)" if is_bullish else "🔴 NÖTR / AYI EĞİLİMİ (SHORT)"
    
    # R:R ve Seviyeler
    risk_dist = max(atr * 1.5, current_price * 0.015)
    stop_loss = round(current_price - risk_dist, 4) if is_bullish else round(current_price + risk_dist, 4)
    tp1 = round(current_price + risk_dist * 1.5, 4) if is_bullish else round(current_price - risk_dist * 1.5, 4)
    tp2 = round(current_price + risk_dist * 2.5, 4) if is_bullish else round(current_price - risk_dist * 2.5, 4)
    tp3 = round(current_price + risk_dist * 4.0, 4) if is_bullish else round(current_price - risk_dist * 4.0, 4)
    
    risk_pct = round(abs(current_price - stop_loss) / current_price * 100, 2)
    tp1_pct = round(abs(tp1 - current_price) / current_price * 100, 2)
    tp2_pct = round(abs(tp2 - current_price) / current_price * 100, 2)
    tp3_pct = round(abs(tp3 - current_price) / current_price * 100, 2)
    
    # 15 mumluk saf OHLCV tablosu oluştur
    raw_rows = []
    tail_df = df.tail(15)
    for _, row in tail_df.iterrows():
        ts = int(row['timestamp']) if 'timestamp' in row else 0
        if ts > 1e12: ts = ts // 1000
        date_str = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M") if ts > 0 else "N/A"
        o, h, l, c, v = float(row['open']), float(row['high']), float(row['low']), float(row['close']), float(row['volume'])
        raw_rows.append(f"{date_str} | Açılış:${o:,.4f} | Yüksek:${h:,.4f} | Düşük:${l:,.4f} | Kapanış:${c:,.4f} | Hacim:{v:,.0f}")
    raw_candles_table = "\n".join(raw_rows)

    # Ham veriler (vol_ratio ve p_change_24h hesaplama)
    vol_ratio = float(last_row.get('volume_ratio', 1.0))
    price_24h_ago = float(df_enriched['close'].iloc[-24]) if len(df_enriched) >= 24 else float(df_enriched['close'].iloc[0])
    p_change_24h = round(((current_price - price_24h_ago) / price_24h_ago) * 100.0, 2) if price_24h_ago else 0.0

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "raw_candles_table": raw_candles_table,
        "direction": direction,
        "direction_label": direction_label,
        "confidence_score": 50,
        "score_grade": "⚪ STANDART PİYASA VERİSİ",
        "rr_ratio": 2.5,
        "current_price": current_price,
        "entry_price": current_price,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "risk_percent": risk_pct,
        "reward_tp1_percent": tp1_pct,
        "reward_tp2_percent": tp2_pct,
        "reward_tp3_percent": tp3_pct,
        "primary_strategy": "Canlı Ham Piyasa Verisi (Raw Market Data & Trends)",
        "strategies": ["Canlı Ham Piyasa Verisi (Raw Market Data & Trends)"],
        "patterns": [],
        "reasons": [
            f"Fiyat ${current_price:,.4f} seviyesinde işlem görüyor.",
            f"RSI({rsi:.1f}) ve Supertrend({supertrend}) aktif piyasa dinamiklerini yansıtıyor.",
            f"EMA Seviyeleri: EMA20(${ema20:,.4f}) | EMA50(${ema50:,.4f}) | EMA200(${ema200:,.4f})"
        ],
        "vetos": [],
        "supports": [{"name": "EMA 50 Dinamik Destek", "price": ema50}],
        "resistances": [{"name": "EMA 200 Majör Direnç", "price": ema200}],
        "indicators": {
            "rsi": round(rsi, 1),
            "atr": round(atr, 4),
            "ema20": round(ema20, 4),
            "ema50": round(ema50, 4),
            "ema200": round(ema200, 4),
            "supertrend": supertrend,
            "macd_hist": round(float(last_row.get('macd_hist', 0.0)), 4),
            "volume_ratio": round(vol_ratio, 2),
            "volume_24h_change_pct": round(float(last_row.get('volume_change_pct', 0.0)), 2),
            "volume_24h_usdt": float(last_row.get('volume', 0.0)) * current_price,
            "price_change_24h": p_change_24h
        }
    }

@app.get("/api/chart-data/{symbol:path}")
async def get_chart_data(symbol: str, timeframe: str = Query("1h")):
    clean_sym = symbol.upper().strip()
    if not clean_sym.endswith("/USDT") and not clean_sym.endswith("USDT"):
        clean_sym = f"{clean_sym}/USDT"
    elif clean_sym.endswith("USDT") and not clean_sym.endswith("/USDT"):
        clean_sym = f"{clean_sym[:-4]}/USDT"

    df = market_manager.get_market_data(clean_sym, timeframe=timeframe, limit=300)
    if df is None or len(df) == 0:
        raise HTTPException(status_code=404, detail="Chart data not found")

    df_enriched = enrich_all_indicators(df)
    candles = []
    for _, row in df_enriched.iterrows():
        ts = int(row['timestamp']) if 'timestamp' in row else 0
        if ts > 1e12: ts = ts // 1000
        candles.append({
            "time": ts,
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "volume": float(row['volume']),
            "ema20": float(row['ema20']) if 'ema20' in row and not math.isnan(row['ema20']) else None,
            "ema50": float(row['ema50']) if 'ema50' in row and not math.isnan(row['ema50']) else None,
            "ema200": float(row['ema200']) if 'ema200' in row and not math.isnan(row['ema200']) else None,
            "rsi": float(row['rsi']) if 'rsi' in row and not math.isnan(row['rsi']) else None,
        })

    setup = calculate_crypto_setup(clean_sym, df_enriched, timeframe=timeframe, min_confidence=1)
    if not setup:
        setup = build_raw_setup_fallback(clean_sym, df_enriched, timeframe=timeframe)

    setup['raw_market_data'] = format_raw_market_data(setup, df_enriched, candle_limit=30)
    setup['ai_prompt'] = generate_ai_prompt(setup, df_enriched)

    mtf_summary = analyze_all_timeframes(clean_sym)
    setup['mtf'] = mtf_summary

    detected_patterns = detect_chart_patterns(df_enriched)

    return sanitize_json({
        "status": "success",
        "symbol": clean_sym,
        "timeframe": timeframe,
        "candles": candles,
        "setup": setup,
        "patterns": detected_patterns,
        "mtf": mtf_summary
    })

@app.get("/api/raw-data/{symbol:path}")
async def get_raw_data(symbol: str, timeframe: str = Query("1h"), limit: int = Query(30)):
    clean_sym = symbol.upper().strip()
    if not clean_sym.endswith("/USDT") and not clean_sym.endswith("USDT"):
        clean_sym = f"{clean_sym}/USDT"
    elif clean_sym.endswith("USDT") and not clean_sym.endswith("/USDT"):
        clean_sym = f"{clean_sym[:-4]}/USDT"

    candle_limit = max(5, min(100, limit))
    df = market_manager.get_market_data(clean_sym, timeframe=timeframe, limit=max(300, candle_limit + 50))
    if df is None or len(df) == 0:
        raise HTTPException(status_code=404, detail="Raw data not found")

    setup = calculate_crypto_setup(clean_sym, df, timeframe=timeframe, min_confidence=1)
    if not setup:
        setup = build_raw_setup_fallback(clean_sym, df, timeframe=timeframe)

    raw_text = format_raw_market_data(setup, df, candle_limit=candle_limit)
    return {
        "status": "success",
        "symbol": clean_sym,
        "timeframe": timeframe,
        "candle_limit": candle_limit,
        "raw_text": raw_text
    }

@app.get("/api/backtest/{symbol:path}")
async def get_strategy_backtest(symbol: str, timeframe: str = Query("1h"), limit: int = Query(500)):
    clean_sym = symbol.upper().strip()
    if not clean_sym.endswith("/USDT") and not clean_sym.endswith("USDT"):
        clean_sym = f"{clean_sym}/USDT"
    elif clean_sym.endswith("USDT") and not clean_sym.endswith("/USDT"):
        clean_sym = f"{clean_sym[:-4]}/USDT"

    candle_limit = max(100, min(1000, limit))
    df = market_manager.get_market_data(clean_sym, timeframe=timeframe, limit=candle_limit)
    if df is None or len(df) < 60:
        raise HTTPException(status_code=404, detail=f"{clean_sym} için backtest mum verisi bulunamadı.")

    report = run_strategy_backtest(clean_sym, df, timeframe=timeframe, lookback=candle_limit)
    return sanitize_json(report)

class AIAnalyzeRequest(BaseModel):
    timeframe: str = "1h"
    api_key: Optional[str] = None

@app.get("/api/ai-config")
async def get_ai_config():
    active_key = get_active_gemini_key()
    return {
        "configured": bool(active_key),
        "key_preview": f"{active_key[:6]}...{active_key[-4:]}" if active_key and len(active_key) > 10 else None
    }

@app.post("/api/ai-analyze/{symbol:path}")
async def run_ai_analysis(symbol: str, req: AIAnalyzeRequest):
    clean_sym = symbol.upper().strip()
    if not clean_sym.endswith("/USDT") and not clean_sym.endswith("USDT"):
        clean_sym = f"{clean_sym}/USDT"
    elif clean_sym.endswith("USDT") and not clean_sym.endswith("/USDT"):
        clean_sym = f"{clean_sym[:-4]}/USDT"

    df = market_manager.get_market_data(clean_sym, timeframe=req.timeframe, limit=200)
    if df is None or len(df) < 50:
        raise HTTPException(status_code=404, detail=f"{clean_sym} için mum verisi bulunamadı.")

    setup = calculate_crypto_setup(clean_sym, df, timeframe=req.timeframe, min_confidence=1)
    if not setup:
        setup = build_raw_setup_fallback(clean_sym, df, timeframe=req.timeframe)

    result = await asyncio.to_thread(analyze_with_gemini, clean_sym, setup, df, user_api_key=req.api_key)
    return sanitize_json(result)

class AIChatRequest(BaseModel):
    symbol: Optional[str] = None
    message: str
    history: Optional[List[Dict[str, str]]] = []
    model_name: Optional[str] = "gemini-2.0-flash"
    api_key: Optional[str] = None

@app.get("/api/ai-models")
async def get_ai_models(api_key: Optional[str] = None):
    key = get_active_gemini_key(api_key)
    if not key:
        return {
            "status": "success",
            "models": [
                {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash (En Hızlı & En Yeni)", "badge": "⚡ Hızlı"},
                {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash (Dengeli & Kararlı)", "badge": "🌟 Önerilen"},
                {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro (Derin Akıl Yürütme)", "badge": "🧠 Zeki"}
            ]
        }
    discovered = discover_available_gemini_models(key)
    model_items = []
    seen = set()
    for item in discovered:
        m_name = item.split(":", 1)[1] if ":" in item else item
        if m_name not in seen:
            seen.add(m_name)
            badge = "⚡ Flash" if "flash" in m_name.lower() else ("🧠 Pro" if "pro" in m_name.lower() else "✨ Standart")
            model_items.append({
                "id": m_name,
                "name": f"Gemini {m_name.replace('gemini-', '').replace('-', ' ').title()}",
                "badge": badge
            })
    return {"status": "success", "models": model_items}

@app.post("/api/ai-chat")
async def run_ai_chat(req: AIChatRequest):
    """Kullanıcının düzenlediği prompt ve mesajları seçtiği Gemini modeline ileten çok turlu interaktif chat endpoint'i."""
    result = await asyncio.to_thread(
        chat_with_gemini,
        message=req.message,
        history=req.history,
        preferred_model=req.model_name or "gemini-2.0-flash",
        user_api_key=req.api_key
    )
    return sanitize_json(result)

@app.post("/api/system/update")
@app.post("/api/webhook/github")
async def trigger_system_update():
    """GitHub Webhook veya tek tıkla otomatik sunucu güncelleme ve yeniden başlatma."""
    import subprocess
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    update_script = os.path.join(root_dir, "update.sh")
    
    try:
        if os.path.exists(update_script) and os.name != 'nt':
            subprocess.Popen(["bash", update_script], cwd=root_dir)
            return {"status": "success", "message": "Sunucu güncelleme işlemi arka planda başlatıldı."}
        else:
            # Fallback git pull
            subprocess.Popen(["git", "pull"], cwd=root_dir)
            return {"status": "success", "message": "Git pull arka planda çalıştırıldı."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class TelegramSettingsRequest(BaseModel):
    enabled: bool = True
    bot_token: str
    chat_id: str
    notify_retest: bool = False
    notify_confirmed: bool = True
    timeframes: List[str] = ["1h"]
    strategies: List[str] = ["PDH_PDL", "SWING_HL", "CHART_PATTERNS"]
    enabled_patterns: List[str] = ["ALL"]

@app.get("/api/telegram/settings")
async def get_telegram_settings():
    config = load_telegram_config()
    # Mask bot token for security
    token = config.get("bot_token", "")
    masked_token = f"{token[:8]}...{token[-4:]}" if len(token) > 15 else token
    return {
        "status": "success",
        "config": {
            **config,
            "masked_token": masked_token,
            "has_token": bool(token)
        }
    }

@app.post("/api/telegram/settings")
async def save_telegram_settings_api(req: TelegramSettingsRequest):
    current = load_telegram_config()
    new_token = req.bot_token.strip()
    # If placeholder / masked sent back, preserve original
    if "..." in new_token and current.get("bot_token"):
        new_token = current["bot_token"]
        
    config = {
        "enabled": req.enabled,
        "bot_token": new_token,
        "chat_id": req.chat_id.strip(),
        "notify_retest": req.notify_retest,
        "notify_confirmed": req.notify_confirmed,
        "timeframes": req.timeframes or ["1h"],
        "strategies": req.strategies or ["PDH_PDL", "SWING_HL", "CHART_PATTERNS"],
        "enabled_patterns": req.enabled_patterns or ["ALL"]
    }
    saved = save_telegram_config(config)
    if not saved:
        raise HTTPException(status_code=500, detail="Telegram ayarları kaydedilemedi.")
    return {"status": "success", "message": "Telegram bildirim ayarları başarıyla kaydedildi!"}

@app.post("/api/telegram/test")
async def test_telegram_alert(req: Optional[TelegramSettingsRequest] = None):
    bot_token = req.bot_token.strip() if req and req.bot_token else None
    chat_id = req.chat_id.strip() if req and req.chat_id else None
    
    if not bot_token or not chat_id or "..." in bot_token:
        config = load_telegram_config()
        bot_token = config.get("bot_token")
        chat_id = config.get("chat_id")
        
    if not bot_token or not chat_id:
        return {"status": "error", "message": "Lütfen önce Bot Token ve Chat ID giriniz."}
        
    test_msg = """<b>🚀 CryptoSignalPro AI — Telegram Bildirim Testi Başarılı!</b>

✅ Sunucu bağlantısı kuruldu.
🎯 <b>2. Aşama (Retest Erken Uyarı)</b> ve 
🔥 <b>3. Aşama (Kesin Giriş Sinyali)</b> bildirimleri bu sohbete otomatik olarak iletilecektir.

🌐 <i>Sistem 7/24 piyasayı taramaya devam ediyor.</i>"""

    res = send_telegram_raw_message(bot_token, chat_id, test_msg)
    return res

def sanitize_json(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: sanitize_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_json(v) for v in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return 0.0
        return data
    return data


# -------------------------------------------------------------
# 📖 TRADE GÜNLÜĞÜ (TRADING JOURNAL) & 📝 TRADE NOTLARI MODELLERİ
# -------------------------------------------------------------
class TradeJournalItemRequest(BaseModel):
    symbol: str
    direction: str = "LONG"
    leverage: Optional[int] = 1
    margin: Optional[float] = 0.0
    position_size: Optional[float] = 0.0
    fee: Optional[float] = None
    fee_rate_pct: Optional[float] = 0.05
    entry_price: float
    target_price: Optional[float] = 0.0
    stop_loss: Optional[float] = 0.0
    exit_price: Optional[float] = None
    status: Optional[str] = "OPEN"
    strategy: Optional[str] = "Kişisel Analiz"
    notes: Optional[str] = ""
    entry_date_str: Optional[str] = None
    exit_date_str: Optional[str] = None

class JournalDepositRequest(BaseModel):
    deposit: float
    default_fee_pct: Optional[float] = None

class TradeNoteItemRequest(BaseModel):
    symbol: str
    target_price: float
    created_price: Optional[float] = 0.0
    condition_type: Optional[str] = "CROSS_ABOVE"
    direction_bias: Optional[str] = "NÖTR"
    note_title: Optional[str] = "Özel Hedef Takibi"
    note_text: Optional[str] = ""
    telegram_notify: Optional[bool] = True
    created_at_str: Optional[str] = None

@app.get("/journal")
@app.get("/journal.html")
async def serve_journal():
    return FileResponse(os.path.join(frontend_dir, "journal.html"))

# --- 📖 TRADE GÜNLÜĞÜ (JOURNAL) API ---
@app.get("/api/journal")
async def get_journal_trades(status: Optional[str] = Query("ALL"), symbol: Optional[str] = None):
    trades = trade_journal_manager.get_all_trades(status=status, symbol=symbol)
    return sanitize_json({"status": "success", "trades": trades})

@app.get("/api/journal/stats")
async def get_journal_stats():
    stats = trade_journal_manager.get_stats()
    return sanitize_json({"status": "success", "stats": stats})

@app.post("/api/journal/deposit")
async def set_journal_deposit(req: JournalDepositRequest):
    updated = trade_journal_manager.update_initial_deposit(req.deposit, req.default_fee_pct)
    return sanitize_json({"status": "success", "settings": updated, "message": "Kasa / Başlangıç depozitosu ve varsayılan komisyon güncellendi."})

@app.post("/api/journal")
async def add_journal_trade(req: TradeJournalItemRequest):
    new_trade = trade_journal_manager.add_trade(req.dict())
    return sanitize_json({"status": "success", "trade": new_trade, "message": "İşlem günlüğe kaydedildi."})

@app.put("/api/journal/{trade_id}")
async def update_journal_trade(trade_id: str, updates: Dict[str, Any]):
    updated = trade_journal_manager.update_trade(trade_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="İşlem bulunamadı.")
    return sanitize_json({"status": "success", "trade": updated, "message": "İşlem güncellendi."})

@app.delete("/api/journal/{trade_id}")
async def delete_journal_trade(trade_id: str):
    success = trade_journal_manager.delete_trade(trade_id)
    if not success:
        raise HTTPException(status_code=404, detail="İşlem bulunamadı.")
    return {"status": "success", "message": "İşlem günlükten silindi."}

@app.get("/api/journal/export/csv")
async def export_journal_csv(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    status: Optional[str] = Query("ALL"),
    symbol: Optional[str] = Query(None)
):
    csv_content = trade_journal_manager.generate_trades_csv(
        status=status,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date
    )
    range_tag = f"_{start_date}_to_{end_date}" if start_date or end_date else "_Tumu"
    filename = f"Trade_Gunlugu{range_tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

@app.get("/api/journal/export/json")
async def export_journal_json(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    status: Optional[str] = Query("ALL"),
    symbol: Optional[str] = Query(None)
):
    data = trade_journal_manager.get_full_export_data(
        status=status,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date
    )
    range_tag = f"_{start_date}_to_{end_date}" if start_date or end_date else "_Tumu"
    filename = f"Trade_Gunlugu_Yedek{range_tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    return Response(
        content=json_str,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


# --- 📝 TRADE NOTLARI & ÖZEL FİYAT ALARMI API ---
@app.get("/api/trade-notes")
async def get_trade_notes():
    notes = trade_notes_manager.get_all_notes()
    return sanitize_json({"status": "success", "notes": notes})

@app.post("/api/trade-notes")
async def add_trade_note(req: TradeNoteItemRequest):
    new_note = trade_notes_manager.add_note(req.dict())
    return sanitize_json({"status": "success", "note": new_note, "message": "Özel trade notu ve fiyat alarmı kaydedildi."})

@app.put("/api/trade-notes/{note_id}")
async def update_trade_note(note_id: str, updates: Dict[str, Any]):
    updated = trade_notes_manager.update_note(note_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Not bulunamadı.")
    return sanitize_json({"status": "success", "note": updated, "message": "Not güncellendi."})

@app.post("/api/trade-notes/{note_id}/toggle")
async def toggle_trade_note(note_id: str):
    toggled = trade_notes_manager.toggle_note_active(note_id)
    if not toggled:
        raise HTTPException(status_code=404, detail="Not bulunamadı.")
    return sanitize_json({"status": "success", "note": toggled, "message": "Alarm durumu değiştirildi."})

@app.delete("/api/trade-notes/{note_id}")
async def delete_trade_note(note_id: str):
    success = trade_notes_manager.delete_note(note_id)
    if not success:
        raise HTTPException(status_code=404, detail="Not bulunamadı.")
    return {"status": "success", "message": "Trade notu ve alarmı silindi."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
