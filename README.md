# Wajib Punya VPS UBUNTU

# Binance Futures Trading Bot

Script ini adalah bot trading sederhana untuk Binance Futures yang menggunakan indikator RSI, EMA, dan Bollinger Bands untuk mendeteksi sinyal trading dan mengeksekusi order otomatis. Bot juga mengirim notifikasi ke Telegram.

---

## Fitur
- Ambil data candlestick dari Binance Futures
- Hitung indikator RSI, EMA, dan deteksi breakout Bollinger Bands
- Buka posisi BUY atau SELL otomatis berdasarkan sinyal trading
- Set Take Profit (TP) dan Stop Loss (SL) otomatis dengan rasio risk/reward 1:1.5
- Kirim notifikasi order dan error ke Telegram
- Mendukung multi-symbol trading

---

## Persiapan
### 1.Buat API di https://www.binance.com/en/my/settings/api-management
Whitelist IP VPS nya di API BINANCE NYA,di API Binance Yang di centang ENABLE future saja 

### 2. Install Python 3.8+  
Pastikan Python sudah terpasang di sistem kamu.
Jalankan pip install python-binance numpy requests

### 2. Install dependencies  
7.python3 bot_trading.py

## DONE
