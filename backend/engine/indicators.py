import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.where(avg_loss != 0, np.where(avg_gain > 0, 100.0, 50.0))
    return rsi.fillna(50.0)

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    return atr.fillna(tr.mean() if not tr.empty else 1.0)

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower

def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
    hl2 = (df['high'] + df['low']) / 2
    atr = calculate_atr(df, period)
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)
    
    close = df['close'].values
    b_upper = basic_upper.values
    b_lower = basic_lower.values
    n = len(df)
    
    f_upper = np.zeros(n)
    f_lower = np.zeros(n)
    st = np.zeros(n)
    dirs = np.ones(n, dtype=int)
    
    if n > 0:
        f_upper[0] = b_upper[0]
        f_lower[0] = b_lower[0]
        dirs[0] = 1
        st[0] = f_lower[0]
        
        for i in range(1, n):
            if b_upper[i] < f_upper[i-1] or close[i-1] > f_upper[i-1]:
                f_upper[i] = b_upper[i]
            else:
                f_upper[i] = f_upper[i-1]
                
            if b_lower[i] > f_lower[i-1] or close[i-1] < f_lower[i-1]:
                f_lower[i] = b_lower[i]
            else:
                f_lower[i] = f_lower[i-1]
                
            if dirs[i-1] == 1:
                if close[i] < f_lower[i]:
                    dirs[i] = -1
                    st[i] = f_upper[i]
                else:
                    dirs[i] = 1
                    st[i] = f_lower[i]
            else:
                if close[i] > f_upper[i]:
                    dirs[i] = 1
                    st[i] = f_lower[i]
                else:
                    dirs[i] = -1
                    st[i] = f_upper[i]
                    
    supertrend = pd.Series(st, index=df.index)
    direction = pd.Series(dirs, index=df.index)
    return supertrend, direction

def find_swing_points(df: pd.DataFrame, window: int = 4) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    timestamps = df['timestamp'].values if 'timestamp' in df.columns else df.index.values
    
    swing_highs = []
    swing_lows = []
    n = len(df)
    
    for i in range(window, n - window):
        is_high = True
        for j in range(1, window + 1):
            if highs[i] < highs[i - j] or highs[i] < highs[i + j]:
                is_high = False
                break
        if is_high:
            swing_highs.append({
                'index': int(i),
                'timestamp': int(timestamps[i]) if hasattr(timestamps[i], '__int__') else int(i),
                'price': float(highs[i]),
                'close': float(closes[i])
            })
            
        is_low = True
        for j in range(1, window + 1):
            if lows[i] > lows[i - j] or lows[i] > lows[i + j]:
                is_low = False
                break
        if is_low:
            swing_lows.append({
                'index': int(i),
                'timestamp': int(timestamps[i]) if hasattr(timestamps[i], '__int__') else int(i),
                'price': float(lows[i]),
                'close': float(closes[i])
            })
            
    return swing_highs, swing_lows

def enrich_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['ema_20'] = calculate_ema(df['close'], 20)
    df['ema_50'] = calculate_ema(df['close'], 50)
    df['ema_100'] = calculate_ema(df['close'], 100)
    df['ema_200'] = calculate_ema(df['close'], 200)
    df['rsi'] = calculate_rsi(df['close'], 14)
    df['atr'] = calculate_atr(df, 14)
    macd, signal, hist = calculate_macd(df['close'])
    df['macd'] = macd
    df['macd_signal'] = signal
    df['macd_hist'] = hist
    bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(df['close'], 20, 2.0)
    df['bb_upper'] = bb_upper
    df['bb_middle'] = bb_mid
    df['bb_lower'] = bb_lower
    st, st_dir = calculate_supertrend(df, 10, 3.0)
    df['supertrend'] = st
    df['supertrend_dir'] = st_dir
    df['volume_sma20'] = calculate_sma(df['volume'], 20)
    df['volume_ratio'] = df['volume'] / df['volume_sma20'].replace(0, 1.0)
    df['donchian_high20'] = df['high'].rolling(window=20).max()
    df['donchian_low20'] = df['low'].rolling(window=20).min()
    return df
