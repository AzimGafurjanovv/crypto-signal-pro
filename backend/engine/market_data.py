import time
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, List, Any, Optional

STABLE_AND_EXCLUDED = ['FDUSD', 'USDC', 'USDP', 'TUSD', 'EUR', 'BUSD', 'DAI', 'AEUR', 'WBTC', 'WBETH', 'USD1', 'USDE', 'PYUSD']

POPULAR_PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "SUI/USDT", "NEAR/USDT",
    "LINK/USDT", "PEPE/USDT", "TRX/USDT", "APT/USDT", "ARB/USDT", "OP/USDT",
    "TIA/USDT", "FET/USDT", "RENDER/USDT", "WIF/USDT", "INJ/USDT",
    "TAO/USDT", "SEI/USDT", "FTM/USDT", "STX/USDT", "GALA/USDT",
    "DOT/USDT", "ATOM/USDT", "MATIC/USDT", "LDO/USDT", "FIL/USDT",
    "SHIB/USDT", "ICP/USDT", "UNI/USDT", "BCH/USDT", "LTC/USDT",
    "KAS/USDT", "AAVE/USDT", "RUNE/USDT", "ORDI/USDT", "FLOKI/USDT", "ENA/USDT"
]

class MarketDataManager:
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 30  # 30 saniye boyunca mum verisini önbellekte tut
        self._top_pairs_cache: Optional[List[str]] = None
        self._top_pairs_cache_time: float = 0
        self._top_pairs_ttl = 300  # 5 dakika boyunca parite evrenini sabit tut (tutarlılık için)
        
        # HTTP Session with Connection Pooling & Auto Retry
        self.session = requests.Session()
        retries = Retry(total=2, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(pool_connections=25, pool_maxsize=25, max_retries=retries)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
        
    def get_top_pairs(self, limit: int = 10) -> List[str]:
        """
        En likit ve en popüler kripto paritelerinin listesini döndürür (En fazla 50 coin tavanı).
        5 dakikalık önbellek sayesinde tarama esnasında coinlerin kaybolması veya titremesi önlenir.
        """
        effective_limit = min(50, max(5, limit))
        now = time.time()
        if self._top_pairs_cache and (now - self._top_pairs_cache_time < self._top_pairs_ttl):
            return self._top_pairs_cache[:effective_limit]
            
        endpoints = [
            "https://data-api.binance.vision/api/v3/ticker/24hr",
            "https://api.binance.com/api/v3/ticker/24hr",
            "https://api.mexc.com/api/v3/ticker/24hr"
        ]
        
        for url in endpoints:
            try:
                resp = self.session.get(url, timeout=3.5)
                if resp.status_code == 200:
                    data = resp.json()
                    valid_tickers = []
                    for t in data:
                        sym = t.get('symbol', '')
                        if sym.endswith('USDT'):
                            base = sym[:-4]
                            if base not in STABLE_AND_EXCLUDED and not any(x in sym for x in ['UPUSDT', 'DOWNUSDT', 'BEAR', 'BULL']):
                                valid_tickers.append(t)
                                
                    valid_tickers.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
                    fetched_symbols = [f"{t['symbol'][:-4]}/USDT" for t in valid_tickers]
                    
                    # Popüler pariteleri ve en yüksek hacimli pariteleri birleştir
                    combined = []
                    for p in POPULAR_PAIRS:
                        if p not in combined:
                            combined.append(p)
                    for f in fetched_symbols:
                        if f not in combined:
                            combined.append(f)
                            
                    self._top_pairs_cache = combined
                    self._top_pairs_cache_time = now
                    return self._top_pairs_cache[:limit]
            except Exception:
                continue
                
        self._top_pairs_cache = POPULAR_PAIRS
        self._top_pairs_cache_time = now
        return POPULAR_PAIRS[:limit]

    def _fetch_from_binance_vision(self, symbol: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        clean_symbol = symbol.replace("/", "")
        interval_map = {
            '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '4h': '4h', '12h': '12h', '1d': '1d', '1w': '1w'
        }
        interval = interval_map.get(timeframe, '1h')
        urls = [
            f"https://data-api.binance.vision/api/v3/klines?symbol={clean_symbol}&interval={interval}&limit={limit}",
            f"https://api.binance.com/api/v3/klines?symbol={clean_symbol}&interval={interval}&limit={limit}"
        ]
        
        for url in urls:
            try:
                resp = self.session.get(url, timeout=3.5)
                if resp.status_code == 200:
                    raw_klines = resp.json()
                    if not raw_klines:
                        continue
                    df = pd.DataFrame(raw_klines, columns=[
                        'timestamp', 'open', 'high', 'low', 'close', 'volume',
                        'close_time', 'quote_asset_volume', 'number_of_trades',
                        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
                    ])
                    for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
                        df[col] = pd.to_numeric(df[col])
                    return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            except Exception:
                continue
        return None

    def _fetch_from_mexc(self, symbol: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        clean_symbol = symbol.replace("/", "")
        interval_map = {
            '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '60m', '4h': '4h', '12h': '12h', '1d': '1d', '1w': '1W'
        }
        interval = interval_map.get(timeframe, '60m')
        url = f"https://api.mexc.com/api/v3/klines?symbol={clean_symbol}&interval={interval}&limit={limit}"
        try:
            resp = self.session.get(url, timeout=3.5)
            if resp.status_code == 200:
                raw_klines = resp.json()
                if not raw_klines:
                    return None
                df = pd.DataFrame(raw_klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_asset_volume'
                ])
                for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col])
                return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        except Exception:
            return None
        return None

    def _fetch_from_okx(self, symbol: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        inst_id = symbol.replace("/", "-")
        interval_map = {
            '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1H', '4h': '4H', '12h': '12H', '1d': '1D', '1w': '1W'
        }
        bar = interval_map.get(timeframe, '1H')
        url = f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={limit}"
        try:
            resp = self.session.get(url, timeout=3.5)
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                if not data:
                    return None
                df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'volCcy', 'volCcyQuote', 'confirm'])
                for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col])
                df = df.iloc[::-1].reset_index(drop=True)
                return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        except Exception:
            return None
        return None

    def get_market_data(self, symbol: str, timeframe: str = '1h', limit: int = 300) -> Optional[pd.DataFrame]:
        cache_key = f"{symbol}_{timeframe}_{limit}"
        now = time.time()
        
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if now - entry['timestamp'] < self.cache_ttl:
                return entry['data']
                
        df = self._fetch_from_binance_vision(symbol, timeframe, limit)
        if df is None or df.empty:
            df = self._fetch_from_mexc(symbol, timeframe, limit)
        if df is None or df.empty:
            df = self._fetch_from_okx(symbol, timeframe, limit)
            
        if df is not None and not df.empty:
            self.cache[cache_key] = {'timestamp': now, 'data': df}
            
        return df

market_manager = MarketDataManager()
