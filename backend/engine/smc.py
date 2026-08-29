import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from .indicators import find_swing_points

def detect_fvg(df: pd.DataFrame, min_gap_percent: float = 0.05) -> List[Dict[str, Any]]:
    """
    Fair Value Gap (FVG / Dengesizlik Bolgesi) tespit eder.
    Bullish FVG: Mum(i) Low > Mum(i-2) High
    Bearish FVG: Mum(i) High < Mum(i-2) Low
    """
    fvgs = []
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    timestamps = df['timestamp'].values if 'timestamp' in df.columns else df.index.values
    n = len(df)
    current_price = closes[-1]
    
    for i in range(2, n):
        # Bullish FVG
        if lows[i] > highs[i - 2]:
            gap_bottom = float(highs[i - 2])
            gap_top = float(lows[i])
            gap_size_pct = ((gap_top - gap_bottom) / gap_bottom) * 100.0
            
            if gap_size_pct >= min_gap_percent:
                is_mitigated = False
                for j in range(i + 1, n):
                    if lows[j] <= gap_bottom:
                        is_mitigated = True
                        break
                
                is_active_zone = (current_price >= gap_bottom * 0.998 and current_price <= gap_top * 1.002)
                
                fvgs.append({
                    'type': 'BULLISH_FVG',
                    'candle_index': int(i - 1),
                    'timestamp': int(timestamps[i - 1]) if hasattr(timestamps[i - 1], '__int__') else int(i - 1),
                    'top': gap_top,
                    'bottom': gap_bottom,
                    'mid': (gap_top + gap_bottom) / 2.0,
                    'size_pct': round(gap_size_pct, 2),
                    'is_mitigated': is_mitigated,
                    'is_active_zone': is_active_zone,
                    'distance_to_price_pct': round(((current_price - ((gap_top + gap_bottom) / 2)) / current_price) * 100.0, 2)
                })
                
        # Bearish FVG
        elif highs[i] < lows[i - 2]:
            gap_top = float(lows[i - 2])
            gap_bottom = float(highs[i])
            gap_size_pct = ((gap_top - gap_bottom) / gap_bottom) * 100.0
            
            if gap_size_pct >= min_gap_percent:
                is_mitigated = False
                for j in range(i + 1, n):
                    if highs[j] >= gap_top:
                        is_mitigated = True
                        break
                        
                is_active_zone = (current_price >= gap_bottom * 0.998 and current_price <= gap_top * 1.002)
                
                fvgs.append({
                    'type': 'BEARISH_FVG',
                    'candle_index': int(i - 1),
                    'timestamp': int(timestamps[i - 1]) if hasattr(timestamps[i - 1], '__int__') else int(i - 1),
                    'top': gap_top,
                    'bottom': gap_bottom,
                    'mid': (gap_top + gap_bottom) / 2.0,
                    'size_pct': round(gap_size_pct, 2),
                    'is_mitigated': is_mitigated,
                    'is_active_zone': is_active_zone,
                    'distance_to_price_pct': round(((((gap_top + gap_bottom) / 2) - current_price) / current_price) * 100.0, 2)
                })
                
    return fvgs

def detect_order_blocks(df: pd.DataFrame, lookback: int = 50) -> List[Dict[str, Any]]:
    """
    Kurumsal Emir Bloklari (Order Blocks - OB) tespit eder.
    """
    obs = []
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    timestamps = df['timestamp'].values if 'timestamp' in df.columns else df.index.values
    n = len(df)
    current_price = closes[-1]
    
    start_idx = max(2, n - lookback)
    for i in range(start_idx, n - 2):
        is_bearish_candle = closes[i] < opens[i]
        strong_displacement_up = False
        for j in range(2, min(6, n - i)):
            if closes[i + j] > highs[i] and closes[i + 1] > opens[i]:
                strong_displacement_up = True
                break
        
        if is_bearish_candle and strong_displacement_up:
            ob_top = float(highs[i])
            ob_bottom = float(lows[i])
            
            is_mitigated = False
            for k in range(i + 3, n):
                if closes[k] < ob_bottom:
                    is_mitigated = True
                    break
                    
            is_active_zone = (current_price >= ob_bottom * 0.997 and current_price <= ob_top * 1.003)
            
            obs.append({
                'type': 'BULLISH_OB',
                'index': int(i),
                'timestamp': int(timestamps[i]) if hasattr(timestamps[i], '__int__') else int(i),
                'top': ob_top,
                'bottom': ob_bottom,
                'mid': (ob_top + ob_bottom) / 2.0,
                'is_mitigated': is_mitigated,
                'is_active_zone': is_active_zone,
                'distance_pct': round(((current_price - ob_top) / current_price) * 100.0, 2)
            })
            
        is_bullish_candle = closes[i] > opens[i]
        strong_displacement_down = False
        for j in range(2, min(6, n - i)):
            if closes[i + j] < lows[i] and closes[i + 1] < opens[i]:
                strong_displacement_down = True
                break
        
        if is_bullish_candle and strong_displacement_down:
            ob_top = float(highs[i])
            ob_bottom = float(lows[i])
            
            is_mitigated = False
            for k in range(i + 3, n):
                if closes[k] > ob_top:
                    is_mitigated = True
                    break
                    
            is_active_zone = (current_price >= ob_bottom * 0.997 and current_price <= ob_top * 1.003)
            
            obs.append({
                'type': 'BEARISH_OB',
                'index': int(i),
                'timestamp': int(timestamps[i]) if hasattr(timestamps[i], '__int__') else int(i),
                'top': ob_top,
                'bottom': ob_bottom,
                'mid': (ob_top + ob_bottom) / 2.0,
                'is_mitigated': is_mitigated,
                'is_active_zone': is_active_zone,
                'distance_pct': round(((ob_bottom - current_price) / current_price) * 100.0, 2)
            })
            
    return obs

def detect_market_structure(df: pd.DataFrame) -> Dict[str, Any]:
    """Piyasa Yapisi Kirilimlarini (BOS) ve Likidite Temizliklerini (Sweeps) tespit eder."""
    swing_highs, swing_lows = find_swing_points(df, window=4)
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    n = len(df)
    
    bos_events = []
    liquidity_sweeps = []
    
    for sh in swing_highs[-5:]:
        sh_idx = sh['index']
        sh_price = sh['price']
        for i in range(sh_idx + 1, n):
            if closes[i] > sh_price:
                bos_events.append({
                    'type': 'BULLISH_BOS',
                    'broken_level': sh_price,
                    'break_candle': int(i),
                    'recency_bars': int(n - 1 - i)
                })
                break
            elif highs[i] > sh_price and closes[i] <= sh_price:
                liquidity_sweeps.append({
                    'type': 'BEARISH_LIQUIDITY_SWEEP',
                    'swept_level': sh_price,
                    'sweep_candle': int(i),
                    'recency_bars': int(n - 1 - i)
                })
                
    for sl in swing_lows[-5:]:
        sl_idx = sl['index']
        sl_price = sl['price']
        for i in range(sl_idx + 1, n):
            if closes[i] < sl_price:
                bos_events.append({
                    'type': 'BEARISH_BOS',
                    'broken_level': sl_price,
                    'break_candle': int(i),
                    'recency_bars': int(n - 1 - i)
                })
                break
            elif lows[i] < sl_price and closes[i] >= sl_price:
                liquidity_sweeps.append({
                    'type': 'BULLISH_LIQUIDITY_SWEEP',
                    'swept_level': sl_price,
                    'sweep_candle': int(i),
                    'recency_bars': int(n - 1 - i)
                })
                
    recent_bos = [b for b in bos_events if b['recency_bars'] <= 12]
    recent_sweeps = [s for s in liquidity_sweeps if s['recency_bars'] <= 8]
    
    return {
        'recent_bos': recent_bos,
        'recent_sweeps': recent_sweeps,
        'swing_highs': swing_highs[-4:],
        'swing_lows': swing_lows[-4:]
    }

def analyze_smc(df: pd.DataFrame) -> Dict[str, Any]:
    fvgs = detect_fvg(df)
    obs = detect_order_blocks(df)
    structure = detect_market_structure(df)
    
    unmitigated_bullish_fvgs = [f for f in fvgs if f['type'] == 'BULLISH_FVG' and not f['is_mitigated']][-3:]
    unmitigated_bearish_fvgs = [f for f in fvgs if f['type'] == 'BEARISH_FVG' and not f['is_mitigated']][-3:]
    
    active_bullish_fvgs = [f for f in unmitigated_bullish_fvgs if f['is_active_zone']]
    active_bearish_fvgs = [f for f in unmitigated_bearish_fvgs if f['is_active_zone']]
    
    active_bullish_obs = [o for o in obs if o['type'] == 'BULLISH_OB' and not o['is_mitigated'] and (o['is_active_zone'] or abs(o['distance_pct']) <= 1.5)][-2:]
    active_bearish_obs = [o for o in obs if o['type'] == 'BEARISH_OB' and not o['is_mitigated'] and (o['is_active_zone'] or abs(o['distance_pct']) <= 1.5)][-2:]
    
    return {
        'all_fvgs': fvgs[-10:],
        'all_obs': obs[-10:],
        'unmitigated_bullish_fvgs': unmitigated_bullish_fvgs,
        'unmitigated_bearish_fvgs': unmitigated_bearish_fvgs,
        'active_bullish_fvgs': active_bullish_fvgs,
        'active_bearish_fvgs': active_bearish_fvgs,
        'active_bullish_obs': active_bullish_obs,
        'active_bearish_obs': active_bearish_obs,
        'structure': structure
    }
