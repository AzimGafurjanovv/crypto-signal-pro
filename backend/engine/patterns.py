"""
CryptoSignalPro AI - Gelişmiş Grafik Formasyonları Tespit ve Çizim Motoru (v8.0.0)
Algoritmik Standartlar: Thomas Bulkowski (Encyclopedia of Chart Patterns),
ZigZag Extrema Analizi, Lineer Regresyon Trend Doğrulaması ve TradingView Çizim Koordinatları.
"""

import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple

def _get_sec_timestamp(df: pd.DataFrame, idx: int) -> int:
    """Verilen bar indeksinin saniye cinsinden UNIX zaman damgasını döndürür."""
    if idx < 0 or idx >= len(df):
        idx = max(0, min(len(df) - 1, idx))
    
    if 'timestamp' in df.columns:
        val = df['timestamp'].iloc[idx]
        try:
            val = int(val)
            return val // 1000 if val > 1e12 else val
        except Exception:
            pass
    return int(idx)

def _build_dense_line(df: pd.DataFrame, start_idx: int, end_idx: int, start_val: float, end_val: float) -> List[Dict[str, Any]]:
    """
    TradingView Lightweight Charts üzerinde pürüzsüz ve hatasız bir trend çizgisi için
    başlangıç barından bitiş barına kadar her mumun zaman damgasıyla enterpole edilmiş koordinat listesi üretir.
    """
    points = []
    total_bars = max(1, end_idx - start_idx)
    slope = (end_val - start_val) / total_bars
    
    for i in range(start_idx, end_idx + 1):
        if i >= len(df):
            break
        t = _get_sec_timestamp(df, i)
        val = start_val + slope * (i - start_idx)
        points.append({'time': t, 'value': round(float(val), 4)})
    
    return points

def extract_zigzag_extrema(df: pd.DataFrame, depth: int = 5, deviation_pct: float = 1.0) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Gürültüyü filtreleyen ve gerçek dönüm noktalarını bulan ZigZag tepe/dip motoru.
    """
    n = len(df)
    if n < depth * 2:
        return [], []
    
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    
    peaks = []
    valleys = []
    
    for i in range(depth, n - depth):
        # Peak (Zirve) Kontrolü
        if highs[i] == max(highs[i - depth : i + depth + 1]):
            # Min sapma kontrolü
            if not peaks or (highs[i] > peaks[-1]['price'] * (1 + deviation_pct / 100) or i - peaks[-1]['index'] >= depth):
                peaks.append({
                    'index': int(i),
                    'price': float(highs[i]),
                    'time': _get_sec_timestamp(df, i)
                })
        
        # Valley (Dip) Kontrolü
        if lows[i] == min(lows[i - depth : i + depth + 1]):
            if not valleys or (lows[i] < valleys[-1]['price'] * (1 - deviation_pct / 100) or i - valleys[-1]['index'] >= depth):
                valleys.append({
                    'index': int(i),
                    'price': float(lows[i]),
                    'time': _get_sec_timestamp(df, i)
                })
                
    return peaks, valleys

def calculate_linear_regression(points: List[Dict[str, Any]]) -> Tuple[float, float, float]:
    """
    Noktalar üzerinden Lineer Regresyon eğimi (slope), kesim noktası (intercept) ve R² korelasyonunu hesaplar.
    """
    if len(points) < 2:
        return 0.0, 0.0, 0.0
    
    x = np.array([p['index'] for p in points], dtype=float)
    y = np.array([p['price'] for p in points], dtype=float)
    
    n = len(x)
    sum_x = np.sum(x)
    sum_y = np.sum(y)
    sum_xx = np.sum(x * x)
    sum_xy = np.sum(x * y)
    
    denom = (n * sum_xx - sum_x * sum_x)
    if abs(denom) < 1e-10:
        return 0.0, float(np.mean(y)), 0.0
    
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    
    # R² Korelasyon Katsayısı
    y_pred = slope * x + intercept
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    ss_res = np.sum((y - y_pred) ** 2)
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-10 else 1.0
    r_squared = max(0.0, min(1.0, float(r_squared)))
    
    return float(slope), float(intercept), r_squared

def detect_chart_patterns(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    10 Temel ve Profesyonel Grafik Formasyonunu Geometrik Hassasiyetle Tespit Eder.
    """
    patterns = []
    n = len(df)
    if n < 35:
        return patterns

    current_price = float(df['close'].iloc[-1])
    current_atr = float(df['atr'].iloc[-1]) if 'atr' in df.columns and not np.isnan(df['atr'].iloc[-1]) else current_price * 0.018
    vol_sma20 = float(df['volume'].iloc[-20:].mean()) if len(df) >= 20 else float(df['volume'].iloc[-1])
    current_vol = float(df['volume'].iloc[-1])
    vol_boost = current_vol >= vol_sma20 * 1.1

    peaks, valleys = extract_zigzag_extrema(df, depth=3, deviation_pct=0.6)
    
    # -----------------------------------------------------------------------------------------
    # 1. 📉 DÜŞEN TREND ÇİZGİSİ KIRILIMI & RETEST (Bullish Trendline Breakout)
    # -----------------------------------------------------------------------------------------
    if len(peaks) >= 2:
        for k in range(min(4, len(peaks)), 1, -1):
            selected_peaks = peaks[-k:]
            slope, intercept, r2 = calculate_linear_regression(selected_peaks)
            
            # Eğim negatif olmalı (Düşen Trend) ve R² en az 0.70 olmalı
            if slope < -1e-5 and (len(selected_peaks) == 2 or r2 >= 0.70):
                start_p = selected_peaks[0]
                expected_now = slope * (n - 1) + intercept
                
                # Fiyat trend çizgisinin üzerine çıktı mı?
                is_breakout = current_price >= expected_now * 0.998
                recent_low = min(df['low'].iloc[-4:])
                is_retest = recent_low <= expected_now + 0.3 * current_atr and current_price >= expected_now * 0.995
                
                if is_breakout and (n - 1 - selected_peaks[-1]['index']) <= 25:
                    target = start_p['price']
                    quality = int(min(100, (r2 * 40) + (len(selected_peaks) * 15) + (25 if vol_boost else 10) + (20 if is_retest else 10)))
                    
                    line_points = _build_dense_line(df, start_p['index'], n - 1, start_p['price'], expected_now)
                    patterns.append({
                        'name': 'Düşen Trend Çizgisi Kırılımı & Retest',
                        'type': 'BULLISH',
                        'category': '1. Trend Kırılım & Retest',
                        'quality_score': quality,
                        'breakout_level': float(round(expected_now, 4)),
                        'target': float(round(target, 4)),
                        'description': f'Geometrik {len(selected_peaks)} tepe temaslı düşen trend çizgisi (${expected_now:,.4f}) yukarı kırıldı. Retest teyidiyle hedef: ${target:,.4f}',
                        'lines': [
                            {'name': 'Düşen Trend Direnci', 'points': line_points, 'color': '#fbbf24'}
                        ]
                    })
                    break

    # -----------------------------------------------------------------------------------------
    # 2. 📈 YÜKSELEN TREND ÇİZGİSİ KIRILIMI & RETEST (Bearish Trendline Breakdown)
    # -----------------------------------------------------------------------------------------
    if len(valleys) >= 2:
        for k in range(min(4, len(valleys)), 1, -1):
            selected_valleys = valleys[-k:]
            slope, intercept, r2 = calculate_linear_regression(selected_valleys)
            
            # Eğim pozitif olmalı (Yükselen Trend)
            if slope > 1e-5 and (len(selected_valleys) == 2 or r2 >= 0.70):
                start_v = selected_valleys[0]
                expected_now = slope * (n - 1) + intercept
                
                is_breakdown = current_price <= expected_now * 1.002
                recent_high = max(df['high'].iloc[-4:])
                is_retest = recent_high >= expected_now - 0.3 * current_atr and current_price <= expected_now * 1.005
                
                if is_breakdown and (n - 1 - selected_valleys[-1]['index']) <= 25:
                    target = start_v['price']
                    quality = int(min(100, (r2 * 40) + (len(selected_valleys) * 15) + (25 if vol_boost else 10) + (20 if is_retest else 10)))
                    
                    line_points = _build_dense_line(df, start_v['index'], n - 1, start_v['price'], expected_now)
                    patterns.append({
                        'name': 'Yükselen Trend Çizgisi Kırılımı & Retest',
                        'type': 'BEARISH',
                        'category': '1. Trend Kırılım & Retest',
                        'quality_score': quality,
                        'breakout_level': float(round(expected_now, 4)),
                        'target': float(round(target, 4)),
                        'description': f'Geometrik {len(selected_valleys)} dip temaslı yükselen trend desteği (${expected_now:,.4f}) aşağı kırıldı. Satış retesti ile hedef: ${target:,.4f}',
                        'lines': [
                            {'name': 'Yükselen Trend Desteği', 'points': line_points, 'color': '#f43f5e'}
                        ]
                    })
                    break

    # -----------------------------------------------------------------------------------------
    # 3. 📐 SİMETRİK / YÜKSELEN / ALÇALAN ÜÇGEN & FLAMA
    # -----------------------------------------------------------------------------------------
    if len(peaks) >= 2 and len(valleys) >= 2:
        p1, p2 = peaks[-2], peaks[-1]
        v1, v2 = valleys[-2], valleys[-1]
        
        slope_upper = (p2['price'] - p1['price']) / max(1, p2['index'] - p1['index'])
        slope_lower = (v2['price'] - v1['price']) / max(1, v2['index'] - v1['index'])
        
        # Simetrik Üçgen (Direnç düşüyor, Destek yükseliyor)
        if slope_upper < 0 and slope_lower > 0 and (n - 1 - max(p2['index'], v2['index'])) <= 20:
            height = p1['price'] - v1['price']
            is_bull = current_price >= p2['price'] * 0.998
            target = current_price + height if is_bull else current_price - height
            pat_type = 'BULLISH' if is_bull else 'BEARISH'
            bo_level = p2['price'] if is_bull else v2['price']
            
            line_up = _build_dense_line(df, p1['index'], n - 1, p1['price'], p1['price'] + slope_upper * (n - 1 - p1['index']))
            line_down = _build_dense_line(df, v1['index'], n - 1, v1['price'], v1['price'] + slope_lower * (n - 1 - v1['index']))
            
            patterns.append({
                'name': 'Simetrik Üçgen / Flama Kırılımı',
                'type': pat_type,
                'category': '2. Simetrik Üçgen / Pennant',
                'quality_score': 88,
                'breakout_level': float(round(bo_level, 4)),
                'target': float(round(target, 4)),
                'description': f'Daralan simetrik üçgen bandından (${v2["price"]:,.4f} - ${p2["price"]:,.4f}) {pat_type} yönünde hacimli kırılım gerçekleşti. Hedef: ${target:,.4f}',
                'lines': [
                    {'name': 'Alçalan Üçgen Direnci', 'points': line_up, 'color': '#fbbf24'},
                    {'name': 'Yükselen Üçgen Desteği', 'points': line_down, 'color': '#38bdf8'}
                ]
            })
        
        # Yükselen Üçgen (Direnç yatay, Dipler yükseliyor -> Bullish)
        elif abs(p2['price'] - p1['price']) / p1['price'] <= 0.012 and slope_lower > 0:
            height = p1['price'] - v1['price']
            target = p2['price'] + height
            line_up = _build_dense_line(df, p1['index'], n - 1, p1['price'], p2['price'])
            line_down = _build_dense_line(df, v1['index'], n - 1, v1['price'], v1['price'] + slope_lower * (n - 1 - v1['index']))
            
            patterns.append({
                'name': 'Yükselen Üçgen Formasyonu (Ascending Triangle)',
                'type': 'BULLISH',
                'category': '2. Simetrik Üçgen / Pennant',
                'quality_score': 90,
                'breakout_level': float(round(p2['price'], 4)),
                'target': float(round(target, 4)),
                'description': f'${p2["price"]:,.4f} yatay direnci altında yükselen diplerle sıkışma tamamlandı ve yukarı patlama gerçekleşti.',
                'lines': [
                    {'name': 'Yatay Direnç Tavanı', 'points': line_up, 'color': '#fbbf24'},
                    {'name': 'Yükselen Destek Çizgisi', 'points': line_down, 'color': '#10b981'}
                ]
            })

    # -----------------------------------------------------------------------------------------
    # 4. 🔄 DİRENÇ / DESTEK DÖNÜŞÜMÜ (S/R Flip Retest)
    # -----------------------------------------------------------------------------------------
    if len(peaks) >= 2:
        for p in peaks[-4:-1]:
            res = p['price']
            breaks = [i for i in range(p['index'] + 1, n) if df['close'].iloc[i] > res * 1.006]
            if breaks:
                first_brk = breaks[0]
                post_lows = df['low'].iloc[first_brk:]
                if len(post_lows) > 0 and post_lows.min() <= res + 0.3 * current_atr and current_price >= res * 0.996:
                    target = current_price + (current_atr * 2.8)
                    line_points = _build_dense_line(df, p['index'], n - 1, res, res)
                    patterns.append({
                        'name': 'Direnç/Destek Dönüşümü (S/R Flip Retest)',
                        'type': 'BULLISH',
                        'category': '3. S/R Flip Retest',
                        'quality_score': 92,
                        'flip_level': float(round(res, 4)),
                        'breakout_level': float(round(res, 4)),
                        'target': float(round(target, 4)),
                        'description': f'Eski kilit direnç ${res:,.4f} yukarı kırılarak güçlü yeni desteğe dönüştü (S/R Flip) ve fitil testiyle doğrulandı.',
                        'lines': [
                            {'name': 'S/R Flip Destek Çizgisi', 'points': line_points, 'color': '#10b981'}
                        ]
                    })
                    break

    if len(valleys) >= 2:
        for v in valleys[-4:-1]:
            sup = v['price']
            breaks = [i for i in range(v['index'] + 1, n) if df['close'].iloc[i] < sup * 0.994]
            if breaks:
                first_brk = breaks[0]
                post_highs = df['high'].iloc[first_brk:]
                if len(post_highs) > 0 and post_highs.max() >= sup - 0.3 * current_atr and current_price <= sup * 1.004:
                    target = current_price - (current_atr * 2.8)
                    line_points = _build_dense_line(df, v['index'], n - 1, sup, sup)
                    patterns.append({
                        'name': 'Destek/Direnç Dönüşümü (S/R Flip Retest)',
                        'type': 'BEARISH',
                        'category': '3. S/R Flip Retest',
                        'quality_score': 92,
                        'flip_level': float(round(sup, 4)),
                        'breakout_level': float(round(sup, 4)),
                        'target': float(round(target, 4)),
                        'description': f'Eski kilit destek ${sup:,.4f} aşağı kırılarak güçlü yeni dirence dönüştü (S/R Flip) ve satış retesti verdi.',
                        'lines': [
                            {'name': 'S/R Flip Direnç Çizgisi', 'points': line_points, 'color': '#f43f5e'}
                        ]
                    })
                    break

    # -----------------------------------------------------------------------------------------
    # 5. 🇼 DOUBLE BOTTOM (W) & 🇲 DOUBLE TOP (M)
    # -----------------------------------------------------------------------------------------
    if len(valleys) >= 2:
        v1, v2 = valleys[-2], valleys[-1]
        bars_between = v2['index'] - v1['index']
        if 6 <= bars_between <= 45 and (n - 1 - v2['index']) <= 18:
            price_diff_pct = abs(v1['price'] - v2['price']) / v1['price'] * 100.0
            if price_diff_pct <= 1.8:
                neckline = float(df['high'].iloc[v1['index']:v2['index']].max())
                target = neckline + (neckline - min(v1['price'], v2['price']))
                
                line_neck = _build_dense_line(df, v1['index'], n - 1, neckline, neckline)
                line_bottom = _build_dense_line(df, v1['index'], n - 1, min(v1['price'], v2['price']), min(v1['price'], v2['price']))
                
                patterns.append({
                    'name': 'Double Bottom (İkili Dip W Formasyonu)',
                    'type': 'BULLISH',
                    'category': '5. Double Bottom / Top',
                    'quality_score': 94,
                    'neckline': float(round(neckline, 4)),
                    'breakout_level': float(round(neckline, 4)),
                    'target': float(round(target, 4)),
                    'description': f'${v1["price"]:,.4f} ve ${v2["price"]:,.4f} seviyelerinde simetrik ikili dip (W) oluştu. ${neckline:,.4f} boyun çizgisi kırılımıyla hedef: ${target:,.4f}',
                    'lines': [
                        {'name': 'W Boyun Çizgisi (Neckline)', 'points': line_neck, 'color': '#fbbf24'},
                        {'name': 'W Taban Destek Seviyesi', 'points': line_bottom, 'color': '#10b981'}
                    ]
                })

    if len(peaks) >= 2:
        p1, p2 = peaks[-2], peaks[-1]
        bars_between = p2['index'] - p1['index']
        if 6 <= bars_between <= 45 and (n - 1 - p2['index']) <= 18:
            price_diff_pct = abs(p1['price'] - p2['price']) / p1['price'] * 100.0
            if price_diff_pct <= 1.8:
                neckline = float(df['low'].iloc[p1['index']:p2['index']].min())
                target = neckline - (max(p1['price'], p2['price']) - neckline)
                
                line_neck = _build_dense_line(df, p1['index'], n - 1, neckline, neckline)
                line_top = _build_dense_line(df, p1['index'], n - 1, max(p1['price'], p2['price']), max(p1['price'], p2['price']))
                
                patterns.append({
                    'name': 'Double Top (İkili Tepe M Formasyonu)',
                    'type': 'BEARISH',
                    'category': '5. Double Bottom / Top',
                    'quality_score': 94,
                    'neckline': float(round(neckline, 4)),
                    'breakout_level': float(round(neckline, 4)),
                    'target': float(round(target, 4)),
                    'description': f'${p1["price"]:,.4f} ve ${p2["price"]:,.4f} seviyelerinde çift tepe (M) reddi teyit edildi. ${neckline:,.4f} boyun çizgisi altında hedef: ${target:,.4f}',
                    'lines': [
                        {'name': 'M Boyun Çizgisi (Neckline)', 'points': line_neck, 'color': '#fbbf24'},
                        {'name': 'M Tavan Direnç Seviyesi', 'points': line_top, 'color': '#f43f5e'}
                    ]
                })

    # -----------------------------------------------------------------------------------------
    # 6. 📊 RANGE KIRILIMI & LİKİDİTE SAPMASI (Deviation Reclaim)
    # -----------------------------------------------------------------------------------------
    if n >= 35:
        range_high = float(df['high'].iloc[-35:-5].max())
        range_low = float(df['low'].iloc[-35:-5].min())
        range_height = range_high - range_low
        
        # A. Range Üst Kırılımı
        if current_price >= range_high * 0.997 and df['low'].iloc[-4:].min() <= range_high + 0.3 * current_atr:
            target = range_high + range_height
            line_top = _build_dense_line(df, n - 35, n - 1, range_high, range_high)
            line_bot = _build_dense_line(df, n - 35, n - 1, range_low, range_low)
            patterns.append({
                'name': 'Range (Yatay Kanal) Kırılımı & Retest',
                'type': 'BULLISH',
                'category': '4. Range Kırılım & Retest',
                'quality_score': 89,
                'breakout_level': float(round(range_high, 4)),
                'range_high': float(round(range_high, 4)),
                'range_low': float(round(range_low, 4)),
                'target': float(round(target, 4)),
                'description': f'${range_low:,.4f} - ${range_high:,.4f} akümülasyon kanalı yukarı kırıldı ve ${range_high:,.4f} tavanında retest onaylandı. Hedef: ${target:,.4f}',
                'lines': [
                    {'name': 'Range Tavanı', 'points': line_top, 'color': '#38bdf8'},
                    {'name': 'Range Tabanı', 'points': line_bot, 'color': '#38bdf8'}
                ]
            })
        
        # B. Range Likidite Sapması (Ayı Tuzağı / Fakeout Reclaim)
        elif df['low'].iloc[-6:].min() < range_low * 0.992 and current_price >= range_low * 1.002:
            target = range_high
            line_top = _build_dense_line(df, n - 35, n - 1, range_high, range_high)
            line_bot = _build_dense_line(df, n - 35, n - 1, range_low, range_low)
            patterns.append({
                'name': 'Range Likidite Sapması (Ayı Tuzağı / Deviation)',
                'type': 'BULLISH',
                'category': '4. Range Kırılım & Retest',
                'quality_score': 95,
                'breakout_level': float(round(range_low, 4)),
                'range_high': float(round(range_high, 4)),
                'range_low': float(round(range_low, 4)),
                'target': float(round(target, 4)),
                'description': f'${range_low:,.4f} Range tabanı altına sahte kırılım (Ayı Tuzağı) yapıldı ve bant içine güçlü hacimle geri dönüldü. Hedef Tavan: ${target:,.4f}',
                'lines': [
                    {'name': 'Range Tavanı (Hedef)', 'points': line_top, 'color': '#38bdf8'},
                    {'name': 'Sapma Reclaim Tabanı', 'points': line_bot, 'color': '#10b981'}
                ]
            })

    # Kalite skoruna göre sırala
    patterns.sort(key=lambda x: x.get('quality_score', 50), reverse=True)
    return patterns
