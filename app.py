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

# === Flask setup ===
app = Flask(__name__)

# === LINE configuration ===
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("❌ Missing LINE credentials. Please check Render Environment Variables.")

# ✅ LINE SDK v3 setup
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


# === Safe CSV loader ===
def load_csv_safely(path):
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="utf-8", dtype=str).fillna("")
    df.columns = df.columns.str.strip().str.lower()
    return df


# === Load data ===
pairs_df = load_csv_safely("data/pairs_color_map.csv")
total_df = load_csv_safely("data/total_meanings.csv")

print("✅ CSV Files Loaded Successfully")
print("Pairs Columns:", pairs_df.columns.tolist())
print("Total Columns:", total_df.columns.tolist())

# === Mapping ===
pairs_map = {str(r["pair"]).zfill(2): r.to_dict() for _, r in pairs_df.iterrows()}
totals_map = {str(r["total"]).zfill(2): r.to_dict() for _, r in total_df.iterrows()}


# === Webhook endpoint ===
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


# === Handle Message Event ===
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip()
    digits = [int(ch) for ch in user_text if ch.isdigit()]

    if not digits:
        reply_text = "กรุณาพิมพ์เฉพาะตัวเลข เช่น 0812345678"
    else:
        # ✅ คำนวณผลรวมจากทุกหลัก
        total_sum = sum(digits)
        key = str(total_sum).zfill(2)

        total_info = totals_map.get(
            key,
            {"meaning": "ไม่พบความหมายรวม", "detail_meaning": ""}
        )

        reply_text = (
            f"🔢 เบอร์: {''.join(str(d) for d in digits)}\n"
            f"🧮 ผลรวม = {total_sum} → {total_info.get('meaning', '')}\n\n"
            f"{total_info.get('detail_meaning', '')}"
        )

    # ✅ ส่งข้อความตอบกลับ
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=reply_text)]
        )
    )


# === Run app ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)