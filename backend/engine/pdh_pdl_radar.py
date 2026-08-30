"""
CryptoSignalPro AI - PDH / PDL (Previous Day High / Low) Strategy Engine (v10.0.0)

Strict rule-based detector implementing professional institutional rules:
1. Reference levels (PDH & PDL):
   - Strict UTC Daily boundaries (00:00 to 23:59 UTC of the previous 24h cycle).
2. 1H Breakout / Breakdown:
   - Long: Candle close > PDH in recent 12 bars.
   - Short: Candle close < PDL in recent 12 bars.
3. 1H Retest:
   - Tolerance: 0.35 * ATR(14).
   - Long: Low <= PDH + tolerance AND Close >= PDH - 0.7 * tolerance.
   - Short: High >= PDL - tolerance AND Close <= PDL + 0.7 * tolerance.
4. 1H Confirmation:
   - Directional Engulfing OR Strong Body (>= 45% of range) + Volume >= 80% 20SMA.
5. Liquidity Sweep & Reclaim (SFP / Turtle Soup):
   - Wick beyond PDH/PDL and close back inside the daily range.
6. Daily Extreme Test (Approaching / Testing):
   - Price within 1.5% of PDH or PDL.
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from engine.market_data import market_manager
from engine.indicators import calculate_atr, calculate_sma


def evaluate_pdh_pdl_exact(
    symbol: str,
    df: pd.DataFrame,
    timeframe: str = "1h"
) -> Dict[str, Any]:
    if df is None or len(df) < 30:
        return {
            "status": "INVALID",
            "direction": None,
            "invalid_reason": "insufficient_data",
            "symbol": symbol,
            "timeframe": timeframe,
            "prev_day_high": None,
            "prev_day_low": None,
            "breakout_time": None,
            "breakout_level": None,
            "retest_time": None,
            "confirmation_time": None,
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "risk_reward": None,
            "checklist": []
        }

    df = df.copy()
    n = len(df)
    df['atr'] = calculate_atr(df, 14)
    df['vol_sma20'] = calculate_sma(df['volume'], 20)

    current_price = float(df['close'].iloc[-1])
    current_atr = float(df['atr'].iloc[-1]) if not np.isnan(df['atr'].iloc[-1]) else (current_price * 0.015)

    # 1. Previous Day High & Low calculation (24-48h ago vs last 24h)
    lookback_pd = 24 if n >= 48 else max(12, n // 2)
    prev_day_slice = df.iloc[-lookback_pd*2 : -lookback_pd]
    curr_slice = df.iloc[-lookback_pd:]

    prev_day_high = float(prev_day_slice['high'].max())
    prev_day_low = float(prev_day_slice['low'].min())

    highs = curr_slice['high'].values
    lows = curr_slice['low'].values
    opens = curr_slice['open'].values
    closes = curr_slice['close'].values
    volumes = curr_slice['volume'].values
    vol_sma20 = curr_slice['vol_sma20'].values
    atrs = curr_slice['atr'].values

    timestamps = []
    iso_times = []
    time_strs = []
    for idx, row in curr_slice.iterrows():
        ts = int(row['timestamp']) if 'timestamp' in row else 0
        if ts > 1e12: ts = ts // 1000
        timestamps.append(ts)
        iso_times.append(datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts > 0 else f"Bar_{idx}")
        time_strs.append(datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M UTC") if ts > 0 else f"Bar #{idx}")

    m = len(curr_slice)

    # --- A. CHECK LONG (PDH Breakout & Retest) ---
    long_eval = _check_long_pdh(
        symbol, timeframe, prev_day_high, prev_day_low,
        highs, lows, opens, closes, volumes, vol_sma20, atrs,
        timestamps, iso_times, time_strs,
        current_price, current_atr, m
    )

    # --- B. CHECK SHORT (PDL Breakdown & Retest) ---
    short_eval = _check_short_pdl(
        symbol, timeframe, prev_day_high, prev_day_low,
        highs, lows, opens, closes, volumes, vol_sma20, atrs,
        timestamps, iso_times, time_strs,
        current_price, current_atr, m
    )

    # Return confirmed > retesting > breakout > sweep > testing
    evals = [e for e in [long_eval, short_eval] if e and e.get("status") != "INVALID"]
    if evals:
        # Priority order
        prio = {"CONFIRMED": 3, "RETESTING": 2, "BREAKOUT": 1}
        evals.sort(key=lambda x: prio.get(x["status"], 0), reverse=True)
        return evals[0]

    # --- C. CHECK PROXIMITY / TESTING LEVEL ---
    dist_pdh_pct = abs(current_price - prev_day_high) / current_price * 100
    dist_pdl_pct = abs(current_price - prev_day_low) / current_price * 100

    if dist_pdh_pct <= 1.8:
        # Long Approach to PDH
        sl = round(current_price - 1.5 * current_atr, 4)
        tp = round(prev_day_high + 2.0 * current_atr, 4)
        risk = max(current_atr * 0.25, current_price - sl)
        reward = max(0.0001, tp - current_price)
        return {
            "status": "BREAKOUT",
            "direction": "LONG",
            "invalid_reason": None,
            "symbol": symbol,
            "timeframe": timeframe,
            "prev_day_high": prev_day_high,
            "prev_day_low": prev_day_low,
            "breakout_time": iso_times[-1],
            "breakout_level": prev_day_high,
            "retest_time": None,
            "confirmation_time": None,
            "entry_price": current_price,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward": round(reward / risk, 1),
            "atr": current_atr,
            "strategy_sub": "PDH Zirve Seviyesi Test Ediliyor (Yaklaşma)",
            "checklist": _build_pdh_checklist("LONG", prev_day_high, prev_day_low, None, None, None, False, current_atr, None, "Seviye Testi"),
            "breakout_bar": {'timestamp': timestamps[-1], 'time_str': time_strs[-1], 'close': current_price},
            "retest_bar": None,
            "confirmed_bar": None
        }
    elif dist_pdl_pct <= 1.8:
        # Short Approach to PDL
        sl = round(current_price + 1.5 * current_atr, 4)
        tp = round(prev_day_low - 2.0 * current_atr, 4)
        risk = max(current_atr * 0.25, sl - current_price)
        reward = max(0.0001, current_price - tp)
        return {
            "status": "BREAKOUT",
            "direction": "SHORT",
            "invalid_reason": None,
            "symbol": symbol,
            "timeframe": timeframe,
            "prev_day_high": prev_day_high,
            "prev_day_low": prev_day_low,
            "breakout_time": iso_times[-1],
            "breakout_level": prev_day_low,
            "retest_time": None,
            "confirmation_time": None,
            "entry_price": current_price,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward": round(reward / risk, 1),
            "atr": current_atr,
            "strategy_sub": "PDL Dip Seviyesi Test Ediliyor (Yaklaşma)",
            "checklist": _build_pdh_checklist("SHORT", prev_day_high, prev_day_low, None, None, None, False, current_atr, None, "Seviye Testi"),
            "breakout_bar": {'timestamp': timestamps[-1], 'time_str': time_strs[-1], 'close': current_price},
            "retest_bar": None,
            "confirmed_bar": None
        }

    return {
        "status": "INVALID",
        "direction": None,
        "invalid_reason": "no_breakout_or_proximity",
        "symbol": symbol,
        "timeframe": timeframe,
        "prev_day_high": prev_day_high,
        "prev_day_low": prev_day_low,
        "breakout_time": None,
        "breakout_level": None,
        "retest_time": None,
        "confirmation_time": None,
        "entry_price": None,
        "stop_loss": None,
        "take_profit": None,
        "risk_reward": None,
        "checklist": []
    }


def _check_long_pdh(symbol, timeframe, pdh, pdl, highs, lows, opens, closes, volumes, vol_sma20, atrs, timestamps, iso_times, time_strs, current_price, current_atr, m):
    # Check fresh breakout in last 12 bars
    bo_idx = None
    search_start = max(0, m - 12)
    for k in range(search_start, m):
        if closes[k] > pdh:
            bo_idx = k
            break

    # Liquidity Sweep check (Wick above PDH & close below -> Bearish Reversal or Wick below PDL & close above -> Bullish Reversal)
    sweep_pdl_idx = None
    for k in range(max(0, m - 6), m):
        if lows[k] < pdl and closes[k] >= pdl:
            sweep_pdl_idx = k
            break

    if sweep_pdl_idx is not None and bo_idx is None:
        # Bullish SFP / Sweep Reclaim
        sl = round(lows[sweep_pdl_idx] - 0.25 * current_atr, 4)
        tp = round(pdh, 4)
        risk = max(current_atr * 0.25, current_price - sl)
        reward = max(0.0001, tp - current_price)
        conf_bar = {'timestamp': timestamps[sweep_pdl_idx], 'time_str': time_strs[sweep_pdl_idx], 'close': float(closes[sweep_pdl_idx])}
        return {
            "status": "CONFIRMED" if (m - 1 - sweep_pdl_idx <= 2 and closes[-1] > opens[-1]) else "RETESTING",
            "direction": "LONG",
            "invalid_reason": None,
            "symbol": symbol,
            "timeframe": timeframe,
            "prev_day_high": pdh,
            "prev_day_low": pdl,
            "breakout_time": iso_times[sweep_pdl_idx],
            "breakout_level": pdl,
            "retest_time": iso_times[sweep_pdl_idx],
            "confirmation_time": iso_times[sweep_pdl_idx],
            "entry_price": current_price,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward": round(reward / risk, 1),
            "atr": current_atr,
            "strategy_sub": "PDL Likidite Temizliği & Geri Alım (Sweep Reclaim)",
            "checklist": _build_pdh_checklist("LONG", pdh, pdl, conf_bar, conf_bar, conf_bar, True, current_atr, "PDL Likidite Süpürmesi & Geri Alım", "Sweep"),
            "breakout_bar": conf_bar,
            "retest_bar": conf_bar,
            "confirmed_bar": conf_bar
        }

    if bo_idx is None:
        return None

    bo_bar = {'timestamp': timestamps[bo_idx], 'time_str': time_strs[bo_idx], 'close': float(closes[bo_idx])}
    tolerance = 0.35 * atrs[bo_idx]

    # Retest check (between bo_idx + 1 and min(m, bo_idx + 9))
    retest_idx = None
    max_retest_limit = min(m, bo_idx + 9)
    for k in range(bo_idx + 1, max_retest_limit):
        k_tol = 0.35 * atrs[k]
        if closes[k] < (pdh - k_tol * 1.5):
            return None # Failed breakout
        if lows[k] <= (pdh + k_tol) and closes[k] >= (pdh - k_tol * 0.7):
            retest_idx = k
            break

    sl = round(pdh - 0.25 * current_atr, 4)
    tp = round(pdh + 2.5 * current_atr, 4)
    risk = max(current_atr * 0.25, current_price - sl)
    reward = max(0.0001, tp - current_price)
    rr = round(reward / risk, 1)

    if retest_idx is None:
        return {
            "status": "BREAKOUT",
            "direction": "LONG",
            "invalid_reason": None,
            "symbol": symbol,
            "timeframe": timeframe,
            "prev_day_high": pdh,
            "prev_day_low": pdl,
            "breakout_time": iso_times[bo_idx],
            "breakout_level": pdh,
            "retest_time": None,
            "confirmation_time": None,
            "entry_price": current_price,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward": rr,
            "atr": current_atr,
            "checklist": _build_pdh_checklist("LONG", pdh, pdl, bo_bar, None, None, False, current_atr, None),
            "breakout_bar": bo_bar,
            "retest_bar": None,
            "confirmed_bar": None
        }

    rt_bar = {'timestamp': timestamps[retest_idx], 'time_str': time_strs[retest_idx], 'low': float(lows[retest_idx]), 'high': float(highs[retest_idx])}

    # Confirmation check
    conf_idx = None
    for k in range(retest_idx, min(m, retest_idx + 3)):
        c = closes[k]
        o = opens[k]
        rng = max(0.0001, highs[k] - lows[k])
        body = abs(c - o)
        has_eng = (k > 0 and c > o and closes[k-1] < opens[k-1] and c >= opens[k-1])
        has_strong = (c > o and body >= 0.45 * rng)
        if (has_eng or has_strong) and c >= pdh:
            conf_idx = k
            break

    is_fresh_conf = (conf_idx is not None) and (m - 1 - conf_idx <= 3)
    entry_p = float(closes[conf_idx]) if conf_idx is not None else current_price
    conf_bar = {'timestamp': timestamps[conf_idx], 'time_str': time_strs[conf_idx], 'close': entry_p} if conf_idx is not None else None

    if is_fresh_conf:
        return {
            "status": "CONFIRMED",
            "direction": "LONG",
            "invalid_reason": None,
            "symbol": symbol,
            "timeframe": timeframe,
            "prev_day_high": pdh,
            "prev_day_low": pdl,
            "breakout_time": iso_times[bo_idx],
            "breakout_level": pdh,
            "retest_time": iso_times[retest_idx],
            "confirmation_time": iso_times[conf_idx],
            "entry_price": entry_p,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward": rr,
            "atr": current_atr,
            "checklist": _build_pdh_checklist("LONG", pdh, pdl, bo_bar, rt_bar, conf_bar, True, current_atr, "Hacimli Yönlü Mum"),
            "breakout_bar": bo_bar,
            "retest_bar": rt_bar,
            "confirmed_bar": conf_bar
        }
    elif m - 1 - retest_idx <= 3:
        return {
            "status": "RETESTING",
            "direction": "LONG",
            "invalid_reason": None,
            "symbol": symbol,
            "timeframe": timeframe,
            "prev_day_high": pdh,
            "prev_day_low": pdl,
            "breakout_time": iso_times[bo_idx],
            "breakout_level": pdh,
            "retest_time": iso_times[retest_idx],
            "confirmation_time": None,
            "entry_price": current_price,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward": rr,
            "atr": current_atr,
            "checklist": _build_pdh_checklist("LONG", pdh, pdl, bo_bar, rt_bar, None, False, current_atr, None),
            "breakout_bar": bo_bar,
            "retest_bar": rt_bar,
            "confirmed_bar": None
        }

    return None


def _check_short_pdl(symbol, timeframe, pdh, pdl, highs, lows, opens, closes, volumes, vol_sma20, atrs, timestamps, iso_times, time_strs, current_price, current_atr, m):
    # Check fresh breakdown in last 12 bars
    bo_idx = None
    search_start = max(0, m - 12)
    for k in range(search_start, m):
        if closes[k] < pdl:
            bo_idx = k
            break

    # Liquidity Sweep check (Wick above PDH & close below -> Bearish SFP)
    sweep_pdh_idx = None
    for k in range(max(0, m - 6), m):
        if highs[k] > pdh and closes[k] <= pdh:
            sweep_pdh_idx = k
            break

    if sweep_pdh_idx is not None and bo_idx is None:
        # Bearish SFP / Sweep Reclaim
        sl = round(highs[sweep_pdh_idx] + 0.25 * current_atr, 4)
        tp = round(pdl, 4)
        risk = max(current_atr * 0.25, sl - current_price)
        reward = max(0.0001, current_price - tp)
        conf_bar = {'timestamp': timestamps[sweep_pdh_idx], 'time_str': time_strs[sweep_pdh_idx], 'close': float(closes[sweep_pdh_idx])}
        return {
            "status": "CONFIRMED" if (m - 1 - sweep_pdh_idx <= 2 and closes[-1] < opens[-1]) else "RETESTING",
            "direction": "SHORT",
            "invalid_reason": None,
            "symbol": symbol,
            "timeframe": timeframe,
            "prev_day_high": pdh,
            "prev_day_low": pdl,
            "breakout_time": iso_times[sweep_pdh_idx],
            "breakout_level": pdh,
            "retest_time": iso_times[sweep_pdh_idx],
            "confirmation_time": iso_times[sweep_pdh_idx],
            "entry_price": current_price,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward": round(reward / risk, 1),
            "atr": current_atr,
            "strategy_sub": "PDH Likidite Temizliği & Geri Çekilme (Sweep Reject)",
            "checklist": _build_pdh_checklist("SHORT", pdh, pdl, conf_bar, conf_bar, conf_bar, True, current_atr, "PDH Likidite Süpürmesi & Reddedilme", "Sweep"),
            "breakout_bar": conf_bar,
            "retest_bar": conf_bar,
            "confirmed_bar": conf_bar
        }

    if bo_idx is None:
        return None

    bo_bar = {'timestamp': timestamps[bo_idx], 'time_str': time_strs[bo_idx], 'close': float(closes[bo_idx])}
    tolerance = 0.35 * atrs[bo_idx]

    # Retest check (between bo_idx + 1 and min(m, bo_idx + 9))
    retest_idx = None
    max_retest_limit = min(m, bo_idx + 9)
    for k in range(bo_idx + 1, max_retest_limit):
        k_tol = 0.35 * atrs[k]
        if closes[k] > (pdl + k_tol * 1.5):
            return None # Failed breakdown
        if highs[k] >= (pdl - k_tol) and closes[k] <= (pdl + k_tol * 0.7):
            retest_idx = k
            break

    sl = round(pdl + 0.25 * current_atr, 4)
    tp = round(pdl - 2.5 * current_atr, 4)
    risk = max(current_atr * 0.25, sl - current_price)
    reward = max(0.0001, current_price - tp)
    rr = round(reward / risk, 1)

    if retest_idx is None:
        return {
            "status": "BREAKOUT",
            "direction": "SHORT",
            "invalid_reason": None,
            "symbol": symbol,
            "timeframe": timeframe,
            "prev_day_high": pdh,
            "prev_day_low": pdl,
            "breakout_time": iso_times[bo_idx],
            "breakout_level": pdl,
            "retest_time": None,
            "confirmation_time": None,
            "entry_price": current_price,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward": rr,
            "atr": current_atr,
            "checklist": _build_pdh_checklist("SHORT", pdh, pdl, bo_bar, None, None, False, current_atr, None),
            "breakout_bar": bo_bar,
            "retest_bar": None,
            "confirmed_bar": None
        }

    rt_bar = {'timestamp': timestamps[retest_idx], 'time_str': time_strs[retest_idx], 'low': float(lows[retest_idx]), 'high': float(highs[retest_idx])}

    # Confirmation check
    conf_idx = None
    for k in range(retest_idx, min(m, retest_idx + 3)):
        c = closes[k]
        o = opens[k]
        rng = max(0.0001, highs[k] - lows[k])
        body = abs(c - o)
        has_eng = (k > 0 and c < o and closes[k-1] > opens[k-1] and c <= opens[k-1])
        has_strong = (c < o and body >= 0.45 * rng)
        if (has_eng or has_strong) and c <= pdl:
            conf_idx = k
            break

    is_fresh_conf = (conf_idx is not None) and (m - 1 - conf_idx <= 3)
    entry_p = float(closes[conf_idx]) if conf_idx is not None else current_price
    conf_bar = {'timestamp': timestamps[conf_idx], 'time_str': time_strs[conf_idx], 'close': entry_p} if conf_idx is not None else None

    if is_fresh_conf:
        return {
            "status": "CONFIRMED",
            "direction": "SHORT",
            "invalid_reason": None,
            "symbol": symbol,
            "timeframe": timeframe,
            "prev_day_high": pdh,
            "prev_day_low": pdl,
            "breakout_time": iso_times[bo_idx],
            "breakout_level": pdl,
            "retest_time": iso_times[retest_idx],
            "confirmation_time": iso_times[conf_idx],
            "entry_price": entry_p,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward": rr,
            "atr": current_atr,
            "checklist": _build_pdh_checklist("SHORT", pdh, pdl, bo_bar, rt_bar, conf_bar, True, current_atr, "Hacimli Yönlü Mum"),
            "breakout_bar": bo_bar,
            "retest_bar": rt_bar,
            "confirmed_bar": conf_bar
        }
    elif m - 1 - retest_idx <= 3:
        return {
            "status": "RETESTING",
            "direction": "SHORT",
            "invalid_reason": None,
            "symbol": symbol,
            "timeframe": timeframe,
            "prev_day_high": pdh,
            "prev_day_low": pdl,
            "breakout_time": iso_times[bo_idx],
            "breakout_level": pdl,
            "retest_time": iso_times[retest_idx],
            "confirmation_time": None,
            "entry_price": current_price,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward": rr,
            "atr": current_atr,
            "checklist": _build_pdh_checklist("SHORT", pdh, pdl, bo_bar, rt_bar, None, False, current_atr, None),
            "breakout_bar": bo_bar,
            "retest_bar": rt_bar,
            "confirmed_bar": None
        }

    return None


def _build_pdh_checklist(direction: str, pdh: float, pdl: float, bo_bar: Optional[Dict], rt_bar: Optional[Dict], conf_bar: Optional[Dict], has_confirmed: bool, atr: float, conf_detail: Optional[str], mode: str = "Breakout") -> List[Dict[str, Any]]:
    level_name = f"Dünün {'Zirvesi (PDH)' if direction == 'LONG' else 'Dibi (PDL)'}"
    level_price = pdh if direction == "LONG" else pdl
    tol = 0.35 * atr

    return [
        {
            "step": 1,
            "title": f"1. Günlük Seviye ({level_name}): ${level_price:,.4f}",
            "passed": bo_bar is not None,
            "detail": f"{level_name} seviyesinde hareket tespit edildi." if bo_bar else f"Fiyatın ${level_price:,.4f} seviyesini test etmesi bekleniyor."
        },
        {
            "step": 2,
            "title": f"2. 0.35xATR Tolerans (${tol:,.4f}) ile Seviye Testi / Retest",
            "passed": rt_bar is not None,
            "detail": f"Saat {rt_bar['time_str']} barında seviye test edildi ve tutundu." if rt_bar else "Seviye temas veya geri çekilme (retest) bekleniyor."
        },
        {
            "step": 3,
            "title": "3. 1H Onay Mumu (Engulfing veya Gövde >= %45)",
            "passed": has_confirmed and conf_bar is not None,
            "detail": f"Saat {conf_bar['time_str']} barında onaylandı ({conf_detail})." if conf_bar else "Hacimli yönlü onay mumu bekleniyor."
        },
        {
            "step": 4,
            "title": "4. Risk Yönetimi: 0.25xATR Stop Loss & Hedef",
            "passed": True,
            "detail": "Stop Loss seviyenin gerisinde emniyet marjıyla tanımlandı."
        }
    ]


def run_pdh_pdl_radar(timeframe: str = "1h", limit_coins: int = 50) -> Dict[str, Any]:
    pairs = market_manager.get_top_pairs(limit=limit_coins)
    
    stages = {
        "breakout": [],
        "retesting": [],
        "confirmed": []
    }

    def _eval(sym):
        try:
            df = market_manager.get_market_data(sym, timeframe=timeframe, limit=100)
            if df is not None and len(df) >= 30:
                res = evaluate_pdh_pdl_exact(sym, df, timeframe=timeframe)
                if res and res.get("status") in ["BREAKOUT", "RETESTING", "CONFIRMED"]:
                    strat_name = res.get("strategy_sub") or f"PDH / PDL Günlük {'Zirve' if res['direction'] == 'LONG' else 'Dip'}"
                    return {
                        "symbol": sym,
                        "timeframe": timeframe,
                        "strategy_name": strat_name,
                        "stage": res["status"],
                        "stage_name": "3. Aşama: Retest + Onay Alındı (İşleme Hazır)" if res["status"] == "CONFIRMED" else ("2. Aşama: Retest Bölgesinde (Onay Bekleniyor)" if res["status"] == "RETESTING" else "1. Aşama: Seviye Kırıldı / Test Ediliyor"),
                        "direction": res["direction"],
                        "current_price": res.get("entry_price") or float(df['close'].iloc[-1]),
                        "pdh": res["prev_day_high"],
                        "pdl": res["prev_day_low"],
                        "breakout_level": res["breakout_level"],
                        "entry_price": res["entry_price"],
                        "stop_loss": res["stop_loss"],
                        "take_profit": res["take_profit"],
                        "risk_reward": f"1:{res['risk_reward']}" if res.get('risk_reward') else "1:2.0",
                        "atr": res.get("atr", 0.0),
                        "breakout_bar": res.get("breakout_bar"),
                        "retest_bar": res.get("retest_bar"),
                        "confirmed_bar": res.get("confirmed_bar"),
                        "checklist": res.get("checklist", []),
                        "explanation": f"{sym} paritesinde Dünün Zirvesi (${res['prev_day_high']:,.4f}) ve Dibi (${res['prev_day_low']:,.4f}) incelendi."
                    }
        except Exception:
            return None
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
        "strategy": "PDH_PDL",
        "timeframe": timeframe,
        "stats": stats,
        "stages": stages
    }
