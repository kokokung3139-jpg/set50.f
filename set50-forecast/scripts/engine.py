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

# SET50 Futures contract month codes
# F=Jan, G=Feb, H=Mar, J=Apr, K=May, M=Jun, N=Jul, Q=Aug, U=Sep, V=Oct, X=Nov, Z=Dec
FUTURES_MONTH_CODES = {
    1:'F', 2:'G', 3:'H', 4:'J', 5:'K', 6:'M',
    7:'N', 8:'Q', 9:'U', 10:'V', 11:'X', 12:'Z'
}
# SET50 Futures หมดอายุ "พุธสุดท้ายของเดือน" รายไตรมาส (มี.ค./มิ.ย./ก.ย./ธ.ค.)
# แต่ก็มีรายเดือนด้วย
FUTURES_QUARTER_MONTHS = [3, 6, 9, 12]

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


def calc_atr(high, low, close, period=14):
    """Average True Range — ใช้บอก Volatility"""
    if len(close) < period + 1: return None
    h_l = high - low
    h_c = (high - close.shift()).abs()
    l_c = (low - close.shift()).abs()
    tr = pd.concat([h_l, h_c, l_c], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()
    return round(float(atr.iloc[-1]), 2)


def calc_historical_vol(close, period=20):
    """Historical Volatility (annualized) — สำหรับประเมิน DW pricing"""
    if len(close) < period + 1: return None
    log_ret = np.log(close / close.shift()).dropna()
    if len(log_ret) < period: return None
    vol = log_ret.tail(period).std() * np.sqrt(252) * 100
    return round(float(vol), 1)


def vol_class(hv):
    """แบ่งระดับ Volatility"""
    if hv is None: return 'UNKNOWN'
    if hv >= 50: return 'HIGH'      # ผันผวนสูง → DW เคลื่อนไหวเร็ว แต่เสี่ยง
    if hv >= 30: return 'MEDIUM'    # ปกติ → เหมาะสำหรับ DW
    return 'LOW'                     # ผันผวนต่ำ → DW เคลื่อนน้อย


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
    # ============================================================
    # 1. RSI (15%) — symmetric weights
    # ============================================================
    if rsi is not None:
        if rsi >= 75:   s, f = -12, f'RSI {rsi} Extreme Overbought'      # Strong SELL signal
        elif rsi >= 70: s, f = -8,  f'RSI {rsi} Overbought'
        elif rsi >= 60: s, f = 10,  f'RSI {rsi} Bullish'
        elif rsi >= 55: s, f = 7,   f'RSI {rsi} Mild Bullish'
        elif rsi >= 45: s, f = 0,   f'RSI {rsi} Neutral'
        elif rsi >= 40: s, f = -7,  f'RSI {rsi} Mild Bearish'
        elif rsi >= 30: s, f = -10, f'RSI {rsi} Bearish'
        elif rsi >= 25: s, f = -8,  f'RSI {rsi} Oversold (some bounce risk)'
        else:           s, f = 8,   f'RSI {rsi} Extreme Oversold (bounce likely)'
        score += s
        factors.append({'name': f, 'score': s, 'weight': 15})

    # ============================================================
    # 2. MACD Histogram (15%) — symmetric weights
    # ============================================================
    if hist is not None:
        if hist > 0.15:   s, f = 12, 'MACD ▲▲ Strong Bull'
        elif hist > 0.05: s, f = 8,  'MACD ▲ Bull'
        elif hist > 0:    s, f = 4,  'MACD ▲ Weak Bull'
        elif hist > -0.05: s, f = -4,  'MACD ▼ Weak Bear'
        elif hist > -0.15: s, f = -8,  'MACD ▼ Bear'
        else:              s, f = -12, 'MACD ▼▼ Strong Bear'
        score += s
        factors.append({'name': f, 'score': s, 'weight': 15})

    # ============================================================
    # 3. MACD Cross Signal (NEW) — detect direction change
    # ============================================================
    if data.get('macd') is not None and data.get('macd_sig') is not None:
        macd_val = data['macd']
        sig_val = data['macd_sig']
        if macd_val > sig_val and hist > 0:
            s, f = 5, 'MACD เหนือ Signal Line ✓'
            score += s
            factors.append({'name': f, 'score': s, 'weight': 5})
        elif macd_val < sig_val and hist < 0:
            s, f = -5, 'MACD ใต้ Signal Line ✗'
            score += s
            factors.append({'name': f, 'score': s, 'weight': 5})

    # ============================================================
    # 4. Fibonacci Position (15%) — symmetric
    # ============================================================
    fib_map = {
        'ABOVE_236': (12, 'เหนือ Fib 23.6% (Strong Bull zone)'),
        'ABOVE_382': (8,  'เหนือ Fib 38.2% (Bull zone)'),
        'ABOVE_500': (3,  'เหนือ Fib 50% (Neutral+)'),
        'ABOVE_618': (-3, 'ใต้ Fib 50% (Neutral-)'),
        'ABOVE_786': (-8, 'ใต้ Fib 61.8% (Bear zone)'),
        'BELOW_786': (-12,'ใต้ Fib 78.6% (Strong Bear zone)')
    }
    if fib_pos in fib_map:
        s, f = fib_map[fib_pos]
        score += s
        factors.append({'name': f, 'score': s, 'weight': 15})

    # ============================================================
    # 5. Volume Trend (10%) — symmetric (ปริมาณยืนยันได้ทั้ง 2 ทิศ)
    # ============================================================
    if vol_t is not None:
        # Volume สูง → ยืนยันทิศทางที่กำลังไป (ตามแรงหุ้น)
        # ต้องดูร่วมกับ pct (%change) ว่าวันนี้ขึ้นหรือลง
        if vol_t > 1.5:
            if pct > 0:   s, f = 8,  f'Volume {vol_t}x + ขึ้น (Buying pressure)'
            elif pct < 0: s, f = -8, f'Volume {vol_t}x + ลง (Selling pressure)'
            else:         s, f = 0,  f'Volume {vol_t}x (rotation)'
        elif vol_t > 1.0:
            if pct > 0:   s, f = 4,  f'Volume {vol_t}x + ขึ้น'
            elif pct < 0: s, f = -4, f'Volume {vol_t}x + ลง'
            else:         s, f = 0,  f'Volume {vol_t}x (balanced)'
        else:
            # Volume น้อย → ไม่มีน้ำหนัก
            s, f = 0, f'Volume {vol_t}x (weak conviction)'
        score += s
        factors.append({'name': f, 'score': s, 'weight': 10})

    # ============================================================
    # 6. Moving Average (10%) — symmetric
    # ============================================================
    if ma50 and ma200:
        if price > ma50 > ma200:   s, f = 10,  'Above MA50>MA200 (Uptrend ชัด)'
        elif price > ma50:          s, f = 5,   'Above MA50 (Short uptrend)'
        elif price > ma200:         s, f = 0,   'Above MA200, below MA50 (mixed)'
        elif price < ma50 < ma200:  s, f = -10, 'Below MA50<MA200 (Downtrend ชัด)'
        elif price < ma50:          s, f = -5,  'Below MA50 (Short downtrend)'
        else:                       s, f = 0,   'Mixed MA signals'
        score += s
        factors.append({'name': f, 'score': s, 'weight': 10})

    # ============================================================
    # 7. Bollinger Bands (10%) — symmetric mean-reversion + breakout
    # ============================================================
    if bb_u and bb_l and bb_u != bb_l:
        bb_pos = (price - bb_l) / (bb_u - bb_l)
        if bb_pos > 0.95:   s, f = -7, 'ติด BB Upper (Overbought - mean reversion)'
        elif bb_pos > 0.75: s, f = 5,  'BB Upper half (Bull momentum)'
        elif bb_pos > 0.55: s, f = 3,  'BB above middle (mild bull)'
        elif bb_pos > 0.45: s, f = 0,  'BB middle (neutral)'
        elif bb_pos > 0.25: s, f = -3, 'BB below middle (mild bear)'
        elif bb_pos > 0.05: s, f = -5, 'BB Lower half (Bear momentum)'
        else:               s, f = 7,  'ติด BB Lower (Oversold - bounce likely)'
        score += s
        factors.append({'name': f, 'score': s, 'weight': 10})

    # ============================================================
    # 8. Daily Change Momentum (10%) — symmetric
    # ============================================================
    if pct > 4:    s, f = 10, f'+{pct}% Strong gain'
    elif pct > 2:  s, f = 7,  f'+{pct}% Good gain'
    elif pct > 0.5: s, f = 4, f'+{pct}% Positive'
    elif pct > -0.5: s, f = 0, f'{pct}% Flat'
    elif pct > -2:  s, f = -4, f'{pct}% Negative'
    elif pct > -4:  s, f = -7, f'{pct}% Decline'
    else:           s, f = -10, f'{pct}% Sharp drop'
    score += s
    factors.append({'name': f, 'score': s, 'weight': 10})

    # ============================================================
    # 9. NEW: Trend Acceleration — ดูว่า momentum กำลังเร่ง/ชะลอ
    # ============================================================
    # ใช้ RSI + MACD hist เป็น proxy
    if rsi is not None and hist is not None:
        # Bullish acceleration: RSI > 55 AND MACD hist > 0.1
        if rsi >= 55 and hist > 0.1:
            s, f = 5, 'Bullish Acceleration (RSI+MACD เร่ง)'
            score += s
            factors.append({'name': f, 'score': s, 'weight': 5})
        # Bearish acceleration: RSI < 45 AND MACD hist < -0.1
        elif rsi <= 45 and hist < -0.1:
            s, f = -5, 'Bearish Acceleration (RSI+MACD ลง)'
            score += s
            factors.append({'name': f, 'score': s, 'weight': 5})

    # === SCORING ===
    confidence = max(0, min(100, 50 + score))

    # Direction thresholds (สมมาตรทั้ง 2 ฝั่ง)
    if score >= 30:    direction = 'STRONG_BUY'
    elif score >= 12:  direction = 'BUY'
    elif score >= -12: direction = 'HOLD'
    elif score >= -30: direction = 'SELL'
    else:              direction = 'STRONG_SELL'

    # ============================================================
    # SMART TARGET/SUPPORT — เลือกระดับ Fib ที่อยู่เหนือ/ใต้ราคาจริง
    # ============================================================
    # สร้าง list ของ levels เรียงจากสูง→ต่ำ
    levels_high_to_low = [
        ('EXT_1618', fibs.get('EXT_1618')),
        ('EXT_1236', fibs.get('EXT_1236')),
        ('0%',       fibs.get('0%')),
        ('23.6%',    fibs.get('23.6%')),
        ('38.2%',    fibs.get('38.2%')),
        ('50.0%',    fibs.get('50.0%')),
        ('61.8%',    fibs.get('61.8%')),
        ('78.6%',    fibs.get('78.6%')),
        ('100%',     fibs.get('100%')),
    ]
    # filter Nones
    levels_high_to_low = [(k, v) for k, v in levels_high_to_low if v is not None]

    # หา levels ที่อยู่เหนือ-ใต้ราคาปัจจุบัน
    above_price = [(k, v) for k, v in levels_high_to_low if v > price]
    below_price = [(k, v) for k, v in levels_high_to_low if v < price]

    # เรียง above (ใกล้ราคา → ไกล) และ below (ใกล้ราคา → ไกล)
    above_price.sort(key=lambda x: x[1])      # ascending → ใกล้ price ก่อน
    below_price.sort(key=lambda x: -x[1])     # descending → ใกล้ price ก่อน

    if direction in ['STRONG_BUY', 'BUY']:
        # ขึ้น → target คือ Fib level ถัดไปด้านบน
        target_level = above_price[0] if above_price else (None, round(price * 1.05, 2))
        # support ใกล้ที่สุดด้านล่าง
        support_level = below_price[0] if below_price else (None, round(price * 0.97, 2))
        # stop loss = ระดับถัดลง 1 ขั้น
        stop_level = below_price[1] if len(below_price) >= 2 else (None, round(price * 0.94, 2))
        target = target_level[1]
        support = support_level[1]
        stop_loss = stop_level[1]
    elif direction in ['STRONG_SELL', 'SELL']:
        # ลง → target คือ Fib level ถัดไปด้านล่าง
        target_level = below_price[0] if below_price else (None, round(price * 0.95, 2))
        # resistance/ดีดกลับใกล้ที่สุดด้านบน
        resist_level = above_price[0] if above_price else (None, round(price * 1.03, 2))
        # stop loss = ระดับถัดขึ้น 1 ขั้น
        stop_level = above_price[1] if len(above_price) >= 2 else (None, round(price * 1.06, 2))
        target = target_level[1]
        support = resist_level[1]      # field "support" ใช้แทน "ดีดกลับ" ใน SELL
        stop_loss = stop_level[1]
    else:
        # HOLD → กรอบบน-ล่างใกล้สุด
        target = above_price[0][1] if above_price else round(price * 1.03, 2)
        support = below_price[0][1] if below_price else round(price * 0.97, 2)
        stop_loss = below_price[1][1] if len(below_price) >= 2 else round(price * 0.94, 2)

    # ============================================================
    # DW RECOMMENDATION — สำคัญสำหรับการเล่น DW
    # ============================================================
    risk = abs(price - stop_loss)
    reward = abs(target - price)
    rr_ratio = round(reward / risk, 2) if risk > 0 else 0

    if direction in ['STRONG_BUY', 'BUY']:
        dw_type = 'CALL'
        dw_emoji = '🟢'
        if direction == 'STRONG_BUY' and confidence >= 70:
            dw_grade = 'A'
        elif confidence >= 60:
            dw_grade = 'B'
        else:
            dw_grade = 'C'
    elif direction in ['STRONG_SELL', 'SELL']:
        dw_type = 'PUT'
        dw_emoji = '🔴'
        if direction == 'STRONG_SELL' and confidence >= 70:
            dw_grade = 'A'
        elif confidence >= 60:
            dw_grade = 'B'
        else:
            dw_grade = 'C'
    else:
        dw_type = 'WAIT'
        dw_emoji = '⏸️'
        dw_grade = '-'

    return {
        'direction':   direction,
        'confidence':  confidence,
        'score':       score,
        'target':      target,
        'support':     support,
        'stop_loss':   stop_loss,
        'risk':        round(risk, 2),
        'reward':      round(reward, 2),
        'rr_ratio':    rr_ratio,
        'dw_type':     dw_type,
        'dw_emoji':    dw_emoji,
        'dw_grade':    dw_grade,
        'factors':     factors,
        'breakouts':   calc_breakout_probs(price, fibs, direction, confidence, data),
    }


def calc_breakout_probs(price, fibs, direction, confidence, data):
    """
    คำนวณ Success Probability ด้วยสูตรสมมาตรทั้ง 2 ฝั่ง:
    - BUY  → ทะลุแนวต้านขึ้น (Breakout up)
    - SELL → หลุดแนวรับลง (Breakdown) + ไม่ผ่านแนวต้าน (Rejection)
    - HOLD → ทั้งสองทิศทาง

    Formula (symmetric):
      base_prob = confidence
      - penalty by distance (4 pts per 1%)
      - penalty by rank (8 pts per slot)
      + bonuses from confirming factors (max ±10)
    """
    rsi  = data.get('rsi') or 50
    hist = data.get('macd_hist') or 0
    vol_t = data.get('vol_trend') or 1.0
    pct = data.get('pct') or 0
    bb_u = data.get('bb_upper')
    bb_l = data.get('bb_lower')
    ma50 = data.get('ma50')
    ma200 = data.get('ma200')
    atr = data.get('atr') or 0

    base = confidence

    # Bearish base = strength of bear signal (mirror of bull confidence)
    # ถ้า confidence = 0 แปลว่า bear แรง → base_bear ควรสูง
    base_bear = max(0, min(100, 100 - confidence))

    all_levels = [
        ('Fib EXT 161.8%', fibs.get('EXT_1618'), 'resist'),
        ('Fib EXT 123.6%', fibs.get('EXT_1236'), 'resist'),
        ('Fib 0% (High)',  fibs.get('0%'),       'resist'),
        ('Fib 23.6%',      fibs.get('23.6%'),    'resist'),
        ('Fib 38.2%',      fibs.get('38.2%'),    'resist'),
        ('Fib 50.0%',      fibs.get('50.0%'),    'pivot'),
        ('Fib 61.8%',      fibs.get('61.8%'),    'support'),
        ('Fib 78.6%',      fibs.get('78.6%'),    'support'),
        ('Fib 100% (Low)', fibs.get('100%'),     'support'),
    ]
    all_levels = [l for l in all_levels if l[1] is not None]

    breakouts = []

    # ============================================================
    # SHARED BONUS CALCULATION (symmetric)
    # ============================================================
    def calc_bull_bonus():
        """Bonuses ที่สนับสนุนการขึ้น"""
        bonus = 0
        if 55 <= rsi < 70: bonus += 5
        elif rsi >= 70:    bonus -= 8
        elif rsi < 40:     bonus -= 3
        if hist > 0.1:     bonus += 5
        elif hist > 0:     bonus += 2
        else:              bonus -= 4
        if vol_t > 1.5 and pct > 0: bonus += 8
        elif vol_t > 1.2 and pct > 0: bonus += 5
        elif vol_t < 0.8: bonus -= 4
        if pct > 2:        bonus += 5
        elif pct > 0:      bonus += 2
        elif pct < -1:     bonus -= 5
        if ma50 and ma200 and price > ma50 > ma200: bonus += 5
        elif ma50 and price < ma50: bonus -= 5
        if bb_u and bb_l and bb_u != bb_l:
            bb_pos = (price - bb_l) / (bb_u - bb_l)
            if bb_pos > 0.95: bonus -= 5
        return bonus

    def calc_bear_bonus():
        """Bonuses ที่สนับสนุนการลง"""
        bonus = 0
        if 30 < rsi <= 45: bonus += 5
        elif rsi <= 30:    bonus -= 8
        elif rsi > 60:     bonus -= 3
        if hist < -0.1:    bonus += 5
        elif hist < 0:     bonus += 2
        else:              bonus -= 4
        if vol_t > 1.5 and pct < 0: bonus += 8
        elif vol_t > 1.2 and pct < 0: bonus += 5
        elif vol_t < 0.8: bonus -= 4
        if pct < -2:       bonus += 5
        elif pct < 0:      bonus += 2
        elif pct > 1:      bonus -= 5
        if ma50 and ma200 and price < ma50 < ma200: bonus += 5
        elif ma50 and price > ma50: bonus -= 5
        if bb_u and bb_l and bb_u != bb_l:
            bb_pos = (price - bb_l) / (bb_u - bb_l)
            if bb_pos < 0.05: bonus -= 5
        return bonus

    bull_bonus = calc_bull_bonus()
    bear_bonus = calc_bear_bonus()

    # ============================================================
    # CALCULATE BOTH DIRECTIONS — แสดงทั้ง 2 ฝั่งเสมอ
    # เพราะ DW เทรดได้ทั้ง CALL + PUT
    # primary direction = ทิศหลักที่ระบบคาดการณ์
    # ============================================================
    primary_up = direction in ['STRONG_BUY', 'BUY']
    primary_dn = direction in ['STRONG_SELL', 'SELL']

    # ============================================================
    # ฝั่งขึ้น (CALL) — ทะลุแนวต้าน
    # ============================================================
    resistances = [l for l in all_levels if l[1] > price and l[1] < price * 1.15]
    resistances.sort(key=lambda x: x[1])

    # Base prob ตามทิศ
    if primary_up:
        base_call = base                # high confidence
    elif primary_dn:
        base_call = base_bear * 0.5     # ทิศตรงข้าม → โอกาสน้อย
    else:
        base_call = 50                  # HOLD → กลาง

    for i, (name, lv, ltype) in enumerate(resistances[:4]):
        distance_pct = ((lv - price) / price) * 100
        # Strong resistance = penalty
        resistance_strength = 0
        if 'High' in name or 'EXT' in name: resistance_strength = 5
        prob = base_call - (distance_pct * 4) - (i * 8) - resistance_strength + bull_bonus
        prob = max(5, min(95, round(prob)))

        breakouts.append({
            'level_name': name, 'level': round(lv, 2),
            'distance': round(lv - price, 2),
            'distance_pct': round(distance_pct, 2),
            'probability': prob,
            'type': 'breakout_up',
            'label': f'⬆️ ทะลุ {name}',
            'side': 'CALL',
            'is_primary': primary_up,
        })

    # ============================================================
    # ฝั่งลง (PUT) — หลุดแนวรับ + ชนแนวต้านเด้งลง
    # ============================================================
    if primary_dn:
        base_put = base_bear
    elif primary_up:
        base_put = base * 0.5           # ทิศตรงข้าม → โอกาสน้อย
    else:
        base_put = 50                   # HOLD → กลาง

    # PUT-1: BREAKDOWN (หลุดแนวรับ)
    supports = [l for l in all_levels if l[1] < price and l[1] > price * 0.85]
    supports.sort(key=lambda x: -x[1])

    for i, (name, lv, ltype) in enumerate(supports[:3]):
        distance_pct = ((price - lv) / price) * 100
        support_strength = 0
        if 'Low' in name or '100' in name: support_strength = 5
        elif '61.8' in name: support_strength = 3
        prob = base_put - (distance_pct * 4) - (i * 8) - support_strength + bear_bonus
        prob = max(5, min(95, round(prob)))

        breakouts.append({
            'level_name': name, 'level': round(lv, 2),
            'distance': round(price - lv, 2),
            'distance_pct': round(distance_pct, 2),
            'probability': prob,
            'type': 'breakdown',
            'label': f'⬇️ หลุด {name}',
            'side': 'PUT',
            'is_primary': primary_dn,
        })

    # PUT-2: REJECTION (ชนแนวต้านเด้งลง) — เฉพาะกรณี ทิศหลักคือ SELL หรือ HOLD
    # ในกรณี BUY ไม่ต้องแสดง rejection (เพราะคาดการณ์ว่าจะทะลุ)
    if not primary_up:
        resistances_near = [l for l in all_levels if l[1] > price and l[1] < price * 1.08]
        resistances_near.sort(key=lambda x: x[1])

        for i, (name, lv, ltype) in enumerate(resistances_near[:2]):
            distance_pct = ((lv - price) / price) * 100
            resistance_strength = 0
            if 'High' in name or 'EXT' in name: resistance_strength = 10
            elif '23.6' in name or '38.2' in name: resistance_strength = 5
            reject_prob = base_put - (distance_pct * 2) + resistance_strength + bear_bonus
            if bb_u and price > bb_u * 0.98: reject_prob += 8
            reject_prob = max(10, min(90, round(reject_prob)))

            breakouts.append({
                'level_name': name, 'level': round(lv, 2),
                'distance': round(lv - price, 2),
                'distance_pct': round(distance_pct, 2),
                'probability': reject_prob,
                'type': 'rejection',
                'label': f'🚫 ชน {name} เด้งลง',
                'side': 'PUT',
                'is_primary': primary_dn,
            })

    # เรียงตาม probability สูง → ต่ำ
    breakouts.sort(key=lambda x: -x['probability'])
    return breakouts


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

        # Volatility (สำคัญสำหรับ DW)
        atr = calc_atr(high_d, low_d, close)
        hv = calc_historical_vol(close)
        vol_cls = vol_class(hv)

        data = {
            'sym': sym, 'sector': SECTORS.get(sym, 'Other'),
            'price': price, 'prev': prev, 'pct': pct,
            'rsi': rsi, 'macd': macd, 'macd_sig': sig, 'macd_hist': hist,
            'ma50': ma50, 'ma200': ma200,
            'bb_upper': bb_u, 'bb_middle': bb_m, 'bb_lower': bb_l,
            'vol_trend': vol_t,
            'atr': atr, 'hist_vol': hv, 'vol_class': vol_cls,
            'fibs': fibs, 'fib_pos': fib_pos,
            'high_30d': round(h30, 2), 'low_30d': round(l30, 2),
        }
        pred = predict(data)
        data['prediction'] = pred
        return data

    except Exception as e:
        return None


def get_active_futures_ticker():
    """หา ticker ของ S50 Futures contract ที่ active"""
    today = datetime.now()
    month, year = today.month, today.year
    yr_code = str(year)[-2:]

    # ลอง near month + back month
    candidates = []
    for m_offset in range(0, 4):
        target_m = month + m_offset
        target_y = year
        if target_m > 12:
            target_m -= 12
            target_y += 1
        yr_c = str(target_y)[-2:]
        code = FUTURES_MONTH_CODES.get(target_m)
        if code:
            candidates.append(f'S50{code}{yr_c}')
            candidates.append(f'S50{code}{yr_c}.BK')

    return candidates


def analyze_set50_futures(stocks, spot_data=None):
    """
    SET50 Futures (S50) — สำหรับเล่น DW SET50 โดยเฉพาะ
    เพราะ DW SET50 อ้างอิงจาก Futures (ไม่ใช่ Spot ปกติ)

    คำนวณพิเศษ:
    - Futures Price + Basis (Futures - Spot)
    - Contango/Backwardation
    - Days to Expiry
    - Fair Value
    - Predict direction + breakthrough probability
    """
    spot_price = spot_data['price'] if spot_data else None

    # พยายามดึง Futures
    candidates = get_active_futures_ticker()
    fut_data = None
    used_tk = None

    for tk in candidates:
        try:
            df = yf.download(tk, period='3mo', interval='1d',
                             auto_adjust=True, progress=False)
            if not df.empty and len(df) > 10:
                fut_data = df
                used_tk = tk
                print(f'  ✅ S50 Futures from: {tk}')
                break
        except Exception:
            continue

    # ถ้าดึงไม่ได้ ใช้ค่าประมาณจาก Spot
    if fut_data is None:
        print('  ⚠️  S50 Futures unavailable — using Spot proxy')
        if spot_data is None:
            return None
        return build_synthetic_futures(spot_data, stocks)

    try:
        close = fut_data['Close'].squeeze()
        high  = fut_data['High'].squeeze()
        low   = fut_data['Low'].squeeze()
        vol   = fut_data['Volume'].squeeze() if 'Volume' in fut_data else None

        fut_price = round(float(close.iloc[-1]), 2)
        fut_prev  = round(float(close.iloc[-2]), 2)
        fut_pct   = round((fut_price - fut_prev) / fut_prev * 100, 2)

        # Basis = Futures - Spot
        if spot_price:
            basis = round(fut_price - spot_price, 2)
            basis_pct = round(basis / spot_price * 100, 2)
            structure = 'CONTANGO' if basis > 0 else 'BACKWARDATION' if basis < 0 else 'EQUAL'
        else:
            basis = None
            basis_pct = None
            structure = 'UNKNOWN'

        # Days to Expiry (ประมาณการ - Futures หมดอายุพุธสุดท้ายของเดือน)
        today = datetime.now()
        # หาวันพุธสุดท้ายของเดือนปัจจุบัน
        from calendar import monthrange
        last_day = monthrange(today.year, today.month)[1]
        last_wed = None
        for d in range(last_day, 0, -1):
            dt = datetime(today.year, today.month, d)
            if dt.weekday() == 2:  # 2 = Wednesday
                last_wed = dt
                break
        if last_wed and last_wed > today:
            days_to_exp = (last_wed - today).days
        else:
            # ใช้พุธสุดท้ายของเดือนถัดไป
            next_m = today.month + 1
            next_y = today.year
            if next_m > 12: next_m, next_y = 1, next_y + 1
            last_day = monthrange(next_y, next_m)[1]
            for d in range(last_day, 0, -1):
                dt = datetime(next_y, next_m, d)
                if dt.weekday() == 2:
                    last_wed = dt; break
            days_to_exp = (last_wed - today).days if last_wed else 30

        # Fair Value = Spot * (1 + (r - d) * t/365)
        # r = risk-free rate Thailand ~1.5%, d = dividend yield SET50 ~3%
        if spot_price:
            r, dyld = 0.015, 0.030
            t = days_to_exp / 365
            fair_value = round(spot_price * (1 + (r - dyld) * t), 2)
            fv_deviation = round(fut_price - fair_value, 2)
        else:
            fair_value = None
            fv_deviation = None

        # Technical Indicators
        rsi = calc_rsi(close)
        macd, sig, hist = calc_macd(close)
        ma20 = calc_ma(close, 20)
        bb_u, bb_m, bb_l = calc_bollinger(close)
        atr = calc_atr(high, low, close)
        hv = calc_historical_vol(close)
        vol_t = calc_volume_trend(vol) if vol is not None else None

        # Fibonacci (ใช้จาก Spot data เพื่อให้สอดคล้องกัน)
        h30 = float(high.tail(30).max())
        l30 = float(low.tail(30).min())
        fibs = fib_levels(h30, l30)
        fib_pos = fib_position(fut_price, fibs)

        data = {
            'sym': 'S50_FUTURES', 'sector': 'FUTURES', 'source': used_tk,
            'price': fut_price, 'prev': fut_prev, 'pct': fut_pct,
            'rsi': rsi, 'macd': macd, 'macd_sig': sig, 'macd_hist': hist,
            'ma50': ma20, 'ma200': None,
            'bb_upper': bb_u, 'bb_middle': bb_m, 'bb_lower': bb_l,
            'vol_trend': vol_t,
            'atr': atr, 'hist_vol': hv, 'vol_class': vol_class(hv),
            'fibs': fibs, 'fib_pos': fib_pos,
            'high_30d': round(h30, 2), 'low_30d': round(l30, 2),
            # FUTURES-SPECIFIC
            'spot_price': spot_price,
            'basis': basis,
            'basis_pct': basis_pct,
            'structure': structure,
            'days_to_exp': days_to_exp,
            'fair_value': fair_value,
            'fv_deviation': fv_deviation,
        }
        pred = predict(data)
        data['prediction'] = pred
        return data
    except Exception as e:
        print(f'S50 Futures error: {e}')
        return build_synthetic_futures(spot_data, stocks) if spot_data else None


def build_synthetic_futures(spot_data, stocks):
    """
    คำนวณ Futures price แบบประมาณการเมื่อดึงข้อมูลจริงไม่ได้
    Synthetic Futures = Spot + Basis (อ้างอิง fair value)
    """
    if not spot_data: return None

    spot = spot_data['price']
    today = datetime.now()
    from calendar import monthrange

    # หาวันหมดอายุ
    last_day = monthrange(today.year, today.month)[1]
    last_wed = None
    for d in range(last_day, 0, -1):
        dt = datetime(today.year, today.month, d)
        if dt.weekday() == 2:
            last_wed = dt; break
    if last_wed and last_wed > today:
        days_to_exp = (last_wed - today).days
    else:
        next_m = today.month + 1
        next_y = today.year
        if next_m > 12: next_m, next_y = 1, next_y + 1
        last_day = monthrange(next_y, next_m)[1]
        for d in range(last_day, 0, -1):
            dt = datetime(next_y, next_m, d)
            if dt.weekday() == 2:
                last_wed = dt; break
        days_to_exp = (last_wed - today).days if last_wed else 30

    r, dyld = 0.015, 0.030
    t = days_to_exp / 365
    fair_value = round(spot * (1 + (r - dyld) * t), 2)
    # ในไทย Futures มักเป็น Backwardation
    fut_price = fair_value

    basis = round(fut_price - spot, 2)
    basis_pct = round(basis / spot * 100, 2)

    data = dict(spot_data)
    data.update({
        'sym': 'S50_FUTURES',
        'sector': 'FUTURES',
        'source': 'synthetic_from_spot',
        'price': fut_price,
        'spot_price': spot,
        'basis': basis,
        'basis_pct': basis_pct,
        'structure': 'BACKWARDATION' if basis < 0 else 'CONTANGO',
        'days_to_exp': days_to_exp,
        'fair_value': fair_value,
        'fv_deviation': 0,
        'note': 'Computed from Spot + Cost of Carry (Yahoo Futures unavailable)'
    })
    pred = predict(data)
    data['prediction'] = pred
    return data



    """Analyze SET50 index — try Yahoo first, fallback to compute from constituents"""

    # Try multiple Yahoo Finance tickers for SET50
    tickers_to_try = ['^SET50.BK', '^SET50', 'SET50.BK', '^SETI']

    idx = None
    used_ticker = None
    for tk in tickers_to_try:
        try:
            test = yf.download(tk, period='1y', interval='1d',
                               auto_adjust=True, progress=False)
            if not test.empty and len(test) > 30:
                idx = test
                used_ticker = tk
                print(f'  ✅ SET50 index from: {tk}')
                break
        except Exception:
            continue

    # If still no data, compute "synthetic SET50" from constituents
    if idx is None and stocks:
        print('  ⚠️  Yahoo ticker not found → computing synthetic SET50 from 50 stocks')
        return synthesize_set50(stocks)

    if idx is None:
        return None

    try:
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

        fibs = fib_levels(SWING_HIGH, SWING_LOW)
        fib_pos = fib_position(price, fibs)

        data = {
            'sym': 'SET50', 'sector': 'INDEX', 'source': used_ticker,
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
        if stocks:
            return synthesize_set50(stocks)
        return None


def synthesize_set50(stocks):
    """
    Compute synthetic SET50 from constituent stocks
    ใช้เมื่อ Yahoo ดึง ^SET50 ไม่ได้
    """
    if not stocks: return None

    # คำนวณ avg %change (proxy ของ index movement)
    avg_pct = np.mean([s.get('pct', 0) for s in stocks])

    # Proxy values from constituents
    avg_rsi = np.mean([s['rsi'] for s in stocks if s.get('rsi')])
    avg_hist = np.mean([s.get('macd_hist', 0) for s in stocks])
    bull_ratio = sum(1 for s in stocks if s.get('macd_hist', 0) > 0) / len(stocks)

    # ใช้ราคา SET50 จาก SWING data + apply %change
    # หา price proxy: ตั้งสมมุติฐานว่า SET50 ปัจจุบันใกล้ SWING_HIGH * 97% (ปรับได้)
    # ดีกว่านั้น: ใช้ราคา SET50 ล่าสุดที่รู้จาก config (สามารถอัพเดทได้)
    estimated_price = round((SWING_HIGH + SWING_LOW) / 2 * (1 + avg_pct/100), 2)
    estimated_prev  = round(estimated_price / (1 + avg_pct/100), 2)

    fibs = fib_levels(SWING_HIGH, SWING_LOW)
    fib_pos = fib_position(estimated_price, fibs)

    data = {
        'sym': 'SET50', 'sector': 'INDEX', 'source': 'synthetic',
        'price': estimated_price, 'prev': estimated_prev, 'pct': round(avg_pct, 2),
        'rsi': round(avg_rsi, 1), 'macd': None,
        'macd_sig': None, 'macd_hist': round(avg_hist, 3),
        'ma50': None, 'ma200': None,
        'bb_upper': None, 'bb_middle': None, 'bb_lower': None,
        'vol_trend': None,
        'fibs': fibs, 'fib_pos': fib_pos,
        'swing_high': SWING_HIGH, 'swing_low': SWING_LOW,
        'note': 'Computed from 50 stocks (synthetic - Yahoo ^SET50 unavailable)'
    }
    pred = predict(data)
    data['prediction'] = pred
    return data


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

    # 50 stocks (ดึงก่อน เพื่อใช้ในการคำนวณ synthetic SET50 ถ้าจำเป็น)
    print(f'📋 Fetching {len(SET50)} stocks...')
    tickers = [s + '.BK' for s in SET50]
    raw = yf.download(tickers, period='6mo', interval='1d',
                      auto_adjust=True, progress=True, group_by='column')

    stocks = []
    for sym in SET50:
        d = analyze_ticker(sym, raw)
        if d: stocks.append(d)
    print(f'✅ Analyzed {len(stocks)}/{len(SET50)} stocks')

    # SET50 Index — ทำหลังหุ้น เพื่อใช้ fallback ได้
    print('📊 Analyzing SET50 Index...')
    set50 = analyze_set50_index(stocks)

    # SET50 Futures (S50) — สำหรับ DW SET50 โดยเฉพาะ
    print('📈 Analyzing S50 Futures (สำหรับ DW SET50)...')
    s50_futures = analyze_set50_futures(stocks, set50)

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
        's50_futures': s50_futures,
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
