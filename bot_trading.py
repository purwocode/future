import time
import json
import threading
import requests
import numpy as np
from binance.client import Client
from binance.enums import ORDER_TYPE_MARKET, FUTURE_ORDER_TYPE_STOP_MARKET, ORDER_TYPE_LIMIT, TIME_IN_FORCE_GTC
from binance.exceptions import BinanceAPIException

# Membaca konfigurasi dari file config.json
with open('config.json') as f:
    config = json.load(f)

symbols = config['symbols']
qty_usdt = config['qty_usdt']
leverage = config['leverage']
telegram_token = config['telegram_token']
telegram_chat_id = config['telegram_chat_id']

# Inisialisasi client Binance
client = Client(api_key='BINANCE_APIKEY',
                api_secret='BINANCE_APIKEY_SECRET')

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{telegram_token}/sendMessage'
    payload = {'chat_id': telegram_chat_id, 'text': message}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def get_current_price(symbol):
    try:
        price = client.futures_symbol_ticker(symbol=symbol)
        return float(price['price'])
    except Exception as e:
        print(f"Error getting price for {symbol}: {e}")
        return None

def get_candlestick_data(symbol, interval='1m', limit=100):
    try:
        candles = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        return np.array([[float(candle[1]), float(candle[4])] for candle in candles])  # Open and Close
    except Exception as e:
        print(f"Error fetching candles: {e}")
        return np.array([])

def calculate_rsi(symbol, period=14):
    candles = get_candlestick_data(symbol)
    if candles.size == 0:
        return 50  # netral jika data tidak ada
    close_prices = candles[:, 1]
    delta = np.diff(close_prices)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = np.mean(gain[-period:])
    avg_loss = np.mean(loss[-period:])
    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    rsi = 100 - (100 / (1 + rs))
    return rsi

def get_quantity_precision(symbol):
    try:
        info = client.futures_exchange_info()
        for item in info['symbols']:
            if item['symbol'] == symbol:
                for f in item['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        step = f['stepSize']
                        return len(step.split('.')[1].rstrip('0')) if '.' in step else 0
    except Exception as e:
        print(f"Error getting quantity precision: {e}")
    return 0

def adjust_quantity(symbol, quantity):
    precision = get_quantity_precision(symbol)
    return round(quantity, precision)

def place_market_order(symbol, side, qty):
    try:
        qty_adjusted = adjust_quantity(symbol, qty)
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=qty_adjusted,
            positionSide='LONG' if side == 'BUY' else 'SHORT'
        )
        return order
    except BinanceAPIException as e:
        send_telegram_message(f"[ERROR] Failed to place market order for {symbol}: {e.message}")
    return None

def check_open_position(symbol):
    try:
        positions = client.futures_position_information(symbol=symbol)
        for pos in positions:
            if float(pos['positionAmt']) != 0:
                return pos['positionSide']
    except Exception as e:
        print(f"Error checking position: {e}")
    return None

def get_price_precision(symbol):
    try:
        info = client.futures_exchange_info()
        for item in info['symbols']:
            if item['symbol'] == symbol:
                for f in item['filters']:
                    if f['filterType'] == 'PRICE_FILTER':
                        tick_size = float(f['tickSize'])
                        return int(abs(np.log10(tick_size)))
    except Exception as e:
        print(f"Error getting price precision: {e}")
    return 2

def set_sl_tp(symbol, entry_price, side):
    try:
        # Menghitung SL dan TP dengan rasio Risk:Reward 1:1.5
        sl_price = entry_price * (1 - 0.003) if side == 'BUY' else entry_price * (1 + 0.003)
        tp_price = entry_price * (1 + 0.0045) if side == 'BUY' else entry_price * (1 - 0.0045)

        # Menyesuaikan harga SL dan TP sesuai dengan presisi harga
        price_precision = get_price_precision(symbol)
        sl_price = round(sl_price, price_precision)
        tp_price = round(tp_price, price_precision)

        # Menghitung qty yang disesuaikan berdasarkan ukuran posisi dan harga
        qty = qty_usdt * leverage[symbol] / entry_price
        qty_adjusted = adjust_quantity(symbol, qty)

        # Membuat order untuk Stop Loss (SL)
        client.futures_create_order(
            symbol=symbol,
            side='SELL' if side == 'BUY' else 'BUY',
            type=FUTURE_ORDER_TYPE_STOP_MARKET,
            stopPrice=sl_price,
            quantity=qty_adjusted,
            positionSide='LONG' if side == 'BUY' else 'SHORT'
        )

        # Membuat order untuk Take Profit (TP)
        client.futures_create_order(
            symbol=symbol,
            side='SELL' if side == 'BUY' else 'BUY',
            type=ORDER_TYPE_LIMIT,
            price=tp_price,
            quantity=qty_adjusted,
            timeInForce=TIME_IN_FORCE_GTC,
            positionSide='LONG' if side == 'BUY' else 'SHORT'
        )

        # Mengirimkan pesan ke Telegram dengan informasi SL/TP yang telah diset
        send_telegram_message(f"SL/TP for {symbol} set at SL: {sl_price}, TP: {tp_price}")
    except BinanceAPIException as e:
        send_telegram_message(f"[ERROR] SL/TP error for {symbol}: {e.message}")

def is_bullish_candle(symbol):
    candles = get_candlestick_data(symbol)
    return candles[-1, 1] > candles[-1, 0] if candles.size > 0 else False

def is_bearish_candle(symbol):
    candles = get_candlestick_data(symbol)
    return candles[-1, 1] < candles[-1, 0] if candles.size > 0 else False

def execute_trade(symbol, side):
    price = get_current_price(symbol)
    if price is None:
        return

    qty = qty_usdt * leverage[symbol] / price

    if check_open_position(symbol) is not None:
        print(f"Position already open for {symbol}. Skipping trade.")
        return

    print(f"Placing {side} order for {symbol} with quantity: {qty}")
    order = place_market_order(symbol, side, qty)
    if order:
        send_telegram_message(f"{side} order for {symbol} placed at {price}")
        set_sl_tp(symbol, price, side)

def main():
    while True:
        for symbol in symbols:
            rsi = calculate_rsi(symbol)
            print(f"{symbol} RSI: {rsi:.2f}")

            if rsi < 30 and is_bullish_candle(symbol):
                execute_trade(symbol, 'BUY')
            elif rsi > 70 and is_bearish_candle(symbol):
                execute_trade(symbol, 'SELL')
            else:
                print(f"{symbol}: No trade signal")

        time.sleep(30)

def start_bot():
    thread = threading.Thread(target=main)
    thread.daemon = True
    thread.start()

if __name__ == '__main__':
    start_bot()
    while True:
        time.sleep(1)
