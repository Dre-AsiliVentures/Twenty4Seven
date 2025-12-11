# backend/mr_strat_deploy_v2.py
from binance import Client
from dotenv import load_dotenv
import datetime
import pandas as pd
import requests
import ta_py as ta
import os
from database import SessionLocal, Trade, LogEntry

load_dotenv()
api_key = os.getenv("api_key")
api_secret = os.getenv("api_secret")
bot_token = os.getenv("bot_token")
chat_id = os.getenv("chat_id")

client = Client(api_key, api_secret)
interval = Client.KLINE_INTERVAL_1MINUTE
support_interval = Client.KLINE_INTERVAL_30MINUTE

class BinanceExecution:
    def __init__(self, token):
        self.db = SessionLocal()
        self.token = token
        self.symbol = f"{token}USDT"
        self.currentDatetime = datetime.datetime.now()

        self.target_sell_price = None
        self.buy_bal = None
        
        # Fetch Data
        self.df = self.datafetch(interval)
        self.lastprice = round(float(self.df['Close'].iloc[-1]), 8)
        
        # Balance Logic
        try:
            buy_bal = float(client.get_asset_balance('USDT')['free']) * 0.97
            self.buy_bal = int(buy_bal)
            self.buy_quantity = int(self.buy_bal / self.lastprice) if self.lastprice > 0 else 0
            
            sell_bal_data = client.get_asset_balance(str(token))
            sell_bal = float(sell_bal_data['free']) if sell_bal_data else 0
            
            # Retrieve last buy quantity from DB instead of txt file
            last_trade = self.db.query(Trade).filter(Trade.symbol == self.symbol, Trade.side == "BUY", Trade.strategy_status == "OPEN").order_by(Trade.id.desc()).first()
            
            if last_trade:
                self.sell_quantity = last_trade.quantity
                self.target_sell_price = last_trade.price * 1.02 # Assuming the 2% logic from your original code
            else:
                self.sell_quantity = 5000000 # Default/Blocking value
                self.target_sell_price = 5000000
                
        except Exception as e:
            self.log(f"Init Error: {e}", "ERROR")

    def log(self, message, level="INFO"):
        print(f"[{level}] {message}")
        entry = LogEntry(timestamp=datetime.datetime.now(), level=level, message=message)
        self.db.add(entry)
        self.db.commit()

    def datafetch(self, interval):
        data = client.get_historical_klines(self.symbol, interval, "30 day ago")
        data_table = pd.DataFrame(data).iloc[:, :6]
        data_table.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        data_table = data_table.set_index('Time')
        data_table.index = pd.to_datetime(data_table.index, unit='ms')
        data_table = data_table.astype(float)
        return data_table

    def send_telegram_Message(self, text):
        url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
        params = {'chat_id': chat_id, 'text': text}
        try:
            requests.post(url, params=params)
        except Exception as e:
            self.log(f"Telegram Error: {e}", "ERROR")

    def place_buy_order(self):
        if self.buy_bal < 1.5:
            self.log(f'{self.symbol} Buy skipped. Low Balance', "WARNING")
            return

        try:
            # SIMULATION MODE (Uncomment next line to go live)
            # order = client.create_order(symbol=self.symbol, side=Client.SIDE_BUY, type=Client.ORDER_TYPE_MARKET, quantity=self.buy_quantity)
            
            # Mock Order for Frontend Demo (Remove this block when live)
            order = {
                'fills': [{'price': self.lastprice, 'commission': 0, 'qty': self.buy_quantity}]
            }
            # End Mock
            
            avg_price = float(order['fills'][0]['price'])
            qty = float(order['fills'][0]['qty'])
            
            self.log(f"{self.symbol} Buy Executed at {avg_price}", "SUCCESS")
            self.send_telegram_Message(f"BUY {self.symbol} at {avg_price}")
            
            # Save to DB
            new_trade = Trade(
                symbol=self.symbol, side="BUY", price=avg_price, 
                quantity=qty, strategy_status="OPEN", timestamp=datetime.datetime.now()
            )
            self.db.add(new_trade)
            self.db.commit()
            
        except Exception as e:
            self.log(f"Buy Error: {e}", "ERROR")

    def place_sell_order(self):
        try:
            # SIMULATION MODE (Uncomment next line to go live)
            # order = client.create_order(symbol=self.symbol, side=Client.SIDE_SELL, type=Client.ORDER_TYPE_MARKET, quantity=self.sell_quantity)

            # Mock Order
            order = {'fills': 'mock'} 
            
            self.log(f"{self.symbol} Sell Executed", "SUCCESS")
            self.send_telegram_Message(f"SELL {self.symbol}")

            # Close the trade in DB
            open_trade = self.db.query(Trade).filter(Trade.symbol == self.symbol, Trade.side == "BUY", Trade.strategy_status == "OPEN").order_by(Trade.id.desc()).first()
            if open_trade:
                open_trade.strategy_status = "CLOSED"
            
            sell_trade = Trade(
                symbol=self.symbol, side="SELL", price=self.lastprice, 
                quantity=self.sell_quantity, strategy_status="CLOSED", timestamp=datetime.datetime.now()
            )
            self.db.add(sell_trade)
            self.db.commit()

        except Exception as e:
            self.log(f"Sell Error: {e}", "ERROR")

    def support_resistance(self, data):
        dataframeLength = len(data)
        lookbackPeriod = dataframeLength
        recent_low = ta.recent_low(data['Low'], lookbackPeriod)
        recent_high = ta.recent_high(data['High'], lookbackPeriod)
        support = ta.support(data['Low'], recent_low)
        resistance = ta.resistance(data['High'], recent_high)
        return support['calculate'](len(data)-support['index']), resistance['calculate'](len(data)-resistance['index'])
    # IMPORTANT: You must close the session when the object is destroyed
        # or execution finishes to prevent connection leaks.
    def __del__(self):
        self.db.close()
class RevCondition:
    def __init__(self, data):
        self.data = data
        self.ema_4 = ta.ema(self.data.Close.values, 3)

    def entry(self):
        return self.data.High.iloc[-1] < self.ema_4[-1] and self.data.Close.iloc[-1] < self.ema_4[-1]

    def exit(self):
        return self.data.Low.iloc[-1] > self.ema_4[-1] and self.data.Open.iloc[-1] > self.ema_4[-1]