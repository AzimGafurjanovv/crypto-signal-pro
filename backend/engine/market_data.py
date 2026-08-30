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
        # Mum Verisi Onbellegi (60 sn TTL)
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 60  # 60 saniye

        # Merkezi Anlik Fiyat Onbellegi
        # Tum arka plan servisleri (trade note alarm, radar, strateji alarm)
        # bu onbellekten fiyat okur. 60 saniyede 1 Binance'e tek toplu istek.
        self._price_cache: Dict[str, float] = {}
        self._price_cache_time: float = 0.0
        self._price_cache_ttl: int = 60

        # Parite Evreni Onbellegi (5 dk TTL)
        self._top_pairs_cache = None
        self._top_pairs_cache_time: float = 0.0
        self._top_pairs_ttl: int = 300

        # HTTP Session
        self.session = requests.Session()
        retries = Retry(total=2, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(pool_connections=25, pool_maxsize=25, max_retries=retries)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    # -------------------------------------------------------------------------
    # MERKEZI TOPLU FIYAT ONBELLEK SISTEMI
    # Sunucu baslarken ve her 60 saniyede bir app.py central_data_updater_loop
    # tarafindan cagrilir. Tum servisler get_cached_price() uzerinden okur.
    # -------------------------------------------------------------------------

    def refresh_price_cache(self) -> bool:
        endpoints = [
            "https://data-api.binance.vision/api/v3/ticker/price",
            "https://api.binance.com/api/v3/ticker/price",
        ]
        for url in endpoints:
            try:
                resp = self.session.get(url, timeout=4.0)
                if resp.status_code == 200:
                    data = resp.json()
                    new_cache: Dict[str, float] = {}
                    for item in data:
                        sym = item.get("symbol", "")
                        if sym.endswith("USDT"):
                            base = sym[:-4]
                            if base not in STABLE_AND_EXCLUDED:
                                try:
                                    new_cache[f"{base}/USDT"] = float(item["price"])
                                except (ValueError, KeyError):
                                    pass
                    if new_cache:
                        self._price_cache = new_cache
                        self._price_cache_time = time.time()
                        print(f"[PriceCache] {len(new_cache)} coin fiyati guncellendi.")
                        return True
            except Exception:
                continue
        return False

    def get_cached_price(self, symbol: str):
        now = time.time()
        if not self._price_cache or (now - self._price_cache_time) > self._price_cache_ttl:
            self.refresh_price_cache()
        sym_key = symbol.upper().strip()
        if "/" not in sym_key:
            sym_key = f"{sym_key}/USDT"
        return self._price_cache.get(sym_key)

    def get_all_cached_prices(self) -> Dict[str, float]:
        now = time.time()
        if not self._price_cache or (now - self._price_cache_time) > self._price_cache_ttl:
            self.refresh_price_cache()
        return dict(self._price_cache)

    # -------------------------------------------------------------------------
    # PARITE EVRENI
    # -------------------------------------------------------------------------

    def get_top_pairs(self, limit: int = 10):
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
                    combined = list(POPULAR_PAIRS)
                    for f in fetched_symbols:
                        if f not in combined:
                            combined.append(f)
                    self._top_pairs_cache = combined
                    self._top_pairs_cache_time = now
                    return self._top_pairs_cache[:effective_limit]
            except Exception:
                continue

        self._top_pairs_cache = list(POPULAR_PAIRS)
        self._top_pairs_cache_time = now
        return self._top_pairs_cache[:effective_limit]

    # -------------------------------------------------------------------------
    # MUM VERISI CEKICILERI (Borsa Yedeklemeli)
    # -------------------------------------------------------------------------

    def _fetch_from_binance_vision(self, symbol: str, timeframe: str, limit: int):
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

    def _fetch_from_mexc(self, symbol: str, timeframe: str, limit: int):
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

    def _fetch_from_okx(self, symbol: str, timeframe: str, limit: int):
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

    def get_market_data(self, symbol: str, timeframe: str = '1h', limit: int = 300):
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
