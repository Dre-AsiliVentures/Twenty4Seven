# main.py
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time
from database import SessionLocal, Trade, LogEntry
from mr_strat_deploy_v2 import BinanceExecution, RevCondition, interval, support_interval

app = FastAPI()

# Enable CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with Vercel Domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

portfolio = ['ADA', 'PHB', 'FET']
is_running = False

async def bot_loop():
    global is_running
    is_running = True
    print("Bot loop started...")
    
    while is_running:
        try:
            for coin in portfolio:
                print(f"Checking {coin}...")
                bot = BinanceExecution(coin)
                
                # Logic
                rev = RevCondition(bot.df)
                support_data = bot.datafetch(support_interval)
                support, resistance = bot.support_resistance(support_data)
                
                # Check Entry
                if (rev.entry() and 
                    bot.lastprice > support and 
                    bot.lastprice < 0.95 * resistance):
                    bot.place_buy_order()
                
                # Check Exit
                elif bot.lastprice > bot.target_sell_price:
                    bot.place_sell_order()
                
                # Log Heartbeat
                bot.log(f"Checked {coin}. Price: {bot.lastprice}. Target: {bot.target_sell_price}", "INFO")
                
                await asyncio.sleep(5) # Short sleep between coins
            
            await asyncio.sleep(50) # Loop sleep
        except Exception as e:
            print(f"Loop Error: {e}")
            await asyncio.sleep(30)

@app.on_event("startup")
async def startup_event():
    # Start bot loop in background
    asyncio.create_task(bot_loop())

@app.get("/")
def read_root():
    return {"status": "Bot is running", "portfolio": portfolio}

@app.get("/trades")
def get_trades():
    db = SessionLocal()
    trades = db.query(Trade).order_by(Trade.timestamp.desc()).limit(50).all()
    return trades

@app.get("/logs")
def get_logs():
    db = SessionLocal()
    logs = db.query(LogEntry).order_by(LogEntry.timestamp.desc()).limit(100).all()
    return logs

@app.get("/stats")
def get_stats():
    # Simple stats endpoint for charts
    db = SessionLocal()
    # Calculate simple PnL based on closed trades
    sells = db.query(Trade).filter(Trade.side == "SELL").all()
    total_trades = len(sells)
    return {"total_trades": total_trades}