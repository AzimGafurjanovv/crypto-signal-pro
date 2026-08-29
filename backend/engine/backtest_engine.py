import time
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime

from .indicators import enrich_all_indicators, find_swing_points
from .smc import analyze_smc
from .divergence import detect_rsi_divergences
from .patterns import detect_chart_patterns

ALL_STRATEGIES = [
    {
        'id': 'smc_order_block',
        'name': 'SMC Kurumsal Emir Bloğu',
        'name_en': 'SMC Order Block (OB)',
        'category': 'Smart Money Concepts'
    },
    {
        'id': 'smc_fvg',
        'name': 'SMC Dengesizlik Boşluğu',
        'name_en': 'SMC Fair Value Gap (FVG)',
        'category': 'Smart Money Concepts'
    },
    {
        'id': 'smc_liquidity_sweep',
        'name': 'SMC Likidite Avı & Reclaim',
        'name_en': 'SMC Liquidity Sweep & Reclaim',
        'category': 'Smart Money Concepts'
    },
    {
        'id': 'trendline_breakout',
        'name': 'Trend Çizgisi Kırılımı + Retest',
        'name_en': 'Trendline Breakout + Retest',
        'category': 'Kilit Grafik Formasyonları'
    },
    {
        'id': 'triangle_breakout',
        'name': 'Simetrik Üçgen / Flama Kırılımı',
        'name_en': 'Symmetrical Triangle / Pennant',
        'category': 'Kilit Grafik Formasyonları'
    },
    {
        'id': 'sr_flip_retest',
        'name': 'Direnç / Destek Dönüşümü (S/R Flip)',
        'name_en': 'S/R Flip Retest',
        'category': 'Kilit Grafik Formasyonları'
    },
    {
        'id': 'range_breakout',
        'name': 'Range Kırılımı / Sapma (Deviation)',
        'name_en': 'Range Breakout & Deviation',
        'category': 'Kilit Grafik Formasyonları'
    },
    {
        'id': 'double_bottom_top',
        'name': 'Double Bottom W / Double Top M',
        'name_en': 'Double Bottom (W) / Top (M)',
        'category': 'Kilit Grafik Formasyonları'
    },
    {
        'id': 'rsi_divergence',
        'name': 'RSI Pozitif / Negatif Uyumsuzluk',
        'name_en': 'RSI Regular/Hidden Divergence',
        'category': 'Momentum & Divergence'
    },
    {
        'id': 'ema_ribbon',
        'name': 'EMA Ribbon Trend Takibi',
        'name_en': 'EMA Ribbon Trend Alignment',
        'category': 'Trend & Momentum'
    },
    {
        'id': 'super_confluence',
        'name': 'Super Trader Çok Katmanlı Konfluens',
        'name_en': 'Super Trader Layered Confluence',
        'category': 'Kompozit Kurumsal Sistem'
    },
    {
        'id': 'pdh_pdl_breakout_retest_user',
        'name': 'Önceki Gün Zirve/Dip Kırılımı + Retest (Benim)',
        'name_en': 'PDH/PDL Breakout & Retest (Benim)',
        'category': 'Kullanıcı Özel Stratejisi'
    }
]

def run_strategy_backtest(symbol: str, df: pd.DataFrame, timeframe: str = "1h", lookback: int = 500, candle_limit: Optional[int] = None, **kwargs) -> Dict[str, Any]:
    """
    Belirli bir kripto paritesi için geçmiş piyasa verileri üzerinde tüm 12 stratejiyi
    (Kullanıcının PDH/PDL stratejisi dahil) ve TP1, TP2, TP3 kazanma olasılıklarını adım adım simüle eden motor.
    """
    if len(df) < 50:
        return {'status': 'error', 'message': 'Yetersiz mum verisi'}

    effective_lookback = candle_limit if candle_limit is not None else lookback
    limit = min(len(df), effective_lookback)
    df_slice = df.tail(limit).copy().reset_index(drop=True)
    df_enriched = enrich_all_indicators(df_slice)
    
    n = len(df_enriched)
    strategy_results = {s['id']: {
        'id': s['id'],
        'name': s['name'],
        'name_en': s['name_en'],
        'category': s['category'],
        'total_trades': 0,
        'wins': 0,
        'losses': 0,
        'win_rate': 0.0,
        'tp1_win_rate': 0.0,
        'tp2_win_rate': 0.0,
        'tp3_win_rate': 0.0,
        'tp1_hits': 0,
        'tp2_hits': 0,
        'tp3_hits': 0,
        'net_profit_pct': 0.0,
        'gross_profit_pct': 0.0,
        'gross_loss_pct': 0.0,
        'profit_factor': 0.0,
        'max_drawdown_pct': 0.0,
        'avg_trade_pct': 0.0,
        'trades': []
    } for s in ALL_STRATEGIES}

    # Minimum ısınma periyodu 35 bar
    step = 2  # Performans ve hız için 2 barlık adım
    
    # Pre-calculate these once on the full dataframe
    full_smc = analyze_smc(df_enriched)
    full_div = detect_rsi_divergences(df_enriched)
    full_patterns = detect_chart_patterns(df_enriched)
    
    for idx in range(35, n - 8, step):
        curr_bar = df_enriched.iloc[idx]
        curr_price = float(curr_bar['close'])
        curr_atr = float(curr_bar['atr']) if not np.isnan(curr_bar['atr']) else curr_price * 0.015
        curr_time = int(curr_bar['timestamp']) // 1000 if 'timestamp' in curr_bar else idx
        
        # Slice results by index inside the loop
        smc = {
            'active_bullish_obs': [ob for ob in full_smc.get('active_bullish_obs', []) if ob.get('index', 0) <= idx],
            'active_bearish_obs': [ob for ob in full_smc.get('active_bearish_obs', []) if ob.get('index', 0) <= idx],
            'active_bullish_fvgs': [fvg for fvg in full_smc.get('active_bullish_fvgs', []) if fvg.get('candle_index', 0) <= idx],
            'active_bearish_fvgs': [fvg for fvg in full_smc.get('active_bearish_fvgs', []) if fvg.get('candle_index', 0) <= idx],
            'structure': {
                'recent_sweeps': [sw for sw in full_smc.get('structure', {}).get('recent_sweeps', []) if sw.get('sweep_candle', 0) <= idx]
            }
        }
        
        div = {
            'bullish_divergence': full_div.get('bullish_divergence') if full_div.get('bullish_divergence') and (n - 1 - full_div['bullish_divergence'].get('recency_bars', 0)) <= idx else None,
            'bearish_divergence': full_div.get('bearish_divergence') if full_div.get('bearish_divergence') and (n - 1 - full_div['bearish_divergence'].get('recency_bars', 0)) <= idx else None,
        }
        
        patterns = []
        for pat in full_patterns:
            max_time = 0
            for line in pat.get('lines', []):
                for pt in line.get('points', []):
                    if pt.get('time', 0) > max_time:
                        max_time = pt.get('time', 0)
            if max_time <= curr_time:
                patterns.append(pat)

        signals_triggered = []

        # --- A. SMC Order Block ---
        if smc['active_bullish_obs']:
            signals_triggered.append(('smc_order_block', 'LONG', smc['active_bullish_obs'][0]['top']))
        elif smc['active_bearish_obs']:
            signals_triggered.append(('smc_order_block', 'SHORT', smc['active_bearish_obs'][0]['bottom']))

        # --- B. SMC FVG ---
        if smc['active_bullish_fvgs']:
            signals_triggered.append(('smc_fvg', 'LONG', smc['active_bullish_fvgs'][0]['mid']))
        elif smc['active_bearish_fvgs']:
            signals_triggered.append(('smc_fvg', 'SHORT', smc['active_bearish_fvgs'][0]['mid']))

        # --- C. SMC Likidite Avı ---
        bull_sweeps = [s for s in smc['structure']['recent_sweeps'] if s['type'] == 'BULLISH_LIQUIDITY_SWEEP']
        bear_sweeps = [s for s in smc['structure']['recent_sweeps'] if s['type'] == 'BEARISH_LIQUIDITY_SWEEP']
        if bull_sweeps and bull_sweeps[0]['recency_bars'] <= 2:
            signals_triggered.append(('smc_liquidity_sweep', 'LONG', curr_price))
        elif bear_sweeps and bear_sweeps[0]['recency_bars'] <= 2:
            signals_triggered.append(('smc_liquidity_sweep', 'SHORT', curr_price))

        # --- D. Formasyonlar ---
        for pat in patterns:
            p_type = pat.get('type')
            cat = pat.get('category', '')
            if '1. Trend' in cat:
                signals_triggered.append(('trendline_breakout', p_type, curr_price))
            elif '2. Simetrik' in cat or 'Üçgen' in cat:
                signals_triggered.append(('triangle_breakout', p_type, curr_price))
            elif '3. S/R' in cat:
                signals_triggered.append(('sr_flip_retest', p_type, curr_price))
            elif '4. Range' in cat:
                signals_triggered.append(('range_breakout', p_type, curr_price))
            elif '5. Double' in cat:
                signals_triggered.append(('double_bottom_top', p_type, curr_price))
            elif '6. PDH/PDL' in cat or 'Benim' in cat:
                signals_triggered.append(('pdh_pdl_breakout_retest_user', p_type, curr_price))

        # --- E. RSI Uyumsuzluk ---
        if div['bullish_divergence'] and div['bullish_divergence']['recency_bars'] <= 2:
            signals_triggered.append(('rsi_divergence', 'LONG', curr_price))
        elif div['bearish_divergence'] and div['bearish_divergence']['recency_bars'] <= 2:
            signals_triggered.append(('rsi_divergence', 'SHORT', curr_price))

        # --- F. EMA Ribbon ---
        ema20 = float(curr_bar['ema20']) if 'ema20' in curr_bar and not np.isnan(curr_bar['ema20']) else curr_price
        ema50 = float(curr_bar['ema50']) if 'ema50' in curr_bar and not np.isnan(curr_bar['ema50']) else curr_price
        ema200 = float(curr_bar['ema200']) if 'ema200' in curr_bar and not np.isnan(curr_bar['ema200']) else curr_price
        
        if curr_price > ema20 > ema50 > ema200:
            signals_triggered.append(('ema_ribbon', 'LONG', curr_price))
        elif curr_price < ema20 < ema50 < ema200:
            signals_triggered.append(('ema_ribbon', 'SHORT', curr_price))

        # --- G. PDH / PDL (Kullanıcı Stratejisi Doğrudan Taraması) ---
        lookback_pd = 24 if idx >= 48 else idx // 2
        if idx >= 30:
            prev_day_sub = df_enriched.iloc[max(0, idx - lookback_pd*2) : idx - lookback_pd]
            if not prev_day_sub.empty:
                pdh_val = float(prev_day_sub['high'].max())
                pdl_val = float(prev_day_sub['low'].min())
                curr_day_sub = df_enriched.iloc[idx - lookback_pd : idx + 1]
                c_high = float(curr_day_sub['high'].max())
                c_low = float(curr_day_sub['low'].min())
                r_low = float(df_enriched['low'].iloc[max(0, idx-3):idx+1].min())
                r_high = float(df_enriched['high'].iloc[max(0, idx-3):idx+1].max())

                if c_high > pdh_val and curr_price >= pdh_val * 0.997:
                    if r_low <= pdh_val * 1.010 and float(curr_bar['close']) >= float(curr_bar['open']):
                        signals_triggered.append(('pdh_pdl_breakout_retest_user', 'LONG', curr_price))
                elif c_low < pdl_val and curr_price <= pdl_val * 1.003:
                    if r_high >= pdl_val * 0.990 and float(curr_bar['close']) <= float(curr_bar['open']):
                        signals_triggered.append(('pdh_pdl_breakout_retest_user', 'SHORT', curr_price))

        # --- H. Super Confluence (Birden fazla strateji kesişimi) ---
        long_count = sum(1 for _, d, _ in signals_triggered if d == 'LONG')
        short_count = sum(1 for _, d, _ in signals_triggered if d == 'SHORT')
        if long_count >= 2:
            signals_triggered.append(('super_confluence', 'LONG', curr_price))
        elif short_count >= 2:
            signals_triggered.append(('super_confluence', 'SHORT', curr_price))

        # Sinyalleri İleriye Doğru Simüle Et (TP1, TP2, TP3 Olasılık Matrisi)
        for strat_id, direction, entry_level in signals_triggered:
            res = strategy_results[strat_id]
            if res['trades'] and (idx - res['trades'][-1]['entry_index']) < 5:
                continue

            entry_p = curr_price
            risk = max(entry_p * 0.012, curr_atr * 1.6)
            
            # Kademeli TP Seviyeleri: TP1 (1:1.0), TP2 (1:2.0), TP3 (1:3.5)
            if direction == 'LONG':
                sl = entry_p - risk
                tp1 = entry_p + risk * 1.0
                tp2 = entry_p + risk * 2.0
                tp3 = entry_p + risk * 3.5
            else:
                sl = entry_p + risk
                tp1 = entry_p - risk * 1.0
                tp2 = entry_p - risk * 2.0
                tp3 = entry_p - risk * 3.5

            future_candles = df_enriched.iloc[idx+1: min(n, idx + 25)]
            is_win = False
            exit_price = entry_p
            exit_index = idx + 1
            exit_time = curr_time
            pnl_pct = 0.0
            exit_reason = 'PENDING'
            
            hit_tp1 = False
            hit_tp2 = False
            hit_tp3 = False

            for f_idx, f_row in future_candles.iterrows():
                f_high = float(f_row['high'])
                f_low = float(f_row['low'])
                f_time = int(f_row['timestamp']) // 1000 if 'timestamp' in f_row else f_idx

                if direction == 'LONG':
                    if f_high >= tp1: hit_tp1 = True
                    if f_high >= tp2: hit_tp2 = True
                    if f_high >= tp3: hit_tp3 = True

                    if f_low <= sl and not hit_tp1:
                        exit_price = sl
                        pnl_pct = -round((entry_p - sl) / entry_p * 100.0, 2)
                        exit_index = f_idx
                        exit_time = f_time
                        is_win = False
                        exit_reason = 'SL'
                        break
                    elif f_high >= tp2 and exit_reason == 'PENDING':
                        exit_price = tp2
                        pnl_pct = round((tp2 - entry_p) / entry_p * 100.0, 2)
                        exit_index = f_idx
                        exit_time = f_time
                        is_win = True
                        exit_reason = 'TP2'
                    elif f_low <= sl:
                        if exit_reason == 'PENDING':
                            exit_price = sl
                            pnl_pct = -round((entry_p - sl) / entry_p * 100.0, 2)
                            exit_index = f_idx
                            exit_time = f_time
                            is_win = False
                            exit_reason = 'SL'
                        break
                else: # SHORT
                    if f_low <= tp1: hit_tp1 = True
                    if f_low <= tp2: hit_tp2 = True
                    if f_low <= tp3: hit_tp3 = True

                    if f_high >= sl and not hit_tp1:
                        exit_price = sl
                        pnl_pct = -round((sl - entry_p) / entry_p * 100.0, 2)
                        exit_index = f_idx
                        exit_time = f_time
                        is_win = False
                        exit_reason = 'SL'
                        break
                    elif f_low <= tp2 and exit_reason == 'PENDING':
                        exit_price = tp2
                        pnl_pct = round((entry_p - tp2) / entry_p * 100.0, 2)
                        exit_index = f_idx
                        exit_time = f_time
                        is_win = True
                        exit_reason = 'TP2'
                    elif f_high >= sl:
                        if exit_reason == 'PENDING':
                            exit_price = sl
                            pnl_pct = -round((sl - entry_p) / entry_p * 100.0, 2)
                            exit_index = f_idx
                            exit_time = f_time
                            is_win = False
                            exit_reason = 'SL'
                        break

            if exit_reason == 'PENDING' and not future_candles.empty:
                last_row = future_candles.iloc[-1]
                last_idx = future_candles.index[-1]
                exit_price = float(last_row['close'])
                exit_index = last_idx
                exit_time = int(last_row['timestamp']) // 1000 if 'timestamp' in last_row else last_idx
                exit_reason = 'TIMEOUT'
                
                if direction == 'LONG':
                    pnl_pct = round((exit_price - entry_p) / entry_p * 100.0, 2)
                else:
                    pnl_pct = round((entry_p - exit_price) / entry_p * 100.0, 2)
                is_win = pnl_pct > 0

            date_str = datetime.fromtimestamp(curr_time).strftime("%m-%d %H:%M") if curr_time > 0 else f"Bar #{idx}"
            exit_date_str = datetime.fromtimestamp(exit_time).strftime("%m-%d %H:%M") if exit_time > 0 else f"Bar #{exit_index}"
            
            strat_name = res['name']
            lines = [
                {'name': 'Giriş Seviyesi (Entry)', 'price': round(entry_p, 4), 'color': '#fbbf24', 'style': 2},
                {'name': 'Stop Loss (Zarar Durdur)', 'price': round(sl, 4), 'color': '#ef4444', 'style': 0},
                {'name': 'TP1 (1:1 R:R Scalp)', 'price': round(tp1, 4), 'color': '#34d399', 'style': 0},
                {'name': 'TP2 (1:2 R:R Ana Hedef)', 'price': round(tp2, 4), 'color': '#10b981', 'style': 0},
                {'name': 'TP3 (1:3.5 R:R Trend)', 'price': round(tp3, 4), 'color': '#8b5cf6', 'style': 0},
            ]

            explanation = f"📌 {date_str} tarihinde ${entry_p:,.4f} seviyesinden {direction} sinyali tetiklendi. "
            if 'pdh_pdl' in strat_id:
                explanation += f"Önceki günün seviyeleri (PDH/PDL) kırılıp test edildikten sonra onay mumu kapandı ve ${entry_p:,.4f} seviyesinden işleme girildi. "
            elif 'order_block' in strat_id:
                explanation += f"Fiyat kurumsal Emir Bloğu (Order Block) bölgesine retest yaptı ve tepki aldı. "
            elif 'trendline' in strat_id:
                explanation += f"Düşen/Yükselen trend çizgisi kırıldı ve onay mumu ile doğrulandı. "
            elif 'rsi_divergence' in strat_id:
                explanation += f"Fiyat ile RSI osilatörü arasındaki uyumsuzluk dönüşü başlattı. "
            
            if is_win:
                explanation += f"İşlem {exit_date_str} tarihinde ${exit_price:,.4f} seviyesinde kâr alarak (%+{pnl_pct}) başarıyla kapandı."
            elif exit_reason == 'SL':
                explanation += f"İşlem ${sl:,.4f} seviyesinde stop oldu (%{pnl_pct})."
            else:
                explanation += f"İşlem 25 mumluk süre sınırında ${exit_price:,.4f} seviyesinde sonlandı (%{pnl_pct})."

            # Kırılma ve Retest Zaman Damgaları
            bo_ts = int(df_enriched['timestamp'].iloc[max(0, idx - 2)] // 1000) if 'timestamp' in df_enriched.columns else int(max(0, idx - 2))
            rt_ts = int(df_enriched['timestamp'].iloc[max(0, idx - 1)] // 1000) if 'timestamp' in df_enriched.columns else int(max(0, idx - 1))

            trade_record = {
                'strategy_id': strat_id,
                'strategy_name': strat_name,
                'entry_index': int(idx),
                'entry_timestamp': int(curr_time),
                'exit_timestamp': int(exit_time),
                'breakout_timestamp': bo_ts,
                'retest_timestamp': rt_ts,
                'breakout_level': round(entry_level, 4) if entry_level else None,
                'entry_time': date_str,
                'exit_time': exit_date_str,
                'direction': direction,
                'entry_price': round(entry_p, 4),
                'exit_price': round(exit_price, 4),
                'stop_loss': round(sl, 4),
                'take_profit': round(tp2, 4),
                'tp1': round(tp1, 4),
                'tp2': round(tp2, 4),
                'tp3': round(tp3, 4),
                'hit_tp1': hit_tp1,
                'hit_tp2': hit_tp2,
                'hit_tp3': hit_tp3,
                'pnl_pct': pnl_pct,
                'is_win': is_win,
                'exit_reason': exit_reason,
                'explanation': explanation,
                'lines': lines
            }
            res['trades'].append(trade_record)

    # İstatistik ve Performans Metriklerini Hesapla
    leaderboard = []
    for s_id, data in strategy_results.items():
        trades = data['trades']
        total = len(trades)
        if total > 0:
            wins = sum(1 for t in trades if t['is_win'])
            losses = total - wins
            win_rate = round((wins / total) * 100.0, 1)
            
            # Kademeli TP Olasılıkları
            tp1_hits = sum(1 for t in trades if t.get('hit_tp1', False))
            tp2_hits = sum(1 for t in trades if t.get('hit_tp2', False))
            tp3_hits = sum(1 for t in trades if t.get('hit_tp3', False))
            
            tp1_win_rate = round((tp1_hits / total) * 100.0, 1)
            tp2_win_rate = round((tp2_hits / total) * 100.0, 1)
            tp3_win_rate = round((tp3_hits / total) * 100.0, 1)

            gross_profit = sum(t['pnl_pct'] for t in trades if t['pnl_pct'] > 0)
            gross_loss = abs(sum(t['pnl_pct'] for t in trades if t['pnl_pct'] < 0))
            net_profit = round(gross_profit - gross_loss, 2)
            profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else round(gross_profit, 2)
            
            # Max Drawdown
            equity_curve = [0.0]
            for t in trades:
                equity_curve.append(equity_curve[-1] + t['pnl_pct'])
            peak = 0.0
            max_dd = 0.0
            for eq in equity_curve:
                if eq > peak: peak = eq
                dd = peak - eq
                if dd > max_dd: max_dd = dd

            composite_score = round(win_rate * 0.5 + min(100, max(-50, net_profit)) * 0.3 + min(5.0, profit_factor) * 8.0, 1)
            
            data['total_trades'] = total
            data['wins'] = wins
            data['losses'] = losses
            data['win_rate'] = win_rate
            data['tp1_win_rate'] = tp1_win_rate
            data['tp2_win_rate'] = tp2_win_rate
            data['tp3_win_rate'] = tp3_win_rate
            data['tp1_hits'] = tp1_hits
            data['tp2_hits'] = tp2_hits
            data['tp3_hits'] = tp3_hits
            data['net_profit_pct'] = net_profit
            data['gross_profit_pct'] = round(gross_profit, 2)
            data['gross_loss_pct'] = round(gross_loss, 2)
            data['profit_factor'] = profit_factor
            data['max_drawdown_pct'] = round(max_dd, 2)
            data['avg_trade_pct'] = round(net_profit / total, 2)
            data['composite_score'] = composite_score
            data['recent_trades'] = trades[-15:]
            del data['trades']
        else:
            data['total_trades'] = 0
            data['win_rate'] = 0.0
            data['tp1_win_rate'] = 0.0
            data['tp2_win_rate'] = 0.0
            data['tp3_win_rate'] = 0.0
            data['tp1_hits'] = 0
            data['tp2_hits'] = 0
            data['tp3_hits'] = 0
            data['net_profit_pct'] = 0.0
            data['profit_factor'] = 0.0
            data['max_drawdown_pct'] = 0.0
            data['composite_score'] = 0.0
            data['recent_trades'] = []
            if 'trades' in data: del data['trades']

        leaderboard.append(data)

    leaderboard.sort(key=lambda x: (x['composite_score'], x['win_rate'], x['net_profit_pct']), reverse=True)
    
    # 🏆 1 Numaralı Şampiyon Strateji
    champion = leaderboard[0] if leaderboard and leaderboard[0]['total_trades'] > 0 else (leaderboard[0] if leaderboard else None)
    
    # Grafik için mum serisi
    candles = []
    for _, row in df_enriched.iterrows():
        ts = int(row['timestamp']) if 'timestamp' in row else 0
        if ts > 1e12: ts = ts // 1000
        candles.append({
            'time': ts,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row['volume'])
        })

    return {
        'status': 'success',
        'symbol': symbol,
        'timeframe': timeframe,
        'lookback_candles': limit,
        'champion_strategy': champion,
        'best_strategy': champion,
        'leaderboard': leaderboard,
        'all_strategies': leaderboard,
        'tested_strategies_count': len(leaderboard),
        'candles': candles
    }
