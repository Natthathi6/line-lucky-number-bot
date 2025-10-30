import os
import pandas as pd
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    MessagingApi,
    ApiClient,
    Configuration,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.exceptions import InvalidSignatureError

app = Flask(__name__)

# === LINE Configuration ===
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# === Load CSVs ===
def load_csv(path):
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    df.columns = df.columns.str.strip().str.lower()
    return df

pairs_df = load_csv("data/pairs_color_map.csv")
total_df = load_csv("data/total_meanings.csv")

pairs_map = {str(r["pair"]).zfill(2): r.to_dict() for _, r in pairs_df.iterrows()}
totals_map = {str(r["total"]).zfill(2): r.to_dict() for _, r in total_df.iterrows()}

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text.strip()

    # === ตรวจว่าเป็นข้อความแบบ "เบอร์ มีคู่เสียมั้ย" หรือไม่ ===
    if any(x in text for x in ["มีคู่เสีย", "คู่เสียมี", "คู่เสียมั้ย", "มีคู่เสียไหม"]):
        # แยกเฉพาะตัวเลขจากข้อความ
        digits = [int(ch) for ch in text if ch.isdigit()]
        if not digits:
            reply = "กรุณาพิมพ์รูปแบบเช่น 0812345678 มีคู่เสียมั้ย"
        else:
            total_sum = sum(digits)
            total_key = str(total_sum).zfill(2)
            total_info = totals_map.get(total_key, {"meaning": "ไม่พบความหมายรวม", "detail_meaning": ""})

            bad_list = []
            for i in range(len(digits) - 1):
                pair = f"{digits[i]}{digits[i+1]}"
                info = pairs_map.get(pair)
                if info and info.get("is_good") == "no":
                    bad_list.append(f"{pair} ({info['meaning']})")

            bad_pairs = "\n".join(bad_list) if bad_list else "ไม่มีคู่เลขเสียเลยครับ ✅"

            reply = (
                f"เบอร์: {''.join(str(d) for d in digits)}\n"
                f"🧮 ผลรวม = {total_sum} → {total_info.get('meaning','')}\n"
                f"{total_info.get('detail_meaning','')}\n\n"
                f"💥 คู่เลขเสียที่พบ:\n{bad_pairs}"
            )

    else:
        # === กรณีผู้ใช้พิมพ์แค่เบอร์ ===
        digits = [int(ch) for ch in text if ch.isdigit()]
        if not digits:
            reply = "กรุณาพิมพ์เฉพาะตัวเลข เช่น 0812345678"
        else:
            total_sum = sum(digits)
            total_key = str(total_sum).zfill(2)
            total_info = totals_map.get(total_key, {"meaning": "ไม่พบความหมายรวม", "detail_meaning": ""})
            reply = (
                f"เบอร์: {''.join(str(d) for d in digits)}\n"
                f"🧮 ผลรวม = {total_sum} → {total_info.get('meaning','')}\n"
                f"{total_info.get('detail_meaning','')}"
            )

    # === ส่งข้อความกลับ ===
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=reply)]
        )
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)