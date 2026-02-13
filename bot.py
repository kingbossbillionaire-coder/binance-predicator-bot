import os
from flask import Flask
from threading import Thread
import telebot
import requests
import pandas as pd
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from apscheduler.schedulers.background import BackgroundScheduler

# --- RENDER HEALTH CHECK SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot is alive! | Render Health Check OK"

def run():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# Start Flask server in background thread BEFORE bot polling
Thread(target=run, daemon=True).start()

# --- TELEGRAM BOT SETUP ---
TOKEN = os.environ.get('BOT_TOKEN')  # ⚠️ MUST match env var name on Render!
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN environment variable not set!")

bot = telebot.TeleBot(TOKEN)

# Lists for the Bot
TOP_COINS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'TRX', 'LINK', 'SUI']
user_alerts = {}  # For price alerts

# --- BINANCE RSI LOGIC (FIXED URL: REMOVED EXTRA SPACES!) ---
def get_prediction(symbol):
    try:
        # 🔥 CRITICAL FIX: Removed spaces after "symbol=" → was "symbol=  {symbol}" (INVALID)
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval=1h&limit=100"
        data = requests.get(url, timeout=10).json()
        if not data or 'code' in data:  # Handle Binance errors
            return f"❌ Invalid symbol: {symbol}"
        
        df = pd.DataFrame(data, columns=['time','open','high','low','close','vol','ct','qv','nt','tb','tq','i'])
        close = df['close'].astype(float)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        if rsi < 35:
            return f"🟢 {symbol} is OVERSOLD (RSI: {rsi:.1f}). Expect a PUMP!"
        if rsi > 65:
            return f"🔴 {symbol} is OVERBOUGHT (RSI: {rsi:.1f}). Expect a DUMP!"
        return f"🟡 {symbol} is NEUTRAL (RSI: {rsi:.1f}). No clear move."
    except Exception as e:
        return f"❌ Error analyzing {symbol}: {str(e)[:50]}"

# --- AUTO ALERT TASK ---
def check_prices():
    for chat_id, alerts in list(user_alerts.items()):
        for alert in alerts[:]:
            try:
                # 🔥 CRITICAL FIX: Removed spaces after "symbol=" → was "symbol=  {coin}"
                res = requests.get(
                    f"https://api.binance.com/api/v3/ticker/price?symbol={alert['coin']}USDT",
                    timeout=5
                ).json()
                curr_p = float(res['price'])
                if curr_p >= alert['target']:
                    bot.send_message(
                        chat_id,
                        f"🔔 **ALERT TRIGGERED**\n{alert['coin']} reached ${curr_p:,.2f} (target: ${alert['target']:,.2f})",
                        parse_mode="Markdown"
                    )
                    alerts.remove(alert)
            except Exception as e:
                print(f"Alert check error for {alert}: {e}")
                continue

scheduler = BackgroundScheduler()
scheduler.add_job(check_prices, 'interval', minutes=5)
scheduler.start()

# --- BOT COMMANDS ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup(row_width=2)
    btns = [InlineKeyboardButton(c, callback_data=f"p_{c}") for c in TOP_COINS[:6]]
    markup.add(*btns)
    markup.add(InlineKeyboardButton("🌟 VIP SIGNAL (50 Stars)", callback_data="buy_vip"))
    
    bot.send_message(
        message.chat.id,
        "🚀 **Binance AI Predictor**\n\nSelect a coin for RSI signal or use:\n`/setalert BTC 105000`",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if call.data.startswith("p_"):
        coin = call.data.split("_")[1]
        bot.answer_callback_query(call.id, "🧠 Analyzing RSI...")
        bot.send_message(call.message.chat.id, get_prediction(coin))
    elif call.data == "buy_vip":
        try:
            bot.send_invoice(
                call.message.chat.id,
                title="VIP Alpha Signal",
                description="High-accuracy trading signal",
                payload="vip_payload",
                provider_token="",  # Telegram Stars requires empty string
                currency="XTR",
                prices=[LabeledPrice("VIP Signal", 50)]
            )
        except Exception as e:
            bot.answer_callback_query(call.id, f"⚠️ Payment unavailable: {str(e)[:30]}")

@bot.message_handler(commands=['setalert'])
def set_alert(message):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            raise ValueError()
        _, coin, price = parts
        cid = message.chat.id
        if cid not in user_alerts:
            user_alerts[cid] = []
        user_alerts[cid].append({'coin': coin.upper(), 'target': float(price)})
        bot.reply_to(message, f"✅ Alert set!\n{coin.upper()} → ${float(price):,.2f}")
    except:
        bot.reply_to(message, "❌ Usage: `/setalert BTC 100000`", parse_mode="Markdown")

# --- PAYMENT HANDLERS (Telegram Stars) ---
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def pay_ok(message):
    bot.send_message(
        message.chat.id,
        "💎 **VIP SIGNAL UNLOCKED**\n\n🎯 SOL/USDT Target: $350\n⏰ Valid for next 24h\n\n*Trade responsibly!*",
        parse_mode="Markdown"
    )

# --- START BOT ---
print(f"✅ Bot starting with token ending in: ...{TOKEN[-6:]}")
print(f"🌐 Render health check server running on port {os.environ.get('PORT', 10000)}")
bot.infinity_polling()
