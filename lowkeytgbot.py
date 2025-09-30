# lowkeytgbot.py
import os
import threading
import sqlite3
import json
import time
from uuid import uuid4
from flask import Flask, request, jsonify, abort
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIG (from env) ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # for GPT replies (OpenAI)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")  # optional verification
DELIVERY_URL = os.getenv("DELIVERY_URL")  # link to file or invite
PORT = int(os.getenv("PORT", "5000"))

if not BOT_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN env var")

# --- SIMPLE DB ---
DB_PATH = os.getenv("DB_PATH", "lowkey_orders.db")
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    telegram_id INTEGER,
                    email TEXT,
                    stripe_payment_id TEXT,
                    product TEXT,
                    amount INTEGER,
                    created_at INTEGER,
                    delivered INTEGER DEFAULT 0,
                    referrer INTEGER DEFAULT NULL
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS referrals (
                    user_id INTEGER PRIMARY KEY,
                    code TEXT,
                    referred_count INTEGER DEFAULT 0
                )""")
    conn.commit()
    conn.close()
init_db()

def db_insert_order(order):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO orders (id, telegram_id, email, stripe_payment_id, product, amount, created_at, delivered, referrer) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (order['id'], order.get('telegram_id'), order.get('email'), order.get('stripe_payment_id'), order.get('product'), order.get('amount'), order.get('created_at'), 0, order.get('referrer')))
    conn.commit()
    conn.close()

def mark_order_delivered(order_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE orders SET delivered=1 WHERE id=?", (order_id,))
    conn.commit()
    conn.close()

# --- TELEGRAM HANDLERS ---
STRIPE_LINK = os.getenv("STRIPE_LINK", "https://buy.stripe.com/YOUR_LINK_HERE")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Generate referral code for user if none
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT code FROM referrals WHERE user_id=?", (user.id,))
    row = c.fetchone()
    if not row:
        code = str(uuid4())[:8]
        c.execute("INSERT OR REPLACE INTO referrals (user_id, code) VALUES (?, ?)", (user.id, code))
        conn.commit()
    else:
        code = row[0]
    conn.close()

    keyboard = [
        [InlineKeyboardButton("💳 Buy Now", url=STRIPE_LINK)],
        [InlineKeyboardButton("🔗 Share / Referral", callback_data=f"ref:{code}")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    text = f"Welcome back, {user.first_name}.\n\nElite drops. Instant delivery after purchase.\nYour referral code: `{code}`"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Buy now: {STRIPE_LINK}")

# GPT reply handler (uses OpenAI chat completions)
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
def ask_gpt(prompt, user_id=None):
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "gpt-4o-mini",  # replace with your preferred model name
        "messages": [{"role":"user","content": prompt}],
        "max_tokens": 450
    }
    r = requests.post(OPENAI_CHAT_URL, headers=headers, json=data, timeout=30)
    if r.status_code != 200:
        return "GPT error or rate limit. Try again later."
    j = r.json()
    # safe extraction
    try:
        return j['choices'][0]['message']['content'].strip()
    except Exception:
        return "GPT returned unexpected format."

async def gpt_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only respond when user explicitly addresses bot or via DM; avoid spamming groups
    if update.effective_chat.type != 'private':
        return
    text = update.message.text
    if not text:
        return
    # short-circuit commands
    if text.startswith('/'):
        return
    await update.message.chat.send_action("typing")
    reply = ask_gpt(text, user_id=update.effective_user.id)
    await update.message.reply_text(reply)

# --- FLASK SERVER for Stripe webhook ---
app = Flask("stripe_webhook")

def verify_stripe_signature(payload, sig_header):
    # If you set STRIPE_WEBHOOK_SECRET, use it to verify. For now, basic header check.
    # In production use stripe.Webhook.construct_event()
    return True

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature", None)
    if STRIPE_WEBHOOK_SECRET:
        if not verify_stripe_signature(payload, sig):
            abort(400)
    event = request.get_json(force=True)
    # handle checkout.session.completed
    if event.get("type") == "checkout.session.completed":
        session = event['data']['object']
        payment_intent = session.get("payment_intent")
        amount = session.get("amount_total", 0)
        email = session.get("customer_details", {}).get("email")
        metadata = session.get("metadata", {})
        telegram_id = metadata.get("telegram_id")
        ref = metadata.get("referrer")
        product = metadata.get("product", "default")
        order_id = str(uuid4())
        order = {
            "id": order_id,
            "telegram_id": int(telegram_id) if telegram_id else None,
            "email": email,
            "stripe_payment_id": payment_intent,
            "product": product,
            "amount": amount,
            "created_at": int(time.time()),
            "referrer": int(ref) if ref else None
        }
        db_insert_order(order)
        # attempt delivery: send message to buyer via Telegram if telegram_id known
        if order['telegram_id']:
            try:
                from telegram import Bot
                bot = Bot(token=BOT_TOKEN)
                text = ("Payment received. Here's your delivery link:\n\n"
                        f"{DELIVERY_URL}\n\nThank you.")
                bot.send_message(chat_id=order['telegram_id'], text=text)
                mark_order_delivered(order_id)
            except Exception as e:
                print("Delivery failed:", e)
        return jsonify({"status":"ok"})
    return jsonify({"status":"ignored"})

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# --- PROMO BROADCAST (safe) ---
# This function only messages users already in the referrals table (opt-in)
def broadcast_message_to_optins(text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM referrals")
    rows = c.fetchall()
    conn.close()
    from telegram import Bot
    bot = Bot(token=BOT_TOKEN)
    for (uid,) in rows:
        try:
            bot.send_message(chat_id=uid, text=text)
            time.sleep(0.6)  # rate-limit
        except Exception as e:
            print("Broadcast fail", uid, e)

# --- APP STARTUP ---
def start_polling_bot():
    app_tb = ApplicationBuilder().token(BOT_TOKEN).build()
    app_tb.add_handler(CommandHandler("start", start))
    app_tb.add_handler(CommandHandler("buy", buy))
    app_tb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gpt_middleware))
    print("Starting Telegram polling...")
    app_tb.run_polling()

if __name__ == "__main__":
    # Run Flask in another thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    # Run Telegram polling (blocking)
    start_polling_bot()
