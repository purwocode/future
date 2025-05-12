# Update sistem & install dependency
sudo apt update && apt upgrade -y
sudo apt install python3 python3-pip python3-venv build-essential wget unzip git -y

# Install TA-Lib dependency (buat indikator RSI)
sudo apt install libffi-dev libssl-dev libatlas-base-dev liblapack-dev gfortran -y
cd /usr/local/src
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xvzf ta-lib-0.4.0-src.tar.gz
cd ta-lib
./configure --prefix=/usr
make
make install

# Buat folder bot
cd /root
mkdir binance_bot
cd binance_bot

# Buat virtualenv biar rapi
python3 -m venv venv
source venv/bin/activate

# Install library Python
pip install --upgrade pip
pip install python-binance ta-lib requests python-telegram-bot

# Cek installasi berhasil
python -c "import talib; print(talib.get_functions())"

# Buat file bot template
cat <<EOL > bot.py
print("Bot Siap Jalan - Tambahkan kode bot di sini!")
EOL

# Pastikan file bot.py bisa jalan
python bot.py

echo "? Semua sudah di-setup. Kode bot tinggal dimasukkan di /root/binance_bot/bot.py"
