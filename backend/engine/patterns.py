"""
CryptoSignalPro AI - Gelismis Grafik Formasyonlari Tespit ve Trend Cizgisi Motoru (v9.0.0)

Algoritmik Standartlar:
- Thomas Bulkowski (Encyclopedia of Chart Patterns)
- Alternating ZigZag: Tepe ve dipler kesinlikle donusumlu (peak -> valley -> peak -> valley)
- TradingView Alt+T Trend Cizgisi Geometrisi: Pivot 1 -> Pivot 2 -> Guncel Bar uzantisi
- Siki Geometrik Dogrulama (Simetrik Ucgen, Yukselen/Alcalan Ucgen, Trendline Breakout, S/R Flip, Double Top/Bottom, Range)
"""

import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple


def _get_sec_timestamp(df: pd.DataFrame, idx: int) -> int:
    """Verilen bar indeksinin saniye cinsinden UNIX zaman damgasini dondurur."""
    if len(df) == 0:
        return 0
    idx = max(0, min(len(df) - 1, int(idx)))
    if 'timestamp' in df.columns:
        try:
            val = int(df['timestamp'].iloc[idx])
            return val // 1000 if val > 1e12 else val
        except Exception:
            pass
    return int(idx)


def _two_point_line(df: pd.DataFrame,
                    start_idx: int, end_idx: int,
                    start_val: float, end_val: float) -> List[Dict[str, Any]]:
    """
    TradingView LineSeries icin 2 uclu trend cizgisi uretir (Alt+T gibi).
    Baslangic: start_idx barindaki start_val
    Bitis: end_idx barindaki end_val
    """
    t1 = _get_sec_timestamp(df, start_idx)
    t2 = _get_sec_timestamp(df, end_idx)
    return [
        {'time': t1, 'value': round(float(start_val), 6)},
        {'time': t2, 'value': round(float(end_val), 6)},
    ]


def _horizontal_line(df: pd.DataFrame,
                     start_idx: int, end_idx: int,
                     level: float) -> List[Dict[str, Any]]:
    """Yatay seviye cizgisi."""
    return _two_point_line(df, start_idx, end_idx, level, level)


def extract_alternating_zigzag(
    df: pd.DataFrame,
    depth: int = 4,
    deviation_pct: float = 0.6
) -> List[Dict[str, Any]]:
    """
    Gercek Donusumlu ZigZag (Alternating Peak/Valley Extrema).
    
    Her zirve mutlaka bir dipten, her dip mutlaka bir zirveden sonra gelmelidir.
    Ardisik ayni tur noktalar gelirse daha uc olan secilir.
    
    Donen format: [{'type': 'peak'|'valley', 'index': int, 'price': float, 'time': int}, ...]
    """
    n = len(df)
    if n < depth * 2 + 1:
        return []

    highs = df['high'].values
    lows = df['low'].values

    extrema: List[Dict[str, Any]] = []

    for i in range(depth, n - depth):
        window_h = highs[max(0, i - depth): min(n, i + depth + 1)]
        window_l = lows[max(0, i - depth): min(n, i + depth + 1)]
        
        is_peak = (highs[i] == window_h.max())
        is_valley = (lows[i] == window_l.min())

        if is_peak and is_valley:
            continue

        if is_peak:
            p_val = float(highs[i])
            t_val = _get_sec_timestamp(df, i)
            if not extrema:
                extrema.append({'type': 'peak', 'index': i, 'price': p_val, 'time': t_val})
            elif extrema[-1]['type'] == 'valley':
                if p_val >= extrema[-1]['price'] * (1 + deviation_pct / 100.0) or (i - extrema[-1]['index'] >= depth):
                    extrema.append({'type': 'peak', 'index': i, 'price': p_val, 'time': t_val})
            elif extrema[-1]['type'] == 'peak':
                if p_val > extrema[-1]['price']:
                    extrema[-1] = {'type': 'peak', 'index': i, 'price': p_val, 'time': t_val}

        elif is_valley:
            v_val = float(lows[i])
            t_val = _get_sec_timestamp(df, i)
            if not extrema:
                extrema.append({'type': 'valley', 'index': i, 'price': v_val, 'time': t_val})
            elif extrema[-1]['type'] == 'peak':
                if v_val <= extrema[-1]['price'] * (1 - deviation_pct / 100.0) or (i - extrema[-1]['index'] >= depth):
                    extrema.append({'type': 'valley', 'index': i, 'price': v_val, 'time': t_val})
            elif extrema[-1]['type'] == 'valley':
                if v_val < extrema[-1]['price']:
                    extrema[-1] = {'type': 'valley', 'index': i, 'price': v_val, 'time': t_val}

    return extrema


def calculate_linear_regression(
    indices: List[int],
    prices: List[float]
) -> Tuple[float, float, float]:
    """(slope, intercept, R^2)"""
    if len(indices) < 2:
        return 0.0, float(np.mean(prices)) if prices else 0.0, 0.0

    x = np.array(indices, dtype=float)
    y = np.array(prices, dtype=float)
    n = len(x)

    denom = n * np.sum(x * x) - np.sum(x) ** 2
    if abs(denom) < 1e-12:
        return 0.0, float(np.mean(y)), 0.0

    slope = (n * np.sum(x * y) - np.sum(x) * np.sum(y)) / denom
    intercept = (np.sum(y) - slope * np.sum(x)) / n

    y_pred = slope * x + intercept
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    ss_res = np.sum((y - y_pred) ** 2)
    r2 = max(0.0, min(1.0, 1.0 - ss_res / ss_tot)) if ss_tot > 1e-10 else 1.0

    return float(slope), float(intercept), float(r2)


def detect_chart_patterns(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    TradingView standardinda 6 temel formasyonu geometrik kesinlikle tespit eder:
    1. Dusen Trend Cizgisi Kirilimi & Retest (Bullish Trendline)
    2. Yukselen Trend Cizgisi Kirilimi & Retest (Bearish Trendline)
    3. Simetrik / Yukselen / Alcalan Ucgen Formasyonlari (Triangles)
    4. Direnc/Destek Donusumu (S/R Flip Retest)
    5. Double Bottom (W) & Double Top (M)
    6. Range (Kanal) Kirilimi & Likidite Sapmasi (Deviation Reclaim)
    """
    patterns: List[Dict[str, Any]] = []
    n = len(df)
    if n < 35:
        return patterns

    current_price = float(df['close'].iloc[-1])
    current_atr = (float(df['atr'].iloc[-1])
                   if 'atr' in df.columns and not np.isnan(df['atr'].iloc[-1])
                   else current_price * 0.018)
    vol_sma20 = float(df['volume'].iloc[-20:].mean()) if n >= 20 else float(df['volume'].iloc[-1])
    current_vol = float(df['volume'].iloc[-1])
    vol_boost = current_vol >= vol_sma20 * 1.15

    # Donusumlu ZigZag Uclari
    extrema = extract_alternating_zigzag(df, depth=4, deviation_pct=0.6)
    peaks = [e for e in extrema if e['type'] == 'peak']
    valleys = [e for e in extrema if e['type'] == 'valley']

    # ─────────────────────────────────────────────────────────────────────────
    # 1. 📉 DUSEN TREND CIZGISI KIRILIMI & RETEST (TradingView Alt+T Trendline)
    # ─────────────────────────────────────────────────────────────────────────
    if len(peaks) >= 2:
        for k in range(min(4, len(peaks)), 1, -1):
            sel_peaks = peaks[-k:]
            idxs = [p['index'] for p in sel_peaks]
            prices = [p['price'] for p in sel_peaks]
            
            slope, intercept, r2 = calculate_linear_regression(idxs, prices)
            min_r2 = 0.75 if len(sel_peaks) > 2 else 0.0

            if slope < -1e-5 and (len(sel_peaks) == 2 or r2 >= min_r2):
                p_first = sel_peaks[0]
                p_last = sel_peaks[-1]
                
                tl_now = slope * (n - 1) + intercept
                tl_start = slope * p_first['index'] + intercept
                
                is_breakout = current_price >= tl_now * 0.997
                recency = n - 1 - p_last['index']
                
                if is_breakout and 2 <= recency <= 35:
                    recent_low = float(df['low'].iloc[-5:].min())
                    is_retest = recent_low <= tl_now * 1.015 and current_price >= tl_now * 0.995
                    
                    target = float(p_first['price'])
                    quality = int(min(100, (r2 * 35) + (len(sel_peaks) * 12) + (20 if vol_boost else 8) + (25 if is_retest else 10)))
                    
                    line_pts = _two_point_line(df, p_first['index'], n - 1, tl_start, tl_now)
                    
                    patterns.append({
                        'name': 'Düşen Trend Çizgisi Kırılımı & Retest',
                        'type': 'BULLISH',
                        'category': '1. Trend Kırılım & Retest',
                        'quality_score': quality,
                        'breakout_level': round(tl_now, 4),
                        'target': round(target, 4),
                        'description': f'{len(sel_peaks)} tepe temaslı düşen trend çizgisi (${tl_now:,.4f}) yukarı kırıldı. Hedef: ${target:,.4f}',
                        'lines': [
                            {
                                'name': 'Düşen Trend Direnci (Alt+T)',
                                'points': line_pts,
                                'color': '#fbbf24',
                                'lineWidth': 2,
                                'lineStyle': 0
                            }
                        ]
                    })
                    break

    # ─────────────────────────────────────────────────────────────────────────
    # 2. 📈 YUKSELEN TREND CIZGISI KIRILIMI & RETEST (TradingView Alt+T Trendline)
    # ─────────────────────────────────────────────────────────────────────────
    if len(valleys) >= 2:
        for k in range(min(4, len(valleys)), 1, -1):
            sel_valleys = valleys[-k:]
            idxs = [v['index'] for v in sel_valleys]
            prices = [v['price'] for v in sel_valleys]
            
            slope, intercept, r2 = calculate_linear_regression(idxs, prices)
            min_r2 = 0.75 if len(sel_valleys) > 2 else 0.0

            if slope > 1e-5 and (len(sel_valleys) == 2 or r2 >= min_r2):
                v_first = sel_valleys[0]
                v_last = sel_valleys[-1]
                
                tl_now = slope * (n - 1) + intercept
                tl_start = slope * v_first['index'] + intercept
                
                is_breakdown = current_price <= tl_now * 1.003
                recency = n - 1 - v_last['index']
                
                if is_breakdown and 2 <= recency <= 35:
                    recent_high = float(df['high'].iloc[-5:].max())
                    is_retest = recent_high >= tl_now * 0.985 and current_price <= tl_now * 1.005
                    
                    target = float(v_first['price'])
                    quality = int(min(100, (r2 * 35) + (len(sel_valleys) * 12) + (20 if vol_boost else 8) + (25 if is_retest else 10)))
                    
                    line_pts = _two_point_line(df, v_first['index'], n - 1, tl_start, tl_now)
                    
                    patterns.append({
                        'name': 'Yükselen Trend Çizgisi Kırılımı & Retest',
                        'type': 'BEARISH',
                        'category': '1. Trend Kırılım & Retest',
                        'quality_score': quality,
                        'breakout_level': round(tl_now, 4),
                        'target': round(target, 4),
                        'description': f'{len(sel_valleys)} dip temaslı yükselen trend desteği (${tl_now:,.4f}) aşağı kırıldı. Hedef: ${target:,.4f}',
                        'lines': [
                            {
                                'name': 'Yükselen Trend Desteği (Alt+T)',
                                'points': line_pts,
                                'color': '#f43f5e',
                                'lineWidth': 2,
                                'lineStyle': 0
                            }
                        ]
                    })
                    break

    # ─────────────────────────────────────────────────────────────────────────
    # 3. 📐 SİMETRİK / YÜKSELEN / ALÇALAN ÜÇGEN & PENNANT
    # ─────────────────────────────────────────────────────────────────────────
    if len(extrema) >= 4:
        recent_ext = extrema[-8:]
        r_peaks = [e for e in recent_ext if e['type'] == 'peak']
        r_valleys = [e for e in recent_ext if e['type'] == 'valley']

        if len(r_peaks) >= 2 and len(r_valleys) >= 2:
            p1, p2 = r_peaks[-2], r_peaks[-1]
            v1, v2 = r_valleys[-2], r_valleys[-1]

            # GEOMETRIK SIRA KONTROLU
            points_sorted = sorted([p1, v1, p2, v2], key=lambda x: x['index'])
            type_seq = [p['type'] for p in points_sorted]
            is_alternating = type_seq in [
                ['peak', 'valley', 'peak', 'valley'],
                ['valley', 'peak', 'valley', 'peak']
            ]

            latest_idx = max(p2['index'], v2['index'])
            earliest_idx = min(p1['index'], v1['index'])
            recency = n - 1 - latest_idx
            pattern_span = latest_idx - earliest_idx

            if is_alternating and 8 <= pattern_span <= 60 and recency <= 20:
                slope_up = (p2['price'] - p1['price']) / max(1, p2['index'] - p1['index'])
                slope_down = (v2['price'] - v1['price']) / max(1, v2['index'] - v1['index'])

                upper_start = p1['price']
                upper_now = p1['price'] + slope_up * (n - 1 - p1['index'])

                lower_start = v1['price']
                lower_now = v1['price'] + slope_down * (n - 1 - v1['index'])

                # A. SIMETRIK UCGEN: Ust cizgi asagi, Alt cizgi yukari (kesinlikle daralan)
                if slope_up < -1e-5 and slope_down > 1e-5:
                    if upper_now > lower_now:
                        height = abs(p1['price'] - v1['price'])
                        is_bull = current_price >= upper_now * 0.997
                        is_bear = current_price <= lower_now * 1.003
                        
                        pat_type = 'BULLISH' if is_bull else ('BEARISH' if is_bear else 'NEUTRAL')
                        bo_lvl = upper_now if is_bull else lower_now
                        target = current_price + height if is_bull else current_price - height
                        
                        line_upper = _two_point_line(df, p1['index'], n - 1, upper_start, upper_now)
                        line_lower = _two_point_line(df, v1['index'], n - 1, lower_start, lower_now)
                        
                        patterns.append({
                            'name': 'Simetrik Üçgen / Flama Kırılımı',
                            'type': pat_type if pat_type != 'NEUTRAL' else 'BULLISH',
                            'category': '2. Simetrik Üçgen / Pennant',
                            'quality_score': 88,
                            'breakout_level': round(bo_lvl, 4),
                            'target': round(target, 4),
                            'description': f'Geometrik simetrik üçgen (${lower_now:,.4f} - ${upper_now:,.4f}) bandından çıkış gerçekleşti. Hedef: ${target:,.4f}',
                            'lines': [
                                {'name': 'Alçalan Direnç Trendi', 'points': line_upper, 'color': '#fbbf24', 'lineWidth': 2, 'lineStyle': 0},
                                {'name': 'Yükselen Destek Trendi', 'points': line_lower, 'color': '#38bdf8', 'lineWidth': 2, 'lineStyle': 0}
                            ]
                        })

                # B. YUKSELEN UCGEN (Direnc yatay, Destek yukari egimli)
                elif abs(p2['price'] - p1['price']) / p1['price'] <= 0.015 and slope_down > 1e-5:
                    flat_res = (p1['price'] + p2['price']) / 2.0
                    height = flat_res - v1['price']
                    target = flat_res + height

                    line_upper = _horizontal_line(df, p1['index'], n - 1, flat_res)
                    line_lower = _two_point_line(df, v1['index'], n - 1, lower_start, lower_now)

                    patterns.append({
                        'name': 'Yükselen Üçgen (Ascending Triangle)',
                        'type': 'BULLISH',
                        'category': '2. Simetrik Üçgen / Pennant',
                        'quality_score': 90,
                        'breakout_level': round(flat_res, 4),
                        'target': round(target, 4),
                        'description': f'${flat_res:,.4f} yatay direnci altında yükselen diplerle sıkışma tamamlandı. Hedef: ${target:,.4f}',
                        'lines': [
                            {'name': 'Yatay Direnç Tavanı', 'points': line_upper, 'color': '#fbbf24', 'lineWidth': 2, 'lineStyle': 0},
                            {'name': 'Yükselen Destek Trendi', 'points': line_lower, 'color': '#10b981', 'lineWidth': 2, 'lineStyle': 0}
                        ]
                    })

                # C. ALCALAN UCGEN (Destek yatay, Direnc asagi egimli)
                elif slope_up < -1e-5 and abs(v2['price'] - v1['price']) / v1['price'] <= 0.015:
                    flat_sup = (v1['price'] + v2['price']) / 2.0
                    height = p1['price'] - flat_sup
                    target = flat_sup - height

                    line_upper = _two_point_line(df, p1['index'], n - 1, upper_start, upper_now)
                    line_lower = _horizontal_line(df, v1['index'], n - 1, flat_sup)

                    patterns.append({
                        'name': 'Alçalan Üçgen (Descending Triangle)',
                        'type': 'BEARISH',
                        'category': '2. Simetrik Üçgen / Pennant',
                        'quality_score': 90,
                        'breakout_level': round(flat_sup, 4),
                        'target': round(target, 4),
                        'description': f'${flat_sup:,.4f} yatay desteği üzerinde alçalan zirvelerle baskı oluştu. Hedef: ${target:,.4f}',
                        'lines': [
                            {'name': 'Alçalan Direnç Trendi', 'points': line_upper, 'color': '#f43f5e', 'lineWidth': 2, 'lineStyle': 0},
                            {'name': 'Yatay Destek Tabanı', 'points': line_lower, 'color': '#fbbf24', 'lineWidth': 2, 'lineStyle': 0}
                        ]
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. 🔄 DIRENC/DESTEK DONUSUMU (S/R Flip Retest)
    # ─────────────────────────────────────────────────────────────────────────
    if len(peaks) >= 2:
        for p in peaks[-4:-1]:
            res = p['price']
            breaks = [i for i in range(p['index'] + 2, n) if df['close'].iloc[i] > res * 1.005]
            if breaks:
                first_brk = breaks[0]
                post_lows = df['low'].iloc[first_brk:]
                if len(post_lows) > 0 and post_lows.min() <= res + 0.35 * current_atr and current_price >= res * 0.995:
                    target = current_price + (current_atr * 2.8)
                    line_pts = _horizontal_line(df, p['index'], n - 1, res)
                    patterns.append({
                        'name': 'Direnç/Destek Dönüşümü (S/R Flip Retest)',
                        'type': 'BULLISH',
                        'category': '3. S/R Flip Retest',
                        'quality_score': 92,
                        'flip_level': round(res, 4),
                        'breakout_level': round(res, 4),
                        'target': round(target, 4),
                        'description': f'Eski kilit direnç ${res:,.4f} yukarı kırılarak yeni güçlü desteğe dönüştü (S/R Flip). Hedef: ${target:,.4f}',
                        'lines': [
                            {'name': 'S/R Flip Destek Çizgisi', 'points': line_pts, 'color': '#10b981', 'lineWidth': 2, 'lineStyle': 2}
                        ]
                    })
                    break

    if len(valleys) >= 2:
        for v in valleys[-4:-1]:
            sup = v['price']
            breaks = [i for i in range(v['index'] + 2, n) if df['close'].iloc[i] < sup * 0.995]
            if breaks:
                first_brk = breaks[0]
                post_highs = df['high'].iloc[first_brk:]
                if len(post_highs) > 0 and post_highs.max() >= sup - 0.35 * current_atr and current_price <= sup * 1.005:
                    target = current_price - (current_atr * 2.8)
                    line_pts = _horizontal_line(df, v['index'], n - 1, sup)
                    patterns.append({
                        'name': 'Destek/Direnç Dönüşümü (S/R Flip Retest)',
                        'type': 'BEARISH',
                        'category': '3. S/R Flip Retest',
                        'quality_score': 92,
                        'flip_level': round(sup, 4),
                        'breakout_level': round(sup, 4),
                        'target': round(target, 4),
                        'description': f'Eski kilit destek ${sup:,.4f} aşağı kırılarak yeni güçlü dirence dönüştü (S/R Flip). Hedef: ${target:,.4f}',
                        'lines': [
                            {'name': 'S/R Flip Direnç Çizgisi', 'points': line_pts, 'color': '#f43f5e', 'lineWidth': 2, 'lineStyle': 2}
                        ]
                    })
                    break

    # ─────────────────────────────────────────────────────────────────────────
    # 5. 🇼 DOUBLE BOTTOM (W) & 🇲 DOUBLE TOP (M)
    # ─────────────────────────────────────────────────────────────────────────
    if len(valleys) >= 2:
        v1, v2 = valleys[-2], valleys[-1]
        bars_between = v2['index'] - v1['index']
        if 8 <= bars_between <= 45 and (n - 1 - v2['index']) <= 18:
            price_diff_pct = abs(v1['price'] - v2['price']) / v1['price'] * 100.0
            if price_diff_pct <= 1.8:
                neckline = float(df['high'].iloc[v1['index']:v2['index'] + 1].max())
                target = neckline + (neckline - min(v1['price'], v2['price']))
                
                line_neck = _horizontal_line(df, v1['index'], n - 1, neckline)
                line_bottom = _horizontal_line(df, v1['index'], v2['index'], min(v1['price'], v2['price']))
                
                patterns.append({
                    'name': 'Double Bottom (İkili Dip W Formasyonu)',
                    'type': 'BULLISH',
                    'category': '5. Double Bottom / Top',
                    'quality_score': 94,
                    'neckline': round(neckline, 4),
                    'breakout_level': round(neckline, 4),
                    'target': round(target, 4),
                    'description': f'${v1["price"]:,.4f} ve ${v2["price"]:,.4f} seviyelerinde simetrik ikili dip (W). Boyun: ${neckline:,.4f}. Hedef: ${target:,.4f}',
                    'lines': [
                        {'name': 'W Boyun Çizgisi (Neckline)', 'points': line_neck, 'color': '#fbbf24', 'lineWidth': 2, 'lineStyle': 0},
                        {'name': 'W Taban Destek Seviyesi', 'points': line_bottom, 'color': '#10b981', 'lineWidth': 1, 'lineStyle': 2}
                    ]
                })

    if len(peaks) >= 2:
        p1, p2 = peaks[-2], peaks[-1]
        bars_between = p2['index'] - p1['index']
        if 8 <= bars_between <= 45 and (n - 1 - p2['index']) <= 18:
            price_diff_pct = abs(p1['price'] - p2['price']) / p1['price'] * 100.0
            if price_diff_pct <= 1.8:
                neckline = float(df['low'].iloc[p1['index']:p2['index'] + 1].min())
                target = neckline - (max(p1['price'], p2['price']) - neckline)
                
                line_neck = _horizontal_line(df, p1['index'], n - 1, neckline)
                line_top = _horizontal_line(df, p1['index'], p2['index'], max(p1['price'], p2['price']))
                
                patterns.append({
                    'name': 'Double Top (İkili Tepe M Formasyonu)',
                    'type': 'BEARISH',
                    'category': '5. Double Bottom / Top',
                    'quality_score': 94,
                    'neckline': round(neckline, 4),
                    'breakout_level': round(neckline, 4),
                    'target': round(target, 4),
                    'description': f'${p1["price"]:,.4f} ve ${p2["price"]:,.4f} seviyelerinde çift tepe (M). Boyun: ${neckline:,.4f}. Hedef: ${target:,.4f}',
                    'lines': [
                        {'name': 'M Boyun Çizgisi (Neckline)', 'points': line_neck, 'color': '#fbbf24', 'lineWidth': 2, 'lineStyle': 0},
                        {'name': 'M Tavan Direnç Seviyesi', 'points': line_top, 'color': '#f43f5e', 'lineWidth': 1, 'lineStyle': 2}
                    ]
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 6. 📊 RANGE KIRILIMI & LİKİDİTE SAPMASI (Deviation Reclaim)
    # ─────────────────────────────────────────────────────────────────────────
    if n >= 40:
        look = min(40, n - 5)
        range_high = float(df['high'].iloc[-look:-5].max())
        range_low = float(df['low'].iloc[-look:-5].min())
        range_height = range_high - range_low
        start_idx = max(0, n - look)

        # A. Range Ust Kirilimi
        if current_price >= range_high * 0.997 and df['low'].iloc[-4:].min() <= range_high + 0.3 * current_atr:
            target = range_high + range_height
            line_top = _horizontal_line(df, start_idx, n - 1, range_high)
            line_bot = _horizontal_line(df, start_idx, n - 1, range_low)
            patterns.append({
                'name': 'Range (Yatay Kanal) Kırılımı & Retest',
                'type': 'BULLISH',
                'category': '4. Range Kırılım & Retest',
                'quality_score': 89,
                'breakout_level': round(range_high, 4),
                'range_high': round(range_high, 4),
                'range_low': round(range_low, 4),
                'target': round(target, 4),
                'description': f'${range_low:,.4f} - ${range_high:,.4f} akümülasyon kanalı yukarı kırıldı. Hedef: ${target:,.4f}',
                'lines': [
                    {'name': 'Range Tavanı', 'points': line_top, 'color': '#38bdf8', 'lineWidth': 2, 'lineStyle': 0},
                    {'name': 'Range Tabanı', 'points': line_bot, 'color': '#38bdf8', 'lineWidth': 1, 'lineStyle': 2}
                ]
            })
        
        # B. Range Likidite Sapmasi (Ayı Tuzağı)
        elif df['low'].iloc[-6:].min() < range_low * 0.992 and current_price >= range_low * 1.002:
            target = range_high
            line_top = _horizontal_line(df, start_idx, n - 1, range_high)
            line_bot = _horizontal_line(df, start_idx, n - 1, range_low)
            patterns.append({
                'name': 'Range Likidite Sapması (Ayı Tuzağı / Deviation)',
                'type': 'BULLISH',
                'category': '4. Range Kırılım & Retest',
                'quality_score': 95,
                'breakout_level': round(range_low, 4),
                'range_high': round(range_high, 4),
                'range_low': round(range_low, 4),
                'target': round(target, 4),
                'description': f'${range_low:,.4f} Range tabanı altına sahte kırılım (Ayı Tuzağı) sonrası güçlü geri dönüş. Hedef: ${target:,.4f}',
                'lines': [
                    {'name': 'Range Tavanı (Hedef)', 'points': line_top, 'color': '#38bdf8', 'lineWidth': 2, 'lineStyle': 0},
                    {'name': 'Sapma Reclaim Tabanı', 'points': line_bot, 'color': '#10b981', 'lineWidth': 2, 'lineStyle': 0}
                ]
            })

    patterns.sort(key=lambda x: x.get('quality_score', 50), reverse=True)
    return patterns
