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
telegram_token = config['telegram_token']
telegram_chat_id = config['telegram_chat_id']

# Inisialisasi client Binance
client = Client(api_key='BINANCE_API_KEY',
                api_secret='BINANCE_API_KEY_SECRET')

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
        return np.array([[float(candle[1]), float(candle[4]), float(candle[2]), float(candle[3]), float(candle[5])] for candle in candles])
    except Exception as e:
        print(f"Error fetching candles: {e}")
        return np.array([])

def calculate_rsi(symbol, period=14):
    candles = get_candlestick_data(symbol)
    if candles.size == 0:
        return 50
    close_prices = candles[:, 1]
    delta = np.diff(close_prices)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = np.mean(gain[-period:])
    avg_loss = np.mean(loss[-period:])
    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    return 100 - (100 / (1 + rs))

def calculate_ema(values, period):
    return np.convolve(values, np.ones(period)/period, mode='valid')[-1]

def bollinger_band_breakout(symbol):
    candles = get_candlestick_data(symbol, limit=20)
    if candles.shape[0] < 20:
        return False, None
    close_prices = candles[:, 1]
    mean = np.mean(close_prices)
    std = np.std(close_prices)
    upper_band = mean + (2 * std)
    lower_band = mean - (2 * std)
    last_price = close_prices[-1]
    if last_price > upper_band:
        return True, 'BUY'
    elif last_price < lower_band:
        return True, 'SELL'
    return False, None

def get_max_leverage(symbol):
    try:
        info = client.futures_leverage_bracket(symbol=symbol)
        if info:
            brackets = info[0]['brackets']
            return max(int(b['initialLeverage']) for b in brackets)
    except Exception as e:
        print(f"Error getting max leverage for {symbol}: {e}")
    return 20

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

# Fungsi untuk menghitung dan mengatur TP dan SL dengan rasio risk/reward 1:1.5
def set_tp_and_sl_by_roi(symbol, entry_price, side, roi=0.01):
    try:
        tp_price = entry_price * (0.5 + roi) if side == 'BUY' else entry_price * (0.5 - roi)
        sl_price = entry_price * (0.5 - roi * 0.75) if side == 'BUY' else entry_price * (0.5 + roi * 0.75)

        # Menyesuaikan harga TP dan SL dengan presisi harga
        price_precision = get_price_precision(symbol)
        tp_price = round(tp_price, price_precision)
        sl_price = round(sl_price, price_precision)

        # Menghitung qty untuk TP dan SL
        qty = qty_usdt * get_max_leverage(symbol) / entry_price
        qty_adjusted = adjust_quantity(symbol, qty)

        # Membuat order TP
        client.futures_create_order(
            symbol=symbol,
            side='SELL' if side == 'BUY' else 'BUY',
            type=ORDER_TYPE_LIMIT,
            price=tp_price,
            quantity=qty_adjusted,
            timeInForce=TIME_IN_FORCE_GTC,
            positionSide='LONG' if side == 'BUY' else 'SHORT'
        )

        # Membuat order SL
        client.futures_create_order(
            symbol=symbol,
            side='SELL' if side == 'BUY' else 'BUY',
            type=FUTURE_ORDER_TYPE_STOP_MARKET,
            stopPrice=sl_price,
            quantity=qty_adjusted,
            positionSide='LONG' if side == 'BUY' else 'SHORT'
        )

        send_telegram_message(f"TP for {symbol} set at {tp_price} (ROI {roi*100}%) and SL set at {sl_price}")
    except BinanceAPIException as e:
        send_telegram_message(f"[ERROR] TP/SL error for {symbol}: {e.message}")

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

    max_leverage = get_max_leverage(symbol)
    client.futures_change_leverage(symbol=symbol, leverage=max_leverage)

    qty = qty_usdt * max_leverage / price

    if check_open_position(symbol) is not None:
        print(f"Position already open for {symbol}. Skipping trade.")
        return

    print(f"Placing {side} order for {symbol} with quantity: {qty}")
    order = place_market_order(symbol, side, qty)
    if order:
        send_telegram_message(f"{side} order for {symbol} placed at {price}")
        set_tp_and_sl_by_roi(symbol, price, side, roi=0.015)

def main():
    while True:
        for symbol in symbols:
            try:
                rsi = calculate_rsi(symbol)
                candles = get_candlestick_data(symbol)
                if candles.shape[0] < 50:
                    continue
                close_prices = candles[:, 1]
                ema20 = calculate_ema(close_prices, 20)
                ema50 = calculate_ema(close_prices, 50)
                breakout, breakout_side = bollinger_band_breakout(symbol)

                print(f"{symbol} RSI: {rsi:.2f}, EMA20: {ema20:.2f}, EMA50: {ema50:.2f}")

                if rsi < 30 and is_bullish_candle(symbol) and ema20 > ema50:
                    execute_trade(symbol, 'BUY')
                elif rsi > 70 and is_bearish_candle(symbol) and ema20 < ema50:
                    execute_trade(symbol, 'SELL')
                elif breakout:
                    execute_trade(symbol, breakout_side)
            except Exception as e:
                send_telegram_message(f"Error in {symbol}: {str(e)}")
        time.sleep(30)

# Main execution
if __name__ == "__main__":
    main()
