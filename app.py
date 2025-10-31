from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import os
import pandas as pd

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 🔹 จำเบอร์ของผู้ใช้แต่ละคน
user_last_number = {}

# ===== LOAD CSV FILES =====
total_df = pd.read_csv("data/total_meanings.csv")
pairs_df = pd.read_csv("data/pairs_color_map.csv")

pairs_df.columns = pairs_df.columns.str.strip()
pairs_df["pair"] = pairs_df["pair"].astype(str).str.zfill(2)
pairs_map = {r["pair"]: r.to_dict() for _, r in pairs_df.iterrows()}

# ===== HELPER FUNCTIONS =====
def calculate_total(phone_number: str):
    digits = [int(d) for d in phone_number if d.isdigit()]
    return sum(digits)

def find_meaning(total_sum: int):
    row = total_df[total_df["total"] == total_sum]
    if not row.empty:
        r = row.iloc[0]
        return f"{r['detail_meaning']}"
    return "ยังไม่มีคำทำนายสำหรับผลรวมนี้ในระบบ"

def check_bad_pairs(phone_number: str):
    """ตรวจคู่เลขเสีย (รองรับทั้ง 0/1 และ yes/no)"""
    bad_pairs = []
    digits = [d for d in phone_number if d.isdigit()]
    for i in range(len(digits) - 1):
        pair = f"{digits[i]}{digits[i+1]}"
        info = pairs_map.get(pair)
        if info:
            val = str(info.get("is_good")).strip().lower()
            if val in ["0", "false", "no"]:  # คู่เสีย
                bad_pairs.append(f"{pair} ({info.get('meaning', 'คู่เสีย')})")
    return bad_pairs

# ===== CALLBACK =====
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print("❌ Error:", e)
        abort(400)
    return "OK"

# ===== HANDLE MESSAGE =====
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id = event.source.user_id

    reply_text = ""

    # ✅ ตรวจมีคำว่า "มีคู่เสีย"
    if "มีคู่เสีย" in user_text:
        numbers = "".join([d for d in user_text if d.isdigit()])
        target_number = numbers or user_last_number.get(user_id)

        if not target_number:
            reply_text = "ยังไม่มีข้อมูลเบอร์ล่าสุดครับ กรุณาพิมพ์เบอร์ก่อน เช่น 0812345678"
        else:
            total_sum = calculate_total(target_number)
            meaning = find_meaning(total_sum)
            bad_pairs = check_bad_pairs(target_number)

            reply_text = (
                f"เบอร์: {target_number}\n"
                f"🧮 ผลรวม = {total_sum} → {meaning}\n\n"
            )

            if bad_pairs:
                reply_text += "💥 คู่เลขเสียที่พบ:\n" + "\n".join(bad_pairs)
            else:
                reply_text += "💫 ไม่มีคู่เลขเสียเลยครับ ✅"

    # ✅ ตรวจว่าพิมพ์เฉพาะเบอร์
    elif user_text.isdigit() and len(user_text) == 10:
        user_last_number[user_id] = user_text
        total_sum = calculate_total(user_text)
        meaning = find_meaning(total_sum)
        reply_text = (
            f"เบอร์: {user_text}\n"
            f"🧮 ผลรวม = {total_sum} → {meaning}"
        )

    else:
        reply_text = "กรุณาพิมพ์เฉพาะตัวเลข เช่น 0812345678 หรือถามว่า 'มีคู่เสียมั้ย'"

    # ✅ ส่งข้อความกลับ LINE
    with ApiClient(config) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

# ===== RUN LOCAL =====
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"🚀 Running on port {port} ...")
    app.run(host="0.0.0.0", port=port)