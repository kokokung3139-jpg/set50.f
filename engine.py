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

# ============================================================
# DW-SPECIFIC ANALYSIS
# ============================================================

DW_MAP = {
    'ADVANC': {'call': 'ADVANC-W1', 'put': 'ADVANC-W2', 'multiplier': 10},
    'AOT':    {'call': 'AOT-W1',    'put': 'AOT-W2',    'multiplier': 10},
    'BBL':    {'call': 'BBL-W1',    'put': 'BBL-W2',    'multiplier': 5},
    'BDMS':   {'call': 'BDMS-W1',   'put': 'BDMS-W2',   'multiplier': 10},
    'CBG':    {'call': 'CBG-W1',    'put': 'CBG-W2',    'multiplier': 10},
    'CPALL':  {'call': 'CPALL-W1',  'put': 'CPALL-W2',  'multiplier': 10},
    'CPF':    {'call': 'CPF-W1',    'put': 'CPF-W2',    'multiplier': 10},
    'CPN':    {'call': 'CPN-W1',    'put': 'CPN-W2',    'multiplier': 10},
    'DELTA':  {'call': 'DELTA-W1',  'put': 'DELTA-W2',  'multiplier': 5},
    'GULF':   {'call': 'GULF-W1',   'put': 'GULF-W2',   'multiplier': 10},
    'KBANK':  {'call': 'KBANK-W1',  'put': 'KBANK-W2',  'multiplier': 5},
    'KTB':    {'call': 'KTB-W1',    'put': 'KTB-W2',    'multiplier': 10},
    'MINT':   {'call': 'MINT-W1',   'put': 'MINT-W2',   'multiplier': 10},
    'MTC':    {'call': 'MTC-W1',    'put': 'MTC-W2',    'multiplier': 10},
    'PTT':    {'call': 'PTT-W1',    'put': 'PTT-W2',    'multiplier': 10},
    'PTTEP':  {'call': 'PTTEP-W1',  'put': 'PTTEP-W2',  'multiplier': 5},
    'SCB':    {'call': 'SCB-W1',    'put': 'SCB-W2',    'multiplier': 5},
    'TRUE':   {'call': 'TRUE-W1',   'put': 'TRUE-W2',   'multiplier': 10},
    'TTB':    {'call': 'TTB-W1',    'put': 'TTB-W2',    'multiplier': 10},
    'WHA':    {'call': 'WHA-W1',    'put': 'WHA-W2',    'multiplier': 10},
}

def calc_volatility(close, high_d, low_d, period=14):
    """ATR + Historical Volatility สำหรับ DW"""
    if len(close) < period:
        return None
    h = high_d.tail(period + 1)
    l = low_d.tail(period + 1)
    c = close.tail(period + 1)
    tr_list = []
    for i in range(1, len(c)):
        tr = max(
            float(h.iloc[i]) - float(l.iloc[i]),
            abs(float(h.iloc[i]) - float(c.iloc[i-1])),
            abs(float(l.iloc[i]) - float(c.iloc[i-1]))
        )
        tr_list.append(tr)
    atr = round(np.mean(tr_list), 2)
    atr_pct = round(atr / float(close.iloc[-1]) * 100, 2)
    returns = close.pct_change().dropna().tail(20)
    hv = round(float(returns.std() * np.sqrt(252) * 100), 1) if len(returns) >= 10 else None
    iv_est = round(hv * 1.2, 1) if hv else None
    if atr_pct > 3:     vol_level = 'HIGH'
    elif atr_pct > 1.5: vol_level = 'MEDIUM'
    else:               vol_level = 'LOW'
    return {'atr': atr, 'atr_pct': atr_pct, 'hv': hv, 'iv_estimate': iv_est, 'level': vol_level}


def calc_trend_prediction(close, rsi, macd_hist, ma50, ma200):
    """ทำนายแนวโน้ม 1-5 วัน"""
    score = 0
    price = float(close.iloc[-1])
    if rsi:
        if rsi > 60: score += 2
        elif rsi > 50: score += 1
        elif rsi < 40: score -= 2
        elif rsi < 50: score -= 1
    if macd_hist:
        if macd_hist > 0.05: score += 2
        elif macd_hist > 0: score += 1
        elif macd_hist < -0.05: score -= 2
        else: score -= 1
    if ma50 and ma200:
        if price > ma50 > ma200: score += 2
        elif price > ma50: score += 1
        elif price < ma50 < ma200: score -= 2
        else: score -= 1
    if len(close) >= 4:
        pct_3d = (float(close.iloc[-1]) - float(close.iloc[-4])) / float(close.iloc[-4]) * 100
        if pct_3d > 2: score += 1
        elif pct_3d < -2: score -= 1
    if score >= 4:    trend = 'STRONG_UP ⬆️⬆️'
    elif score >= 2:  trend = 'UP ⬆️'
    elif score >= -1: trend = 'SIDEWAYS ↔️'
    elif score >= -3: trend = 'DOWN ⬇️'
    else:             trend = 'STRONG_DOWN ⬇️⬇️'
    return {'trend_1_5d': trend, 'trend_score': score}


def calc_entry_exit_zones(price, fibs, direction):
    """Entry/Exit Zone ตาม Fibonacci สำหรับ DW"""
    if direction in ['STRONG_BUY', 'BUY']:
        entry_levels = [{'level': k, 'price': fibs[k]} for k in ['61.8%','50.0%','38.2%'] if fibs[k] <= price * 1.01]
        exit_levels  = [{'level': k, 'price': fibs[k]} for k in ['23.6%','0%','EXT_1236','EXT_1618'] if fibs[k] > price * 1.005]
    elif direction in ['STRONG_SELL', 'SELL']:
        entry_levels = [{'level': k, 'price': fibs[k]} for k in ['38.2%','50.0%','61.8%'] if fibs[k] >= price * 0.99]
        exit_levels  = [{'level': k, 'price': fibs[k]} for k in ['78.6%','100%'] if fibs[k] < price * 0.995]
    else:
        entry_levels, exit_levels = [], []
    return {'entry_zone': entry_levels[:2], 'exit_zone': exit_levels[:2]}


def calc_dw_recommendation(sym, direction, confidence, volatility, trend_data, pred, current_price):
    """คำแนะนำ DW: Call/Put, Grade, Risk/Reward, Timing"""
    dw_info = DW_MAP.get(sym)
    target    = pred['target']
    stop_loss = pred['stop_loss']

    if direction in ['STRONG_BUY', 'BUY']:
        dw_type = 'CALL 📈'
        dw_code = dw_info['call'] if dw_info else f'{sym}-DW-CALL'
        reward = round(target - current_price, 2) if target > current_price else 0
        risk   = round(current_price - stop_loss, 2) if current_price > stop_loss else 0
    elif direction in ['STRONG_SELL', 'SELL']:
        dw_type = 'PUT 📉'
        dw_code = dw_info['put'] if dw_info else f'{sym}-DW-PUT'
        reward = round(current_price - target, 2) if current_price > target else 0
        risk   = round(stop_loss - current_price, 2) if stop_loss > current_price else 0
    else:
        return {'action': 'WAIT ⏳', 'reason': 'สัญญาณยังไม่ชัดเจน รอก่อน'}

    rr_ratio  = round(reward / risk, 1) if risk > 0 else 0
    vol_level = volatility['level'] if volatility else 'MEDIUM'

    if vol_level == 'HIGH':
        vol_note = '⚠️ Volatility สูง DW เคลื่อนไวมาก ใช้ขนาดเล็ก'
    elif vol_level == 'MEDIUM':
        vol_note = '✅ Volatility ปกติ เหมาะเล่น DW'
    else:
        vol_note = '⚠️ Volatility ต่ำ DW เคลื่อนช้า อาจไม่คุ้ม'

    trend_score = trend_data.get('trend_score', 0) if trend_data else 0
    if abs(trend_score) >= 4:   timing = 'เข้าได้เลย 🔥'
    elif abs(trend_score) >= 2: timing = 'รอยืนยัน 1 แท่ง ⏱️'
    else:                       timing = 'รอสัญญาณชัดขึ้น 🔍'

    if confidence >= 75 and rr_ratio >= 2 and vol_level != 'LOW':
        grade = 'A 🟢 แนะนำ'
    elif confidence >= 60 and rr_ratio >= 1.5:
        grade = 'B 🟡 พิจารณา'
    else:
        grade = 'C 🔴 รอก่อน'

    # === โอกาสสำเร็จ (Success Probability) ===
    # คำนวณจาก 4 ปัจจัย:
    # 1. Confidence จาก multi-factor model (35%)
    # 2. Risk/Reward ratio (25%)
    # 3. Trend score (25%)
    # 4. Volatility เหมาะสม (15%)

    # ปัจจัย 1: Confidence
    conf_score = min(100, confidence)

    # ปัจจัย 2: R/R ratio (ยิ่งสูงยิ่งดี cap ที่ 3:1)
    rr_score = min(100, rr_ratio / 3.0 * 100)

    # ปัจจัย 3: Trend alignment
    trend_score_abs = abs(trend_score)
    trend_score_norm = min(100, trend_score_abs / 6.0 * 100)

    # ปัจจัย 4: Volatility fit
    if vol_level == 'MEDIUM':   vol_score = 100
    elif vol_level == 'HIGH':   vol_score = 70
    else:                       vol_score = 40

    success_prob = round(
        conf_score    * 0.35 +
        rr_score      * 0.25 +
        trend_score_norm * 0.25 +
        vol_score     * 0.15
    )
    success_prob = max(0, min(99, success_prob))

    # Label
    if success_prob >= 75:   prob_label = f'{success_prob}% 🔥 สูง'
    elif success_prob >= 55: prob_label = f'{success_prob}% ✅ ปานกลาง'
    else:                    prob_label = f'{success_prob}% ⚠️ ต่ำ'

    return {
        'action': dw_type,
        'dw_code': dw_code,
        'grade': grade,
        'timing': timing,
        'risk_reward': rr_ratio,
        'reward_pts': reward,
        'risk_pts': risk,
        'vol_note': vol_note,
        'vol_level': vol_level,
        'multiplier': dw_info['multiplier'] if dw_info else 10,
        'success_prob': success_prob,
        'success_prob_label': prob_label,
    }


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
        # Target ต้องสูงกว่าราคาปัจจุบัน
        fib_levels_up = ['23.6%', '38.2%', '50.0%', '61.8%', '78.6%', '0%', 'EXT_1236', 'EXT_1618']
        target = next((fibs[f] for f in fib_levels_up if fibs[f] > price * 1.005), round(price * 1.05, 2))
        # Support ต้องต่ำกว่าราคาปัจจุบัน
        fib_levels_down = ['61.8%', '50.0%', '38.2%', '78.6%', '100%']
        support = next((fibs[f] for f in fib_levels_down if fibs[f] < price), round(price * 0.97, 2))
        stop_loss = round(support * 0.985, 2)
    elif direction in ['STRONG_SELL', 'SELL']:
        # Target ต้องต่ำกว่าราคาปัจจุบัน
        fib_levels_down = ['61.8%', '78.6%', '100%', '50.0%']
        target = next((fibs[f] for f in fib_levels_down if fibs[f] < price * 0.995), round(price * 0.95, 2))
        # Stop loss ต้องสูงกว่าราคาปัจจุบัน
        fib_levels_up = ['38.2%', '23.6%', '50.0%', '0%']
        stop_loss = next((fibs[f] for f in fib_levels_up if fibs[f] > price), round(price * 1.03, 2))
        support = fibs['100%'] if fibs['100%'] < price else round(price * 0.95, 2)
    else:
        fib_levels_up = ['23.6%', '38.2%', '50.0%', 'EXT_1236']
        target = next((fibs[f] for f in fib_levels_up if fibs[f] > price * 1.005), round(price * 1.03, 2))
        fib_levels_down = ['61.8%', '50.0%', '78.6%']
        support = next((fibs[f] for f in fib_levels_down if fibs[f] < price), round(price * 0.97, 2))
        stop_loss = round(support * 0.985, 2)

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

        # DW Analysis
        volatility = calc_volatility(close, high_d, low_d) if high_d is not None and low_d is not None else None
        trend_data = calc_trend_prediction(close, rsi, hist, ma50, ma200)
        entry_exit = calc_entry_exit_zones(price, fibs, pred['direction'])
        dw_rec     = calc_dw_recommendation(sym, pred['direction'], pred['confidence'], volatility, trend_data, pred, price)

        data['volatility']  = volatility
        data['trend']       = trend_data
        data['entry_exit']  = entry_exit
        data['dw']          = dw_rec

        return data

    except Exception as e:
        return None


def fetch_set50_futures_data():
    """
    ดึงข้อมูล SET50 Index + Futures proxy
    - ใช้ ^SET50 (spot) เป็นหลัก
    - คำนวณ Futures premium/discount จาก basis
    - ดึง TFEX S50 proxy จาก volume/OI pattern
    """
    results = {}

    # 1. SET50 Spot Index
    for ticker in ['^SET50', 'SET50.BK', '^SETI']:
        try:
            df = yf.download(ticker, period='1y', interval='1d',
                             auto_adjust=True, progress=False)
            if not df.empty and len(df) > 50:
                results['spot'] = df
                results['spot_ticker'] = ticker
                print(f'  SET50 spot: {ticker} OK ({len(df)} bars)')
                break
        except:
            continue

    # 2. Futures proxy — ใช้ S50Z24.BK หรือ near-month
    futures_tickers = ['S50Z25.BK', 'S50M25.BK', 'S50U25.BK', 'S50H25.BK',
                       'S50Z24.BK', 'S50M24.BK']
    for fticker in futures_tickers:
        try:
            fdf = yf.download(fticker, period='3mo', interval='1d',
                              auto_adjust=True, progress=False)
            if not fdf.empty and len(fdf) > 5:
                results['futures'] = fdf
                results['futures_ticker'] = fticker
                print(f'  S50 Futures: {fticker} OK ({len(fdf)} bars)')
                break
        except:
            continue

    # 3. ดึง intraday 5min สำหรับ momentum ระยะสั้น
    try:
        intra = yf.download(results.get('spot_ticker', '^SET50'),
                            period='5d', interval='5m',
                            auto_adjust=True, progress=False)
        if not intra.empty:
            results['intraday'] = intra
            print(f'  Intraday 5m: {len(intra)} bars')
    except:
        pass

    return results


def calc_futures_basis(spot_price, futures_data):
    """
    คำนวณ Futures Basis = Futures - Spot
    Basis บวก = Contango (ตลาดมองบวก)
    Basis ลบ  = Backwardation (ตลาดมองลบ)
    """
    if futures_data is None or futures_data.empty:
        return None

    try:
        fut_close = futures_data['Close'].squeeze()
        fut_price = round(float(fut_close.iloc[-1]), 2)
        basis = round(fut_price - spot_price, 2)
        basis_pct = round(basis / spot_price * 100, 2)

        # Basis trend (3 วัน)
        if len(fut_close) >= 4:
            basis_3d_ago = float(fut_close.iloc[-4]) - spot_price
            basis_trend = 'EXPANDING' if basis > basis_3d_ago else 'CONTRACTING'
        else:
            basis_trend = 'UNKNOWN'

        if basis > 5:      basis_signal = 'BULLISH 🟢 Contango แรง'
        elif basis > 1:    basis_signal = 'MILD_BULL 🟡 Contango เล็กน้อย'
        elif basis > -1:   basis_signal = 'NEUTRAL ⚪ Flat'
        elif basis > -5:   basis_signal = 'MILD_BEAR 🟠 Backwardation เล็กน้อย'
        else:              basis_signal = 'BEARISH 🔴 Backwardation แรง'

        return {
            'futures_price': fut_price,
            'basis': basis,
            'basis_pct': basis_pct,
            'basis_signal': basis_signal,
            'basis_trend': basis_trend,
        }
    except:
        return None


def calc_intraday_momentum(intraday_df):
    """
    วิเคราะห์ momentum ระยะสั้นจาก 5min bar
    - VWAP position
    - Opening range breakout
    - Intraday trend
    """
    if intraday_df is None or intraday_df.empty:
        return None
    try:
        close = intraday_df['Close'].squeeze()
        high  = intraday_df['High'].squeeze()
        low   = intraday_df['Low'].squeeze()
        vol   = intraday_df['Volume'].squeeze() if 'Volume' in intraday_df.columns else None

        # VWAP (วันนี้)
        today_bars = intraday_df.tail(78)  # ~78 bars ต่อวัน (5min x 6.5h)
        if len(today_bars) > 5 and vol is not None:
            tv = today_bars['Volume'].squeeze()
            tc = today_bars['Close'].squeeze()
            th = today_bars['High'].squeeze()
            tl = today_bars['Low'].squeeze()
            typical = (tc + th + tl) / 3
            vwap = round(float((typical * tv).sum() / tv.sum()), 2) if tv.sum() > 0 else None
        else:
            vwap = None

        current_price = round(float(close.iloc[-1]), 2)

        # Opening range (30 min แรก = 6 bars)
        if len(intraday_df) >= 6:
            today_start = intraday_df.tail(78).head(6)
            or_high = round(float(today_start['High'].max()), 2)
            or_low  = round(float(today_start['Low'].min()), 2)
            if current_price > or_high:   or_signal = 'BREAKOUT_UP 🚀'
            elif current_price < or_low:  or_signal = 'BREAKOUT_DOWN 📉'
            else:                         or_signal = 'INSIDE_RANGE ↔️'
        else:
            or_high, or_low, or_signal = None, None, None

        # Intraday trend (เส้น 20-bar EMA)
        if len(close) >= 20:
            ema20 = close.ewm(span=20, adjust=False).mean()
            intra_trend = 'UP ⬆️' if current_price > float(ema20.iloc[-1]) else 'DOWN ⬇️'
        else:
            intra_trend = None

        # RSI intraday
        intra_rsi = calc_rsi(close, p=9)

        # VWAP signal
        if vwap:
            vwap_signal = 'ABOVE_VWAP 🟢' if current_price > vwap else 'BELOW_VWAP 🔴'
        else:
            vwap_signal = None

        return {
            'vwap': vwap,
            'vwap_signal': vwap_signal,
            'or_high': or_high,
            'or_low': or_low,
            'or_signal': or_signal,
            'intra_trend': intra_trend,
            'intra_rsi': intra_rsi,
        }
    except Exception as e:
        print(f'Intraday error: {e}')
        return None


def calc_set50_dw_signal(spot_data, basis_data, intraday_data, volatility):
    """
    สัญญาณ DW SET50 แบบละเอียด
    รวม: Daily trend + Futures basis + Intraday momentum + Volatility
    คะแนน 0-100 แยก CALL / PUT
    """
    score = 0
    signals = []
    weights_used = 0

    price    = spot_data.get('price', 0)
    rsi      = spot_data.get('rsi')
    hist     = spot_data.get('macd_hist')
    ma50     = spot_data.get('ma50')
    ma200    = spot_data.get('ma200')
    fib_pos  = spot_data.get('fib_pos')
    pct      = spot_data.get('pct', 0)
    bb_u     = spot_data.get('bb_upper')
    bb_l     = spot_data.get('bb_lower')

    # === ปัจจัย 1: Daily RSI (15%) ===
    if rsi:
        if rsi >= 70:    s = -12; note = f'RSI {rsi} Overbought ⚠️'
        elif rsi >= 60:  s = 12;  note = f'RSI {rsi} Bullish 🟢'
        elif rsi >= 55:  s = 8;   note = f'RSI {rsi} Mild Bull'
        elif rsi >= 45:  s = 0;   note = f'RSI {rsi} Neutral'
        elif rsi >= 40:  s = -8;  note = f'RSI {rsi} Mild Bear'
        elif rsi >= 30:  s = -12; note = f'RSI {rsi} Bearish 🔴'
        else:            s = 10;  note = f'RSI {rsi} Oversold (bounce)'
        score += s; signals.append({'factor': 'RSI Daily', 'score': s, 'weight': 15, 'note': note})
        weights_used += 15

    # === ปัจจัย 2: MACD Histogram (15%) ===
    if hist is not None:
        if hist > 2:     s = 15;  note = f'MACD Hist +{hist} Strong Bull 🟢'
        elif hist > 0.5: s = 10;  note = f'MACD Hist +{hist} Bull'
        elif hist > 0:   s = 5;   note = f'MACD Hist +{hist} Mild Bull'
        elif hist > -0.5: s = -5; note = f'MACD Hist {hist} Mild Bear'
        elif hist > -2:  s = -10; note = f'MACD Hist {hist} Bear'
        else:            s = -15; note = f'MACD Hist {hist} Strong Bear 🔴'
        score += s; signals.append({'factor': 'MACD Histogram', 'score': s, 'weight': 15, 'note': note})
        weights_used += 15

    # === ปัจจัย 3: MA Trend (15%) ===
    if ma50 and ma200:
        if price > ma50 > ma200:   s = 15; note = 'Above MA50 > MA200 Bull trend 🟢'
        elif price > ma50:          s = 8;  note = 'Above MA50 (mild bull)'
        elif price > ma200:         s = 3;  note = 'Above MA200 only (weak)'
        elif price < ma50 < ma200:  s = -15; note = 'Below MA50 < MA200 Bear trend 🔴'
        elif price < ma50:          s = -8;  note = 'Below MA50 (mild bear)'
        else:                       s = -3;  note = 'Below MA200 only'
        score += s; signals.append({'factor': 'MA Trend', 'score': s, 'weight': 15, 'note': note})
        weights_used += 15

    # === ปัจจัย 4: Fibonacci Position (10%) ===
    fib_map = {
        'ABOVE_236': (10, 'Above 23.6% — Strong Bull Zone 🟢'),
        'ABOVE_382': (7,  'Above 38.2% — Bull Zone'),
        'ABOVE_500': (3,  'Above 50% — Neutral+'),
        'ABOVE_618': (-3, 'Above 61.8% — Neutral-'),
        'ABOVE_786': (-7, 'Above 78.6% — Weak'),
        'BELOW_786': (-10,'Below 78.6% — Bear Zone 🔴'),
    }
    if fib_pos in fib_map:
        s, note = fib_map[fib_pos]
        score += s; signals.append({'factor': 'Fibonacci', 'score': s, 'weight': 10, 'note': note})
        weights_used += 10

    # === ปัจจัย 5: Futures Basis (15%) — สำคัญมากสำหรับ DW SET50 ===
    if basis_data:
        basis = basis_data.get('basis', 0)
        if basis > 8:    s = 15; note = f'Basis +{basis} pts Contango แรงมาก 🟢'
        elif basis > 3:  s = 10; note = f'Basis +{basis} pts Contango บวก'
        elif basis > 0:  s = 5;  note = f'Basis +{basis} pts Mild Contango'
        elif basis > -3: s = -5; note = f'Basis {basis} pts Mild Backwardation'
        elif basis > -8: s = -10; note = f'Basis {basis} pts Backwardation'
        else:            s = -15; note = f'Basis {basis} pts Backwardation แรงมาก 🔴'
        score += s; signals.append({'factor': 'Futures Basis', 'score': s, 'weight': 15, 'note': note})
        weights_used += 15
    else:
        weights_used += 0  # ไม่มี futures data ไม่นับ weight

    # === ปัจจัย 6: Intraday Momentum (15%) ===
    if intraday_data:
        intra_score = 0
        intra_notes = []

        # VWAP
        vs = intraday_data.get('vwap_signal', '')
        if 'ABOVE' in str(vs):   intra_score += 5; intra_notes.append('Above VWAP')
        elif 'BELOW' in str(vs): intra_score -= 5; intra_notes.append('Below VWAP')

        # Opening Range
        ors = intraday_data.get('or_signal', '')
        if 'BREAKOUT_UP' in str(ors):   intra_score += 8; intra_notes.append('OR Breakout UP')
        elif 'BREAKOUT_DOWN' in str(ors): intra_score -= 8; intra_notes.append('OR Breakout DOWN')

        # Intraday trend
        it = intraday_data.get('intra_trend', '')
        if 'UP' in str(it):   intra_score += 5; intra_notes.append('Intra UP')
        elif 'DOWN' in str(it): intra_score -= 5; intra_notes.append('Intra DOWN')

        # Intraday RSI
        irsi = intraday_data.get('intra_rsi')
        if irsi:
            if irsi > 65:   intra_score += 5; intra_notes.append(f'IRSI {irsi} Bull')
            elif irsi < 35: intra_score -= 5; intra_notes.append(f'IRSI {irsi} Bear')

        s = max(-15, min(15, intra_score))
        score += s
        signals.append({'factor': 'Intraday Momentum', 'score': s, 'weight': 15,
                        'note': ' + '.join(intra_notes) if intra_notes else 'Neutral'})
        weights_used += 15

    # === ปัจจัย 7: Bollinger + Daily %change (15%) ===
    bb_score = 0
    if bb_u and bb_l and bb_u != bb_l:
        bb_pos = (price - bb_l) / (bb_u - bb_l)
        if bb_pos > 0.9:   bb_score = -8
        elif bb_pos > 0.6: bb_score = 6
        elif bb_pos > 0.4: bb_score = 2
        elif bb_pos > 0.1: bb_score = -4
        else:              bb_score = 8

    pct_score = 0
    if pct > 1.5:    pct_score = 7
    elif pct > 0.5:  pct_score = 4
    elif pct > 0:    pct_score = 2
    elif pct > -0.5: pct_score = -2
    elif pct > -1.5: pct_score = -4
    else:            pct_score = -7

    s = round((bb_score + pct_score) / 2)
    note = f'BB pos + Daily {pct}%'
    score += s; signals.append({'factor': 'BB + Daily%', 'score': s, 'weight': 15, 'note': note})
    weights_used += 15

    # === คำนวณ Confidence ===
    max_possible = weights_used
    normalized = (score + max_possible) / (2 * max_possible) * 100 if max_possible > 0 else 50
    confidence = round(max(0, min(100, normalized)))

    # === Direction ===
    if score >= 35:    direction = 'STRONG_BUY';  dw_action = 'DW CALL แนะนำแรง 🔥'
    elif score >= 15:  direction = 'BUY';          dw_action = 'DW CALL พิจารณา ✅'
    elif score >= -15: direction = 'HOLD';         dw_action = 'รอสัญญาณ ⏳'
    elif score >= -35: direction = 'SELL';         dw_action = 'DW PUT พิจารณา ✅'
    else:              direction = 'STRONG_SELL';  dw_action = 'DW PUT แนะนำแรง 🔥'

    # === Target Levels (Fibonacci) ===
    fibs = spot_data.get('fibs', {})
    p = price
    if direction in ['STRONG_BUY', 'BUY']:
        targets = [v for v in [fibs.get('23.6%'), fibs.get('0%'), fibs.get('EXT_1236')] if v and v > p * 1.003]
        stops   = [v for v in [fibs.get('61.8%'), fibs.get('78.6%'), fibs.get('100%')] if v and v < p * 0.998]
    else:
        targets = [v for v in [fibs.get('61.8%'), fibs.get('78.6%'), fibs.get('100%')] if v and v < p * 0.997]
        stops   = [v for v in [fibs.get('38.2%'), fibs.get('23.6%'), fibs.get('0%')] if v and v > p * 1.002]

    target1 = targets[0] if targets else None
    target2 = targets[1] if len(targets) > 1 else None
    stop    = stops[0] if stops else None

    reward = round(abs(target1 - p), 2) if target1 else None
    risk   = round(abs(p - stop), 2) if stop else None
    rr     = round(reward / risk, 1) if reward and risk and risk > 0 else None

    # === Success Probability ===
    prob_score = 0
    prob_score += confidence * 0.40
    prob_score += (min(rr, 3) / 3 * 100) * 0.25 if rr else 25
    prob_score += (abs(score) / max_possible * 100) * 0.20 if max_possible else 0
    vol_fit = volatility.get('level') if volatility else 'MEDIUM'
    prob_score += {'MEDIUM': 100, 'HIGH': 65, 'LOW': 35}.get(vol_fit, 70) * 0.15
    success_prob = round(max(0, min(99, prob_score)))

    if success_prob >= 75:   prob_label = f'{success_prob}% 🔥 สูง'
    elif success_prob >= 55: prob_label = f'{success_prob}% ✅ ปานกลาง'
    else:                    prob_label = f'{success_prob}% ⚠️ ต่ำ'

    return {
        'direction':     direction,
        'dw_action':     dw_action,
        'score':         score,
        'confidence':    confidence,
        'success_prob':  success_prob,
        'success_prob_label': prob_label,
        'target1':       target1,
        'target2':       target2,
        'stop_loss':     stop,
        'risk_reward':   rr,
        'reward_pts':    reward,
        'risk_pts':      risk,
        'signals':       signals,
    }


def analyze_set50_index():
    """
    วิเคราะห์ SET50 Index สำหรับ DW SET50 โดยเฉพาะ
    รวม: Spot + Futures Basis + Intraday + Volatility
    """
    try:
        print('  Fetching SET50 data...')
        raw = fetch_set50_futures_data()

        spot_df     = raw.get('spot')
        futures_df  = raw.get('futures')
        intraday_df = raw.get('intraday')

        if spot_df is None or spot_df.empty:
            print('  SET50 spot data unavailable')
            return None

        close = spot_df['Close'].squeeze()
        high  = spot_df['High'].squeeze()
        low   = spot_df['Low'].squeeze()
        vol   = spot_df['Volume'].squeeze() if 'Volume' in spot_df.columns else None

        price = round(float(close.iloc[-1]), 2)
        prev  = round(float(close.iloc[-2]), 2)
        pct   = round((price - prev) / prev * 100, 2)

        rsi  = calc_rsi(close)
        macd, sig, hist = calc_macd(close)
        ma5   = calc_ma(close, 5)
        ma10  = calc_ma(close, 10)
        ma20  = calc_ma(close, 20)
        ma50  = calc_ma(close, 50)
        ma200 = calc_ma(close, 200)
        bb_u, bb_m, bb_l = calc_bollinger(close)
        vol_t = calc_volume_trend(vol) if vol is not None else None
        volatility = calc_volatility(close, high, low) if len(close) >= 14 else None

        # Fibonacci จาก swing 52 สัปดาห์
        h52 = round(float(high.tail(252).max()), 2)
        l52 = round(float(low.tail(252).min()), 2)
        fibs = fib_levels(h52, l52)
        fib_pos = fib_position(price, fibs)

        # Fibonacci 30 วัน (ระยะสั้น)
        h30 = round(float(high.tail(30).max()), 2)
        l30 = round(float(low.tail(30).min()), 2)
        fibs_30d = fib_levels(h30, l30)

        # Futures Basis
        basis_data = calc_futures_basis(price, futures_df)

        # Intraday Momentum
        intraday_data = calc_intraday_momentum(intraday_df)

        spot_data_for_signal = {
            'price': price, 'pct': pct,
            'rsi': rsi, 'macd_hist': hist,
            'ma50': ma50, 'ma200': ma200,
            'bb_upper': bb_u, 'bb_lower': bb_l,
            'fib_pos': fib_pos, 'fibs': fibs,
        }

        # สัญญาณ DW SET50 แบบละเอียด
        dw_signal = calc_set50_dw_signal(spot_data_for_signal, basis_data, intraday_data, volatility)

        # Weekly trend
        if len(close) >= 5:
            pct_5d = round((price - float(close.iloc[-6])) / float(close.iloc[-6]) * 100, 2)
        else:
            pct_5d = None
        if len(close) >= 20:
            pct_20d = round((price - float(close.iloc[-21])) / float(close.iloc[-21]) * 100, 2)
        else:
            pct_20d = None

        return {
            'sym': 'SET50', 'sector': 'INDEX',
            'price': price, 'prev': prev, 'pct': pct,
            'pct_5d': pct_5d, 'pct_20d': pct_20d,
            'rsi': rsi, 'macd': macd, 'macd_sig': sig, 'macd_hist': hist,
            'ma5': ma5, 'ma10': ma10, 'ma20': ma20, 'ma50': ma50, 'ma200': ma200,
            'bb_upper': bb_u, 'bb_middle': bb_m, 'bb_lower': bb_l,
            'vol_trend': vol_t,
            'volatility': volatility,
            'fibs': fibs,
            'fibs_30d': fibs_30d,
            'fib_pos': fib_pos,
            'high_52w': h52, 'low_52w': l52,
            'high_30d': h30, 'low_30d': l30,
            'futures': basis_data,
            'intraday': intraday_data,
            'dw_signal': dw_signal,
            'prediction': {
                'direction':   dw_signal['direction'],
                'confidence':  dw_signal['confidence'],
                'score':       dw_signal['score'],
                'target':      dw_signal['target1'],
                'target2':     dw_signal['target2'],
                'support':     dw_signal['stop_loss'],
                'stop_loss':   dw_signal['stop_loss'],
                'factors':     dw_signal['signals'],
            },
        }
    except Exception as e:
        print(f'SET50 index error: {e}')
        import traceback; traceback.print_exc()
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
