"""
CryptoSignalPro AI - Swing High/Low Breakout-Retest Strategy Engine (v10.0.0)

Strict rule-based detector implementing the exact mathematical rules:
1. 1H candles (OHLCV)
2. swing_lookback (default: 3) -> is_swing_high(i) & is_swing_low(i)
   NO LOOK-AHEAD BIAS: A swing point at index i is confirmed only after swing_lookback candles close after it.
3. Reference level (swing_level): Most recently confirmed swing high (LONG) or swing low (SHORT)
4. 1H Breakout: candle CLOSE > swing_level (LONG) or CLOSE < swing_level (SHORT)
   - Taze Kırılım Kuralı: Son 12 bar içinde gerçekleşmelidir.
5. 1H Retest: tolerance = 0.35 * ATR(14)
   - Taze Retest Aralığı: Kırılımdan sonraki EN FAZLA 8 bar içinde olmalıdır (1 <= k - breakout_idx <= 8).
   - LONG: low <= breakout_level + tolerance VE close >= breakout_level - tolerance * 0.7
   - SHORT: high >= breakout_level - tolerance VE close <= breakout_level + tolerance * 0.7
   - Invalidation: candle CLOSE through level by > tolerance on wrong side.
6. 1H Confirmation (within 2 candles of retest):
   - Pattern: Engulfing OR body >= 50% of candle range in breakout direction
   - Level held: candle CLOSE still on breakout side of breakout_level
   - Volume: candle volume >= 80% of 20-candle average volume
   - Taze Onay: Son 3 bar içinde taze kapanmış olmalıdır.
7. Risk levels:
   - Stop loss: breakout_level - 0.25 * ATR (LONG) or breakout_level + 0.25 * ATR (SHORT)
   - Take profit: next significant support/resistance level in trade direction (dynamic)
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
    # Step 1: Detect Confirmed Swing Points (No Look-Ahead Bias)
    # -------------------------------------------------------------
    confirmed_swing_highs = []
    confirmed_swing_lows = []

    for i in range(swing_lookback, n - swing_lookback):
        conf_idx = i + swing_lookback
        
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

    # Find the best candidate: Long or Short
    candidates = []
    if confirmed_swing_highs:
        candidates.append(("LONG", confirmed_swing_highs[-1]))
    if confirmed_swing_lows:
        candidates.append(("SHORT", confirmed_swing_lows[-1]))

    if not candidates:
        return {
            "status": "INVALID",
            "direction": None,
            "invalid_reason": "no_confirmed_swings",
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

    # Evaluate best direction
    best_eval = None
    for dir_cand, sw_cand in candidates:
        ev = _evaluate_single_swing_direction(
            dir_cand, sw_cand, df, highs, lows, opens, closes, volumes, vol_sma20, atrs,
            timestamps, iso_times, time_strs, current_price, current_atr, symbol, timeframe, n
        )
        if ev and ev.get("status") in ["CONFIRMED", "RETESTING", "BREAKOUT"]:
            best_eval = ev
            if ev.get("status") in ["CONFIRMED", "RETESTING"]:
                break

    return best_eval if best_eval else _evaluate_single_swing_direction(
        candidates[0][0], candidates[0][1], df, highs, lows, opens, closes, volumes, vol_sma20, atrs,
        timestamps, iso_times, time_strs, current_price, current_atr, symbol, timeframe, n
    )


def _evaluate_single_swing_direction(
    direction: str,
    latest_swing: Dict[str, Any],
    df: pd.DataFrame,
    highs, lows, opens, closes, volumes, vol_sma20, atrs,
    timestamps, iso_times, time_strs,
    current_price: float,
    current_atr: float,
    symbol: str,
    timeframe: str,
    n: int
) -> Dict[str, Any]:
    swing_level = latest_swing['price']
    swing_conf_idx = latest_swing['conf_idx']
    swing_conf_time = latest_swing['conf_time']
    swing_time_str = latest_swing['swing_time_str']

    # Step 2: Taze Kırılım Tespiti (Son 12 bar içinde)
    search_start = max(swing_conf_idx, n - 12)
    breakout_idx = None
    for k in range(search_start, n):
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
            "invalid_reason": f"No fresh breakout close beyond swing level (${swing_level:,.4f})",
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
    tolerance = 0.35 * bo_atr

    # Step 3: Taze Retest (Kırılımdan sonraki EN FAZLA 8 bar içinde)
    retest_idx = None
    invalid_reason = None
    max_retest_limit = min(n, breakout_idx + 9)

    for k in range(breakout_idx + 1, max_retest_limit):
        k_atr = atrs[k] if atrs[k] > 0 else bo_atr
        k_tolerance = 0.35 * k_atr

        if direction == "LONG" and closes[k] < (bo_level - k_tolerance):
            invalid_reason = f"Breakout failed: candle closed at ${closes[k]:,.4f} below swing level"
            break
        elif direction == "SHORT" and closes[k] > (bo_level + k_tolerance):
            invalid_reason = f"Breakout failed: candle closed at ${closes[k]:,.4f} above swing level"
            break

        if direction == "LONG" and lows[k] <= (bo_level + k_tolerance) and closes[k] >= (bo_level - k_tolerance * 0.7):
            retest_idx = k
            break
        elif direction == "SHORT" and highs[k] >= (bo_level - k_tolerance) and closes[k] <= (bo_level + k_tolerance * 0.7):
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

    sl_price = round(bo_level - 0.25 * current_atr, 4) if direction == "LONG" else round(bo_level + 0.25 * current_atr, 4)
    tp_price = _find_next_swing_target(df, current_price, direction=direction, atr=current_atr)
    risk = max(current_atr * 0.25, abs(current_price - sl_price))
    reward = max(0.0001, abs(tp_price - current_price))
    rr_ratio = round(reward / risk, 1)

    if retest_idx is None:
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
            tp=tp_price,
            rr=rr_ratio,
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

    # Step 4: Confirmation (On retest candle or within 2 candles after it)
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
        rng = max(0.0001, h - l)
        body = abs(c - o)

        has_engulfing = False
        if k > 0:
            prev_c = closes[k-1]
            prev_o = opens[k-1]
            if direction == "LONG" and c > o and prev_c < prev_o and c >= prev_o and o <= prev_c:
                has_engulfing = True
            elif direction == "SHORT" and c < o and prev_c > prev_o and c <= prev_o and o >= prev_c:
                has_engulfing = True

        has_strong_body = (c > o if direction == "LONG" else c < o) and (body >= 0.45 * rng)
        pattern_ok = has_engulfing or has_strong_body
        level_held = (c >= bo_level if direction == "LONG" else c <= bo_level)
        volume_ok = (v >= v_avg * 0.80) if v_avg > 0 else True

        if pattern_ok and level_held and volume_ok:
            conf_idx = k
            pattern_name = f"{'Bullish' if direction == 'LONG' else 'Bearish'} Engulfing" if has_engulfing else f"Strong Directional Candle (Body: {body/rng*100:.1f}%)"
            conf_pattern_detail = f"{pattern_name}, Close: ${c:,.4f}"
            break

    is_fresh_conf = (conf_idx is not None) and (n - 1 - conf_idx <= 3)
    entry_p = float(closes[conf_idx]) if conf_idx is not None else current_price
    risk = max(current_atr * 0.25, abs(entry_p - sl_price))
    reward = max(0.0001, abs(tp_price - entry_p))
    rr_ratio = round(reward / risk, 1)

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
    elif n - 1 - retest_idx <= 3:
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
    else:
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
            tp=tp_price,
            rr=rr_ratio,
            atr=current_atr,
            checklist=_build_swing_checklist(direction, swing_level, bo_bar, None, None, False, current_atr, None),
            breakout_bar=bo_bar,
            retest_bar=None,
            confirmed_bar=None
        )


def _find_next_swing_target(df: pd.DataFrame, entry: float, direction: str, atr: float) -> float:
    if df is None or len(df) == 0:
        return round(entry + 2.5 * atr, 4) if direction == "LONG" else round(entry - 2.5 * atr, 4)
    
    if direction == "LONG":
        highs = df['high'].values
        higher_highs = [h for h in highs[-50:] if h > entry * 1.01]
        if higher_highs:
            return round(float(min(higher_highs)), 4)
        return round(entry + 2.5 * atr, 4)
    else:
        lows = df['low'].values
        lower_lows = [l for l in lows[-50:] if l < entry * 0.99]
        if lower_lows:
            return round(float(max(lower_lows)), 4)
        return round(entry - 2.5 * atr, 4)


def _build_swing_checklist(direction: str, swing_level: float, bo_bar: Optional[Dict], rt_bar: Optional[Dict], conf_bar: Optional[Dict], has_confirmed: bool, atr: float, conf_detail: Optional[str]) -> List[Dict[str, Any]]:
    level_name = f"Swing {'High (Zirve)' if direction == 'LONG' else 'Low (Dip)'}"
    tol = 0.35 * atr

    return [
        {
            "step": 1,
            "title": f"1. 1H Kırılım (Breakout): {level_name} (${swing_level:,.4f})",
            "passed": bo_bar is not None,
            "detail": f"Saat {bo_bar['time_str']} barında mum kapanışı (${bo_bar['close']:,.4f}) ile seviye kırıldı." if bo_bar else f"Fiyatın ${swing_level:,.4f} seviyesi ötesinde 1H mum kapatması bekleniyor."
        },
        {
            "step": 2,
            "title": f"2. 1H Retest: 0.35xATR Tolerans (${tol:,.4f}) ile Seviye Testi",
            "passed": rt_bar is not None,
            "detail": f"Saat {rt_bar['time_str']} barında fitil seviyeye değdi ve seviye tutundu." if rt_bar else "Kırılan swing seviyesine geri çekilme (Pullback) bekleniyor."
        },
        {
            "step": 3,
            "title": "3. 1H Onay Mumu (Engulfing veya Gövde >= %45 & Hacim)",
            "passed": has_confirmed and conf_bar is not None,
            "detail": f"Saat {conf_bar['time_str']} barında onaylandı ({conf_detail})." if conf_bar else "Retest sonrası yönlü hacimli onay mumu bekleniyor."
        },
        {
            "step": 4,
            "title": "4. Risk Yönetimi: Stop Loss & Dinamik Kâr Al Seviyeleri",
            "passed": True,
            "detail": f"Stop Loss: 0.25xATR emniyet marjı ile seviyenin gerisine kuruldu."
        }
    ]


def _build_swing_response(status: str, direction: str, invalid_reason: Optional[str], symbol: str, timeframe: str, swing_level: float, swing_conf_time: str, bo_time: Optional[str], bo_level: float, rt_time: Optional[str], conf_time: Optional[str], entry: float, sl: float, tp: Optional[float], rr: Optional[float], atr: float, checklist: List[Dict[str, Any]], breakout_bar: Optional[Dict] = None, retest_bar: Optional[Dict] = None, confirmed_bar: Optional[Dict] = None) -> Dict[str, Any]:
    return {
        "status": status,
        "direction": direction,
        "invalid_reason": invalid_reason,
        "symbol": symbol,
        "timeframe": timeframe,
        "swing_level": swing_level,
        "swing_confirmed_time": swing_conf_time,
        "breakout_time": bo_time,
        "breakout_level": bo_level,
        "retest_time": rt_time,
        "confirmation_time": conf_time,
        "entry_price": entry,
        "stop_loss": sl,
        "take_profit": tp,
        "risk_reward": rr,
        "atr": atr,
        "checklist": checklist,
        "breakout_bar": breakout_bar,
        "retest_bar": retest_bar,
        "confirmed_bar": confirmed_bar
    }


def run_swing_radar(timeframe: str = "1h", limit_coins: int = 50, swing_lookback: int = 3) -> Dict[str, Any]:
    pairs = market_manager.get_top_pairs(limit=limit_coins)
    
    stages = {
        "breakout": [],
        "retesting": [],
        "confirmed": []
    }

    def _eval(sym):
        try:
            df = market_manager.get_market_data(sym, timeframe=timeframe, limit=100)
            if df is not None and len(df) >= (swing_lookback * 2 + 10):
                res = evaluate_swing_strategy_exact(sym, df, timeframe=timeframe, swing_lookback=swing_lookback)
                if res and res.get("status") in ["BREAKOUT", "RETESTING", "CONFIRMED"]:
                    return {
                        "symbol": sym,
                        "timeframe": timeframe,
                        "strategy_name": f"Yapısal Swing {'High' if res['direction'] == 'LONG' else 'Low'}",
                        "stage": res["status"],
                        "stage_name": "3. Aşama: Retest + Onay Alındı (İşleme Hazır)" if res["status"] == "CONFIRMED" else ("2. Aşama: Retest Bölgesinde (Onay Bekleniyor)" if res["status"] == "RETESTING" else "1. Aşama: Yeni Kırıldı (Retest Bekleniyor)"),
                        "direction": res["direction"],
                        "current_price": res.get("entry_price") or float(df['close'].iloc[-1]),
                        "swing_level": res["swing_level"],
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
                        "explanation": f"{sym} 1H grafiğinde teyitli Swing {'High Zirve' if res['direction'] == 'LONG' else 'Low Dip'} kırılımı ve retest süreci incelendi."
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
        "strategy": "SWING_HL",
        "timeframe": timeframe,
        "stats": stats,
        "stages": stages
    }
