# 📊 SET50 Forecast · DW Decision Engine

ระบบทำนายแนวโน้ม SET50 + หุ้นรายตัว 50 ตัว สำหรับตัดสินใจซื้อ DW
รันอัตโนมัติด้วย GitHub Actions และแสดงผลผ่าน Web Dashboard บน GitHub Pages

## ⚡ Features

- **Multi-factor Prediction Model** — RSI + MACD + Fibonacci + MA + Bollinger + Volume + Momentum
- **Confidence Score 0-100%** — บอกความมั่นใจของสัญญาณ
- **เป้าหมายราคา + แนวรับ-ต้าน** อัตโนมัติ
- **DW Decision Box** — แนะนำ Call/Put พร้อม Stop Loss
- **อัพเดทอัตโนมัติ** ทุก 30 นาทีในช่วงตลาดเปิด
- **PWA** — ติดตั้งบนหน้าจอมือถือเหมือนแอป
- **Responsive** — ใช้ได้บนมือถือ iPad คอม

## 🚀 Setup (10 นาที)

### 1. สร้าง GitHub Repository
```
1. ไป github.com → New repository
2. ตั้งชื่อ "set50-forecast" (หรืออะไรก็ได้)
3. เลือก Public
4. กด Create
```

### 2. Upload Files
- ลาก-วางทุกไฟล์ในโฟลเดอร์นี้ขึ้น GitHub
- หรือใช้คำสั่ง git:
```bash
git init
git add .
git commit -m "Initial setup"
git remote add origin https://github.com/YOUR_USERNAME/set50-forecast.git
git push -u origin main
```

### 3. เปิด GitHub Pages
```
1. Repository → Settings → Pages
2. Source: Deploy from a branch
3. Branch: main → /docs
4. Save
5. รอ 1-2 นาที จะได้ URL: https://YOUR_USERNAME.github.io/set50-forecast
```

### 4. รัน First Update
```
1. Repository → Actions
2. เลือก "SET50 Forecast Auto-Update"
3. กด "Run workflow" → "Run workflow"
4. รอ 2-3 นาที
5. เปิด URL → เห็นข้อมูลจริง 🎉
```

## 📱 ติดตั้งบนมือถือ

### iPhone/iPad
```
Safari เปิด URL → กดปุ่มแชร์ → "Add to Home Screen"
```

### Android
```
Chrome เปิด URL → เมนู ⋮ → "Add to Home Screen"
```

จะได้ icon บนหน้าจอ เปิดเหมือนแอปจริง

## ⚙️ Schedule

- **ทุก 30 นาที** ในเวลาตลาด (10:00-17:00 จันทร์-ศุกร์)
- **สรุปวัน** 17:30 หลังตลาดปิด
- **Manual** กดปุ่ม Refresh ในเว็บ → trigger update

## 📐 Multi-Factor Model

| ปัจจัย | น้ำหนัก | คำอธิบาย |
|--------|---------|---------|
| RSI (14) | 15% | Overbought/Oversold |
| MACD Histogram | 15% | Momentum direction |
| Fibonacci Position | 15% | แนวรับ-ต้านสำคัญ |
| Moving Average | 10% | Trend filter |
| Bollinger Bands | 10% | Volatility position |
| Volume Trend | 10% | ยืนยัน signal |
| Momentum % | 10% | Daily change |
| (Sector, Fund Flow, etc.) | 15% | กำลังพัฒนา |

→ **Confidence Score 0-100%**

## 🎯 DW Decision Logic

```
STRONG_BUY / BUY  → พิจารณา DW Call (CALL)
HOLD              → รอสัญญาณชัดเจน
SELL / STRONG_SELL → พิจารณา DW Put (PUT)
```

## 📊 หุ้นใน SET50 ที่วิเคราะห์

ADVANC, AOT, BANPU, BBL, BDMS, BH, CBG, CCET, COM7, CPN, CPALL, CRC, CPF, DELTA, GPSC, GULF, IVL, KBANK, KKP, KTB, KTC, MINT, MTC, PTTEP, PTT, PTTGC, SCB, SCC, SCGP, TIDLOR, TISCO, TOP, TRUE, TTB, WHA, TU, TCAP, OSP, AWC, CENTEL, CK, GUNKUL, ERW, TLI, VGI, SAWAD, TQM, BTS, CPAXT, SPALI

## ⚠️ Disclaimer

ระบบนี้ใช้เพื่อการศึกษาเท่านั้น **ไม่ใช่คำแนะนำการลงทุน**
ผู้ลงทุนควรศึกษาและตัดสินใจเอง การลงทุนมีความเสี่ยง

## 📝 License

MIT License — ใช้ได้อย่างอิสระ

## 🎯 Radar — Strong Movers Detection (NEW)

ระบบจับหุ้นที่มี **โอกาสขึ้น/ลงแรง** สูงด้วย 5 มิติ:

| มิติ | น้ำหนัก | วัดอะไร |
|------|---------|--------|
| 🚀 Momentum | 30% | RSI + MACD + %change ความแรง |
| 📊 Volume | 20% | Volume vs ค่าเฉลี่ย 10 วัน |
| 📈 Trend | 20% | สอดคล้อง MA50/MA200 |
| 🎯 Setup | 20% | Fib position + Bollinger |
| 🔄 Market Sync | 10% | สอดคล้อง SET50 Index |

**Total Score 0-100** → กรองหุ้นที่:
- Radar ≥ 60
- Confidence ≥ 55%

**Success Probability** = 60% Radar + 40% Confidence
→ บอก "โอกาสสำเร็จ" ของการคาดการณ์

### ตัวอย่างการใช้กับ DW

- **Radar UP score 80+** → DW Call น่าเข้า
- **Radar DOWN score 80+** → DW Put น่าเข้า
- **Pentagon ขยายเต็ม** = สัญญาณแข็งทุกมิติ

## 🔬 Model V3 — Symmetric Bull/Bear Analysis (ใหม่!)

ปรับสูตรให้วิเคราะห์ขาขึ้น-ขาลงแม่นยำเท่ากัน

### ปัจจัยที่มี Symmetric Weight

| ปัจจัย | Bull max | Bear max |
|--------|---------:|---------:|
| RSI (มี zone Extreme OB / OS) | +10 | -12 |
| MACD Histogram (6 ระดับ) | +12 | -12 |
| MACD Cross Signal | +5 | -5 |
| Fibonacci Position | +12 | -12 |
| Volume + price direction | +8 | -8 |
| Moving Average | +10 | -10 |
| Bollinger Bands | +5/-7 | -5/+7 |
| Daily %change (7 ระดับ) | +10 | -10 |
| **Trend Acceleration** (ใหม่) | +5 | -5 |

### Breakout Probability — Symmetric Formula

```
For CALL (ทะลุขึ้น):     base = confidence
For PUT (หลุด/เด้งลง):  base = 100 - confidence
penalty: distance × 4 + rank × 8 + level_strength
bonus:   bull_bonus()  or  bear_bonus()  (mirror logic)
```

→ ผลลัพธ์: หุ้น Bull แรง 95% โอกาสทะลุ ↔ หุ้น Bear แรง 95% โอกาสหลุด

### Direction Thresholds (สมมาตร)

| Score | Direction |
|-------|-----------|
| ≥ +30 | 🟢 STRONG_BUY |
| ≥ +12 | 🟢 BUY |
| -12 ถึง +12 | 🟡 HOLD |
| ≤ -12 | 🔴 SELL |
| ≤ -30 | 🔴 STRONG_SELL |
