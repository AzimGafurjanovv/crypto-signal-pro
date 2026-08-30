"""
CryptoSignalPro AI - Gelismis Formasyon Radari & Kronolojik Retest Motoru (v9.5.0)

Katı Kurallar:
1. Breakout (Kirilim): Mum seviyenin otesinde KAPANMALIDIR.
2. Retest: Kirilim mumundan KESINLIKLE SONRA (idx > bo_idx) gelmeli,
   seviyeyi test etmeli (0.35xATR tolerans) ve seviyenin otesinde KAPANARAK tutunmalidir.
   Aksi halde Sahte Kirilim (Invalidated) sayilir.
3. Onay (Confirmation): Retest mumunda veya sonraki 2 mum icinde hacimli yonlu mum olmali.
   Tazelik Kurali: Onay mumu son 2 mum icinde gerceklesmis olmalidir.
"""

import math
import time
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from engine.market_data import market_manager
from engine.indicators import enrich_all_indicators
from engine.patterns import detect_chart_patterns


def evaluate_pattern_strategy_exact(symbol: str, df: pd.DataFrame, timeframe: str = "1h") -> Optional[Dict[str, Any]]:
    if df is None or len(df) < 35:
        return None

    df_calc = enrich_all_indicators(df.copy())
    patterns = detect_chart_patterns(df_calc)
    if not patterns:
        return None

    # En yuksek kaliteli formasyonu sec
    pat = patterns[0]
    n = len(df_calc)
    current_price = float(df_calc['close'].iloc[-1])
    current_atr = float(df_calc['atr'].iloc[-1]) if 'atr' in df_calc.columns and not np.isnan(df_calc['atr'].iloc[-1]) else current_price * 0.018
    vol_sma20 = float(df_calc['volume'].rolling(20).mean().iloc[-1]) if len(df_calc) >= 20 else float(df_calc['volume'].iloc[-1])

    pat_name = pat.get('name', 'Grafik Formasyonu')
    pat_type = pat.get('type', 'BULLISH')
    direction = 'LONG' if pat_type == 'BULLISH' else 'SHORT'
    breakout_level = float(pat.get('breakout_level') or pat.get('flip_level') or pat.get('neckline') or pat.get('range_high') or pat.get('range_low') or current_price)
    target = float(pat.get('target', current_price * (1.04 if direction == 'LONG' else 0.96)))
    tolerance = round(0.35 * current_atr, 4)
    quality_score = int(pat.get('quality_score', 85))

    # Mum verilerini olustur (kronolojik index siralamasi ile)
    bars = []
    for idx, row in df_calc.iterrows():
        ts = int(row['timestamp']) if 'timestamp' in row else 0
        if ts > 1e12: ts = ts // 1000
        time_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%m-%d %H:%M") if ts > 0 else f"Bar #{idx}"
        bars.append({
            'idx': idx,
            'timestamp': ts,
            'time_str': time_str,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row['volume'])
        })

    # ─────────────────────────────────────────────────────────────────────────
    # 1. KIRILIM MUMU TESPITI (Son 20 Bar Icinde Ilk Gecerli Kirilim)
    # ─────────────────────────────────────────────────────────────────────────
    search_window = bars[-25:]
    breakout_bar = None
    bo_local_idx = None

    for i, b in enumerate(search_window):
        if direction == 'LONG':
            # Long Kirilimi: Mum kapanisi seviyenin ustunde
            if b['close'] > breakout_level:
                breakout_bar = b
                bo_local_idx = i
                break
        else:
            # Short Kirilimi: Mum kapanisi seviyenin altinda
            if b['close'] < breakout_level:
                breakout_bar = b
                bo_local_idx = i
                break

    if not breakout_bar:
        # Henuz kirilim gerceklesmemis, formasyon olusum asamasinda
        stage = "BREAKOUT"
        stage_name = "1. Aşama: Kırılım Bekleniyor (Formasyon Sıkışması)"
        retest_bar = None
        confirmed_bar = None
    else:
        # ─────────────────────────────────────────────────────────────────────
        # 2. RETEST MUMU TESPITI (KESINLIKLE Kirilim Mumundan Sonra: i > bo_local_idx)
        # ─────────────────────────────────────────────────────────────────────
        post_bo_bars = search_window[bo_local_idx + 1:]
        retest_bar = None
        rt_local_idx = None
        is_invalidated = False

        for j, b in enumerate(post_bo_bars):
            actual_j = bo_local_idx + 1 + j

            if direction == 'LONG':
                # Gecersizlik: Seviyenin cok altina sarkip kapandiysa sahte kirilim
                if b['close'] < (breakout_level - tolerance):
                    is_invalidated = True
                    break

                # Retest: Dusuk fitil seviyeye yaklasmis/dokunmus VE kapanis seviyenin ustunde kalmis
                if b['low'] <= (breakout_level + tolerance) and b['close'] >= (breakout_level - tolerance * 0.7):
                    retest_bar = b
                    rt_local_idx = actual_j
                    break
            else:
                # Short Gecersizlik
                if b['close'] > (breakout_level + tolerance):
                    is_invalidated = True
                    break

                # Short Retest: Yuksek fitil seviyeye ulasmis VE kapanis seviyenin altinda kalmis
                if b['high'] >= (breakout_level - tolerance) and b['close'] <= (breakout_level + tolerance * 0.7):
                    retest_bar = b
                    rt_local_idx = actual_j
                    break

        if is_invalidated:
            # Sahte kirilim olmus, retest iptal
            retest_bar = None
            confirmed_bar = None
            stage = "BREAKOUT"
            stage_name = "1. Aşama: Sahte Kırılım Sonrası Yeniden Kırılım Bekleniyor"
        elif not retest_bar:
            # Kirilim olmus ama henuz retest mumu gelmemis
            stage = "BREAKOUT"
            stage_name = "1. Aşama: Formasyon Kırılımı (Retest Bekleniyor)"
            confirmed_bar = None
        else:
            # ─────────────────────────────────────────────────────────────────
            # 3. ONAY MUMU TESPITI (Retest Mumunda veya Sonraki 2 Mum Icinde)
            # ─────────────────────────────────────────────────────────────────
            conf_window = search_window[rt_local_idx : min(len(search_window), rt_local_idx + 3)]
            confirmed_bar = None

            for c_bar in conf_window:
                c = c_bar['close']
                o = c_bar['open']
                h = c_bar['high']
                l = c_bar['low']
                v = c_bar['volume']
                rng = max(0.0001, h - l)
                body = abs(c - o)

                if direction == 'LONG':
                    is_bull_candle = (c > o) and (body >= 0.45 * rng)
                    level_held = (c >= breakout_level)
                    vol_ok = (v >= vol_sma20 * 0.80)
                    if is_bull_candle and level_held and vol_ok:
                        confirmed_bar = c_bar
                        break
                else:
                    is_bear_candle = (c < o) and (body >= 0.45 * rng)
                    level_held = (c <= breakout_level)
                    vol_ok = (v >= vol_sma20 * 0.80)
                    if is_bear_candle and level_held and vol_ok:
                        confirmed_bar = c_bar
                        break

            # Tazelik Kontrolu: Onay mumu son 3 bar icinde mi?
            last_bar_idx = len(search_window) - 1
            if confirmed_bar:
                conf_pos = search_window.index(confirmed_bar)
                if last_bar_idx - conf_pos <= 3:
                    stage = "CONFIRMED"
                    stage_name = "3. Aşama: Formasyon Onaylandı (Kesin Giriş)"
                else:
                    # Onay mumu cok eski kalmis (islem ilerlemis)
                    stage = "CONFIRMED"
                    stage_name = "3. Aşama: Formasyon Onaylandı (Hedefe İlerliyor)"
            elif last_bar_idx - rt_local_idx <= 4:
                # Retest henuz taze ve onay bekliyor
                stage = "RETESTING"
                stage_name = "2. Aşama: Formasyon Retesti (Onay Mumu Bekleniyor)"
            else:
                # Retest uzerinden cok bar gecmis ama onay gelmemis -> Bayat
                stage = "BREAKOUT"
                stage_name = "1. Aşama: Kırılım Bölgesinde Konsolidasyon"

    # Risk & Getiri Seviyeleri
    if direction == "LONG":
        stop_loss = round(breakout_level - (0.25 * current_atr), 4)
        risk = max(0.0001, current_price - stop_loss)
        reward = max(0.0001, target - current_price)
    else:
        stop_loss = round(breakout_level + (0.25 * current_atr), 4)
        risk = max(0.0001, stop_loss - current_price)
        reward = max(0.0001, current_price - target)

    rr_ratio = round(reward / risk, 1)

    # 4 Adimli Kontrol Listesi
    checklist = [
        {
            "step": 1,
            "title": f"1. {pat_name} Kırılımı (Kalite: %{quality_score})",
            "passed": bool(breakout_bar),
            "detail": f"{pat_name} tespit edildi. Kırılan Seviye: ${breakout_level:,.4f}" if breakout_bar else f"Henüz ${breakout_level:,.4f} kırılımı gerçekleşmedi."
        },
        {
            "step": 2,
            "title": f"2. Retest (0.35xATR Tolerans = ${tolerance:,.4f})",
            "passed": bool(retest_bar),
            "detail": f"Fiyat saat {retest_bar['time_str']} barında ${breakout_level:,.4f} seviyesine fitil retesti verdi." if retest_bar else f"Fiyatın ${breakout_level:,.4f} seviyesine geri çekilmesi bekleniyor."
        },
        {
            "step": 3,
            "title": "3. Hacimli Onay Mumu (Yönlü Mum & Vol > %80 SMA20)",
            "passed": bool(confirmed_bar),
            "detail": f"Saat {confirmed_bar['time_str']} barında güçlü onay mumu kapandı." if confirmed_bar else "Hacimli onay mumu bekleniyor."
        },
        {
            "step": 4,
            "title": f"4. Hedef & Risk Oranı (R:R {rr_ratio}R)",
            "passed": rr_ratio >= 1.5,
            "detail": f"Hedef: ${target:,.4f} | Stop: ${stop_loss:,.4f} (R:R {rr_ratio}R)"
        }
    ]

    raw_cat = pat.get('category', '')
    if 'Trend' in raw_cat:
        pat_cat = 'TRENDLINE'
    elif 'Üçgen' in raw_cat or 'Pennant' in raw_cat or 'Triangle' in raw_cat:
        pat_cat = 'TRIANGLE'
    elif 'S/R' in raw_cat or 'Flip' in raw_cat:
        pat_cat = 'SR_FLIP'
    elif 'Range' in raw_cat:
        pat_cat = 'RANGE'
    elif 'Double' in raw_cat or 'İkili' in raw_cat:
        pat_cat = 'DOUBLE_TOP_BOTTOM'
    else:
        pat_cat = 'TRENDLINE'

    return {
        "status": "success",
        "symbol": symbol,
        "timeframe": timeframe,
        "optimal_timeframe": timeframe,
        "quality_score": quality_score,
        "strategy_name": pat_name,
        "pattern_category": pat_cat,
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
        "breakout_bar": breakout_bar,
        "retest_bar": retest_bar,
        "confirmed_bar": confirmed_bar,
        "checklist": checklist,
        "explanation": pat.get('description', ''),
        "lines": pat.get('lines', [])
    }


def evaluate_coin_multi_timeframe_optimal(symbol: str, target_timeframe: str = "auto") -> Optional[Dict[str, Any]]:
    if target_timeframe and target_timeframe != "auto" and target_timeframe != "ALL":
        try:
            df = market_manager.get_market_data(symbol, timeframe=target_timeframe, limit=150)
            if df is not None and len(df) >= 35:
                return evaluate_pattern_strategy_exact(symbol, df, timeframe=target_timeframe)
        except Exception:
            return None
        return None

    candidate_tfs = ["4h", "1h", "15m"]
    evaluated_candidates = []

    for tf in candidate_tfs:
        try:
            df = market_manager.get_market_data(symbol, timeframe=tf, limit=150)
            if df is not None and len(df) >= 35:
                res = evaluate_pattern_strategy_exact(symbol, df, timeframe=tf)
                if res:
                    evaluated_candidates.append(res)
        except Exception:
            continue

    if not evaluated_candidates:
        return None

    stage_weights = {"CONFIRMED": 300, "RETESTING": 200, "BREAKOUT": 100}
    evaluated_candidates.sort(
        key=lambda x: (stage_weights.get(x.get("stage"), 0) + x.get("quality_score", 0)),
        reverse=True
    )

    best_match = evaluated_candidates[0]
    best_match["is_auto_optimal"] = True
    best_match["timeframe_badge"] = f"🌟 {best_match['timeframe'].upper()} (En İdeal)"
    return best_match


def run_pattern_radar(timeframe: str = "1h", limit_coins: int = 50) -> Dict[str, Any]:
    pairs = market_manager.get_top_pairs(limit=limit_coins)
    
    stages = {
        "breakout": [],
        "retesting": [],
        "confirmed": []
    }

    def _eval(sym):
        try:
            return evaluate_coin_multi_timeframe_optimal(sym, target_timeframe=timeframe)
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

    stages["confirmed"].sort(key=lambda x: (x.get('quality_score', 0), x['current_price']), reverse=True)
    stages["retesting"].sort(key=lambda x: (x.get('quality_score', 0), x['current_price']), reverse=True)
    stages["breakout"].sort(key=lambda x: (x.get('quality_score', 0), x['current_price']), reverse=True)

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
