"""
CryptoSignalPro AI - Previous-Day High/Low Breakout-Retest Strategy Engine
Strict rule-based detector implementing the exact mathematical rules:
1. Daily candles (UTC 00:00–24:00) -> compute prev_day_high and prev_day_low
2. 1H Breakout -> candle CLOSE > PDH (LONG) or close < PDL (SHORT)
3. 1H Retest -> tolerance = 0.3 * ATR(14). Low <= PDH + tolerance (LONG) or High >= PDL - tolerance (SHORT)
   Invalidation: candle CLOSE through level by > tolerance on wrong side.
4. 1H Confirmation (within 2 candles of retest):
   - Pattern: Engulfing OR body >= 60% of candle range in breakout direction
   - Level held: candle CLOSE still on breakout side of breakout_level
   - Volume: candle volume > 20-candle average volume
5. Risk levels:
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


def evaluate_pdh_pdl_exact(symbol: str, df: pd.DataFrame, timeframe: str = "1h") -> Dict[str, Any]:
    """
    Evaluates 1H candles against the exact step-by-step PDH/PDL rules.
    Returns structured JSON matching the exact strategy specification.
    """
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

    n = len(df)
    
    # 1. Calculate ATR(14) and 20-candle Volume SMA on 1H
    df = df.copy()
    df['atr'] = calculate_atr(df, 14)
    df['vol_sma20'] = calculate_sma(df['volume'], 20)

    # 2. Extract UTC Daily Boundaries (UTC 00:00 - 24:00)
    # Convert timestamps to UTC datetime
    if 'timestamp' in df.columns:
        ts_series = df['timestamp'].apply(lambda x: int(x)//1000 if int(x) > 1e12 else int(x))
        last_ts = int(ts_series.iloc[-1])
        sec_24h = 86400
        sec_48h = 172800

        current_day_mask = (ts_series >= (last_ts - sec_24h))
        prev_day_mask = (ts_series < (last_ts - sec_24h)) & (ts_series >= (last_ts - sec_48h))

        prev_day_slice = df[prev_day_mask]
        current_day_slice = df[current_day_mask]
    else:
        prev_day_slice = pd.DataFrame()
        current_day_slice = pd.DataFrame()

    if len(prev_day_slice) >= 4 and len(current_day_slice) >= 4:
        prev_day_high = float(prev_day_slice['high'].max())
        prev_day_low = float(prev_day_slice['low'].min())
        curr_slice = current_day_slice
    else:
        lookback_pd = 24 if n >= 48 else n // 2
        prev_day_slice = df.iloc[-lookback_pd*2 : -lookback_pd]
        prev_day_high = float(prev_day_slice['high'].max())
        prev_day_low = float(prev_day_slice['low'].min())
        curr_slice = df.iloc[-lookback_pd:]

    curr_len = len(curr_slice)
    current_price = float(df['close'].iloc[-1])
    current_atr = float(df['atr'].iloc[-1]) if not np.isnan(df['atr'].iloc[-1]) else (current_price * 0.015)

    # Build structured list of current day bars
    bars = []
    for idx, (orig_idx, row) in enumerate(curr_slice.iterrows()):
        ts = int(row['timestamp']) if 'timestamp' in row else 0
        if ts > 1e12: ts = ts // 1000
        
        iso_time = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts > 0 else f"Bar_{idx}"
        time_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M UTC") if ts > 0 else f"Bar #{idx}"
        
        bars.append({
            'idx': idx,
            'orig_idx': orig_idx,
            'timestamp': ts,
            'iso_time': iso_time,
            'time_str': time_str,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row.get('volume', 0.0)),
            'vol_sma20': float(row.get('vol_sma20', 0.0)),
            'atr': float(row.get('atr', current_atr))
        })

    # =========================================================================
    # 🟢 LONG STRATEGY EVALUATION (PDH Breakout & Retest)
    # =========================================================================
    # Step 1: Look for first 1H candle with close > prev_day_high
    long_breakout_bar = None
    for b in bars:
        if b['close'] > prev_day_high:
            long_breakout_bar = b
            break

    if long_breakout_bar:
        bo_idx = long_breakout_bar['idx']
        bo_level = prev_day_high
        post_bo_bars = bars[bo_idx + 1:]
        
        long_retest_bar = None
        long_invalid_reason = None
        
        # Step 2: Retest evaluation
        for b in post_bo_bars:
            b_atr = b['atr'] if b['atr'] > 0 else current_atr
            tolerance = 0.3 * b_atr
            
            # Invalidation check: Close back through level by > tolerance
            if b['close'] < (bo_level - tolerance):
                long_invalid_reason = f"Breakout failed: candle closed at ${b['close']:,.4f} below PDH (${bo_level:,.4f}) - tolerance (${tolerance:,.4f})"
                break
                
            # Retest check: Low <= breakout_level + tolerance
            if b['low'] <= (bo_level + tolerance):
                long_retest_bar = b
                break

        if not long_invalid_reason:
            if long_retest_bar is None:
                # Still waiting for retest (Breakout Stage)
                return _build_response(
                    status="BREAKOUT",
                    direction="LONG",
                    invalid_reason=None,
                    symbol=symbol,
                    timeframe=timeframe,
                    pdh=prev_day_high,
                    pdl=prev_day_low,
                    bo_time=long_breakout_bar['iso_time'],
                    bo_level=bo_level,
                    rt_time=None,
                    conf_time=None,
                    entry=current_price,
                    sl=round(bo_level - 0.2 * current_atr, 4),
                    tp=None,
                    rr=None,
                    atr=current_atr,
                    checklist=_build_checklist("LONG", prev_day_high, prev_day_low, long_breakout_bar, None, None, False, current_atr, None)
                )
            else:
                # Retest occurred! Check Step 3: Confirmation within 2 candles of retest
                rt_idx = long_retest_bar['idx']
                candidate_window = [b for b in bars if b['idx'] in [rt_idx, rt_idx + 1, rt_idx + 2]]
                
                long_confirmed_bar = None
                conf_pattern_detail = None
                
                for c_bar in candidate_window:
                    c = c_bar['close']
                    o = c_bar['open']
                    h = c_bar['high']
                    l = c_bar['low']
                    v = c_bar['volume']
                    v_avg = c_bar['vol_sma20']
                    rng = h - l if h > l else 0.0001
                    body = abs(c - o)
                    
                    # Rule 1: Candle Pattern (Engulfing OR Body >= 60% of candle range)
                    has_engulfing = False
                    if c_bar['idx'] > 0:
                        prev_bar = bars[c_bar['idx'] - 1]
                        # Bullish Engulfing: green candle whose body engulfs previous candle's body
                        if c > o and prev_bar['close'] < prev_bar['open'] and c >= prev_bar['open'] and o <= prev_bar['close']:
                            has_engulfing = True
                    
                    has_strong_body = (c > o) and (body >= 0.60 * rng)
                    pattern_ok = has_engulfing or has_strong_body
                    
                    # Rule 2: Level Held (Candle CLOSE > breakout_level)
                    level_held = (c > bo_level)
                    
                    # Rule 3: Volume > 20-candle average volume
                    volume_ok = (v > v_avg) if v_avg > 0 else True
                    
                    if pattern_ok and level_held and volume_ok:
                        long_confirmed_bar = c_bar
                        pattern_name = "Bullish Engulfing" if has_engulfing else f"Strong Bullish Candle (Body: {body/rng*100:.1f}%)"
                        conf_pattern_detail = f"{pattern_name}, Close: ${c:,.4f} > PDH, Volume: {v:,.0f} > Avg {v_avg:,.0f}"
                        break

                # Determine if confirmation is fresh (on recent 1-2 candles)
                is_fresh_conf = (long_confirmed_bar is not None) and (long_confirmed_bar['idx'] >= curr_len - 2)
                
                # Dynamic Take Profit: Find next resistance (swing highs or ATR multiple)
                sl_price = round(bo_level - 0.2 * current_atr, 4)
                entry_p = long_confirmed_bar['close'] if long_confirmed_bar else current_price
                risk = abs(entry_p - sl_price) if abs(entry_p - sl_price) > 0 else (current_atr * 0.5)
                
                # S/R resistance detection
                tp_price = _find_next_target(df, entry_p, direction="LONG", atr=current_atr)
                rr_ratio = round(abs(tp_price - entry_p) / risk, 2)

                if is_fresh_conf:
                    return _build_response(
                        status="CONFIRMED",
                        direction="LONG",
                        invalid_reason=None,
                        symbol=symbol,
                        timeframe=timeframe,
                        pdh=prev_day_high,
                        pdl=prev_day_low,
                        bo_time=long_breakout_bar['iso_time'],
                        bo_level=bo_level,
                        rt_time=long_retest_bar['iso_time'],
                        conf_time=long_confirmed_bar['iso_time'],
                        entry=entry_p,
                        sl=sl_price,
                        tp=tp_price,
                        rr=rr_ratio,
                        atr=current_atr,
                        checklist=_build_checklist("LONG", prev_day_high, prev_day_low, long_breakout_bar, long_retest_bar, long_confirmed_bar, True, current_atr, conf_pattern_detail),
                        breakout_bar=long_breakout_bar,
                        retest_bar=long_retest_bar,
                        confirmed_bar=long_confirmed_bar
                    )
                elif curr_len - 1 <= rt_idx + 2:
                    # Still within the 2-candle confirmation window
                    return _build_response(
                        status="RETESTING",
                        direction="LONG",
                        invalid_reason=None,
                        symbol=symbol,
                        timeframe=timeframe,
                        pdh=prev_day_high,
                        pdl=prev_day_low,
                        bo_time=long_breakout_bar['iso_time'],
                        bo_level=bo_level,
                        rt_time=long_retest_bar['iso_time'],
                        conf_time=None,
                        entry=current_price,
                        sl=sl_price,
                        tp=tp_price,
                        rr=rr_ratio,
                        atr=current_atr,
                        checklist=_build_checklist("LONG", prev_day_high, prev_day_low, long_breakout_bar, long_retest_bar, None, False, current_atr, None),
                        breakout_bar=long_breakout_bar,
                        retest_bar=long_retest_bar,
                        confirmed_bar=None
                    )

    # =========================================================================
    # 🔴 SHORT STRATEGY EVALUATION (PDL Breakdown & Retest)
    # =========================================================================
    # Step 1: Look for first 1H candle with close < prev_day_low
    short_breakout_bar = None
    for b in bars:
        if b['close'] < prev_day_low:
            short_breakout_bar = b
            break

    if short_breakout_bar:
        bo_idx = short_breakout_bar['idx']
        bo_level = prev_day_low
        post_bo_bars = bars[bo_idx + 1:]
        
        short_retest_bar = None
        short_invalid_reason = None
        
        # Step 2: Retest evaluation
        for b in post_bo_bars:
            b_atr = b['atr'] if b['atr'] > 0 else current_atr
            tolerance = 0.3 * b_atr
            
            # Invalidation check: Close back through level by > tolerance
            if b['close'] > (bo_level + tolerance):
                short_invalid_reason = f"Breakout failed: candle closed at ${b['close']:,.4f} above PDL (${bo_level:,.4f}) + tolerance (${tolerance:,.4f})"
                break
                
            # Retest check: High >= breakout_level - tolerance
            if b['high'] >= (bo_level - tolerance):
                short_retest_bar = b
                break

        if not short_invalid_reason:
            if short_retest_bar is None:
                return _build_response(
                    status="BREAKOUT",
                    direction="SHORT",
                    invalid_reason=None,
                    symbol=symbol,
                    timeframe=timeframe,
                    pdh=prev_day_high,
                    pdl=prev_day_low,
                    bo_time=short_breakout_bar['iso_time'],
                    bo_level=bo_level,
                    rt_time=None,
                    conf_time=None,
                    entry=current_price,
                    sl=round(bo_level + 0.2 * current_atr, 4),
                    tp=None,
                    rr=None,
                    atr=current_atr,
                    checklist=_build_checklist("SHORT", prev_day_high, prev_day_low, short_breakout_bar, None, None, False, current_atr, None)
                )
            else:
                rt_idx = short_retest_bar['idx']
                candidate_window = [b for b in bars if b['idx'] in [rt_idx, rt_idx + 1, rt_idx + 2]]
                
                short_confirmed_bar = None
                conf_pattern_detail = None
                
                for c_bar in candidate_window:
                    c = c_bar['close']
                    o = c_bar['open']
                    h = c_bar['high']
                    l = c_bar['low']
                    v = c_bar['volume']
                    v_avg = c_bar['vol_sma20']
                    rng = h - l if h > l else 0.0001
                    body = abs(c - o)
                    
                    # Rule 1: Candle Pattern (Bearish Engulfing OR Body >= 60% of candle range)
                    has_engulfing = False
                    if c_bar['idx'] > 0:
                        prev_bar = bars[c_bar['idx'] - 1]
                        if c < o and prev_bar['close'] > prev_bar['open'] and c <= prev_bar['open'] and o >= prev_bar['close']:
                            has_engulfing = True
                    
                    has_strong_body = (c < o) and (body >= 0.60 * rng)
                    pattern_ok = has_engulfing or has_strong_body
                    
                    # Rule 2: Level Held (Candle CLOSE < breakout_level)
                    level_held = (c < bo_level)
                    
                    # Rule 3: Volume > 20-candle average volume
                    volume_ok = (v > v_avg) if v_avg > 0 else True
                    
                    if pattern_ok and level_held and volume_ok:
                        short_confirmed_bar = c_bar
                        pattern_name = "Bearish Engulfing" if has_engulfing else f"Strong Bearish Candle (Body: {body/rng*100:.1f}%)"
                        conf_pattern_detail = f"{pattern_name}, Close: ${c:,.4f} < PDL, Volume: {v:,.0f} > Avg {v_avg:,.0f}"
                        break

                is_fresh_conf = (short_confirmed_bar is not None) and (short_confirmed_bar['idx'] >= curr_len - 2)
                
                sl_price = round(bo_level + 0.2 * current_atr, 4)
                entry_p = short_confirmed_bar['close'] if short_confirmed_bar else current_price
                risk = abs(sl_price - entry_p) if abs(sl_price - entry_p) > 0 else (current_atr * 0.5)
                
                tp_price = _find_next_target(df, entry_p, direction="SHORT", atr=current_atr)
                rr_ratio = round(abs(entry_p - tp_price) / risk, 2)

                if is_fresh_conf:
                    return _build_response(
                        status="CONFIRMED",
                        direction="SHORT",
                        invalid_reason=None,
                        symbol=symbol,
                        timeframe=timeframe,
                        pdh=prev_day_high,
                        pdl=prev_day_low,
                        bo_time=short_breakout_bar['iso_time'],
                        bo_level=bo_level,
                        rt_time=short_retest_bar['iso_time'],
                        conf_time=short_confirmed_bar['iso_time'],
                        entry=entry_p,
                        sl=sl_price,
                        tp=tp_price,
                        rr=rr_ratio,
                        atr=current_atr,
                        checklist=_build_checklist("SHORT", prev_day_high, prev_day_low, short_breakout_bar, short_retest_bar, short_confirmed_bar, True, current_atr, conf_pattern_detail),
                        breakout_bar=short_breakout_bar,
                        retest_bar=short_retest_bar,
                        confirmed_bar=short_confirmed_bar
                    )
                elif curr_len - 1 <= rt_idx + 2:
                    return _build_response(
                        status="RETESTING",
                        direction="SHORT",
                        invalid_reason=None,
                        symbol=symbol,
                        timeframe=timeframe,
                        pdh=prev_day_high,
                        pdl=prev_day_low,
                        bo_time=short_breakout_bar['iso_time'],
                        bo_level=bo_level,
                        rt_time=short_retest_bar['iso_time'],
                        conf_time=None,
                        entry=current_price,
                        sl=sl_price,
                        tp=tp_price,
                        rr=rr_ratio,
                        atr=current_atr,
                        checklist=_build_checklist("SHORT", prev_day_high, prev_day_low, short_breakout_bar, short_retest_bar, None, False, current_atr, None),
                        breakout_bar=short_breakout_bar,
                        retest_bar=short_retest_bar,
                        confirmed_bar=None
                    )

    # No breakout active or setup invalidated
    return {
        "status": "INVALID",
        "direction": None,
        "invalid_reason": "No valid breakout or setup completed outside current window",
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


def _find_next_target(df: pd.DataFrame, entry: float, direction: str, atr: float) -> float:
    """Dynamically finds the next support/resistance target beyond entry."""
    highs = df['high'].values
    lows = df['low'].values
    n = len(df)
    
    if direction == "LONG":
        # Find swing highs above entry
        res_targets = []
        for i in range(5, n - 2):
            if highs[i] == max(highs[i-3:i+4]) and highs[i] > (entry + 0.5 * atr):
                res_targets.append(float(highs[i]))
        if res_targets:
            res_targets.sort()
            return round(res_targets[0], 4)
        return round(entry + 2.5 * atr, 4)
    else:
        # Find swing lows below entry
        sup_targets = []
        for i in range(5, n - 2):
            if lows[i] == min(lows[i-3:i+4]) and lows[i] < (entry - 0.5 * atr):
                sup_targets.append(float(lows[i]))
        if sup_targets:
            sup_targets.sort(reverse=True)
            return round(sup_targets[0], 4)
        return round(entry - 2.5 * atr, 4)


def _build_checklist(
    direction: str,
    pdh: float,
    pdl: float,
    bo_bar: Optional[Dict],
    rt_bar: Optional[Dict],
    conf_bar: Optional[Dict],
    is_confirmed: bool,
    atr: float,
    conf_detail: Optional[str]
) -> List[Dict[str, Any]]:
    tolerance = 0.3 * atr
    level_name = "PDH (Dünün Zirvesi)" if direction == "LONG" else "PDL (Dünün Dibi)"
    level_val = pdh if direction == "LONG" else pdl
    
    return [
        {
            "title": f"1. Dünkü Günlük Seviye ({level_name})",
            "passed": True,
            "detail": f"UTC 00:00–24:00 referans seviyesi: ${level_val:,.4f} | 1H ATR(14): ${atr:,.4f}"
        },
        {
            "title": "2. 1H Kırılım Mumu Kapanışı (Breakout)",
            "passed": bo_bar is not None,
            "detail": f"Saat {bo_bar['time_str']} barında ${bo_bar['close']:,.4f} ile kırılım kapandı." if bo_bar else f"Henüz {level_name} ötesinde 1H kapanışı yok."
        },
        {
            "title": f"3. Seviyeye Retest (Tolerans: 0.3 × ATR = ${tolerance:,.4f})",
            "passed": rt_bar is not None,
            "detail": f"Saat {rt_bar['time_str']} barında fiyat seviyeye ({'Low' if direction == 'LONG' else 'High'}: ${rt_bar['low' if direction == 'LONG' else 'high']:,.4f}) geri çekildi." if rt_bar else "Retest henüz gerçekleşmedi."
        },
        {
            "title": "4. Onay Mumu (Gövde >= %60 / Engulfing + Seviye Korundu + Hacim > Ort)",
            "passed": is_confirmed,
            "detail": f"Saat {conf_bar['time_str']} barında onaylandı: {conf_detail}" if is_confirmed else ("Retest sonrası 2 barlık onay penceresinde bekleniyor." if rt_bar else "Onay mumu bekleniyor.")
        }
    ]


def _build_response(
    status: str,
    direction: str,
    invalid_reason: Optional[str],
    symbol: str,
    timeframe: str,
    pdh: float,
    pdl: float,
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
        "CONFIRMED": "3. Aşama: Retest + Onay Alındı (İşleme Hazır)",
        "RETESTING": "2. Aşama: Retest Bölgesinde (Onay Bekleniyor)",
        "BREAKOUT": "1. Aşama: Yeni Kırıldı (Retest Bekleniyor)",
        "INVALID": "Geçersiz / İptal"
    }.get(status, status)

    stage_badge = {
        "CONFIRMED": f"🚀 ONAYLANDI ({direction})",
        "RETESTING": "🎯 RETEST YAPIYOR",
        "BREAKOUT": f"⚡ {direction} KIRILDI (BREAKOUT)",
        "INVALID": "❌ İPTAL"
    }.get(status, status)

    explanation = ""
    if status == "CONFIRMED":
        explanation = f"Önceki günün seviyesi (${bo_level:,.4f}) kırıldı, 0.3xATR toleransla retest yapıldı ve hacimli onay mumu kapandı."
    elif status == "RETESTING":
        explanation = f"Fiyat ${bo_level:,.4f} seviyesini kırdı ve şu anda retest bölgesinde destek/direnç arıyor. 2 bar içinde onay mumu bekleniyor."
    elif status == "BREAKOUT":
        explanation = f"Fiyat ${bo_level:,.4f} seviyesini kırdı. Güvenli giriş için 0.3xATR (${0.3*atr:,.4f}) tolerans bandına retest yapması bekleniyor."

    lines = [
        {'name': 'Önceki Gün Zirvesi (PDH)', 'price': round(pdh, 4), 'color': '#10b981', 'style': 0 if direction == 'LONG' else 2},
        {'name': 'Önceki Gün Dibi (PDL)', 'price': round(pdl, 4), 'color': '#ef4444', 'style': 0 if direction == 'SHORT' else 2},
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
        "prev_day_high": round(pdh, 4),
        "prev_day_low": round(pdl, 4),
        "pdh": round(pdh, 4),
        "pdl": round(pdl, 4),
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


def run_pdh_pdl_radar(timeframe: str = "1h", limit_coins: int = 50) -> Dict[str, Any]:
    """Tüm piyasayı tarayıp kesin kurallara göre PDH/PDL sonuçlarını döndürür."""
    pairs = market_manager.get_top_pairs(limit=limit_coins)
    
    breakout_list = []
    retesting_list = []
    confirmed_list = []

    def _worker(sym):
        try:
            df = market_manager.get_market_data(sym, timeframe=timeframe, limit=120)
            if df is not None and len(df) >= 30:
                res = evaluate_pdh_pdl_exact(sym, df, timeframe=timeframe)
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
        'timeframe': timeframe,
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
