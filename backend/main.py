# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from database import SessionLocal, Trade, LogEntry
from mr_strat_deploy_v2 import BinanceExecution, RevCondition, interval, support_interval

app = FastAPI()

# Enable CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

portfolio = ['ADA', 'PHB', 'FET']

# Global control flag
# Default is False (Stopped). Set to True if you want it to auto-start on deploy.
bot_active = False 

async def bot_loop():
    global bot_active
    print("Bot process initialized. Waiting for start command...")
    
    while True:
        # 1. If bot is STOPPED, just sleep and check again later
        if not bot_active:
            await asyncio.sleep(2) 
            continue

        # 2. If bot is RUNNING, execute strategy
        try:
            for coin in portfolio:
                # Double check in case it was stopped mid-loop
                if not bot_active: 
                    break

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
                bot.log(f"Checked {coin}. Price: {bot.lastprice}", "INFO")
                
                await asyncio.sleep(5) # Short sleep between coins
            
            await asyncio.sleep(50) # Loop sleep
            
        except Exception as e:
            print(f"Loop Error: {e}")
            await asyncio.sleep(30)

@app.on_event("startup")
async def startup_event():
    # Start the loop logic in the background immediately
    asyncio.create_task(bot_loop())

@app.get("/")
def read_root():
    # Return the current running status to the frontend
    return {"status": "Online", "bot_active": bot_active, "portfolio": portfolio}

@app.post("/start")
def start_bot():
    global bot_active
    bot_active = True
    print("COMMAND: Bot Started")
    return {"message": "Bot started", "bot_active": True}

@app.post("/stop")
def stop_bot():
    global bot_active
    bot_active = False
    print("COMMAND: Bot Stopped")
    return {"message": "Bot stopped", "bot_active": False}

@app.get("/trades")
def get_trades():
    db = SessionLocal()
    trades = db.query(Trade).order_by(Trade.timestamp.desc()).limit(50).all()
    db.close()
    return trades

@app.get("/logs")
def get_logs():
    db = SessionLocal()
    logs = db.query(LogEntry).order_by(LogEntry.timestamp.desc()).limit(100).all()
    db.close()
    return logs

@app.get("/stats")
def get_stats():
    db = SessionLocal()
    sells = db.query(Trade).filter(Trade.side == "SELL").all()
    total_trades = len(sells)
    db.close()
    return {"total_trades": total_trades}