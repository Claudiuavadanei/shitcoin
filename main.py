import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# Fix Windows console UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware


from config import config, BASE_DIR
from src.api.routes import router as api_router, ws_manager, websocket_broadcaster
from src.scanner.market_scanner import scanner
from src.engine.trading_engine import trading_engine

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | [%(name)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Main")

FRONTEND_DIR = BASE_DIR / "src" / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing Shitcoin Sniper Pro Bot...")
    logger.info(f"Trading Mode: {config.trading_mode} | Auto-Buy: {config.auto_buy_enabled} | Port: {config.port}")
    
    await scanner.start()
    await trading_engine.start()
    broadcaster_task = asyncio.create_task(websocket_broadcaster())
    
    yield
    
    # Shutdown
    logger.info("Shutting down bot services...")
    broadcaster_task.cancel()
    await scanner.stop()
    await trading_engine.stop()

app = FastAPI(
    title="Shitcoin Sniper Pro",
    description="Autonomous Multi-Chain Crypto Sniper & Anti-Rug Trading Bot",
    version="2.4.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router)

# WebSocket Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection open and receive any client messages/pings
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WS error: {e}")
        ws_manager.disconnect(websocket)

# Static Files & Frontend Serving
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
async def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Shitcoin Sniper Pro Bot API Running"}

if __name__ == "__main__":
    print("=" * 65)
    print(f"🚀 SHITCOIN SNIPER PRO BOT STARTING ON http://localhost:{config.port}")
    print(f"📊 Mode: {config.trading_mode} | Auto-Buy: {config.auto_buy_enabled}")
    print("=" * 65)
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="info"
    )
