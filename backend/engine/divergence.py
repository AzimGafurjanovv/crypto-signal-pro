import numpy as np
import pandas as pd
from typing import Dict, Any, List
from .indicators import find_swing_points

def detect_rsi_divergences(df: pd.DataFrame) -> Dict[str, Any]:
    """
    RSI ve Fiyat arasındaki Uyumsuzlukları (Regular & Hidden Divergence) tespit eder.
    """
    if 'rsi' not in df.columns:
        return {'bullish_divergence': None, 'bearish_divergence': None}
        
    swing_highs, swing_lows = find_swing_points(df, window=4)
    rsi_values = df['rsi'].values
    n = len(df)
    
    bullish_div = None
    bearish_div = None
    
    # Bullish Divergence kontrolü
    if len(swing_lows) >= 2:
        sl2 = swing_lows[-1]
        
        if (n - 1 - sl2['index']) <= 15:
            for idx in range(max(0, len(swing_lows) - 4), len(swing_lows) - 1)[::-1]:
                sl1 = swing_lows[idx]
                price_ll = sl2['price'] < sl1['price']
                rsi_hl = rsi_values[sl2['index']] > rsi_values[sl1['index']]
                
                if price_ll and rsi_hl:
                    bullish_div = {
                        'type': 'REGULAR_BULLISH',
                        'name_tr': 'Pozitif Uyumsuzluk (Boğa Dönüşü - Regular Bullish Divergence)',
                        'price1': sl1['price'],
                        'price2': sl2['price'],
                        'rsi1': round(float(rsi_values[sl1['index']]), 1),
                        'rsi2': round(float(rsi_values[sl2['index']]), 1),
                        'recency_bars': int(n - 1 - sl2['index']),
                        'strength': 'GUCLU' if rsi_values[sl2['index']] <= 40 else 'ORTA'
                    }
                    break
                elif (sl2['price'] > sl1['price']) and (rsi_values[sl2['index']] < rsi_values[sl1['index']]):
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
                
    # Bearish Divergence kontrolü
    if len(swing_highs) >= 2:
        sh2 = swing_highs[-1]
        
        if (n - 1 - sh2['index']) <= 15:
            for idx in range(max(0, len(swing_highs) - 4), len(swing_highs) - 1)[::-1]:
                sh1 = swing_highs[idx]
                price_hh = sh2['price'] > sh1['price']
                rsi_lh = rsi_values[sh2['index']] < rsi_values[sh1['index']]
                
                if price_hh and rsi_lh:
                    bearish_div = {
                        'type': 'REGULAR_BEARISH',
                        'name_tr': 'Negatif Uyumsuzluk (Ayı Dönüşü - Regular Bearish Divergence)',
                        'price1': sh1['price'],
                        'price2': sh2['price'],
                        'rsi1': round(float(rsi_values[sh1['index']]), 1),
                        'rsi2': round(float(rsi_values[sh2['index']]), 1),
                        'recency_bars': int(n - 1 - sh2['index']),
                        'strength': 'GUCLU' if rsi_values[sh2['index']] >= 60 else 'ORTA'
                    }
                    break
                elif (sh2['price'] < sh1['price']) and (rsi_values[sh2['index']] > rsi_values[sh1['index']]):
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
