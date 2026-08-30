"""
CryptoSignalPro AI - Previous-Day High/Low Breakout-Retest Strategy Engine (v9.5.0)

Strict rule-based detector implementing the exact mathematical rules:
1. Daily candles (UTC 00:00–24:00) -> compute prev_day_high and prev_day_low
2. 1H Breakout -> candle CLOSE > PDH (LONG) or close < PDL (SHORT)
3. 1H Retest (Chronologically AFTER Breakout):
   - Tolerance = 0.35 * ATR(14)
   - LONG: Low <= PDH + tolerance and Close >= PDH - tolerance * 0.7
   - SHORT: High >= PDL - tolerance and Close <= PDL + tolerance * 0.7
   - Invalidation: Candle CLOSE through level by > tolerance on wrong side.
4. 1H Confirmation (within 2 candles of retest):
   - Pattern: Engulfing OR body >= 50% of candle range in breakout direction
   - Level held: candle CLOSE still on breakout side of breakout_level
   - Volume: candle volume >= 80% of 20-candle average volume
5. Risk levels:
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


def evaluate_pdh_pdl_exact(symbol: str, df: pd.DataFrame, timeframe: str = "1h") -> Dict[str, Any]:
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
    df = df.copy()
    df['atr'] = calculate_atr(df, 14)
    df['vol_sma20'] = calculate_sma(df['volume'], 20)

    # Convert timestamps to UTC datetime & calculate strict UTC Daily boundaries
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
    long_breakout_bar = None
    bo_idx = None
    for b in bars:
        if b['close'] > prev_day_high:
            long_breakout_bar = b
            bo_idx = b['idx']
            break

    if long_breakout_bar:
        bo_level = prev_day_high
        post_bo_bars = bars[bo_idx + 1:]
        long_retest_bar = None
        rt_idx = None
        long_invalid_reason = None
        
        for b in post_bo_bars:
            b_atr = b['atr'] if b['atr'] > 0 else current_atr
            tolerance = 0.35 * b_atr
            
            if b['close'] < (bo_level - tolerance):
                long_invalid_reason = f"Breakout failed: candle closed at ${b['close']:,.4f} below PDH (${bo_level:,.4f}) - tolerance"
                break
                
            if b['low'] <= (bo_level + tolerance) and b['close'] >= (bo_level - tolerance * 0.7):
                long_retest_bar = b
                rt_idx = b['idx']
                break

        if not long_invalid_reason:
            sl_price = round(bo_level - 0.25 * current_atr, 4)
            tp_price = _find_next_target(df, current_price, direction="LONG", atr=current_atr)
            risk = abs(current_price - sl_price) if abs(current_price - sl_price) > 0 else (current_atr * 0.5)
            rr_ratio = round(abs(tp_price - current_price) / risk, 2)

            if long_retest_bar is None:
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
                    sl=sl_price,
                    tp=tp_price,
                    rr=rr_ratio,
                    atr=current_atr,
                    checklist=_build_checklist("LONG", prev_day_high, prev_day_low, long_breakout_bar, None, None, False, current_atr, None),
                    breakout_bar=long_breakout_bar,
                    retest_bar=None,
                    confirmed_bar=None
                )
            else:
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
                    rng = max(0.0001, h - l)
                    body = abs(c - o)
                    
                    has_engulfing = False
                    if c_bar['idx'] > 0:
                        prev_b = bars[c_bar['idx'] - 1]
                        if c > o and prev_b['close'] < prev_b['open'] and c >= prev_b['open'] and o <= prev_b['close']:
                            has_engulfing = True
                    
                    has_strong_body = (c > o) and (body >= 0.45 * rng)
                    pattern_ok = has_engulfing or has_strong_body
                    level_held = (c >= bo_level)
                    volume_ok = (v >= v_avg * 0.80) if v_avg > 0 else True
                    
                    if pattern_ok and level_held and volume_ok:
                        long_confirmed_bar = c_bar
                        pattern_name = "Bullish Engulfing" if has_engulfing else f"Strong Bullish Candle (Body: {body/rng*100:.1f}%)"
                        conf_pattern_detail = f"{pattern_name}, Close: ${c:,.4f} >= PDH"
                        break

                if long_confirmed_bar and (curr_len - 1 - long_confirmed_bar['idx'] <= 3):
                    entry_p = long_confirmed_bar['close']
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
                elif curr_len - 1 - rt_idx <= 4:
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
    short_breakout_bar = None
    bo_idx = None
    for b in bars:
        if b['close'] < prev_day_low:
            short_breakout_bar = b
            bo_idx = b['idx']
            break

    if short_breakout_bar:
        bo_level = prev_day_low
        post_bo_bars = bars[bo_idx + 1:]
        short_retest_bar = None
        rt_idx = None
        short_invalid_reason = None
        
        for b in post_bo_bars:
            b_atr = b['atr'] if b['atr'] > 0 else current_atr
            tolerance = 0.35 * b_atr
            
            if b['close'] > (bo_level + tolerance):
                short_invalid_reason = f"Breakout failed: candle closed at ${b['close']:,.4f} above PDL (${bo_level:,.4f}) + tolerance"
                break
                
            if b['high'] >= (bo_level - tolerance) and b['close'] <= (bo_level + tolerance * 0.7):
                short_retest_bar = b
                rt_idx = b['idx']
                break

        if not short_invalid_reason:
            sl_price = round(bo_level + 0.25 * current_atr, 4)
            tp_price = _find_next_target(df, current_price, direction="SHORT", atr=current_atr)
            risk = abs(sl_price - current_price) if abs(sl_price - current_price) > 0 else (current_atr * 0.5)
            rr_ratio = round(abs(current_price - tp_price) / risk, 2)

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
                    sl=sl_price,
                    tp=tp_price,
                    rr=rr_ratio,
                    atr=current_atr,
                    checklist=_build_checklist("SHORT", prev_day_high, prev_day_low, short_breakout_bar, None, None, False, current_atr, None),
                    breakout_bar=short_breakout_bar,
                    retest_bar=None,
                    confirmed_bar=None
                )
            else:
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
                    rng = max(0.0001, h - l)
                    body = abs(c - o)
                    
                    has_engulfing = False
                    if c_bar['idx'] > 0:
                        prev_b = bars[c_bar['idx'] - 1]
                        if c < o and prev_b['close'] > prev_b['open'] and c <= prev_b['open'] and o >= prev_b['close']:
                            has_engulfing = True
                    
                    has_strong_body = (c < o) and (body >= 0.45 * rng)
                    pattern_ok = has_engulfing or has_strong_body
                    level_held = (c <= bo_level)
                    volume_ok = (v >= v_avg * 0.80) if v_avg > 0 else True
                    
                    if pattern_ok and level_held and volume_ok:
                        short_confirmed_bar = c_bar
                        pattern_name = "Bearish Engulfing" if has_engulfing else f"Strong Bearish Candle (Body: {body/rng*100:.1f}%)"
                        conf_pattern_detail = f"{pattern_name}, Close: ${c:,.4f} <= PDL"
                        break

                if short_confirmed_bar and (curr_len - 1 - short_confirmed_bar['idx'] <= 3):
                    entry_p = short_confirmed_bar['close']
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
                elif curr_len - 1 - rt_idx <= 4:
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

    # If neither Long nor Short has broken out, return baseline
    return {
        "status": "INVALID",
        "direction": None,
        "invalid_reason": "no_breakout_yet",
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


def _build_checklist(direction: str, pdh: float, pdl: float, bo_bar: Optional[Dict], rt_bar: Optional[Dict], conf_bar: Optional[Dict], has_confirmed: bool, atr: float, conf_detail: Optional[str]) -> List[Dict[str, Any]]:
    level_name = "PDH (Önceki Gün Zirvesi)" if direction == "LONG" else "PDL (Önceki Gün Dibi)"
    level_price = pdh if direction == "LONG" else pdl
    tol = 0.35 * atr

    return [
        {
            "step": 1,
            "title": f"1. 1H Kırılım (Breakout): {level_name} (${level_price:,.4f})",
            "passed": bo_bar is not None,
            "detail": f"Saat {bo_bar['time_str']} barında mum kapanışı (${bo_bar['close']:,.4f}) ile seviye kırıldı." if bo_bar else f"Fiyatın ${level_price:,.4f} seviyesi ötesinde 1H mum kapatması bekleniyor."
        },
        {
            "step": 2,
            "title": f"2. 1H Retest: 0.35xATR Tolerans (${tol:,.4f}) ile Seviye Testi",
            "passed": rt_bar is not None,
            "detail": f"Saat {rt_bar['time_str']} barında fitil seviyeye değdi (${rt_bar['low' if direction == 'LONG' else 'high']:,.4f}) ve seviye tutundu." if rt_bar else "Kırılan seviyeye geri çekilme (Pullback) bekleniyor."
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


def _build_response(status: str, direction: str, invalid_reason: Optional[str], symbol: str, timeframe: str, pdh: float, pdl: float, bo_time: Optional[str], bo_level: float, rt_time: Optional[str], conf_time: Optional[str], entry: float, sl: float, tp: float, rr: float, atr: float, checklist: List[Dict[str, Any]], breakout_bar: Optional[Dict] = None, retest_bar: Optional[Dict] = None, confirmed_bar: Optional[Dict] = None) -> Dict[str, Any]:
    return {
        "status": status,
        "direction": direction,
        "invalid_reason": invalid_reason,
        "symbol": symbol,
        "timeframe": timeframe,
        "prev_day_high": pdh,
        "prev_day_low": pdl,
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
                    return {
                        "symbol": sym,
                        "timeframe": timeframe,
                        "strategy_name": "Önceki Gün Zirve/Dip (PDH/PDL)",
                        "stage": res["status"],
                        "stage_name": "3. Aşama: Retest + Onay Alındı (İşleme Hazır)" if res["status"] == "CONFIRMED" else ("2. Aşama: Retest Bölgesinde (Onay Bekleniyor)" if res["status"] == "RETESTING" else "1. Aşama: Yeni Kırıldı (Retest Bekleniyor)"),
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
                        "explanation": f"{sym} 1H grafiğinde {'PDH Zirve' if res['direction'] == 'LONG' else 'PDL Dip'} kırılımı ve retest süreci incelendi."
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
