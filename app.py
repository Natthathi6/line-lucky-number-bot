import os
import pandas as pd
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.exceptions import InvalidSignatureError

# === Flask Setup ===
app = Flask(__name__)

# === LINE Config ===
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("❌ Missing LINE credentials. Please check environment variables.")

line_bot_api = MessagingApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# === CSV Loader (ป้องกัน error header และ encoding) ===
def load_csv_safely(path):
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="utf-8", dtype=str).fillna("")
    df.columns = df.columns.str.strip().str.lower()
    return df

# === Load data files ===
pairs_df = load_csv_safely("data/pairs_color_map.csv")
total_df = load_csv_safely("data/total_meanings.csv")

print("✅ CSV Files Loaded Successfully")
print("Pairs Columns:", pairs_df.columns.tolist())
print("Total Columns:", total_df.columns.tolist())

# === Validate Columns ===
if "pair" not in pairs_df.columns:
    raise ValueError(f"❌ CSV Error: Missing 'pair' column. Found {pairs_df.columns.tolist()}")
if "total" not in total_df.columns:
    raise ValueError(f"❌ CSV Error: Missing 'total' column. Found {total_df.columns.tolist()}")

# === Create Mappings ===
pairs_map = {str(r["pair"]).zfill(2): r.to_dict() for _, r in pairs_df.iterrows()}
totals_map = {str(r["total"]).zfill(2): r.to_dict() for _, r in total_df.iterrows()}


# === Flask route for LINE webhook ===
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


# === Handle Message ===
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip()

    if not user_text.isdigit():
        reply_text = "กรุณาพิมพ์เฉพาะตัวเลข เช่น 0812345678"
    else:
        number = user_text[-8:]  # ใช้แค่ 8 หลักท้าย
        pairs = [number[i:i+2] for i in range(0, len(number), 2)]

        results = []
        for p in pairs:
            info = pairs_map.get(p, {"meaning": "ไม่พบข้อมูล"})
            results.append(f"{p}: {info.get('meaning', '')}")

        total_sum = sum(int(p) for p in pairs) % 100
        total_info = totals_map.get(str(total_sum).zfill(2), {"meaning": "ไม่พบความหมายรวม"})

        reply_text = (
            f"🔢 เบอร์: {user_text}\n"
            f"🧮 ผลรวม = {total_sum} → {total_info.get('meaning', '')}"
        )

    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=reply_text)]
        )
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)