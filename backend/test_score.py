import sys
sys.path.insert(0, 'C:/Users/MR/.gemini/antigravity/scratch/crypto-signal-pro/backend')
from engine.market_data import market_manager
from engine.setup_calculator import calculate_crypto_setup, WEIGHT
from engine.ai_prompt_generator import generate_ai_prompt
from engine.mtf_analysis import analyze_all_timeframes

print('=== GÜVEN SKORU AĞIRLIK MATRİSİ ===')
print('Maksimum teorik puan:', sum(WEIGHT.values()))
for k, v in WEIGHT.items():
    print('  ', k, ':', str(v) + 'p')
print()

print('=== CANLI TARAMA (Top 5 Pairs) ===')
pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'TRX/USDT']
found = []
for sym in pairs:
    df = market_manager.get_market_data(sym, timeframe='1h', limit=160)
    mtf = analyze_all_timeframes(sym)
    setup = calculate_crypto_setup(sym, df, timeframe='1h', mtf_data=mtf)
    if setup and not setup['is_invalidated']:
        found.append(setup)

found.sort(key=lambda x: x['confidence_score'], reverse=True)
for s in found:
    sb = s['score_breakdown']
    cats = sb['categories']
    print(s['symbol'], '|', s['direction_label'], '| %' + str(s['confidence_score']), '(' + s['score_label'] + ') | RR:', s['rr_ratio'])
    print('   Ham: Long=' + str(sb['long_raw']) + 'p Short=' + str(sb['short_raw']) + 'p | Cezalar:', sb['penalties'])
    print('   Formasyon:', cats['pattern_strength'], '| SMC:', cats['smc_confluence'], '| Trend:', cats['trend_alignment'], '| Div:', cats['divergence_signal'], '| Hacim:', cats['volume_confirm'])
    print()

print('=== AI PROMPT ÖRNEK (ilk 1000 karakter) ===')
if found:
    s = found[0]
    s['ai_prompt'] = generate_ai_prompt(s)
    print(s['ai_prompt'][:1000])
    print('...[devam]...')
