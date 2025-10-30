import re
import pandas as pd
from flask import Flask, jsonify, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv
import os

app = Flask(__name__)

# โหลด .env
load_dotenv()
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# โหลดข้อมูล
pairs_df = pd.read_csv("data/pairs_color_map.csv", dtype=str).fillna("")
pairs_map = {str(r.pair): r for _, r in pairs_df.iterrows()}
total_df = pd.read_csv("data/total_meanings.csv", dtype={"total": int}).fillna("")

# state สำหรับจำเบอร์แต่ละ user
last_result = {}

# ---------- ฟังก์ชันคำนวณ ----------
def calc_double_total(number):
    digits = [int(d) for d in re.findall(r"\d", number)]
    return sum(digits)

def calc_single_total(total):
    while total > 9:
        total = sum(int(d) for d in str(total))
    return total

def sliding_pairs(number):
    digits = re.findall(r"\d", number)
    return [digits[i] + digits[i+1] for i in range(len(digits)-1)]

def analyze_number(number):
    digits = re.findall(r"\d", number)
    if len(digits) < 6:
        return {"error": "กรุณาใส่เบอร์โทรอย่างน้อย 6 หลัก"}

    pairs = sliding_pairs(number)
    total = calc_double_total(number)
    single = calc_single_total(total)

    row = total_df[total_df["total"] == total]
    meaning = row.iloc[0]["meaning"] if not row.empty else "ไม่มีข้อมูล"
    detail = row.iloc[0].get("detail_meaning", "") if not row.empty else ""
    bad_pairs = [p for p in pairs if p in pairs_map and pairs_map[p].is_good == "0"]

    return {
        "digits": "".join(digits),
        "total": total,
        "single": single,
        "meaning": meaning,
        "detail": detail,
        "bad_pairs": bad_pairs
    }

# ---------- LINE Webhook ----------
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    return "OK", 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()

    if any(ch.isdigit() for ch in user_text):
        result = analyze_number(user_text)
        reply = (
            f"🔢 เบอร์: {result['digits']}\n"
            f"🧮 ผลรวม = {result['total']} → {result['meaning']}\n"
            f"     {result['detail']}"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        last_result[event.source.user_id] = result
        return

    if "คู่เสีย" in user_text:
        data = last_result.get(event.source.user_id)
        if not data:
            reply = "กรุณาพิมพ์เบอร์ก่อนครับ เช่น 0812345678"
        elif data["bad_pairs"]:
            reply = f"พบคู่เสีย: {', '.join(data['bad_pairs'])}"
        else:
            reply = "ไม่พบคู่เสียในเบอร์นี้"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    reply = "พิมพ์เบอร์โทรเพื่อดูผลรวมได้เลยครับ เช่น 0812345678"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

@app.route("/")
def home():
    return "Lucky Number Bot พร้อมใช้งาน!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)