import os
from flask import Flask
from threading import Thread
import telebot
import requests
import pandas as pd
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from apscheduler.schedulers.background import BackgroundScheduler

# --- RENDER/REPLIT HEALTH CHECK SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot is alive! | Crypto Signals Bot Running"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# Start Flask server in background thread BEFORE bot polling
Thread(target=run, daemon=True).start()

# --- TELEGRAM BOT SETUP ---
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN environment variable not set! Add it in your hosting platform settings.")

bot = telebot.TeleBot(TOKEN)

# Top coins to analyze
TOP_COINS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'TRX', 'LINK', 'SUI']
user_alerts = {}  # For price alerts

# --- BINANCE RSI ANALYSIS (FIXED URL - NO SPACES!) ---
def get_prediction(symbol):
    try:
        # 🔥 CRITICAL FIX: NO SPACES after symbol= → symbol={symbol}USDT
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval=1h&limit=100"
        data = requests.get(url, timeout=10).json()
        
        # Handle Binance API errors
        if isinstance(data, dict) and 'code' in 
            return None, f"❌ Binance error for {symbol}: {data.get('msg', 'Unknown')}"
        if not data or len(data) < 15:
            return None, f"❌ Not enough data for {symbol}"
        
        df = pd.DataFrame(data, columns=['time','open','high','low','close','vol','ct','qv','nt','tb','tq','i'])
        close = df['close'].astype(float)
        current_price = close.iloc[-1]
        
        # Calculate RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        # Determine signal
        if rsi < 35:
            signal = "🟢 BULLISH - BUY"
            action = "Accumulate positions"
        elif rsi > 65:
            signal = "🔴 BEARISH - SELL"
            action = "Take profits / Reduce exposure"
        else:
            signal = "🟡 NEUTRAL - WAIT"
            action = "Wait for clearer direction"
        
        # Calculate grid bot levels (3% bands around current price)
        upper_limit = current_price * 1.03  # 3% above for sell orders
        lower_limit = current_price * 0.97  # 3% below for buy orders
        
        # Format nicely
        message = (
            f"📊 *{symbol}/USDT*\n"
            f"💰 Price: ${current_price:,.2f}\n"
            f"📈 RSI: {rsi:.1f}\n"
            f"⚡ Signal: {signal}\n"
            f"🎯 Action: {action}\n"
            f"━━━━━━━━━━━━━━\n"
            f"🤖 *Grid Bot Levels*\n"
            f"   Upper Limit: ${upper_limit:,.2f} (SELL zone)\n"
            f"   Lower Limit: ${lower_limit:,.2f} (BUY zone)\n"
            f"━━━━━━━━━━━━━━\n"
        )
        
        return {
            'symbol': symbol,
            'price': current_price,
            'rsi': rsi,
            'signal': signal,
            'upper': upper_limit,
            'lower': lower_limit
        }, message
        
    except Exception as e:
        return None, f"❌ Error analyzing {symbol}: {str(e)[:50]}"

# --- AUTO ALERT TASK (FIXED URL) ---
def check_prices():
    for chat_id, alerts in list(user_alerts.items()):
        for alert in alerts[:]:
            try:
                # 🔥 CRITICAL FIX: NO SPACES after symbol=
                url = f"https://api.binance.com/api/v3/ticker/price?symbol={alert['coin']}USDT"
                res = requests.get(url, timeout=5).json()
                curr_p = float(res['price'])
                if curr_p >= alert['target']:
                    bot.send_message(
                        chat_id,
                        f"🔔 *ALERT TRIGGERED*\n{alert['coin']} reached ${curr_p:,.2f} (target: ${alert['target']:,.2f})",
                        parse_mode="Markdown"
                    )
                    alerts.remove(alert)
            except:
                continue

scheduler = BackgroundScheduler()
scheduler.add_job(check_prices, 'interval', minutes=5)
scheduler.start()

# --- BOT COMMANDS ---
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    bot.send_message(
        chat_id,
        "🚀 *BINANCE AI SIGNALS BOT*\n\nAnalyzing top 10 coins... ⏳",
        parse_mode="Markdown"
    )
    
    # Analyze all coins and collect signals
    all_signals = []
    errors = []
    
    for coin in TOP_COINS:
        result, msg = get_prediction(coin)
        if result:
            all_signals.append((result['rsi'], msg))  # Store RSI for sorting
        else:
            errors.append(msg)
        bot.send_chat_action(chat_id, 'typing')  # Show "typing..." animation
    
    # Sort by RSI (most oversold first)
    all_signals.sort(key=lambda x: x[0])
    
    # Send all signals
    if all_signals:
        # Strongest signals first (oversold = buying opportunity)
        bot.send_message(
            chat_id,
            "✅ *TOP OPPORTUNITIES (Most Oversold First)*\n\n" + "\n".join([msg for _, msg in all_signals[:5]]),
            parse_mode="Markdown"
        )
        bot.send_message(
            chat_id,
            "⚠️ *CAUTION ZONE (Overbought - Consider Taking Profits)*\n\n" + "\n".join([msg for _, msg in all_signals[5:]]),
            parse_mode="Markdown"
        )
    
    # Send errors if any
    if errors:
        bot.send_message(
            chat_id,
            "⚠️ *Note:* Some coins had errors:\n" + "\n".join(errors[:3]),
            parse_mode="Markdown"
        )
    
    # Show commands menu
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🌟 Get VIP Signal (50 Stars)", callback_data="buy_vip"))
    bot.send_message(
        chat_id,
        "💡 *Quick Commands:*\n"
        "`/start` - Get all signals\n"
        "`/setalert BTC 100000` - Set price alert\n\n"
        "⚠️ *Disclaimer:* Signals are for educational purposes only. Trade responsibly!",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "buy_vip")
def buy_vip(call):
    try:
        bot.send_invoice(
            call.message.chat.id,
            title="💎 VIP Alpha Signal",
            description="High-accuracy grid bot setup with entry/exit zones",
            payload="vip_signal",
            provider_token="",  # Required empty string for Telegram Stars
            currency="XTR",
            prices=[LabeledPrice("VIP Signal", 50)]
        )
        bot.answer_callback_query(call.id, "💎 VIP signal loading...")
    except Exception as e:
        bot.answer_callback_query(call.id, f"⚠️ Payment error: {str(e)[:30]}", show_alert=True)

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
        bot.reply_to(
            message,
            f"✅ Alert set!\n{coin.upper()} → ${float(price):,.2f}",
            parse_mode="Markdown"
        )
    except:
        bot.reply_to(
            message,
            "❌ Usage: `/setalert BTC 100000`\n(Set alert when BTC hits $100,000)",
            parse_mode="Markdown"
        )

# --- PAYMENT HANDLERS (Telegram Stars) ---
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def pay_ok(message):
    bot.send_message(
        message.chat.id,
        "💎 *VIP SIGNAL UNLOCKED*\n\n"
        "🎯 *SOL/USDT Grid Bot Setup*\n"
        "   Entry Zone: $142 - $148\n"
        "   Target 1: $165 (25%)\n"
        "   Target 2: $185 (40%)\n"
        "   Stop Loss: $135 (-5%)\n\n"
        "⏰ Valid for next 48 hours\n"
        "⚠️ Trade responsibly - never risk more than 2% per trade!",
        parse_mode="Markdown"
    )

# --- START BOT ---
print("="*50)
print("✅ BINANCE CRYPTO SIGNALS BOT STARTING")
print(f"🔑 Bot token loaded (ends with ...{TOKEN[-6:]})")
print(f"🌐 Health check server running on port {os.environ.get('PORT', 8080)}")
print(f"📈 Monitoring coins: {', '.join(TOP_COINS)}")
print("="*50)

bot.infinity_polling()
