# 🚀 คู่มือ Setup แบบละเอียด (พร้อมรูป)

## ขั้นตอนทั้งหมด ~10 นาที

---

## ① สร้าง GitHub Account (ถ้ายังไม่มี)

ไป **[github.com](https://github.com)** → Sign up
- ฟรี 100%
- ใช้อีเมลส่วนตัว

---

## ② สร้าง Repository ใหม่

1. กดเครื่องหมาย **➕** ขวาบน → **New repository**
2. ตั้งค่า:
   - **Repository name**: `set50-forecast`
   - **Public** ✅
   - **Add a README** ❌ (ไม่ต้องติ๊ก)
3. กด **Create repository**

---

## ③ Upload ไฟล์

### วิธี A: ลากไฟล์ (ง่ายสุด)

1. ในหน้า Repository ที่ว่างเปล่า → กด **uploading an existing file**
2. ลากโฟลเดอร์ `set50-forecast` ทั้งโฟลเดอร์เข้าไป
3. รอ upload เสร็จ
4. ใส่ commit message: `Initial setup`
5. กด **Commit changes**

### วิธี B: ใช้ Git CLI

```bash
cd set50-forecast
git init
git add .
git commit -m "Initial setup"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/set50-forecast.git
git push -u origin main
```

---

## ④ เปิด GitHub Pages

1. Repository → **Settings** (มุมขวาบน)
2. เมนูซ้าย → **Pages**
3. Source: **Deploy from a branch**
4. Branch:
   - เลือก `main`
   - เลือก `/docs`
5. กด **Save**
6. รอ 1-2 นาที จะได้ URL:
   ```
   https://YOUR_USERNAME.github.io/set50-forecast
   ```

---

## ⑤ รัน First Update

ตอนนี้เว็บเปิดได้แล้ว แต่ข้อมูลยังเป็น sample

1. Repository → tab **Actions**
2. ถ้ามีแจ้งเตือน → กด **I understand my workflows, go ahead and enable them**
3. ซ้ายมือ เลือก **SET50 Forecast Auto-Update**
4. ขวามือ กด **Run workflow** → **Run workflow** (ปุ่มเขียว)
5. รอ 2-3 นาที จะเห็น ✅ สีเขียว
6. รีโหลดเว็บ → เห็นข้อมูลจริง 🎉

---

## ⑥ ติดตั้งบนมือถือ

### iPhone/iPad
```
1. เปิด Safari (ไม่ใช่ Chrome)
2. ไปที่ URL ของคุณ
3. กดปุ่มแชร์ ⬆️ (ด้านล่าง)
4. เลื่อนลง → "เพิ่มลงในหน้าจอหลัก"
5. กด "เพิ่ม"
```

### Android
```
1. เปิด Chrome
2. ไปที่ URL ของคุณ
3. เมนู ⋮ (มุมขวาบน)
4. "เพิ่มลงในหน้าจอหลัก"
5. กด "เพิ่ม"
```

ได้ icon บนหน้าจอ → กดเปิดเหมือนแอปจริง

---

## ⑦ ตั้งเวลา Auto-Update

ระบบจะรันอัตโนมัติ:
- **ทุก 30 นาที** เวลา 10:00-17:00 BKK (จันทร์-ศุกร์)
- **17:30 BKK** สรุปประจำวัน

ไม่ต้องทำอะไร → ระบบทำงานเองตลอด

---

## 🔧 Troubleshooting

### ❌ Web เปิดไม่เห็นข้อมูล
→ ตรวจสอบว่ารัน workflow แล้ว ในขั้นตอน ⑤

### ❌ Workflow ขึ้น Error
→ ไปที่ Actions → คลิก run ที่ Error → ดู log
- ส่วนใหญ่เกิดจาก Yahoo Finance ล่ม → รอ 5 นาที แล้วรันใหม่

### ❌ ข้อมูลไม่อัพเดท
→ กด Refresh ในเว็บ
→ หรือไป Actions → Run workflow ด้วยมือ

### ❌ GitHub Pages ยังไม่ขึ้น
→ รอ 5 นาทีหลังตั้งค่า
→ ตรวจสอบว่าเลือก folder `/docs` แล้ว

---

## 📝 Custom เพิ่มเติม

### เพิ่ม/ลด หุ้น
แก้ไฟล์ `scripts/engine.py` → ตัวแปร `SET50`

### ปรับ Schedule
แก้ไฟล์ `.github/workflows/forecast.yml` → ส่วน `cron`

### เปลี่ยน Swing Fibonacci
แก้ไฟล์ `scripts/engine.py` → `SWING_HIGH`, `SWING_LOW`

---

## 🎉 พร้อมใช้!

URL ของคุณคือ: `https://YOUR_USERNAME.github.io/set50-forecast`

- เปิดได้ทุกที่ที่มีเน็ต
- ข้อมูลอัพเดทอัตโนมัติ
- ดู Multi-factor + Confidence + DW Recommendation
- กดเข้าหุ้นแต่ละตัวดูรายละเอียดได้

Happy Trading! 📊🚀
