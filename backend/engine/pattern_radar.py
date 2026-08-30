"""
CryptoSignalPro AI - Formasyon & Klasik/Modern Setup Radarı (v10.0.0)

Kapsamlı Retest & Geri Çekilme (Pullback) Motoru:
1. 10 Klasik ve Modern Grafik Formasyonu (Trendline, Simetrik/Yükselen/Alçalan Üçgen, S/R Flip, Range, Çift Dip/Tepe).
2. Kırılım Sonrası Geri Çekilme (Pullback) & Retest Tespiti:
   - Seviye Retesti: Kırılan formasyon çizgisi/seviyesine geri çekilme.
   - Sağlıklı Küçük Geri Çekilme (Minor Pullback): Kırılım tepesinden/dibinden geriye doğru %30-%60 düzeltme mumu.
   - Konsolidasyon & Bayrak (Bull/Bear Flag): Kırılan seviyenin hemen ötesinde dar bantlı sindirme.
3. Hacimli Yönlü Onay Mumu.
4. TradingView Hafif Grafik Çizim Verileri (Trend çizgileri, hedefler, retest işaretçileri).
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from engine.market_data import market_manager
from engine.patterns import detect_chart_patterns
from engine.indicators import calculate_atr, calculate_sma


def evaluate_pattern_with_retest(
    symbol: str,
    df: pd.DataFrame,
    pattern: Dict[str, Any],
    timeframe: str = "1h"
) -> Dict[str, Any]:
    current_price = float(df['close'].iloc[-1])
    current_atr = float(df['atr'].iloc[-1]) if 'atr' in df.columns and not np.isnan(df['atr'].iloc[-1]) else (current_price * 0.015)
    vol_sma20 = float(df['vol_sma20'].iloc[-1]) if 'vol_sma20' in df.columns and not np.isnan(df['vol_sma20'].iloc[-1]) else float(df['volume'].mean())

    pat_name = pattern.get('name', 'Formasyon')
    direction = "LONG" if pattern.get('type') == 'BULLISH' else "SHORT"
    breakout_level = float(pattern.get('breakout_level') or pattern.get('entry_price') or current_price)
    target = float(pattern.get('target', current_price * 1.05 if direction == "LONG" else current_price * 0.95))
    quality_score = pattern.get('confidence', 75)
    lines = pattern.get('lines', [])

    n = len(df)
    search_bars_count = min(16, n)
    search_df = df.iloc[-search_bars_count:].copy()

    search_window = []
    for idx, (orig_idx, row) in enumerate(search_df.iterrows()):
        ts = int(row['timestamp']) if 'timestamp' in row else 0
        if ts > 1e12: ts = ts // 1000
        search_window.append({
            'local_idx': idx,
            'orig_idx': orig_idx,
            'timestamp': ts,
            'time_str': datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M UTC") if ts > 0 else f"Bar #{orig_idx}",
            'iso_time': datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts > 0 else f"Bar_{orig_idx}",
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row.get('volume', 0.0))
        })

    # 1. TAZE KIRILIM TESPİTİ (Son 12 bar içinde)
    breakout_bar = None
    bo_local_idx = None
    tolerance = 0.50 * current_atr

    for i, b in enumerate(search_window):
        if direction == 'LONG':
            if b['close'] > (breakout_level - 0.15 * tolerance):
                breakout_bar = b
                bo_local_idx = i
                break
        else:
            if b['close'] < (breakout_level + 0.15 * tolerance):
                breakout_bar = b
                bo_local_idx = i
                break

    if not breakout_bar:
        stage = "BREAKOUT"
        stage_name = "1. Aşama: Formasyon Sıkışması (Kırılım Bekleniyor)"
        retest_bar = None
        confirmed_bar = None
    else:
        # 2. RETEST & GERİ ÇEKİLME (PULLBACK) TESPİTİ
        post_bo_bars = search_window[bo_local_idx + 1 : min(len(search_window), bo_local_idx + 9)]
        retest_bar = None
        rt_local_idx = None
        is_invalidated = False

        max_high_post_bo = breakout_bar['high']
        min_low_post_bo = breakout_bar['low']

        for j, b in enumerate(post_bo_bars):
            actual_j = bo_local_idx + 1 + j
            max_high_post_bo = max(max_high_post_bo, b['high'])
            min_low_post_bo = min(min_low_post_bo, b['low'])

            if direction == 'LONG':
                # Geçersizlik: Kırılan seviyenin çok altında derin kapanış -> Sahte Kırılım
                if b['close'] < (breakout_level - tolerance * 1.5):
                    is_invalidated = True
                    break

                # Retest & Geri Çekilme Kriterleri:
                # Kriter A: Doğrudan seviyeye fitil/temas retesti
                cond_level_touch = (b['low'] <= breakout_level + tolerance * 1.2) and (b['close'] >= breakout_level - tolerance * 0.7)
                # Kriter B: Kırılım tepesinden sonraki sağlıklı küçük geri çekilme (Pullback mumu: close < open veya fitil çekilmesi)
                cond_minor_pullback = (b['low'] <= max_high_post_bo - 0.35 * current_atr) and (b['close'] >= breakout_level - tolerance * 0.5)
                # Kriter C: Bayrak/Sindirme mumu
                cond_flag = (b['close'] < b['open']) and (b['close'] >= breakout_level - tolerance * 0.3)

                if cond_level_touch or cond_minor_pullback or cond_flag:
                    retest_bar = b
                    rt_local_idx = actual_j
                    break
            else:
                if b['close'] > (breakout_level + tolerance * 1.5):
                    is_invalidated = True
                    break

                cond_level_touch = (b['high'] >= breakout_level - tolerance * 1.2) and (b['close'] <= breakout_level + tolerance * 0.7)
                cond_minor_pullback = (b['high'] >= min_low_post_bo + 0.35 * current_atr) and (b['close'] <= breakout_level + tolerance * 0.5)
                cond_flag = (b['close'] > b['open']) and (b['close'] <= breakout_level + tolerance * 0.3)

                if cond_level_touch or cond_minor_pullback or cond_flag:
                    retest_bar = b
                    rt_local_idx = actual_j
                    break

        if is_invalidated:
            retest_bar = None
            confirmed_bar = None
            stage = "BREAKOUT"
            stage_name = "1. Aşama: Sahte Kırılım Sonrası Yeniden Kırılım Bekleniyor"
        elif not retest_bar:
            stage = "BREAKOUT"
            stage_name = "1. Aşama: Taze Kırılım (Retest / Geri Çekilme Bekleniyor)"
            confirmed_bar = None
        else:
            # 3. ONAY MUMU (Retest / Geri Çekilme Sonrası)
            conf_window = search_window[rt_local_idx : min(len(search_window), rt_local_idx + 4)]
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
                    is_bull_candle = (c > o) and (body >= 0.38 * rng or c >= retest_bar['high'])
                    level_held = (c >= breakout_level - tolerance * 0.5)
                    vol_ok = (v >= vol_sma20 * 0.75) if vol_sma20 > 0 else True
                    if is_bull_candle and level_held and vol_ok:
                        confirmed_bar = c_bar
                        break
                else:
                    is_bear_candle = (c < o) and (body >= 0.38 * rng or c <= retest_bar['low'])
                    level_held = (c <= breakout_level + tolerance * 0.5)
                    vol_ok = (v >= vol_sma20 * 0.75) if vol_sma20 > 0 else True
                    if is_bear_candle and level_held and vol_ok:
                        confirmed_bar = c_bar
                        break

            last_bar_idx = len(search_window) - 1
            if confirmed_bar:
                stage = "CONFIRMED"
                stage_name = "3. Aşama: Geri Çekilme Sonrası Onay Mumu Kapandı (Giriş Hazır)"
            elif last_bar_idx - rt_local_idx <= 2:
                stage = "RETESTING"
                stage_name = "2. Aşama: Retest / Geri Çekilme Bölgesinde (Onay Mumu Bekleniyor)"
            else:
                stage = "BREAKOUT"
                stage_name = "1. Aşama: Kırılım Bölgesinde Konsolidasyon"
                retest_bar = None

    if direction == "LONG":
        stop_loss = round(breakout_level - (0.25 * current_atr), 4)
        risk = max(0.0001, current_price - stop_loss)
        reward = max(0.0001, target - current_price)
    else:
        stop_loss = round(breakout_level + (0.25 * current_atr), 4)
        risk = max(0.0001, stop_loss - current_price)
        reward = max(0.0001, current_price - target)

    rr_ratio = round(reward / risk, 1)

    tf_labels = {'15m': '15 Dakikalık (15m)', '1h': '1 Saatlik (1h)', '4h': '4 Saatlik (4h)'}
    tf_str = tf_labels.get(timeframe, timeframe)

    checklist = [
        {
            "step": 1,
            "title": f"1. {pat_name} Kırılımı [{tf_str}] (Kalite: %{quality_score})",
            "passed": breakout_bar is not None,
            "detail": f"Saat {breakout_bar['time_str']} barında mum kapanışı (${breakout_bar['close']:,.4f}) ile kırıldı." if breakout_bar else f"Fiyatın ${breakout_level:,.4f} formasyon çizgisini kırması bekleniyor."
        },
        {
            "step": 2,
            "title": f"2. Retest / Geri Çekilme (Pullback) & Düzeltme Sindirimi",
            "passed": retest_bar is not None,
            "detail": f"Saat {retest_bar['time_str']} barında sağlıklı geri çekilme/retest yapıldı ve seviye tutundu." if retest_bar else "Kırılım sonrası sağlıklı geri çekilme (Pullback) veya seviye retesti bekleniyor."
        },
        {
            "step": 3,
            "title": f"3. Hacimli Yönlü Onay Mumu [{tf_str}]",
            "passed": confirmed_bar is not None,
            "detail": f"Saat {confirmed_bar['time_str']} barında hacimli onay mumu kapandı (${confirmed_bar['close']:,.4f})." if confirmed_bar else "Geri çekilme sonrası yönlü onay mumu bekleniyor."
        },
        {
            "step": 4,
            "title": f"4. Risk/Ödül Planı: Hedef ${target:,.4f} | R:R {rr_ratio}R",
            "passed": True,
            "detail": f"Stop Loss: ${stop_loss:,.4f} (0.25xATR emniyetli koruma)."
        }
    ]

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "timeframe_badge": tf_str,
        "strategy_name": pat_name,
        "pattern_category": pattern.get('category', 'TRENDLINE'),
        "stage": stage,
        "stage_name": stage_name,
        "direction": direction,
        "current_price": current_price,
        "breakout_level": breakout_level,
        "entry_price": float(confirmed_bar['close']) if confirmed_bar else current_price,
        "stop_loss": stop_loss,
        "take_profit": target,
        "risk_reward": rr_ratio,
        "quality_score": quality_score,
        "atr": current_atr,
        "breakout_bar": breakout_bar,
        "retest_bar": retest_bar,
        "confirmed_bar": confirmed_bar,
        "chart_lines": lines,
        "checklist": checklist,
        "explanation": f"{symbol} {tf_str} grafiğinde {pat_name} formasyonu, geri çekilme/retest ve onay dinamikleriyle incelendi."
    }


def run_pattern_radar(timeframe: str = "1h", limit_coins: int = 50) -> Dict[str, Any]:
    pairs = market_manager.get_top_pairs(limit=limit_coins)
    
    stages = {
        "breakout": [],
        "retesting": [],
        "confirmed": []
    }

    def _eval(sym):
        try:
            df = market_manager.get_market_data(sym, timeframe=timeframe, limit=100)
            if df is not None and len(df) >= 35:
                df['atr'] = calculate_atr(df, 14)
                df['vol_sma20'] = calculate_sma(df['volume'], 20)
                patterns = detect_chart_patterns(df)
                if patterns:
                    best_pat = patterns[0]
                    res = evaluate_pattern_with_retest(sym, df, best_pat, timeframe=timeframe)
                    return res
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

    stages["confirmed"].sort(key=lambda x: (x.get('quality_score', 0), x['risk_reward']), reverse=True)
    stages["retesting"].sort(key=lambda x: (x.get('quality_score', 0), x['risk_reward']), reverse=True)
    stages["breakout"].sort(key=lambda x: (x.get('quality_score', 0), x['risk_reward']), reverse=True)

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
