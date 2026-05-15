# 🔧 Troubleshooting — แก้ปัญหาที่พบบ่อย

## ❓ ปัญหา: "SET50 Index data unavailable"

**สาเหตุ:** Yahoo Finance ไม่มี ticker `^SET50` สำหรับตลาดไทย

**แก้ไข (v2 แก้แล้ว):** ระบบจะลอง 4 ticker ตามลำดับ:
1. `^SET50.BK`
2. `^SET50`
3. `SET50.BK`
4. `^SETI`

ถ้ายังไม่ได้ → คำนวณ **Synthetic SET50** จาก 50 หุ้นแทน (ค่าเฉลี่ย %change, RSI)

จะมีข้อความเตือนสีเหลือง: *"⚠️ ข้อมูล SET50 คำนวณจากค่าเฉลี่ย 50 หุ้น"*

---

## ❓ ปัญหา: Target ต่ำกว่าราคาปัจจุบัน (เช่น หุ้น 46 บาท → target 43)

**สาเหตุ:** Fibonacci คำนวณจาก Swing 30 วัน อาจอยู่ใต้ราคา

**แก้ไข (v2 แก้แล้ว):** ระบบจะหา Fib level ที่อยู่ **เหนือ/ใต้ราคาจริง** เท่านั้น:

- **BUY** → target คือ Fib level ถัดไป**เหนือ**ราคา
- **SELL** → target คือ Fib level ถัดไป**ใต้**ราคา
- ถ้าราคาทะลุ Fib หมดแล้ว → ใช้ Extension 123.6% / 161.8%

---

## ❓ ปัญหา: ไม่รู้ว่าควรเข้า DW Call หรือ Put

**v2 มี DW Decision Box แล้ว:**

| Grade | ความหมาย |
|-------|----------|
| 🟢 **A** | STRONG signal + Confidence ≥ 70% — มั่นใจสูง |
| 🟡 **B** | Signal ปกติ + Confidence ≥ 60% — พอใช้ |
| 🟠 **C** | Signal อ่อน — ระมัดระวัง |
| ⏸️ **Wait** | สัญญาณไม่ชัด — รอ |

แสดง:
- **DW CALL/PUT** ตามทิศทาง
- **Target / Stop Loss** ในระดับ Fib
- **R:R Ratio** (Risk : Reward)
- **Volatility (HV)** — บอกว่า DW เคลื่อนเร็ว/ช้า

---

## ❓ ปัญหา: Volatility คืออะไร สำคัญยังไงกับ DW?

**Historical Volatility (HV)** = ความผันผวนของหุ้น (% ต่อปี)

| HV | ระดับ | ผลกับ DW |
|----|------|---------|
| < 30% | LOW | DW เคลื่อนช้า ต้องถือนาน |
| 30-50% | MEDIUM | **เหมาะสม** ⭐ |
| > 50% | HIGH | DW เคลื่อนเร็ว แต่เสี่ยงสูง |

---

## ❓ ปัญหา: GitHub Actions ขึ้น Error สีแดง

**ทำแบบนี้:**
1. ไป Repository → Actions tab
2. คลิก workflow ที่ error
3. คลิก job → ดู log
4. ถ้า error เกี่ยวกับ Yahoo Finance → รอ 5 นาทีแล้ว Run ใหม่
5. ถ้า error อื่น → screenshot ส่งให้ผมดู

**คำสั่ง Re-run:**
- Actions → คลิก run ที่ error → ปุ่ม **"Re-run all jobs"** ขวาบน

---

## ❓ ปัญหา: เปิดเว็บแล้วเห็นแต่ Sample Data

**สาเหตุ:** ยังไม่ได้รัน Workflow ครั้งแรก

**แก้ไข:**
1. ไป Actions → SET50 Forecast Auto-Update
2. กด **Run workflow** → **Run workflow**
3. รอ 2-3 นาที
4. Refresh หน้าเว็บ

---

## ❓ ปัญหา: เพิ่ม/ลดหุ้น

**แก้ไฟล์ `scripts/engine.py`:**

```python
SET50 = [
    'ADVANC','AOT', ...   # ใส่/ลบหุ้นตรงนี้
]

# ถ้าหุ้นไม่อยู่ในกลุ่มไหน เพิ่มที่นี่
SECTORS = {
    'YOUR_STOCK': 'Sector_Name',
}
```

แล้ว Commit → Workflow จะ trigger อัตโนมัติ

---

## ❓ ปัญหา: อยากเปลี่ยน Swing High/Low สำหรับ Fibonacci

**แก้ใน `scripts/engine.py`:**

```python
SWING_HIGH = 1032.59    # ← อัพเดทตามจุดสูงล่าสุด
SWING_LOW  = 957.00     # ← อัพเดทตามจุดต่ำล่าสุด
```

แล้ว Commit changes

---

## ❓ ปัญหา: อยากให้รันบ่อยกว่า 30 นาที

**แก้ใน `.github/workflows/forecast.yml`:**

```yaml
schedule:
  # ปัจจุบัน: ทุก 30 นาที
  - cron: '*/30 3-10 * * 1-5'

  # อยากให้ทุก 15 นาที:
  - cron: '*/15 3-10 * * 1-5'

  # อยากให้ทุก 10 นาที:
  - cron: '*/10 3-10 * * 1-5'
```

⚠️ **ข้อจำกัด GitHub Free:** มี 2000 นาที/เดือน
- ทุก 30 นาที = ~200 นาที/เดือน ✅ ปลอดภัย
- ทุก 15 นาที = ~400 นาที/เดือน ✅ พอ
- ทุก 5 นาที = ~1200 นาที/เดือน ⚠️ ใกล้ limit

---

## ✉️ ติดต่อ

มีปัญหา? Screenshot + บอกขั้นตอนที่ทำ → ผมช่วยแก้ให้ครับ
