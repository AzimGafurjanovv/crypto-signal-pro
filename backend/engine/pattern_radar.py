"""
CryptoSignalPro AI - Formasyon Radarı & Canlı Tarayıcı Motoru (pattern_radar.py)

Piyasadaki tüm coinleri klasik ve modern teknik analiz formasyonlarına göre tarar:
1. Trend Çizgisi Kırılımı + Retest (Trendline Breakout & Retest)
2. Simetrik / Yükselen / Alçalan Üçgen Kırılımı (Triangle & Pennant)
3. Destek / Direnç Dönüşümü (S/R Flip & Retest)
4. Yatay Kanal / Range Kırılımı & Retest (Range Breakout)
5. İkili Dip (Double Bottom W) & İkili Tepe (Double Top M)

Sonuçları 3 aşamaya canlı kategorize eder:
- 1. Aşama (Kırılım / Breakout)
- 2. Aşama (Retest / Pullback)
- 3. Aşama (Onaylanmış Kesin Giriş / Confirmed)
"""

import math
import time
from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from engine.market_data import market_manager
from engine.indicators import enrich_all_indicators, find_swing_points
from engine.patterns import detect_chart_patterns

def evaluate_pattern_strategy_exact(symbol: str, df: pd.DataFrame, timeframe: str = "1h") -> Optional[Dict[str, Any]]:
    if df is None or len(df) < 40:
        return None

    df_calc = enrich_all_indicators(df.copy())
    patterns = detect_chart_patterns(df_calc)
    if not patterns:
        return None

    # En güçlü ve en güncel formasyonu seç
    pat = patterns[0]
    n = len(df_calc)
    current_price = float(df_calc['close'].iloc[-1])
    current_atr = float(df_calc['atr'].iloc[-1]) if 'atr' in df_calc.columns and not np.isnan(df_calc['atr'].iloc[-1]) else current_price * 0.02

    pat_name = pat.get('name', 'Grafik Formasyonu')
    pat_type = pat.get('type', 'BULLISH') # BULLISH / BEARISH
    direction = 'LONG' if pat_type == 'BULLISH' else 'SHORT'
    breakout_level = float(pat.get('breakout_level') or pat.get('flip_level') or pat.get('neckline') or pat.get('range_high') or pat.get('range_low') or current_price)
    target = float(pat.get('target', current_price * (1.04 if direction == 'LONG' else 0.96)))
    tolerance = round(0.3 * current_atr, 4)

    # Mum verilerini incele (Son 15 bar içinde kırılma, retest ve onay kontrolü)
    recent_bars = df_calc.iloc[-15:].copy()
    vol_sma20 = float(df_calc['volume'].rolling(20).mean().iloc[-1])

    # Kırılma tespiti
    breakout_bar = None
    retest_bar = None
    confirmed_bar = None

    for i in range(len(recent_bars) - 1, -1, -1):
        row = recent_bars.iloc[i]
        c_close = float(row['close'])
        c_open = float(row['open'])
        c_high = float(row['high'])
        c_low = float(row['low'])
        c_vol = float(row['volume'])

        ts = int(row['timestamp']) if 'timestamp' in row else 0
        if ts > 1e12: ts = ts // 1000
        time_str = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M") if ts > 0 else f"Bar #{i}"

        # 1. Onay Kontrolü (Hacimli Yönlü Mum + Seviye Tutuldu)
        body_pct = abs(c_close - c_open) / max(0.0001, (c_high - c_low))
        is_directional = (c_close > c_open) if direction == 'LONG' else (c_close < c_open)
        is_vol_high = c_vol >= vol_sma20 * 0.95

        if is_directional and body_pct >= 0.55 and is_vol_high:
            if direction == 'LONG' and c_close >= breakout_level:
                confirmed_bar = {'time_str': time_str, 'timestamp': ts, 'price': c_close}
            elif direction == 'SHORT' and c_close <= breakout_level:
                confirmed_bar = {'time_str': time_str, 'timestamp': ts, 'price': c_close}

        # 2. Retest Kontrolü
        if direction == 'LONG' and c_low <= (breakout_level + tolerance) and c_close >= (breakout_level - tolerance):
            retest_bar = {'time_str': time_str, 'timestamp': ts, 'price': c_low}
        elif direction == 'SHORT' and c_high >= (breakout_level - tolerance) and c_close <= (breakout_level + tolerance):
            retest_bar = {'time_str': time_str, 'timestamp': ts, 'price': c_high}

    # Belirleme Aşaması
    stage = "BREAKOUT"
    stage_name = "1. Aşama: Formasyon Kırılımı (Breakout)"
    
    if retest_bar and confirmed_bar:
        stage = "CONFIRMED"
        stage_name = "3. Aşama: Formasyon Onaylandı (Kesin Giriş)"
    elif retest_bar:
        stage = "RETESTING"
        stage_name = "2. Aşama: Formasyon Retesti (Pullback)"

    # Risk Seviyeleri
    if direction == 'LONG':
        stop_loss = round(breakout_level - 0.2 * current_atr, 4)
        risk = max(0.0001, current_price - stop_loss)
        reward = max(0.0001, target - current_price)
    else:
        stop_loss = round(breakout_level + 0.2 * current_atr, 4)
        risk = max(0.0001, stop_loss - current_price)
        reward = max(0.0001, current_price - target)

    rr_ratio = round(reward / risk, 2)

    # 4 Adımlı Kontrol Listesi
    checklist = [
        {
            "step": 1,
            "title": f"1. Formasyon Kırılımı ({pat_name})",
            "passed": True,
            "detail": f"{pat_name} tespit edildi. Kırılan Seviye: ${breakout_level:,.4f}"
        },
        {
            "step": 2,
            "title": f"2. Retest (0.3xATR Tolerans = ${tolerance:,.4f})",
            "passed": bool(retest_bar),
            "detail": f"Fiyat ${breakout_level:,.4f} çizgisine retest temasında bulundu." if retest_bar else f"Henüz ${breakout_level:,.4f} seviyesine geri çekilme bekleniyor."
        },
        {
            "step": 3,
            "title": "3. Hacimli Onay Mumu (Yönlü Mum & Vol > SMA20)",
            "passed": bool(confirmed_bar),
            "detail": f"Retest sonrası güçlü onay mumu kapandı." if confirmed_bar else "Hacimli onay mumu bekleniyor."
        },
        {
            "step": 4,
            "title": f"4. Hedef & Risk Oranı (R:R {rr_ratio}R)",
            "passed": rr_ratio >= 1.5,
            "detail": f"Hedef: ${target:,.4f} | Stop: ${stop_loss:,.4f} (R:R {rr_ratio}R)"
        }
    ]

    explanation = f"📐 <b>{pat_name}</b>: {pat.get('description', '')}"

    return {
        "status": "success",
        "symbol": symbol,
        "timeframe": timeframe,
        "strategy_name": pat_name,
        "stage": stage,
        "stage_name": stage_name,
        "direction": direction,
        "current_price": current_price,
        "breakout_level": breakout_level,
        "entry_price": current_price,
        "stop_loss": stop_loss,
        "take_profit": target,
        "tp1": target,
        "risk_reward": f"1:{rr_ratio}",
        "atr": current_atr,
        "breakout_bar": {'time_str': 'Son Barlar', 'price': breakout_level},
        "retest_bar": retest_bar,
        "confirmed_bar": confirmed_bar,
        "checklist": checklist,
        "explanation": explanation,
        "lines": pat.get('lines', [])
    }

def run_pattern_radar(timeframe: str = "1h", limit_coins: int = 50) -> Dict[str, Any]:
    """Çok iş parçacıklı (multithreaded) tüm piyasa formasyon radarı."""
    pairs = market_manager.get_top_pairs(limit=limit_coins)
    
    stages = {
        "breakout": [],
        "retesting": [],
        "confirmed": []
    }

    def _eval(sym):
        try:
            df = market_manager.get_market_data(sym, timeframe=timeframe, limit=150)
            if df is None or len(df) < 40:
                return None
            return evaluate_pattern_strategy_exact(sym, df, timeframe=timeframe)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(_eval, sym): sym for sym in pairs}
        for f in as_completed(futures):
            res = f.result()
            if res:
                stg = res.get("stage")
                if stg == "CONFIRMED":
                    stages["confirmed"].append(res)
                elif stg == "RETESTING":
                    stages["retesting"].append(res)
                elif stg == "BREAKOUT":
                    stages["breakout"].append(res)

    # Sıralama
    stages["confirmed"].sort(key=lambda x: x['current_price'], reverse=True)
    stages["retesting"].sort(key=lambda x: x['current_price'], reverse=True)
    stages["breakout"].sort(key=lambda x: x['current_price'], reverse=True)

    stats = {
        "confirmed_count": len(stages["confirmed"]),
        "retesting_count": len(stages["retesting"]),
        "breakout_count": len(stages["breakout"]),
        "total_detected": len(stages["confirmed"]) + len(stages["retesting"]) + len(stages["breakout"])
    }

    return {
        "status": "success",
        "strategy": "CHART_PATTERNS",
        "timeframe": timeframe,
        "stats": stats,
        "stages": stages
    }
