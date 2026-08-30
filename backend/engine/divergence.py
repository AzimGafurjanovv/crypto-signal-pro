import numpy as np
import pandas as pd
from typing import Dict, Any, List
from .indicators import find_swing_points

def detect_rsi_divergences(df: pd.DataFrame) -> Dict[str, Any]:
    """
    RSI ve Fiyat arasındaki Uyumsuzlukları (Regular & Hidden Divergence) tespit eder.
    Genişletilmiş 50 barlık pencere ve çoklu swing tepe/dip karşılaştırması.
    """
    if 'rsi' not in df.columns:
        return {'bullish_divergence': None, 'bearish_divergence': None}
        
    swing_highs, swing_lows = find_swing_points(df, window=4)
    rsi_values = df['rsi'].values
    n = len(df)
    
    bullish_div = None
    bearish_div = None
    
    # Bullish Divergence kontrolü (Regular LL vs RSI HL, Hidden HL vs RSI LL)
    if len(swing_lows) >= 2:
        sl2 = swing_lows[-1]
        
        # Son swing dip 50 bar içinde olmalı
        if (n - 1 - sl2['index']) <= 50:
            for idx in range(max(0, len(swing_lows) - 6), len(swing_lows) - 1)[::-1]:
                sl1 = swing_lows[idx]
                bars_gap = sl2['index'] - sl1['index']
                if bars_gap < 5 or bars_gap > 60:
                    continue
                    
                price_ll = sl2['price'] < sl1['price']
                rsi_hl = (rsi_values[sl2['index']] - rsi_values[sl1['index']]) >= 1.5
                
                # Regular Bullish Divergence (Trend Dönüşü)
                if price_ll and rsi_hl:
                    bullish_div = {
                        'type': 'REGULAR_BULLISH',
                        'name_tr': 'Pozitif Uyumsuzluk (Boğa Dönüşü - Regular Bullish Divergence)',
                        'price1': sl1['price'],
                        'price2': sl2['price'],
                        'rsi1': round(float(rsi_values[sl1['index']]), 1),
                        'rsi2': round(float(rsi_values[sl2['index']]), 1),
                        'recency_bars': int(n - 1 - sl2['index']),
                        'strength': 'GÜÇLÜ' if rsi_values[sl2['index']] <= 38 else 'ORTA'
                    }
                    break
                # Hidden Bullish Divergence (Trend Devamı)
                elif (sl2['price'] > sl1['price']) and (rsi_values[sl1['index']] - rsi_values[sl2['index']] >= 1.5):
                    bullish_div = {
                        'type': 'HIDDEN_BULLISH',
                        'name_tr': 'Gizli Pozitif Uyumsuzluk (Boğa Trend Devamı - Hidden Bullish Divergence)',
                        'price1': sl1['price'],
                        'price2': sl2['price'],
                        'rsi1': round(float(rsi_values[sl1['index']]), 1),
                        'rsi2': round(float(rsi_values[sl2['index']]), 1),
                        'recency_bars': int(n - 1 - sl2['index']),
                        'strength': 'ORTA'
                    }
                    break
                
    # Bearish Divergence kontrolü (Regular HH vs RSI LH, Hidden LH vs RSI HH)
    if len(swing_highs) >= 2:
        sh2 = swing_highs[-1]
        
        if (n - 1 - sh2['index']) <= 50:
            for idx in range(max(0, len(swing_highs) - 6), len(swing_highs) - 1)[::-1]:
                sh1 = swing_highs[idx]
                bars_gap = sh2['index'] - sh1['index']
                if bars_gap < 5 or bars_gap > 60:
                    continue
                    
                price_hh = sh2['price'] > sh1['price']
                rsi_lh = (rsi_values[sh1['index']] - rsi_values[sh2['index']]) >= 1.5
                
                # Regular Bearish Divergence (Trend Dönüşü)
                if price_hh and rsi_lh:
                    bearish_div = {
                        'type': 'REGULAR_BEARISH',
                        'name_tr': 'Negatif Uyumsuzluk (Ayı Dönüşü - Regular Bearish Divergence)',
                        'price1': sh1['price'],
                        'price2': sh2['price'],
                        'rsi1': round(float(rsi_values[sh1['index']]), 1),
                        'rsi2': round(float(rsi_values[sh2['index']]), 1),
                        'recency_bars': int(n - 1 - sh2['index']),
                        'strength': 'GÜÇLÜ' if rsi_values[sh2['index']] >= 62 else 'ORTA'
                    }
                    break
                # Hidden Bearish Divergence (Trend Devamı)
                elif (sh2['price'] < sh1['price']) and (rsi_values[sh2['index']] - rsi_values[sh1['index']] >= 1.5):
                    bearish_div = {
                        'type': 'HIDDEN_BEARISH',
                        'name_tr': 'Gizli Negatif Uyumsuzluk (Ayı Trend Devamı - Hidden Bearish Divergence)',
                        'price1': sh1['price'],
                        'price2': sh2['price'],
                        'rsi1': round(float(rsi_values[sh1['index']]), 1),
                        'rsi2': round(float(rsi_values[sh2['index']]), 1),
                        'recency_bars': int(n - 1 - sh2['index']),
                        'strength': 'ORTA'
                    }
                    break
                
    return {
        'bullish_divergence': bullish_div,
        'bearish_divergence': bearish_div
    }
