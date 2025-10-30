from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import pandas as pd
import os

# === Flask app ===
app = Flask(__name__)

# === โหลดค่าจาก Environment (Render) ===
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise Exception("❌ Missing LINE channel credentials. Please check environment variables.")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# === โหลดข้อมูลคู่เลขและความหมายผลรวม ===
pairs_df = pd.read_csv("data/pairs_color_map.csv", dtype=str).fillna("")
total_df = pd.read_csv("data/total_meanings.csv", dtype=str).fillna("")

# แปลงเป็น dictionary
pairs_map = {str(r["pair"]).zfill(2): r.to_dict() for _, r in pairs_df.iterrows()}
total_map = {str(r["total"]).zfill(2): r.to_dict() for _, r in total_df.iterrows()}

# === ฟังก์ชันวิเคราะห์เบอร์ ===
def analyze_number(number):
    # เอาเฉพาะตัวเลข
    number = ''.join(filter(str.isdigit, number))
    if len(number) < 6:
        return {"error": "⚠️ กรุณากรอกเบอร์ให้ครบ เช่น 0812345678"}

    # คำนวณผลรวม
    digits = [int(ch) for ch in number]
    total = sum(digits)
    total_str = str(total)

    # ดึงความหมายผลรวม
    meaning_info = total_map.get(total_str, None)
    if meaning_info:
        meaning = meaning_info.get("meaning", "")
        detail = meaning_info.get("detail_meaning", "")
    else:
        meaning = "ไม่พบความหมายผลรวมนี้ในฐานข้อมูล"
        detail = ""

    # ตรวจหาคู่เลขเสีย
    check_part = number[-7:]  # ใช้เฉพาะ 7 หลักสุดท้าย
    pairs = [check_part[i:i+2] for i in range(len(check_part) - 1)]
    bad_pairs = [p for p in pairs if p in pairs_map and pairs_map[p].get("is_good") == "0"]

    # สร้างข้อความตอบกลับ
    reply_text = f"🔢 เบอร์: {number}\n🧮 ผลรวม = {total} → {meaning}"
    if detail:
        reply_text += f"\n     {detail}"

    if bad_pairs:
        reply_text += f"\n⚠️ พบคู่เสีย: {', '.join(bad_pairs)}"
    else:
        reply_text += f"\n✅ ไม่พบคู่เสียในเบอร์นี้"

    return {"reply": reply_text}


# === ROUTES ===

@app.route("/")
def home():
    return "Lucky Number Bot พร้อมใช้งาน!"

@app.route("/callback", methods=['POST'])
def callback():
    # รับ Header จาก LINE
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    # ตรวจสอบลายเซ็น
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


# === จัดการข้อความจากผู้ใช้ ===
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()

    # ถามเรื่องคู่เสีย
    if user_text in ["มีคู่เสียมั้ย", "เช็กคู่เสีย", "ดูคู่เสีย"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="⚙️ กรุณาพิมพ์เบอร์อีกครั้ง เพื่อวิเคราะห์คู่เสีย")
        )
        return

    # วิเคราะห์เบอร์
    result = analyze_number(user_text)
    if "error" in result:
        reply_text = result["error"]
    else:
        reply_text = result["reply"]

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))


# === รันเซิร์ฟเวอร์ (สำหรับ Render) ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)