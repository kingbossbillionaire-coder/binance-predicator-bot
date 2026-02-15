import os
from flask import Flask
from threading import Thread
import telebot
import requests
import json

app = Flask('')
@app.route('/')
def home(): return "✅ Bot alive"
def run(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
Thread(target=run, daemon=True).start()

TOKEN = os.environ['BOT_TOKEN']
bot = telebot.TeleBot(TOKEN)

def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
    try:
        r = requests.get(url, timeout=5)
        return float(r.json()['price'])
    except:
        return None

@bot.message_handler(commands=['start'])
def start(m):
    coins = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP']
    bot.send_message(m.chat.id, "🚀 Getting live prices from Binance...\n")
    
    for coin in coins:
        price = get_price(coin)
        if price:
            bot.send_message(m.chat.id, f"✅ {coin}/USDT: ${price:,.2f}")
        else:
            bot.send_message(m.chat.id, f"❌ Failed to get {coin} price")

bot.infinity_polling()
