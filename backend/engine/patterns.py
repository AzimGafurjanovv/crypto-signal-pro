import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from .indicators import find_swing_points

def detect_chart_patterns(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Kullanıcının talep ettiği 5 Kilit Profesyonel Setup ve Formasyon Motoru (İki Dilli TR/EN):
    1. TREND ÇİZGİSİ KIRILIMI + RETEST (Trendline Breakout + Retest)
    2. SİMETRİK ÜÇGEN / FLAMA KIRILIMI (Symmetrical Triangle / Pennant Breakout)
    3. DİRENÇ / DESTEK DÖNÜŞÜMÜ (S/R Flip Retest)
    4. RANGE KIRILIMI + RETEST / SAPMA (Range Breakout / Deviation Reclaim)
    5. DOUBLE BOTTOM (İKİLİ DİP W) / DOUBLE TOP (İKİLİ TEPE M)
    """
    patterns = []
    if len(df) < 35:
        return patterns

    swing_highs, swing_lows = find_swing_points(df, window=3)
    n = len(df)
    current_price = float(df['close'].iloc[-1])
    timestamps = df['timestamp'].values if 'timestamp' in df.columns else df.index.values

    # ---------------- 1. TREND ÇİZGİSİ KIRILIMI + RETEST (Trendline Breakout + Retest) ----------------
    if len(swing_highs) >= 3:
        sh1, sh2, sh3 = swing_highs[-3], swing_highs[-2], swing_highs[-1]
        if sh1['price'] > sh2['price'] > sh3['price']:
            slope = (sh3['price'] - sh1['price']) / (sh3['index'] - sh1['index'])
            expected_trend_level = sh1['price'] + slope * (n - 1 - sh1['index'])
            
            is_broken_up = current_price >= expected_trend_level * 0.998
            recent_low = min(df['low'].iloc[-4:])
            retested = recent_low <= expected_trend_level * 1.008 and current_price >= expected_trend_level * 0.995
            
            if is_broken_up and retested and (n - 1 - sh3['index']) <= 25:
                target = sh1['price']
                t1 = int(timestamps[sh1['index']]) // 1000 if hasattr(timestamps[0], '__int__') else int(sh1['index'])
                t_now = int(timestamps[-1]) // 1000 if hasattr(timestamps[0], '__int__') else int(n - 1)
                
                patterns.append({
                    'name': 'Trend Çizgisi Kırılımı + Retest (Trendline Breakout + Retest)',
                    'type': 'BULLISH',
                    'category': '1. Trend Kırılım & Retest',
                    'reliability': 'ÇOK YÜKSEK',
                    'breakout_level': float(expected_trend_level),
                    'target': float(target),
                    'description': f'Düşen ana trend çizgisi yukarı kırıldı ve ${expected_trend_level:,.2f} seviyesinde retest (onay) tamamlandı. Hedef: ${target:,.2f}',
                    'lines': [
                        {'name': 'Düşen Trend Çizgisi (Bearish Trendline)', 'points': [{'time': t1, 'value': float(sh1['price'])}, {'time': t_now, 'value': float(expected_trend_level)}], 'color': '#fbbf24'}
                    ]
                })

    if len(swing_lows) >= 3:
        sl1, sl2, sl3 = swing_lows[-3], swing_lows[-2], swing_lows[-1]
        if sl1['price'] < sl2['price'] < sl3['price']:
            slope = (sl3['price'] - sl1['price']) / (sl3['index'] - sl1['index'])
            expected_trend_level = sl1['price'] + slope * (n - 1 - sl1['index'])
            
            is_broken_down = current_price <= expected_trend_level * 1.002
            recent_high = max(df['high'].iloc[-4:])
            retested = recent_high >= expected_trend_level * 0.992 and current_price <= expected_trend_level * 1.005
            
            if is_broken_down and retested and (n - 1 - sl3['index']) <= 25:
                target = sl1['price']
                t1 = int(timestamps[sl1['index']]) // 1000 if hasattr(timestamps[0], '__int__') else int(sl1['index'])
                t_now = int(timestamps[-1]) // 1000 if hasattr(timestamps[0], '__int__') else int(n - 1)
                
                patterns.append({
                    'name': 'Trend Çizgisi Kırılımı + Retest (Trendline Breakout + Retest)',
                    'type': 'BEARISH',
                    'category': '1. Trend Kırılım & Retest',
                    'reliability': 'ÇOK YÜKSEK',
                    'breakout_level': float(expected_trend_level),
                    'target': float(target),
                    'description': f'Yükselen ana trend çizgisi aşağı kırıldı ve ${expected_trend_level:,.2f} seviyesinde retest satışı geldi. Hedef: ${target:,.2f}',
                    'lines': [
                        {'name': 'Yükselen Trend Çizgisi (Bullish Trendline)', 'points': [{'time': t1, 'value': float(sl1['price'])}, {'time': t_now, 'value': float(expected_trend_level)}], 'color': '#fbbf24'}
                    ]
                })

    # ---------------- 2. SİMETRİK ÜÇGEN / FLAMA KIRILIMI (Symmetrical Triangle / Pennant Breakout) ----------------
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        sh1, sh2 = swing_highs[-2], swing_highs[-1]
        sl1, sl2 = swing_lows[-2], swing_lows[-1]
        
        is_converging = (sh2['price'] < sh1['price'] * 0.995) and (sl2['price'] > sl1['price'] * 1.005)
        if is_converging and (n - 1 - max(sh2['index'], sl2['index'])) <= 20:
            triangle_height = sh1['price'] - sl1['price']
            is_break_up = current_price >= sh2['price'] * 0.998
            target = current_price + triangle_height if is_break_up else current_price - triangle_height
            pat_type = 'BULLISH' if is_break_up else 'BEARISH'
            
            t1 = int(timestamps[sh1['index']]) // 1000 if hasattr(timestamps[0], '__int__') else int(sh1['index'])
            t2 = int(timestamps[sh2['index']]) // 1000 if hasattr(timestamps[0], '__int__') else int(sh2['index'])
            tl1 = int(timestamps[sl1['index']]) // 1000 if hasattr(timestamps[0], '__int__') else int(sl1['index'])
            tl2 = int(timestamps[sl2['index']]) // 1000 if hasattr(timestamps[0], '__int__') else int(sl2['index'])
            
            patterns.append({
                'name': 'Simetrik Üçgen / Flama Kırılımı (Symmetrical Triangle / Pennant Breakout)',
                'type': pat_type,
                'category': '2. Simetrik Üçgen / Pennant',
                'reliability': 'ÇOK YÜKSEK',
                'target': float(target),
                'description': f'Daralan flama/üçgen bandından (${sl2["price"]:,.2f} - ${sh2["price"]:,.2f}) hacimli patlama gerçekleşti. Hedef: ${target:,.2f}',
                'lines': [
                    {'name': 'Alçalan Direnç', 'points': [{'time': t1, 'value': float(sh1['price'])}, {'time': t2, 'value': float(sh2['price'])}], 'color': '#f43f5e'},
                    {'name': 'Yükselen Destek', 'points': [{'time': tl1, 'value': float(sl1['price'])}, {'time': tl2, 'value': float(sl2['price'])}], 'color': '#10b981'}
                ]
            })

    # ---------------- 3. DİRENÇ / DESTEK DÖNÜŞÜMÜ (S/R Flip Retest) ----------------
    for sh in swing_highs[-4:-1]:
        res_level = sh['price']
        breaks = [i for i in range(sh['index'] + 1, n) if df['close'].iloc[i] > res_level * 1.005]
        if breaks:
            first_break = breaks[0]
            recent_lows = df['low'].iloc[first_break:]
            if len(recent_lows) > 0 and recent_lows.min() <= res_level * 1.01 and current_price >= res_level * 0.996:
                atr = float(df['atr'].iloc[-1]) if 'atr' in df.columns else current_price * 0.02
                target = current_price + (atr * 2.5)
                t_sh = int(timestamps[sh['index']]) // 1000 if hasattr(timestamps[0], '__int__') else int(sh['index'])
                t_now = int(timestamps[-1]) // 1000 if hasattr(timestamps[0], '__int__') else int(n - 1)
                
                patterns.append({
                    'name': 'Direnç/Destek Dönüşümü (S/R Flip Retest)',
                    'type': 'BULLISH',
                    'category': '3. S/R Flip Retest',
                    'reliability': 'ÇOK YÜKSEK',
                    'flip_level': float(res_level),
                    'target': float(target),
                    'description': f'Eski kilit direnç ${res_level:,.2f} yukarı kırılarak güçlü yeni desteğe dönüştü (S/R Flip) ve retest ile onaylandı.',
                    'lines': [
                        {'name': 'S/R Flip Destek Çizgisi', 'points': [{'time': t_sh, 'value': float(res_level)}, {'time': t_now, 'value': float(res_level)}], 'color': '#10b981'}
                    ]
                })
                break

    for sl in swing_lows[-4:-1]:
        supp_level = sl['price']
        breaks = [i for i in range(sl['index'] + 1, n) if df['close'].iloc[i] < supp_level * 0.995]
        if breaks:
            first_break = breaks[0]
            recent_highs = df['high'].iloc[first_break:]
            if len(recent_highs) > 0 and recent_highs.max() >= supp_level * 0.99 and current_price <= supp_level * 1.004:
                atr = float(df['atr'].iloc[-1]) if 'atr' in df.columns else current_price * 0.02
                target = current_price - (atr * 2.5)
                t_sl = int(timestamps[sl['index']]) // 1000 if hasattr(timestamps[0], '__int__') else int(sl['index'])
                t_now = int(timestamps[-1]) // 1000 if hasattr(timestamps[0], '__int__') else int(n - 1)
                
                patterns.append({
                    'name': 'Direnç/Destek Dönüşümü (S/R Flip Retest)',
                    'type': 'BEARISH',
                    'category': '3. S/R Flip Retest',
                    'reliability': 'ÇOK YÜKSEK',
                    'flip_level': float(supp_level),
                    'target': float(target),
                    'description': f'Eski kilit destek ${supp_level:,.2f} aşağı kırılarak güçlü yeni dirence dönüştü (S/R Flip) ve satış retesti verdi.',
                    'lines': [
                        {'name': 'S/R Flip Direnç Çizgisi', 'points': [{'time': t_sl, 'value': float(supp_level)}, {'time': t_now, 'value': float(supp_level)}], 'color': '#f43f5e'}
                    ]
                })
                break

    # ---------------- 4. RANGE (YATAY BANT) KIRILIMI + RETEST / SAPMA ----------------
    if len(df) >= 30:
        range_high = df['high'].iloc[-35:-5].max()
        range_low = df['low'].iloc[-35:-5].min()
        range_height = range_high - range_low
        
        if current_price >= range_high * 0.997 and df['low'].iloc[-4:].min() <= range_high * 1.012:
            target = range_high + range_height
            t_start = int(timestamps[-35]) // 1000 if hasattr(timestamps[0], '__int__') else int(n - 35)
            t_now = int(timestamps[-1]) // 1000 if hasattr(timestamps[0], '__int__') else int(n - 1)
            patterns.append({
                'name': 'Range Kırılımı + Retest (Range Breakout + Retest)',
                'type': 'BULLISH',
                'category': '4. Range Kırılım & Retest',
                'reliability': 'ÇOK YÜKSEK',
                'range_high': float(range_high),
                'range_low': float(range_low),
                'target': float(target),
                'description': f'${range_low:,.2f} - ${range_high:,.2f} yatay akümülasyon bandı yukarı kırıldı ve ${range_high:,.2f} tavanında retest onaylandı. Hedef: ${target:,.2f}',
                'lines': [
                    {'name': 'Range Tavanı (Range High)', 'points': [{'time': t_start, 'value': float(range_high)}, {'time': t_now, 'value': float(range_high)}], 'color': '#38bdf8'},
                    {'name': 'Range Tabanı (Range Low)', 'points': [{'time': t_start, 'value': float(range_low)}, {'time': t_now, 'value': float(range_low)}], 'color': '#38bdf8'}
                ]
            })
        elif df['low'].iloc[-6:].min() < range_low * 0.992 and current_price >= range_low * 1.002:
            target = range_high
            t_start = int(timestamps[-35]) // 1000 if hasattr(timestamps[0], '__int__') else int(n - 35)
            t_now = int(timestamps[-1]) // 1000 if hasattr(timestamps[0], '__int__') else int(n - 1)
            patterns.append({
                'name': 'Range Likidite Sapması (Deviation Reclaim)',
                'type': 'BULLISH',
                'category': '4. Range Kırılım & Retest',
                'reliability': 'ÇOK YÜKSEK',
                'range_high': float(range_high),
                'range_low': float(range_low),
                'target': float(target),
                'description': f'${range_low:,.2f} Range tabanı altına sahte kırılım (Deviation / Fakeout) yapıldı ve bant içine geri dönüldü. Hedef Range Tavanı: ${target:,.2f}',
                'lines': [
                    {'name': 'Range Tavanı', 'points': [{'time': t_start, 'value': float(range_high)}, {'time': t_now, 'value': float(range_high)}], 'color': '#38bdf8'},
                    {'name': 'Range Tabanı', 'points': [{'time': t_start, 'value': float(range_low)}, {'time': t_now, 'value': float(range_low)}], 'color': '#38bdf8'}
                ]
            })

    # ---------------- 5. DOUBLE BOTTOM (İKİLİ DİP W) / DOUBLE TOP (İKİLİ TEPE M) ----------------
    if len(swing_lows) >= 2:
        sl1, sl2 = swing_lows[-2], swing_lows[-1]
        if (n - 1 - sl2['index']) <= 18:
            price_diff_pct = abs(sl1['price'] - sl2['price']) / sl1['price'] * 100.0
            if price_diff_pct <= 1.8:
                neckline = df['high'].iloc[sl1['index']:sl2['index']].max()
                target = neckline + (neckline - min(sl1['price'], sl2['price']))
                t_neck = int(timestamps[sl1['index']]) // 1000 if hasattr(timestamps[0], '__int__') else int(sl1['index'])
                t_now = int(timestamps[-1]) // 1000 if hasattr(timestamps[0], '__int__') else int(n - 1)
                patterns.append({
                    'name': 'Double Bottom (İkili Dip W Pattern)',
                    'type': 'BULLISH',
                    'category': '5. Double Bottom / Top',
                    'reliability': 'YÜKSEK',
                    'neckline': float(neckline),
                    'target': float(target),
                    'description': f'${sl1["price"]:,.2f} ve ${sl2["price"]:,.2f} seviyelerinde çift dip (W) tamamlandı. ${neckline:,.2f} boyun çizgisi üzerinde hedef: ${target:,.2f}',
                    'lines': [
                        {'name': 'W Boyun Çizgisi (Neckline)', 'points': [{'time': t_neck, 'value': float(neckline)}, {'time': t_now, 'value': float(neckline)}], 'color': '#fbbf24'}
                    ]
                })

    if len(swing_highs) >= 2:
        sh1, sh2 = swing_highs[-2], swing_highs[-1]
        if (n - 1 - sh2['index']) <= 18:
            price_diff_pct = abs(sh1['price'] - sh2['price']) / sh1['price'] * 100.0
            if price_diff_pct <= 1.8:
                neckline = df['low'].iloc[sh1['index']:sh2['index']].min()
                target = neckline - (max(sh1['price'], sh2['price']) - neckline)
                t_neck = int(timestamps[sh1['index']]) // 1000 if hasattr(timestamps[0], '__int__') else int(sh1['index'])
                t_now = int(timestamps[-1]) // 1000 if hasattr(timestamps[0], '__int__') else int(n - 1)
                patterns.append({
                    'name': 'Double Top (İkili Tepe M Pattern)',
                    'type': 'BEARISH',
                    'category': '5. Double Bottom / Top',
                    'reliability': 'YÜKSEK',
                    'neckline': float(neckline),
                    'target': float(target),
                    'description': f'${sh1["price"]:,.2f} ve ${sh2["price"]:,.2f} seviyelerinde çift tepe (M) satışı teyit edildi. ${neckline:,.2f} altında hedef: ${target:,.2f}',
                    'lines': [
                        {'name': 'M Boyun Çizgisi (Neckline)', 'points': [{'time': t_neck, 'value': float(neckline)}, {'time': t_now, 'value': float(neckline)}], 'color': '#fbbf24'}
                    ]
                })

    # ---------------- 6. ÖNCEKİ GÜN ZİRVE/DİP KIRILIMI + RETEST (PDH/PDL) (BENİM) ----------------
    if n >= 24:
        # Zaman damgası kullanarak her zaman diliminde (15m, 1h, 4h) tam 24 saatlik gerçek döngüyü bul
        if 'timestamp' in df.columns:
            ts_series = df['timestamp'].apply(lambda x: int(x)//1000 if int(x) > 1e12 else int(x))
            last_ts = int(ts_series.iloc[-1])
            sec_24h = 86400
            sec_48h = 172800

            current_day_mask = (ts_series >= (last_ts - sec_24h))
            prev_day_mask = (ts_series < (last_ts - sec_24h)) & (ts_series >= (last_ts - sec_48h))

            prev_day_slice = df[prev_day_mask]
            current_day_slice = df[current_day_mask]

            if len(prev_day_slice) >= 4 and len(current_day_slice) >= 4:
                pdh = float(prev_day_slice['high'].max())
                pdl = float(prev_day_slice['low'].min())
                curr_slice = current_day_slice
                t_start = int(ts_series[prev_day_mask].iloc[0])
                t_now = int(last_ts)
            else:
                lookback_pd = 24 if n >= 48 else n // 2
                prev_day_slice = df.iloc[-lookback_pd*2 : -lookback_pd]
                pdh = float(prev_day_slice['high'].max())
                pdl = float(prev_day_slice['low'].min())
                curr_slice = df.iloc[-lookback_pd:]
                t_start = int(timestamps[-lookback_pd*2]) // 1000 if hasattr(timestamps[0], '__int__') else int(n - lookback_pd*2)
                t_now = int(timestamps[-1]) // 1000 if hasattr(timestamps[0], '__int__') else int(n - 1)
        else:
            lookback_pd = 24 if n >= 48 else n // 2
            prev_day_slice = df.iloc[-lookback_pd*2 : -lookback_pd]
            pdh = float(prev_day_slice['high'].max())
            pdl = float(prev_day_slice['low'].min())
            curr_slice = df.iloc[-lookback_pd:]
            t_start = int(timestamps[-lookback_pd*2]) // 1000 if hasattr(timestamps[0], '__int__') else int(n - lookback_pd*2)
            t_now = int(timestamps[-1]) // 1000 if hasattr(timestamps[0], '__int__') else int(n - 1)

        curr_len = len(curr_slice)
        atr_val = float(df['atr'].iloc[-1]) if 'atr' in df.columns else (current_price * 0.015)
        tolerance = 0.3 * atr_val
        vol_sma20 = float(df['volume'].iloc[-20:].mean()) if len(df) >= 20 else float(df['volume'].iloc[-1])

        # 1. Kırılım Kapanışlarını Bul
        breakout_bars_bull = [idx for idx, (_, row) in enumerate(curr_slice.iterrows()) if float(row['close']) > pdh]
        breakout_bars_bear = [idx for idx, (_, row) in enumerate(curr_slice.iterrows()) if float(row['close']) < pdl]

        # 🟢 Bullish PDH Breakout + Retest + Onay Mumu Teyidi
        if breakout_bars_bull:
            first_bo = breakout_bars_bull[0]
            post_bo_slice = curr_slice.iloc[first_bo + 1:]
            
            retest_ok = False
            retest_idx = -1
            for idx, (_, row) in enumerate(post_bo_slice.iterrows()):
                # Invalidation
                if float(row['close']) < (pdh - tolerance):
                    break
                if float(row['low']) <= (pdh + tolerance):
                    retest_ok = True
                    retest_idx = first_bo + 1 + idx
                    break

            is_confirmed = False
            conf_detail = ""
            if retest_ok:
                candidate_bars = curr_slice.iloc[retest_idx : min(curr_len, retest_idx + 3)]
                for _, row in candidate_bars.iterrows():
                    c, o, h, l, v = float(row['close']), float(row['open']), float(row['high']), float(row['low']), float(row.get('volume', 0.0))
                    rng = h - l if h > l else 0.0001
                    body = abs(c - o)
                    
                    has_strong_body = (c > o) and (body >= 0.60 * rng)
                    level_held = (c > pdh)
                    vol_ok = (v >= vol_sma20)
                    
                    if has_strong_body and level_held and vol_ok:
                        is_confirmed = True
                        conf_detail = f"Güçlü Boğa İtki Mumu (Gövde: %{body/rng*100:.0f}, Hacim > Ort)"
                        break

            if is_confirmed:
                target = pdh + (pdh - pdl) * 0.618
                patterns.append({
                    'name': 'Önceki Gün Zirve Kırılımı + Retest (PDH/PDL) (Benim)',
                    'type': 'BULLISH',
                    'category': '6. PDH/PDL Kırılım & Retest (Benim)',
                    'reliability': 'ÇOK YÜKSEK',
                    'breakout_level': float(pdh),
                    'target': float(target),
                    'description': f'Önceki günün zirvesi (${pdh:,.4f} PDH) kırıldı, 0.3xATR toleransla retest yapıldı ve onaylandı ({conf_detail}). Hedef: ${target:,.4f}',
                    'lines': [
                        {'name': 'Önceki Gün Zirvesi (PDH)', 'points': [{'time': t_start, 'value': float(pdh)}, {'time': t_now, 'value': float(pdh)}], 'color': '#10b981'},
                        {'name': 'Önceki Gün Dibi (PDL)', 'points': [{'time': t_start, 'value': float(pdl)}, {'time': t_now, 'value': float(pdl)}], 'color': '#ef4444'}
                    ]
                })

        # 🔴 Bearish PDL Breakdown + Retest + Onay Mumu Teyidi
        if breakout_bars_bear:
            first_bo = breakout_bars_bear[0]
            post_bo_slice = curr_slice.iloc[first_bo + 1:]
            
            retest_ok = False
            retest_idx = -1
            for idx, (_, row) in enumerate(post_bo_slice.iterrows()):
                if float(row['close']) > (pdl + tolerance):
                    break
                if float(row['high']) >= (pdl - tolerance):
                    retest_ok = True
                    retest_idx = first_bo + 1 + idx
                    break

            is_confirmed = False
            conf_detail = ""
            if retest_ok:
                candidate_bars = curr_slice.iloc[retest_idx : min(curr_len, retest_idx + 3)]
                for _, row in candidate_bars.iterrows():
                    c, o, h, l, v = float(row['close']), float(row['open']), float(row['high']), float(row['low']), float(row.get('volume', 0.0))
                    rng = h - l if h > l else 0.0001
                    body = abs(c - o)
                    
                    has_strong_body = (c < o) and (body >= 0.60 * rng)
                    level_held = (c < pdl)
                    vol_ok = (v >= vol_sma20)
                    
                    if has_strong_body and level_held and vol_ok:
                        is_confirmed = True
                        conf_detail = f"Güçlü Ayı İtki Mumu (Gövde: %{body/rng*100:.0f}, Hacim > Ort)"
                        break

            if is_confirmed:
                target = pdl - (pdh - pdl) * 0.618
                patterns.append({
                    'name': 'Önceki Gün Dip Kırılımı + Retest (PDH/PDL) (Benim)',
                    'type': 'BEARISH',
                    'category': '6. PDH/PDL Kırılım & Retest (Benim)',
                    'reliability': 'ÇOK YÜKSEK',
                    'breakout_level': float(pdl),
                    'target': float(target),
                    'description': f'Önceki günün dibi (${pdl:,.4f} PDL) kırıldı, 0.3xATR toleransla retest yapıldı ve onaylandı ({conf_detail}). Hedef: ${target:,.4f}',
                    'lines': [
                        {'name': 'Önceki Gün Zirvesi (PDH)', 'points': [{'time': t_start, 'value': float(pdh)}, {'time': t_now, 'value': float(pdh)}], 'color': '#10b981'},
                        {'name': 'Önceki Gün Dibi (PDL)', 'points': [{'time': t_start, 'value': float(pdl)}, {'time': t_now, 'value': float(pdl)}], 'color': '#ef4444'}
                    ]
                })

    return patterns
