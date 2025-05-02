from flask import Flask, request, jsonify
from binance.client import Client
from binance.enums import *
import json

# Gantilah dengan API Key dan Secret Anda
api_key = 'API_KEY_ANDA'
api_secret = 'API_SECRET_ANDA'

client = Client(api_key, api_secret)

# Membuat Flask app
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = json.loads(request.data)
    print(f"Received data: {data}")

    # Mengekstrak data dari payload webhook
    signal = data.get('signal')  # Signal yang dikirim dari TradingView (BUY atau SELL)
    symbol = data.get('symbol', 'BTCUSDT')  # Pasangan simbol yang akan diperdagangkan
    quantity = data.get('quantity', 0.001)  # Jumlah yang akan diperdagangkan (contoh 0.001 BTC)

    # Cek sinyal dan eksekusi order
    if signal == "BUY":
        place_order(symbol, 'BUY', quantity)
    elif signal == "SELL":
        place_order(symbol, 'SELL', quantity)

    return jsonify({'status': 'success'}), 200

# Fungsi untuk menempatkan order di Binance
def place_order(symbol, side, quantity):
    order = client.futures_create_order(
        symbol=symbol,
        side=side,
        type=ORDER_TYPE_MARKET,
        quantity=quantity
    )
    print(f"Order placed: {side} {quantity} {symbol}")
    return order

if __name__ == '__main__':
    app.run(debug=True, port=5000)
