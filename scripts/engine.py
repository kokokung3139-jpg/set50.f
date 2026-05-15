"""
SET50 Forecast Engine
======================
Multi-factor prediction model for SET50 + 50 stocks
Outputs JSON for web dashboard
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timezone, timedelta
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# CONFIG
# ============================================================
SET50 = [
    'ADVANC','AOT','BANPU','BBL','BDMS','BH','CBG','CCET','COM7','CPN',
    'CPALL','CRC','CPF','DELTA','GPSC','GULF','IVL','KBANK','KKP','KTB',
    'KTC','MINT','MTC','PTTEP','PTT','PTTGC','SCB','SCC','SCGP','TIDLOR',
    'TISCO','TOP','TRUE','TTB','WHA','TU','TCAP','OSP','AWC','CENTEL',
    'CK','GUNKUL','ERW','TLI','VGI','SAWAD','TQM','BTS','CPAXT','SPALI'
]

SECTORS = {
    'ADVANC':'ICT','TRUE':'ICT','DELTA':'Tech','CCET':'Tech','COM7':'Tech',
    'KBANK':'Bank','BBL':'Bank','SCB':'Bank','KTB':'Bank','KKP':'Bank',
    'TISCO':'Bank','TTB':'Bank',
    'PTT':'Energy','PTTEP':'Energy','PTTGC':'Chem','GULF':'Energy',
    'GPSC':'Energy','BANPU':'Energy','TOP':'Energy','GUNKUL':'Energy',
    'CPALL':'Retail','CRC':'Retail','CPAXT':'Retail',
    'CBG':'Food','CPF':'Food','MINT':'Food','TU':'Food','OSP':'Food',
    'BDMS':'Health','BH':'Health',
    'AOT':'Transport','BTS':'Transport',
    'SCC':'Industry','SCGP':'Industry','IVL':'Chem',
    'CPN':'Property','WHA':'Property','AWC':'Property','SPALI':'Property',
    'KTC':'Finance','MTC':'Finance','TIDLOR':'Finance','TCAP':'Finance',
    'SAWAD':'Finance','TQM':'Finance','TLI':'Finance',
    'CK':'Construction','ERW':'Tourism','CENTEL':'Tourism','VGI':'Media'
}

# Swing High/Low สำหรับ Fibonacci (อัพเดทเป็นระยะ)
SWING_HIGH = 1032.59
SWING_LOW  = 957.00

# ============================================================
# INDICATOR CALCULATIONS
# ============================================================

def calc_rsi(s, p=14):
    """RSI(14) using Wilder's smoothing"""
    if len(s) < p + 1:
        return None
    d = s.diff()
    g = d.clip(lower=0).ewm(com=p-1, min_periods=p).mean()
    l = (-d.clip(upper=0)).ewm(com=p-1, min_periods=p).mean()
    rs = g / l.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 1)


def calc_macd(s, fast=12, slow=26, sig=9):
    """MACD(12,26,9)"""
    if len(s) < slow + sig:
        return None, None, None
    ef = s.ewm(span=fast, adjust=False).mean()
    es = s.ewm(span=slow, adjust=False).mean()
    m  = ef - es
    sg = m.ewm(span=sig, adjust=False).mean()
    h  = m - sg
    return (round(float(m.iloc[-1]), 3),
            round(float(sg.iloc[-1]), 3),
            round(float(h.iloc[-1]), 3))


def calc_ma(s, period):
    """Simple Moving Average"""
    if len(s) < period: return None
    return round(float(s.rolling(period).mean().iloc[-1]), 2)


def calc_bollinger(s, period=20, std=2):
    """Bollinger Bands"""
    if len(s) < period: return None, None, None
    sma = s.rolling(period).mean()
    sd  = s.rolling(period).std()
    upper = sma + (sd * std)
    lower = sma - (sd * std)
    return (round(float(upper.iloc[-1]), 2),
            round(float(sma.iloc[-1]),   2),
            round(float(lower.iloc[-1]), 2))


def calc_volume_trend(v, period=10):
    """Volume vs Average"""
    if len(v) < period: return None
    avg = v.rolling(period).mean().iloc[-1]
    cur = v.iloc[-1]
    if avg == 0 or pd.isna(avg): return None
    return round(float(cur / avg), 2)


def fib_levels(high, low):
    """Fibonacci Retracement"""
    d = high - low
    return {
        '0%': round(high, 2),
        '23.6%': round(high - d * 0.236, 2),
        '38.2%': round(high - d * 0.382, 2),
        '50.0%': round(high - d * 0.500, 2),
        '61.8%': round(high - d * 0.618, 2),
        '78.6%': round(high - d * 0.786, 2),
        '100%': round(low, 2),
        'EXT_1236': round(low + d * 1.236, 2),
        'EXT_1618': round(low + d * 1.618, 2),
    }


def fib_position(price, fibs):
    """Where is price relative to Fib?"""
    if price >= fibs['23.6%']: return 'ABOVE_236'
    if price >= fibs['38.2%']: return 'ABOVE_382'
    if price >= fibs['50.0%']: return 'ABOVE_500'
    if price >= fibs['61.8%']: return 'ABOVE_618'
    if price >= fibs['78.6%']: return 'ABOVE_786'
    return 'BELOW_786'


# ============================================================
# MULTI-FACTOR PREDICTION MODEL
# ============================================================

def predict(data):
    """
    Multi-factor prediction with confidence score
    Returns: direction, confidence, target, support, resistance
    """
    score = 0
    factors = []

    rsi      = data.get('rsi')
    hist     = data.get('macd_hist')
    price    = data['price']
    fibs     = data['fibs']
    fib_pos  = data['fib_pos']
    vol_t    = data.get('vol_trend')
    ma50     = data.get('ma50')
    ma200    = data.get('ma200')
    bb_u     = data.get('bb_upper')
    bb_l     = data.get('bb_lower')
    pct      = data.get('pct', 0)

    # 1. RSI (15%)
    if rsi is not None:
        if rsi >= 70:  s, f = -10, 'RSI Overbought'
        elif rsi >= 60: s, f = 10, 'RSI Bullish'
        elif rsi >= 50: s, f = 5, 'RSI Neutral-Bull'
        elif rsi >= 40: s, f = -5, 'RSI Neutral-Bear'
        elif rsi >= 30: s, f = -10, 'RSI Bearish'
        else:           s, f = 12, 'RSI Oversold (bounce)'
        score += s
        factors.append({'name': f, 'score': s, 'weight': 15})

    # 2. MACD Histogram (15%)
    if hist is not None:
        if hist > 0.1:  s, f = 12, 'MACD Strong Bull'
        elif hist > 0:  s, f = 8, 'MACD Bull'
        elif hist > -0.1: s, f = -5, 'MACD Bear weak'
        else:             s, f = -10, 'MACD Bearish'
        score += s
        factors.append({'name': f, 'score': s, 'weight': 15})

    # 3. Fibonacci Position (15%)
    fib_map = {
        'ABOVE_236': (12, 'Above Fib 23.6% (strong bull)'),
        'ABOVE_382': (8,  'Above Fib 38.2% (bull)'),
        'ABOVE_500': (4,  'Above Fib 50% (neutral+)'),
        'ABOVE_618': (-2, 'Above Fib 61.8% (neutral-)'),
        'ABOVE_786': (-8, 'Below Fib 61.8% (weak)'),
        'BELOW_786': (-12,'Below Fib 78.6% (weak)')
    }
    if fib_pos in fib_map:
        s, f = fib_map[fib_pos]
        score += s
        factors.append({'name': f, 'score': s, 'weight': 15})

    # 4. Volume Trend (10%)
    if vol_t is not None:
        if vol_t > 1.5:   s, f = 8, f'Volume +{vol_t}x (strong)'
        elif vol_t > 1.0: s, f = 4, f'Volume +{vol_t}x (avg)'
        else:             s, f = -4, f'Volume -{vol_t}x (weak)'
        score += s
        factors.append({'name': f, 'score': s, 'weight': 10})

    # 5. Moving Average (10%)
    if ma50 and ma200:
        if price > ma50 > ma200: s, f = 10, 'Above MA50 & MA200 (Bull trend)'
        elif price > ma50:       s, f = 5, 'Above MA50'
        elif price < ma50 < ma200: s, f = -10, 'Below MA50 & MA200 (Bear)'
        else:                     s, f = -3, 'Mixed MA signals'
        score += s
        factors.append({'name': f, 'score': s, 'weight': 10})

    # 6. Bollinger Bands (10%)
    if bb_u and bb_l:
        bb_pos = (price - bb_l) / (bb_u - bb_l) if bb_u != bb_l else 0.5
        if bb_pos > 0.9:   s, f = -6, 'BB Upper band (overbought)'
        elif bb_pos > 0.6: s, f = 5, 'BB Upper half (bull)'
        elif bb_pos > 0.4: s, f = 2, 'BB Middle (neutral)'
        elif bb_pos > 0.1: s, f = -2, 'BB Lower half (bear)'
        else:              s, f = 6, 'BB Lower band (oversold)'
        score += s
        factors.append({'name': f, 'score': s, 'weight': 10})

    # 7-10. ลด weight สำหรับปัจจัยที่ต้องดึง external data
    # (Fund flow, Sector, Correlation, Historical → ใช้ proxy)

    # 7. Daily Change Momentum (10%)
    if pct > 3:   s, f = 8, f'+{pct}% strong'
    elif pct > 0: s, f = 4, f'+{pct}% positive'
    elif pct > -2: s, f = -3, f'{pct}% weak'
    else:         s, f = -8, f'{pct}% bearish'
    score += s
    factors.append({'name': f, 'score': s, 'weight': 10})

    # === SCORING ===
    confidence = max(0, min(100, 50 + score))

    # Direction
    if score >= 25:   direction = 'STRONG_BUY'
    elif score >= 10: direction = 'BUY'
    elif score >= -10: direction = 'HOLD'
    elif score >= -25: direction = 'SELL'
    else:              direction = 'STRONG_SELL'

    # Target & Support
    if direction in ['STRONG_BUY', 'BUY']:
        target = fibs['38.2%'] if price < fibs['38.2%'] else fibs['23.6%']
        support = fibs['61.8%']
        stop_loss = fibs['78.6%']
    elif direction in ['STRONG_SELL', 'SELL']:
        target = fibs['78.6%']
        support = fibs['100%']
        stop_loss = fibs['50.0%']
    else:
        target = fibs['38.2%']
        support = fibs['61.8%']
        stop_loss = fibs['78.6%']

    return {
        'direction':  direction,
        'confidence': confidence,
        'score':      score,
        'target':     target,
        'support':    support,
        'stop_loss':  stop_loss,
        'factors':    factors,
    }


# ============================================================
# DATA PROCESSING
# ============================================================

def analyze_ticker(sym, raw):
    """Analyze single ticker"""
    tk = sym + '.BK'
    try:
        if isinstance(raw, pd.DataFrame) and 'Close' in raw.columns:
            close  = raw['Close'][tk].dropna() if tk in raw['Close'].columns else None
            high_d = raw['High'][tk].dropna()  if tk in raw['High'].columns  else None
            low_d  = raw['Low'][tk].dropna()   if tk in raw['Low'].columns   else None
            vol_d  = raw['Volume'][tk].dropna() if tk in raw['Volume'].columns else None
        else:
            return None

        if close is None or len(close) < 30:
            return None

        price = round(float(close.iloc[-1]), 2)
        prev  = round(float(close.iloc[-2]), 2)
        pct   = round((price - prev) / prev * 100, 2)

        rsi = calc_rsi(close)
        macd, sig, hist = calc_macd(close)
        ma50  = calc_ma(close, 50) if len(close) >= 50 else None
        ma200 = calc_ma(close, 200) if len(close) >= 200 else None
        bb_u, bb_m, bb_l = calc_bollinger(close)
        vol_t = calc_volume_trend(vol_d) if vol_d is not None else None

        h30 = float(high_d.tail(30).max())
        l30 = float(low_d.tail(30).min())
        fibs = fib_levels(h30, l30)
        fib_pos = fib_position(price, fibs)

        data = {
            'sym': sym, 'sector': SECTORS.get(sym, 'Other'),
            'price': price, 'prev': prev, 'pct': pct,
            'rsi': rsi, 'macd': macd, 'macd_sig': sig, 'macd_hist': hist,
            'ma50': ma50, 'ma200': ma200,
            'bb_upper': bb_u, 'bb_middle': bb_m, 'bb_lower': bb_l,
            'vol_trend': vol_t,
            'fibs': fibs, 'fib_pos': fib_pos,
            'high_30d': round(h30, 2), 'low_30d': round(l30, 2),
        }
        pred = predict(data)
        data['prediction'] = pred
        return data

    except Exception as e:
        return None


def analyze_set50_index():
    """Analyze SET50 index itself"""
    try:
        idx = yf.download('^SET50', period='1y', interval='1d',
                          auto_adjust=True, progress=False)
        if idx.empty: return None

        close = idx['Close'].squeeze()
        high  = idx['High'].squeeze()
        low   = idx['Low'].squeeze()
        vol   = idx['Volume'].squeeze() if 'Volume' in idx else None

        price = round(float(close.iloc[-1]), 2)
        prev  = round(float(close.iloc[-2]), 2)
        pct   = round((price - prev) / prev * 100, 2)

        rsi = calc_rsi(close)
        macd, sig, hist = calc_macd(close)
        ma50  = calc_ma(close, 50)
        ma200 = calc_ma(close, 200)
        bb_u, bb_m, bb_l = calc_bollinger(close)
        vol_t = calc_volume_trend(vol) if vol is not None else None

        # ใช้ Swing จาก config
        fibs = fib_levels(SWING_HIGH, SWING_LOW)
        fib_pos = fib_position(price, fibs)

        data = {
            'sym': 'SET50', 'sector': 'INDEX',
            'price': price, 'prev': prev, 'pct': pct,
            'rsi': rsi, 'macd': macd, 'macd_sig': sig, 'macd_hist': hist,
            'ma50': ma50, 'ma200': ma200,
            'bb_upper': bb_u, 'bb_middle': bb_m, 'bb_lower': bb_l,
            'vol_trend': vol_t,
            'fibs': fibs, 'fib_pos': fib_pos,
            'swing_high': SWING_HIGH, 'swing_low': SWING_LOW,
        }
        pred = predict(data)
        data['prediction'] = pred
        return data
    except Exception as e:
        print(f'SET50 index error: {e}')
        return None


# ============================================================
# RADAR — STRONG MOVERS DETECTION
# ============================================================

def calc_radar_score(s, set50_idx):
    """
    คำนวณคะแนน Radar 5 มิติ เพื่อจับหุ้นโอกาสขึ้น/ลงแรงสูง

    มิติที่วัด:
    1. Momentum     — RSI + MACD + %change
    2. Volume       — Volume ยืนยันการเคลื่อนไหว
    3. Trend        — สอดคล้อง MA50/MA200
    4. Setup        — Fib + Bollinger position
    5. Market Sync  — สอดคล้องกับ SET50
    """
    rsi   = s.get('rsi') or 50
    hist  = s.get('macd_hist') or 0
    price = s['price']
    pct   = s.get('pct') or 0
    ma50  = s.get('ma50')
    ma200 = s.get('ma200')
    bb_u  = s.get('bb_upper')
    bb_l  = s.get('bb_lower')
    vol_t = s.get('vol_trend') or 1.0
    fib_pos = s.get('fib_pos')

    direction_bias = 'UP' if s['prediction']['direction'] in ['BUY','STRONG_BUY'] else \
                     'DOWN' if s['prediction']['direction'] in ['SELL','STRONG_SELL'] else 'NEUTRAL'

    # 1. MOMENTUM
    momentum = 50
    if direction_bias == 'UP':
        momentum += min(25, (rsi - 50) * 1.0) if rsi > 50 else max(-20, (rsi - 50) * 1.0)
        momentum += min(15, hist * 30) if hist > 0 else max(-15, hist * 30)
        momentum += min(15, pct * 3) if pct > 0 else max(-15, pct * 3)
    elif direction_bias == 'DOWN':
        momentum += min(25, (50 - rsi) * 1.0) if rsi < 50 else max(-20, (50 - rsi) * 1.0)
        momentum += min(15, -hist * 30) if hist < 0 else max(-15, -hist * 30)
        momentum += min(15, -pct * 3) if pct < 0 else max(-15, -pct * 3)
    momentum = max(0, min(100, momentum))

    # 2. VOLUME
    if vol_t > 2.0:   volume = 95
    elif vol_t > 1.5: volume = 85
    elif vol_t > 1.2: volume = 70
    elif vol_t > 1.0: volume = 55
    elif vol_t > 0.8: volume = 40
    else:             volume = 25

    # 3. TREND
    trend = 50
    if ma50 and ma200:
        if direction_bias == 'UP':
            if price > ma50 > ma200: trend = 90
            elif price > ma50:        trend = 70
            elif price > ma200:       trend = 55
            else:                     trend = 25
        elif direction_bias == 'DOWN':
            if price < ma50 < ma200: trend = 90
            elif price < ma50:        trend = 70
            elif price < ma200:       trend = 55
            else:                     trend = 25

    # 4. SETUP QUALITY
    setup = 50
    if direction_bias == 'UP':
        fib_score = {'ABOVE_236':85, 'ABOVE_382':80, 'ABOVE_500':70,
                     'ABOVE_618':55, 'ABOVE_786':35, 'BELOW_786':20}.get(fib_pos, 50)
        bb_score = 50
        if bb_u and bb_l and bb_u != bb_l:
            bb_p = (price - bb_l) / (bb_u - bb_l)
            if bb_p > 0.9:   bb_score = 30
            elif bb_p > 0.5: bb_score = 75
            elif bb_p > 0.2: bb_score = 60
            else:            bb_score = 40
        setup = round((fib_score + bb_score) / 2)
    elif direction_bias == 'DOWN':
        fib_score = {'BELOW_786':85, 'ABOVE_786':75, 'ABOVE_618':60,
                     'ABOVE_500':40, 'ABOVE_382':25, 'ABOVE_236':15}.get(fib_pos, 50)
        bb_score = 50
        if bb_u and bb_l and bb_u != bb_l:
            bb_p = (price - bb_l) / (bb_u - bb_l)
            if bb_p < 0.1:   bb_score = 30
            elif bb_p < 0.5: bb_score = 75
            elif bb_p < 0.8: bb_score = 60
            else:            bb_score = 40
        setup = round((fib_score + bb_score) / 2)

    # 5. MARKET SYNC
    sync = 50
    if set50_idx:
        idx_pct = set50_idx.get('pct', 0)
        idx_hist = set50_idx.get('macd_hist', 0)
        if direction_bias == 'UP':
            if idx_pct > 0 and idx_hist > 0:  sync = 85
            elif idx_pct > 0:                  sync = 70
            elif idx_pct < 0:                  sync = 30
            else:                              sync = 50
        elif direction_bias == 'DOWN':
            if idx_pct < 0 and idx_hist < 0:  sync = 85
            elif idx_pct < 0:                  sync = 70
            elif idx_pct > 0:                  sync = 30
            else:                              sync = 50

    radar_total = round(
        momentum * 0.30 + volume * 0.20 + trend * 0.20 +
        setup * 0.20 + sync * 0.10
    )

    return {
        'momentum':  round(momentum),
        'volume':    round(volume),
        'trend':     round(trend),
        'setup':     round(setup),
        'sync':      round(sync),
        'total':     radar_total,
        'direction': direction_bias,
    }


def build_radar(stocks, set50_idx):
    """หาหุ้นที่มีโอกาสขึ้น/ลงแรงสูง"""
    radar_up = []
    radar_down = []

    for s in stocks:
        rs = calc_radar_score(s, set50_idx)
        conf = s['prediction']['confidence']
        s['radar'] = rs
        # Success Probability = 60% Radar + 40% Confidence
        success_prob = round(rs['total'] * 0.6 + conf * 0.4)
        s['success_prob'] = success_prob

        base = {
            'sym': s['sym'], 'price': s['price'], 'pct': s['pct'],
            'rsi': s['rsi'], 'sector': s['sector'],
            'target': s['prediction']['target'],
            'support': s['prediction']['support'],
            'stop_loss': s['prediction']['stop_loss'],
            'direction_label': s['prediction']['direction'],
            'confidence': conf,
            'radar': rs,
            'success_prob': success_prob,
        }

        if rs['direction'] == 'UP' and rs['total'] >= 60 and conf >= 55:
            base['upside_pct'] = round((s['prediction']['target'] - s['price']) / s['price'] * 100, 2)
            radar_up.append(base)
        elif rs['direction'] == 'DOWN' and rs['total'] >= 60 and conf >= 55:
            base['downside_pct'] = round((s['price'] - s['prediction']['target']) / s['price'] * 100, 2)
            radar_down.append(base)

    radar_up.sort(key=lambda x: -x['success_prob'])
    radar_down.sort(key=lambda x: -x['success_prob'])

    return {
        'up':         radar_up[:10],
        'down':       radar_down[:10],
        'total_up':   len(radar_up),
        'total_down': len(radar_down),
    }


# ============================================================
# MAIN
# ============================================================

def main():
    print('🚀 SET50 Forecast Engine Starting...')

    bkk = timezone(timedelta(hours=7))
    now = datetime.now(bkk)

    # SET50 Index
    print('📊 Analyzing SET50 Index...')
    set50 = analyze_set50_index()

    # 50 stocks
    print(f'📋 Fetching {len(SET50)} stocks...')
    tickers = [s + '.BK' for s in SET50]
    raw = yf.download(tickers, period='6mo', interval='1d',
                      auto_adjust=True, progress=True, group_by='column')

    stocks = []
    for sym in SET50:
        d = analyze_ticker(sym, raw)
        if d: stocks.append(d)
    print(f'✅ Analyzed {len(stocks)}/{len(SET50)} stocks')

    # Sector aggregate
    sec_agg = {}
    for s in stocks:
        sec = s['sector']
        if sec not in sec_agg:
            sec_agg[sec] = {'count':0, 'rsi':[], 'pct':[], 'buy':0, 'sell':0, 'hold':0}
        sec_agg[sec]['count'] += 1
        if s['rsi']: sec_agg[sec]['rsi'].append(s['rsi'])
        sec_agg[sec]['pct'].append(s['pct'])
        d = s['prediction']['direction']
        if 'BUY' in d: sec_agg[sec]['buy'] += 1
        elif 'SELL' in d: sec_agg[sec]['sell'] += 1
        else: sec_agg[sec]['hold'] += 1

    sectors = []
    for k, v in sec_agg.items():
        sectors.append({
            'sector': k,
            'count': v['count'],
            'avg_rsi': round(np.mean(v['rsi']), 1) if v['rsi'] else 0,
            'avg_pct': round(np.mean(v['pct']), 2),
            'buy': v['buy'], 'sell': v['sell'], 'hold': v['hold'],
        })
    sectors.sort(key=lambda x: -x['avg_rsi'])

    # Summary
    buy_count  = sum(1 for s in stocks if 'BUY' in s['prediction']['direction'])
    sell_count = sum(1 for s in stocks if 'SELL' in s['prediction']['direction'])
    hold_count = len(stocks) - buy_count - sell_count
    avg_conf   = round(np.mean([s['prediction']['confidence'] for s in stocks]), 1)
    avg_rsi    = round(np.mean([s['rsi'] for s in stocks if s['rsi']]), 1)

    # Radar - Strong Movers Detection
    radar = build_radar(stocks, set50)

    result = {
        'updated_at':  now.isoformat(),
        'updated_display': now.strftime('%d/%m/%Y %H:%M:%S'),
        'set50_index': set50,
        'stocks':      stocks,
        'sectors':     sectors,
        'radar':       radar,
        'summary': {
            'total': len(stocks),
            'buy':   buy_count,
            'sell':  sell_count,
            'hold':  hold_count,
            'avg_confidence': avg_conf,
            'avg_rsi': avg_rsi,
        }
    }

    # Save
    os.makedirs('docs/data', exist_ok=True)
    out = 'docs/data/forecast.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f'✅ Saved: {out}')

    # Also save timestamp-stamped backup
    backup = f'docs/data/forecast_{now.strftime("%Y%m%d_%H%M")}.json'
    with open(backup, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f'\n📊 SUMMARY')
    print(f'  Total:  {len(stocks)}')
    print(f'  🟢 BUY: {buy_count}')
    print(f'  🟡 HOLD: {hold_count}')
    print(f'  🔴 SELL: {sell_count}')
    print(f'  Confidence: {avg_conf}%')


if __name__ == '__main__':
    main()
