import telebot
import requests
import os
import pandas as pd
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from apscheduler.schedulers.background import BackgroundScheduler

# --- CONFIGURATION ---
TOKEN = os.getenv('BOT_TOKEN') # We will set this in Koyeb later
bot = telebot.TeleBot(TOKEN)

# Lists for the Bot
TOP_COINS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'TRX', 'LINK', 'SUI']
user_alerts = {} # For price alerts

# --- LOGIC: BINANCE RSI ---
def get_prediction(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval=1h&limit=100"
        data = requests.get(url).json()
        df = pd.DataFrame(data, columns=['time','open','high','low','close','vol','ct','qv','nt','tb','tq','i'])
        close = df['close'].astype(float)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        if rsi < 35: return f"🟢 {symbol} is OVERSOLD (RSI: {rsi:.1f}). Expect a PUMP!"
        if rsi > 65: return f"🔴 {symbol} is OVERBOUGHT (RSI: {rsi:.1f}). Expect a DUMP!"
        return f"🟡 {symbol} is NEUTRAL (RSI: {rsi:.1f}). No clear move."
    except: return "❌ Coin error."

# --- AUTO ALERT TASK ---
def check_prices():
    for chat_id, alerts in list(user_alerts.items()):
        for alert in alerts[:]:
            try:
                res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={alert['coin']}USDT").json()
                curr_p = float(res['price'])
                if curr_p >= alert['target']:
                    bot.send_message(chat_id, f"🔔 **ALERT:** {alert['coin']} reached ${curr_p:,.2f}!")
                    alerts.remove(alert)
            except: continue

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
    
    bot.send_message(message.chat.id, f"🚀 **Binance AI Predictor**\n\nSelect a coin for a signal or use `/setalert BTC 105000`", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if call.data.startswith("p_"):
        coin = call.data.split("_")[1]
        bot.answer_callback_query(call.id, "Analyzing...")
        bot.send_message(call.message.chat.id, get_prediction(coin))
    elif call.data == "buy_vip":
        bot.send_invoice(call.message.chat.id, "VIP Alpha Signal", "High-accuracy signal.", "vip_payload", "", "XTR", [LabeledPrice("VIP", 50)])

@bot.message_handler(commands=['setalert'])
def set_alert(message):
    try:
        _, coin, price = message.text.split()
        cid = message.chat.id
        if cid not in user_alerts: user_alerts[cid] = []
        user_alerts[cid].append({'coin': coin.upper(), 'target': float(price)})
        bot.reply_to(message, "✅ Alert set!")
    except: bot.reply_to(message, "Usage: /setalert BTC 100000")

# Payment confirmation logic
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(q): bot.answer_pre_checkout_query(q.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def pay_ok(m):
    bot.send_message(m.chat.id, "✅ VIP Signal: **SOL/USDT Target $350**")

bot.infinity_polling()
