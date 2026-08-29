"""
CryptoSignalPro AI - Swing High/Low Breakout-Retest Strategy Engine
Strict rule-based detector implementing the exact mathematical rules:
1. 1H candles (OHLCV)
2. swing_lookback (default: 3) -> is_swing_high(i) & is_swing_low(i)
   NO LOOK-AHEAD BIAS: A swing point at index i is confirmed only after swing_lookback candles close after it.
3. Reference level (swing_level): Most recently confirmed swing high (LONG) or swing low (SHORT)
4. 1H Breakout: candle CLOSE > swing_level (LONG) or CLOSE < swing_level (SHORT)
5. 1H Retest: tolerance = 0.3 * ATR(14)
   LONG: low <= breakout_level + tolerance
   SHORT: high >= breakout_level - tolerance
   Invalidation: candle CLOSE through level by > tolerance on wrong side.
6. 1H Confirmation (within 2 candles of retest):
   - Pattern: Engulfing OR body >= 60% of candle range in breakout direction
   - Level held: candle CLOSE still on breakout side of breakout_level
   - Volume: candle volume > 20-candle average volume
7. Risk levels:
   - Stop loss: breakout_level - 0.2 * ATR (LONG) or breakout_level + 0.2 * ATR (SHORT)
   - Take profit: next significant support/resistance level in trade direction (dynamic)
   - Risk:Reward ratio calculated
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from engine.market_data import market_manager
from engine.indicators import calculate_atr, calculate_sma


def evaluate_swing_strategy_exact(
    symbol: str,
    df: pd.DataFrame,
    timeframe: str = "1h",
    swing_lookback: int = 3
) -> Dict[str, Any]:
    """
    Evaluates 1H candles against the exact step-by-step Swing High/Low rules.
    Returns structured JSON matching the exact strategy specification.
    """
    if df is None or len(df) < (swing_lookback * 2 + 10):
        return {
            "status": "INVALID",
            "direction": None,
            "invalid_reason": "insufficient_data",
            "symbol": symbol,
            "timeframe": timeframe,
            "swing_level": None,
            "swing_confirmed_time": None,
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
    
    # Calculate ATR(14) and 20-candle Volume SMA on 1H
    df['atr'] = calculate_atr(df, 14)
    df['vol_sma20'] = calculate_sma(df['volume'], 20)

    highs = df['high'].values
    lows = df['low'].values
    opens = df['open'].values
    closes = df['close'].values
    volumes = df['volume'].values
    vol_sma20 = df['vol_sma20'].values
    atrs = df['atr'].values

    timestamps = []
    iso_times = []
    time_strs = []
    for idx, row in df.iterrows():
        ts = int(row['timestamp']) if 'timestamp' in row else 0
        if ts > 1e12: ts = ts // 1000
        timestamps.append(ts)
        iso_times.append(datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts > 0 else f"Bar_{idx}")
        time_strs.append(datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M UTC") if ts > 0 else f"Bar #{idx}")

    current_price = float(closes[-1])
    current_atr = float(atrs[-1]) if not np.isnan(atrs[-1]) else (current_price * 0.015)

    # -------------------------------------------------------------
    # Step 1: Detect Confirmed Swing Points (Strictly No Look-Ahead Bias)
    # -------------------------------------------------------------
    # A candle at index i is swing high if:
    # High[i] > max(High[i-lookback : i]) AND High[i] > max(High[i+1 : i+1+lookback])
    # This swing point is ONLY CONFIRMED at index: i + lookback
    confirmed_swing_highs = [] # list of (swing_idx, confirmation_idx, swing_price, swing_time, conf_time)
    confirmed_swing_lows = []  # list of (swing_idx, confirmation_idx, swing_price, swing_time, conf_time)

    for i in range(swing_lookback, n - swing_lookback):
        conf_idx = i + swing_lookback
        
        # Check Swing High
        left_highs = highs[i - swing_lookback : i]
        right_highs = highs[i + 1 : i + 1 + swing_lookback]
        if highs[i] > max(left_highs) and highs[i] > max(right_highs):
            confirmed_swing_highs.append({
                'swing_idx': i,
                'conf_idx': conf_idx,
                'price': float(highs[i]),
                'swing_time': iso_times[i],
                'swing_time_str': time_strs[i],
                'conf_time': iso_times[conf_idx],
                'conf_time_str': time_strs[conf_idx]
            })

        # Check Swing Low
        left_lows = lows[i - swing_lookback : i]
        right_lows = lows[i + 1 : i + 1 + swing_lookback]
        if lows[i] < min(left_lows) and lows[i] < min(right_lows):
            confirmed_swing_lows.append({
                'swing_idx': i,
                'conf_idx': conf_idx,
                'price': float(lows[i]),
                'swing_time': iso_times[i],
                'swing_time_str': time_strs[i],
                'conf_time': iso_times[conf_idx],
                'conf_time_str': time_strs[conf_idx]
            })

    # Evaluate both LONG (using most recent confirmed swing high) and SHORT (using most recent confirmed swing low)
    long_eval = _evaluate_direction(
        direction="LONG",
        symbol=symbol,
        timeframe=timeframe,
        swing_list=confirmed_swing_highs,
        df=df,
        highs=highs, lows=lows, opens=opens, closes=closes, volumes=volumes, vol_sma20=vol_sma20, atrs=atrs,
        timestamps=timestamps, iso_times=iso_times, time_strs=time_strs,
        current_price=current_price, current_atr=current_atr, n=n
    )

    short_eval = _evaluate_direction(
        direction="SHORT",
        symbol=symbol,
        timeframe=timeframe,
        swing_list=confirmed_swing_lows,
        df=df,
        highs=highs, lows=lows, opens=opens, closes=closes, volumes=volumes, vol_sma20=vol_sma20, atrs=atrs,
        timestamps=timestamps, iso_times=iso_times, time_strs=time_strs,
        current_price=current_price, current_atr=current_atr, n=n
    )

    # Prioritize CONFIRMED > RETESTING > BREAKOUT
    if long_eval["status"] == "CONFIRMED":
        return long_eval
    if short_eval["status"] == "CONFIRMED":
        return short_eval
    if long_eval["status"] == "RETESTING":
        return long_eval
    if short_eval["status"] == "RETESTING":
        return short_eval
    if long_eval["status"] == "BREAKOUT":
        return long_eval
    if short_eval["status"] == "BREAKOUT":
        return short_eval

    # If neither is active, return the most recent direction evaluation or INVALID
    return long_eval if long_eval["invalid_reason"] != "no_swing_level" else short_eval


def _evaluate_direction(
    direction: str,
    symbol: str,
    timeframe: str,
    swing_list: List[Dict],
    df: pd.DataFrame,
    highs: np.ndarray, lows: np.ndarray, opens: np.ndarray, closes: np.ndarray, volumes: np.ndarray, vol_sma20: np.ndarray, atrs: np.ndarray,
    timestamps: List[int], iso_times: List[str], time_strs: List[str],
    current_price: float, current_atr: float, n: int
) -> Dict[str, Any]:
    
    if not swing_list:
        return {
            "status": "INVALID",
            "direction": direction,
            "invalid_reason": "no_swing_level",
            "symbol": symbol,
            "timeframe": timeframe,
            "swing_level": None,
            "swing_confirmed_time": None,
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

    # Reference level = most recently confirmed swing point
    latest_swing = swing_list[-1]
    swing_level = latest_swing['price']
    swing_conf_idx = latest_swing['conf_idx']
    swing_conf_time = latest_swing['conf_time']
    swing_time_str = latest_swing['swing_time_str']

    # Step 2 — Breakout: Look for first 1H candle AFTER confirmation that closes beyond swing_level
    breakout_idx = None
    for k in range(swing_conf_idx, n):
        if direction == "LONG" and closes[k] > swing_level:
            breakout_idx = k
            break
        elif direction == "SHORT" and closes[k] < swing_level:
            breakout_idx = k
            break

    if breakout_idx is None:
        return {
            "status": "INVALID",
            "direction": direction,
            "invalid_reason": f"No breakout close beyond swing level (${swing_level:,.4f})",
            "symbol": symbol,
            "timeframe": timeframe,
            "swing_level": round(swing_level, 4),
            "swing_confirmed_time": swing_conf_time,
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

    bo_level = swing_level
    bo_time = iso_times[breakout_idx]
    bo_time_str = time_strs[breakout_idx]
    bo_atr = atrs[breakout_idx] if atrs[breakout_idx] > 0 else current_atr
    tolerance = 0.3 * bo_atr

    # Step 3 — Retest: Starting from candle after breakout candle
    retest_idx = None
    invalid_reason = None

    for k in range(breakout_idx + 1, n):
        k_atr = atrs[k] if atrs[k] > 0 else bo_atr
        k_tolerance = 0.3 * k_atr

        # Invalidation check: Close back through level by > tolerance
        if direction == "LONG" and closes[k] < (bo_level - k_tolerance):
            invalid_reason = f"Breakout failed: candle closed at ${closes[k]:,.4f} below swing level (${bo_level:,.4f}) - tolerance (${k_tolerance:,.4f})"
            break
        elif direction == "SHORT" and closes[k] > (bo_level + k_tolerance):
            invalid_reason = f"Breakout failed: candle closed at ${closes[k]:,.4f} above swing level (${bo_level:,.4f}) + tolerance (${k_tolerance:,.4f})"
            break

        # Retest check: Low <= bo_level + tolerance (LONG) or High >= bo_level - tolerance (SHORT)
        if direction == "LONG" and lows[k] <= (bo_level + k_tolerance):
            retest_idx = k
            break
        elif direction == "SHORT" and highs[k] >= (bo_level - k_tolerance):
            retest_idx = k
            break

    if invalid_reason:
        return {
            "status": "INVALID",
            "direction": direction,
            "invalid_reason": invalid_reason,
            "symbol": symbol,
            "timeframe": timeframe,
            "swing_level": round(swing_level, 4),
            "swing_confirmed_time": swing_conf_time,
            "breakout_time": bo_time,
            "breakout_level": round(bo_level, 4),
            "retest_time": None,
            "confirmation_time": None,
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "risk_reward": None,
            "checklist": []
        }

    bo_bar = {
        'timestamp': timestamps[breakout_idx],
        'time_str': bo_time_str,
        'close': float(closes[breakout_idx])
    }

    if retest_idx is None:
        # Step 2 passed, waiting for Retest
        sl_price = round(bo_level - 0.2 * current_atr, 4) if direction == "LONG" else round(bo_level + 0.2 * current_atr, 4)
        return _build_swing_response(
            status="BREAKOUT",
            direction=direction,
            invalid_reason=None,
            symbol=symbol,
            timeframe=timeframe,
            swing_level=swing_level,
            swing_conf_time=swing_conf_time,
            bo_time=bo_time,
            bo_level=bo_level,
            rt_time=None,
            conf_time=None,
            entry=current_price,
            sl=sl_price,
            tp=None,
            rr=None,
            atr=current_atr,
            checklist=_build_swing_checklist(direction, swing_level, bo_bar, None, None, False, current_atr, None),
            breakout_bar=bo_bar,
            retest_bar=None,
            confirmed_bar=None
        )

    rt_time = iso_times[retest_idx]
    rt_time_str = time_strs[retest_idx]
    rt_bar = {
        'timestamp': timestamps[retest_idx],
        'time_str': rt_time_str,
        'low': float(lows[retest_idx]),
        'high': float(highs[retest_idx])
    }

    # Step 4 — Confirmation: Checked on retest candle or up to 2 candles after it
    conf_idx = None
    conf_pattern_detail = None
    cand_indices = [k for k in range(retest_idx, min(n, retest_idx + 3))]

    for k in cand_indices:
        c = closes[k]
        o = opens[k]
        h = highs[k]
        l = lows[k]
        v = volumes[k]
        v_avg = vol_sma20[k]
        rng = h - l if h > l else 0.0001
        body = abs(c - o)

        # Rule 1: Candle Pattern
        has_engulfing = False
        if k > 0:
            prev_c = closes[k-1]
            prev_o = opens[k-1]
            if direction == "LONG" and c > o and prev_c < prev_o and c >= prev_o and o <= prev_c:
                has_engulfing = True
            elif direction == "SHORT" and c < o and prev_c > prev_o and c <= prev_o and o >= prev_c:
                has_engulfing = True

        has_strong_body = (c > o if direction == "LONG" else c < o) and (body >= 0.60 * rng)
        pattern_ok = has_engulfing or has_strong_body

        # Rule 2: Level Held
        level_held = (c > bo_level if direction == "LONG" else c < bo_level)

        # Rule 3: Volume > 20-candle average volume
        volume_ok = (v > v_avg) if v_avg > 0 else True

        if pattern_ok and level_held and volume_ok:
            conf_idx = k
            pattern_name = f"{'Bullish' if direction == 'LONG' else 'Bearish'} Engulfing" if has_engulfing else f"Strong Directional Candle (Body: {body/rng*100:.1f}%)"
            conf_pattern_detail = f"{pattern_name}, Close: ${c:,.4f}, Volume: {v:,.0f} > Avg {v_avg:,.0f}"
            break

    is_fresh_conf = (conf_idx is not None) and (conf_idx >= n - 2)
    sl_price = round(bo_level - 0.2 * current_atr, 4) if direction == "LONG" else round(bo_level + 0.2 * current_atr, 4)
    entry_p = float(closes[conf_idx]) if conf_idx is not None else current_price
    risk = abs(entry_p - sl_price) if abs(entry_p - sl_price) > 0 else (current_atr * 0.5)

    # Dynamic Take Profit
    tp_price = _find_next_swing_target(df, entry_p, direction=direction, atr=current_atr)
    rr_ratio = round(abs(tp_price - entry_p) / risk, 2)

    conf_bar = {
        'timestamp': timestamps[conf_idx] if conf_idx is not None else None,
        'time_str': time_strs[conf_idx] if conf_idx is not None else None,
        'close': entry_p
    } if conf_idx is not None else None

    if is_fresh_conf:
        return _build_swing_response(
            status="CONFIRMED",
            direction=direction,
            invalid_reason=None,
            symbol=symbol,
            timeframe=timeframe,
            swing_level=swing_level,
            swing_conf_time=swing_conf_time,
            bo_time=bo_time,
            bo_level=bo_level,
            rt_time=rt_time,
            conf_time=iso_times[conf_idx],
            entry=entry_p,
            sl=sl_price,
            tp=tp_price,
            rr=rr_ratio,
            atr=current_atr,
            checklist=_build_swing_checklist(direction, swing_level, bo_bar, rt_bar, conf_bar, True, current_atr, conf_pattern_detail),
            breakout_bar=bo_bar,
            retest_bar=rt_bar,
            confirmed_bar=conf_bar
        )
    elif n - 1 <= retest_idx + 2:
        # Still inside confirmation window
        return _build_swing_response(
            status="RETESTING",
            direction=direction,
            invalid_reason=None,
            symbol=symbol,
            timeframe=timeframe,
            swing_level=swing_level,
            swing_conf_time=swing_conf_time,
            bo_time=bo_time,
            bo_level=bo_level,
            rt_time=rt_time,
            conf_time=None,
            entry=current_price,
            sl=sl_price,
            tp=tp_price,
            rr=rr_ratio,
            atr=current_atr,
            checklist=_build_swing_checklist(direction, swing_level, bo_bar, rt_bar, None, False, current_atr, None),
            breakout_bar=bo_bar,
            retest_bar=rt_bar,
            confirmed_bar=None
        )

    # Window expired without confirmation
    return {
        "status": "INVALID",
        "direction": direction,
        "invalid_reason": "Retest window expired (2 candles) without volume/pattern confirmation",
        "symbol": symbol,
        "timeframe": timeframe,
        "swing_level": round(swing_level, 4),
        "swing_confirmed_time": swing_conf_time,
        "breakout_time": bo_time,
        "breakout_level": round(bo_level, 4),
        "retest_time": rt_time,
        "confirmation_time": None,
        "entry_price": None,
        "stop_loss": None,
        "take_profit": None,
        "risk_reward": None,
        "checklist": []
    }


def _find_next_swing_target(df: pd.DataFrame, entry: float, direction: str, atr: float) -> float:
    """Finds next dynamic S/R level beyond entry."""
    highs = df['high'].values
    lows = df['low'].values
    n = len(df)
    
    if direction == "LONG":
        res_targets = []
        for i in range(3, n - 2):
            if highs[i] == max(highs[i-3:i+4]) and highs[i] > (entry + 0.5 * atr):
                res_targets.append(float(highs[i]))
        if res_targets:
            res_targets.sort()
            return round(res_targets[0], 4)
        return round(entry + 2.5 * atr, 4)
    else:
        sup_targets = []
        for i in range(3, n - 2):
            if lows[i] == min(lows[i-3:i+4]) and lows[i] < (entry - 0.5 * atr):
                sup_targets.append(float(lows[i]))
        if sup_targets:
            sup_targets.sort(reverse=True)
            return round(sup_targets[0], 4)
        return round(entry - 2.5 * atr, 4)


def _build_swing_checklist(
    direction: str,
    swing_level: float,
    bo_bar: Optional[Dict],
    rt_bar: Optional[Dict],
    conf_bar: Optional[Dict],
    is_confirmed: bool,
    atr: float,
    conf_detail: Optional[str]
) -> List[Dict[str, Any]]:
    tolerance = 0.3 * atr
    level_name = "Teyitli Swing High (Zirve)" if direction == "LONG" else "Teyitli Swing Low (Dip)"
    
    return [
        {
            "title": f"1. Yapısal Referans Seviyesi ({level_name})",
            "passed": True,
            "detail": f"Lookback(3) teyitli yapısal seviye: ${swing_level:,.4f} | 1H ATR(14): ${atr:,.4f}"
        },
        {
            "title": "2. 1H Kırılım Mumu Kapanışı (Breakout Close)",
            "passed": bo_bar is not None,
            "detail": f"Saat {bo_bar['time_str']} barında ${bo_bar['close']:,.4f} ile kırılım kapandı." if bo_bar else f"Henüz {level_name} ötesinde 1H kapanışı yok."
        },
        {
            "title": f"3. Seviyeye Retest (Tolerans: 0.3 × ATR = ${tolerance:,.4f})",
            "passed": rt_bar is not None,
            "detail": f"Saat {rt_bar['time_str']} barında fiyat seviyeye ({'Low' if direction == 'LONG' else 'High'}: ${rt_bar['low' if direction == 'LONG' else 'high']:,.4f}) geri çekildi." if rt_bar else "Retest henüz gerçekleşmedi."
        },
        {
            "title": "4. Katı Onay Mumu (Gövde >= %60 / Engulfing + Seviye Korundu + Hacim > 20 Ort)",
            "passed": is_confirmed,
            "detail": f"Saat {conf_bar['time_str']} barında onaylandı: {conf_detail}" if is_confirmed else ("Retest sonrası 2 barlık onay penceresinde bekleniyor." if rt_bar else "Onay mumu bekleniyor.")
        }
    ]


def _build_swing_response(
    status: str,
    direction: str,
    invalid_reason: Optional[str],
    symbol: str,
    timeframe: str,
    swing_level: float,
    swing_conf_time: str,
    bo_time: Optional[str],
    bo_level: float,
    rt_time: Optional[str],
    conf_time: Optional[str],
    entry: float,
    sl: float,
    tp: Optional[float],
    rr: Optional[float],
    atr: float,
    checklist: List[Dict],
    breakout_bar: Optional[Dict] = None,
    retest_bar: Optional[Dict] = None,
    confirmed_bar: Optional[Dict] = None
) -> Dict[str, Any]:
    
    stage_name = {
        "CONFIRMED": "3. Aşama: Swing Retest + Onay Alındı (İşleme Hazır)",
        "RETESTING": "2. Aşama: Swing Retest Bölgesinde (Onay Bekleniyor)",
        "BREAKOUT": "1. Aşama: Yeni Swing Kırıldı (Retest Bekleniyor)",
        "INVALID": "Geçersiz / İptal"
    }.get(status, status)

    stage_badge = {
        "CONFIRMED": f"🚀 ONAYLANDI ({direction})",
        "RETESTING": "🎯 RETEST YAPIYOR",
        "BREAKOUT": f"⚡ {direction} SWING KIRILDI",
        "INVALID": "❌ İPTAL"
    }.get(status, status)

    explanation = ""
    if status == "CONFIRMED":
        explanation = f"Teyitli Swing seviyesi (${bo_level:,.4f}) kırıldı, 0.3xATR toleransla retest yapıldı ve hacimli onay mumu kapandı."
    elif status == "RETESTING":
        explanation = f"Fiyat Swing seviyesini (${bo_level:,.4f}) kırdı ve şu anda retest bölgesinde destek/direnç arıyor. 2 bar içinde onay mumu bekleniyor."
    elif status == "BREAKOUT":
        explanation = f"Fiyat Swing seviyesini (${bo_level:,.4f}) kırdı. Güvenli giriş için 0.3xATR (${0.3*atr:,.4f}) tolerans bandına retest yapması bekleniyor."

    lines = [
        {'name': f"Swing {'High (Zirve)' if direction == 'LONG' else 'Low (Dip)'}", 'price': round(swing_level, 4), 'color': '#06b6d4', 'style': 0},
        {'name': 'Giriş Seviyesi', 'price': round(entry, 4), 'color': '#fbbf24', 'style': 2},
        {'name': 'Stop Loss (0.2xATR)', 'price': round(sl, 4), 'color': '#ef4444', 'style': 0}
    ]
    if tp:
        lines.append({'name': 'Hedef (Dinamik S/R)', 'price': round(tp, 4), 'color': '#10b981', 'style': 0})

    return {
        "status": status,
        "stage": status,
        "stage_name": stage_name,
        "stage_badge": stage_badge,
        "direction": direction,
        "invalid_reason": invalid_reason,
        "symbol": symbol,
        "timeframe": timeframe,
        "strategy_type": "SWING_HL",
        "strategy_title": "Swing High / Low Breakout & Retest",
        "swing_level": round(swing_level, 4),
        "swing_confirmed_time": swing_conf_time,
        "pdh": round(swing_level, 4) if direction == 'LONG' else None,
        "pdl": round(swing_level, 4) if direction == 'SHORT' else None,
        "breakout_time": bo_time,
        "breakout_level": round(bo_level, 4),
        "retest_time": rt_time,
        "confirmation_time": conf_time,
        "current_price": round(entry, 4),
        "entry_price": round(entry, 4),
        "stop_loss": round(sl, 4),
        "take_profit": round(tp, 4) if tp else None,
        "risk_reward": rr,
        "rr_ratio": rr,
        "atr": round(atr, 4),
        "tolerance": round(0.3 * atr, 4),
        "explanation": explanation,
        "checklist": checklist,
        "breakout_bar": breakout_bar,
        "retest_bar": retest_bar,
        "confirmed_bar": confirmed_bar,
        "lines": lines
    }


def run_swing_radar(timeframe: str = "1h", limit_coins: int = 50, swing_lookback: int = 3) -> Dict[str, Any]:
    """Tüm piyasayı tarayıp kesin Swing High/Low Breakout & Retest sonuçlarını döndürür."""
    pairs = market_manager.get_top_pairs(limit=limit_coins)
    
    breakout_list = []
    retesting_list = []
    confirmed_list = []

    def _worker(sym):
        try:
            df = market_manager.get_market_data(sym, timeframe=timeframe, limit=120)
            if df is not None and len(df) >= (swing_lookback * 2 + 10):
                res = evaluate_swing_strategy_exact(sym, df, timeframe=timeframe, swing_lookback=swing_lookback)
                if res and res.get('status') in ['CONFIRMED', 'RETESTING', 'BREAKOUT']:
                    return res
        except Exception as e:
            return None
        return None

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_worker, s): s for s in pairs}
        for f in as_completed(futures):
            res = f.result()
            if res:
                st = res.get('status')
                if st == 'CONFIRMED':
                    confirmed_list.append(res)
                elif st == 'RETESTING':
                    retesting_list.append(res)
                elif st == 'BREAKOUT':
                    breakout_list.append(res)

    return {
        'status': 'success',
        'strategy_type': 'SWING_HL',
        'strategy_title': 'Swing High / Low Breakout-Retest Radarı',
        'timeframe': timeframe,
        'swing_lookback': swing_lookback,
        'total_scanned': len(pairs),
        'stats': {
            'confirmed_count': len(confirmed_list),
            'retesting_count': len(retesting_list),
            'breakout_count': len(breakout_list),
            'total_detected': len(confirmed_list) + len(retesting_list) + len(breakout_list)
        },
        'stages': {
            'confirmed': confirmed_list,
            'retesting': retesting_list,
            'breakout': breakout_list
        }
    }
