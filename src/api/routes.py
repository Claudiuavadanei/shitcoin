"""
FastAPI REST API & Real-time WebSocket Gateway
Equipped with AI Market Intelligence, Copilot Chat, and Smart Signal routes.
"""
import asyncio
import json
import logging
from typing import Dict, Any, List, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from config import config
from src.storage.database import db
from src.scanner.market_scanner import scanner
from src.security.safety_checker import safety_checker
from src.engine.trading_engine import trading_engine
from src.ai.market_analyst import market_analyst
from src.ai.llm_client import llm_client

logger = logging.getLogger("API")
router = APIRouter(prefix="/api")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Active clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Active clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return
        dead = []
        payload = json.dumps(message)
        for ws in self.active_connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_connections.discard(ws)

ws_manager = ConnectionManager()

# Request Models
class BuyRequest(BaseModel):
    token_address: str
    chain: str = "solana"
    amount_usd: float = 15.0

class SellRequest(BaseModel):
    token_address: str

class ChatRequest(BaseModel):
    message: str

class AnalyzeTokenRequest(BaseModel):
    token_address: str
    chain: str = "solana"

class ConfigUpdateRequest(BaseModel):
    trading_mode: str = "PAPER"
    auto_buy_enabled: bool = True
    scanner_active: bool = True
    ai_filtering_enabled: bool = True
    min_ai_confidence: int = 80
    ai_smart_exit_enabled: bool = True
    break_even_enabled: bool = True
    break_even_trigger_percent: float = 6.0
    break_even_offset_percent: float = 1.0
    buy_amount_usd: float = 15.0
    buy_amount_sol: float = 0.1
    max_open_positions: int = 30
    take_profit_percent: float = 18.0
    trailing_stop_enabled: bool = True
    trailing_stop_offset_percent: float = 5.0
    stop_loss_percent: float = 12.0
    max_hold_time_minutes: int = 60
    min_liquidity_usd: float = 8000.0
    min_volume_usd: float = 1000.0
    max_dev_holding_percent: float = 15.0
    max_buy_tax_percent: float = 5.0
    max_sell_tax_percent: float = 5.0
    min_safety_score: int = 80

class ResetBalanceRequest(BaseModel):
    sol: float = 10.0
    usd: float = 1500.0

@router.get("/state")
async def get_state():
    """Returns complete state snapshot of the bot, AI settings, and configurations."""
    state = await db.get_state()
    return {
        "config": {
            "trading_mode": config.trading_mode,
            "auto_buy_enabled": config.auto_buy_enabled,
            "scanner_active": config.scanner_active,
            "ai_filtering_enabled": config.ai_filtering_enabled,
            "min_ai_confidence": config.min_ai_confidence,
            "ai_smart_exit_enabled": config.ai_smart_exit_enabled,
            "break_even_enabled": config.break_even_enabled,
            "break_even_trigger_percent": config.break_even_trigger_percent,
            "break_even_offset_percent": config.break_even_offset_percent,
            "buy_amount_usd": config.buy_amount_usd,
            "buy_amount_sol": config.buy_amount_sol,
            "max_open_positions": config.max_open_positions,
            "take_profit_percent": config.take_profit_percent,
            "trailing_stop_enabled": config.trailing_stop_enabled,
            "trailing_stop_offset_percent": config.trailing_stop_offset_percent,
            "stop_loss_percent": config.stop_loss_percent,
            "max_hold_time_minutes": config.max_hold_time_minutes,
            "min_liquidity_usd": config.min_liquidity_usd,
            "min_volume_usd": config.min_volume_usd,
            "max_dev_holding_percent": config.max_dev_holding_percent,
            "max_buy_tax_percent": config.max_buy_tax_percent,
            "max_sell_tax_percent": config.max_sell_tax_percent,
            "min_safety_score": config.min_safety_score,
            "enabled_chains": config.enabled_chains
        },
        "state": state
    }

@router.post("/config")
async def update_config(req: ConfigUpdateRequest):
    """Updates bot configuration live."""
    config.trading_mode = req.trading_mode
    config.auto_buy_enabled = req.auto_buy_enabled
    config.scanner_active = req.scanner_active
    config.ai_filtering_enabled = req.ai_filtering_enabled
    config.min_ai_confidence = req.min_ai_confidence
    config.ai_smart_exit_enabled = req.ai_smart_exit_enabled
    config.break_even_enabled = req.break_even_enabled
    config.break_even_trigger_percent = req.break_even_trigger_percent
    config.break_even_offset_percent = req.break_even_offset_percent
    config.buy_amount_usd = req.buy_amount_usd
    config.buy_amount_sol = req.buy_amount_sol
    config.max_open_positions = req.max_open_positions
    config.take_profit_percent = req.take_profit_percent
    config.trailing_stop_enabled = req.trailing_stop_enabled
    config.trailing_stop_offset_percent = req.trailing_stop_offset_percent
    config.stop_loss_percent = req.stop_loss_percent
    config.max_hold_time_minutes = req.max_hold_time_minutes
    config.min_liquidity_usd = req.min_liquidity_usd
    config.min_volume_usd = req.min_volume_usd
    config.max_dev_holding_percent = req.max_dev_holding_percent
    config.max_buy_tax_percent = req.max_buy_tax_percent
    config.max_sell_tax_percent = req.max_sell_tax_percent
    config.min_safety_score = req.min_safety_score

    await db.add_log("INFO", f"Bot configuration updated. TP: +{config.take_profit_percent}% | SL: -{config.stop_loss_percent}% | BE: {'ON' if config.break_even_enabled else 'OFF'} at +{config.break_even_trigger_percent}%")
    await ws_manager.broadcast({"type": "CONFIG_UPDATED", "config": req.model_dump()})
    return {"success": True, "message": "Config updated"}


@router.post("/bot/toggle-auto-buy")
async def toggle_auto_buy():
    config.auto_buy_enabled = not config.auto_buy_enabled
    status_str = "ENABLED" if config.auto_buy_enabled else "PAUSED"
    await db.add_log("INFO", f"Auto-Buy is now {status_str}")
    await ws_manager.broadcast({"type": "AUTO_BUY_TOGGLED", "auto_buy_enabled": config.auto_buy_enabled})
    return {"success": True, "auto_buy_enabled": config.auto_buy_enabled}

@router.post("/bot/toggle-scanner")
async def toggle_scanner():
    config.scanner_active = not config.scanner_active
    status_str = "ENABLED" if config.scanner_active else "PAUSED"
    await db.add_log("INFO", f"Scanner is now {status_str}")
    await ws_manager.broadcast({"type": "SCANNER_TOGGLED", "scanner_active": config.scanner_active})
    return {"success": True, "scanner_active": config.scanner_active}

@router.post("/ai/toggle-ai-sniper")
async def toggle_ai_sniper():
    config.ai_filtering_enabled = not config.ai_filtering_enabled
    status_str = "ENABLED (Smart Entry)" if config.ai_filtering_enabled else "OFF (Basic Safety Only)"
    await db.add_log("INFO", f"AI Smart Screener is now {status_str}")
    await ws_manager.broadcast({"type": "AI_TOGGLED", "ai_filtering_enabled": config.ai_filtering_enabled})
    return {"success": True, "ai_filtering_enabled": config.ai_filtering_enabled}

@router.post("/bot/reset-balance")
async def reset_balance(req: ResetBalanceRequest):
    await db.reset_paper_balance(req.sol, req.usd)
    await db.add_log("INFO", f"Paper balance reset to {req.sol} SOL / ${req.usd} USD")
    await ws_manager.broadcast({"type": "BALANCE_RESET", "sol": req.sol, "usd": req.usd})
    return {"success": True}

@router.post("/bot/full-reset")
async def full_reset(req: Optional[ResetBalanceRequest] = None):
    sol = req.sol if req else config.paper_balance_sol
    usd = req.usd if req else config.paper_balance_usd
    await db.full_reset(sol, usd)
    scanner.seen_tokens.clear()
    await db.add_log("SUCCESS", f"🔄 Full System Reset performed. Balances reset to {sol} SOL / ${usd:,.2f} USD. PnL: $0.00.")
    await ws_manager.broadcast({"type": "FULL_RESET"})
    return {"success": True, "message": "Full system reset completed"}



@router.post("/bot/panic-sell-all")
async def panic_sell_all():
    res = await trading_engine.panic_sell_all()
    return res

@router.post("/trade/buy")
async def manual_buy(req: BuyRequest):
    res = await trading_engine.buy_token(req.token_address, req.chain, req.amount_usd)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Buy failed"))
    return res

@router.post("/trade/sell")
async def manual_sell(req: SellRequest):
    res = await trading_engine.sell_position(req.token_address, reason="MANUAL_SELL 👤")
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Sell failed"))
    return res

@router.get("/token/inspect/{chain}/{address}")
async def inspect_token(chain: str, address: str):
    """Deep contract audit and AI momentum analysis for any token."""
    details = await scanner.fetch_token_details(chain, address)
    pair_data = details.get("pair_data") if details else None
    safety = await safety_checker.check_token(chain, address, pair_data)
    
    pre_token = {**(details or {}), "safety": safety, "token_address": address, "chain": chain}
    ai_analysis = await market_analyst.analyze_token(pre_token)
    
    return {
        "success": True,
        "token": details,
        "safety": safety,
        "ai": ai_analysis
    }

@router.post("/ai/chat")
async def ai_copilot_chat(req: ChatRequest):
    """Interactive conversational Copilot endpoint."""
    state = await db.get_state()
    context = {
        "positions": state.get("positions", {}),
        "stats": state.get("stats", {}),
        "config": {
            "trading_mode": config.trading_mode,
            "auto_buy_enabled": config.auto_buy_enabled,
            "ai_filtering_enabled": config.ai_filtering_enabled,
            "min_ai_confidence": config.min_ai_confidence
        }
    }
    reply = await llm_client.chat_copilot(req.message, context)
    return {"success": True, "reply": reply}

@router.get("/ai/market-sentiment")
async def get_market_sentiment():
    """Calculates live multi-chain market sentiment based on recent scans."""
    state = await db.get_state()
    recent = state.get("scanned_tokens", [])[:25]
    if not recent:
        return {"sentiment": "NEUTRAL", "bullish_pct": 50, "summary": "Monitorizare DEX activă..."}
    
    buy_signals = sum(1 for t in recent if t.get("ai", {}).get("signal") in ["BUY", "STRONG_BUY"])
    bullish_pct = int((buy_signals / len(recent)) * 100) if recent else 50
    
    if bullish_pct >= 60:
        sentiment = "BULLISH_MOMENTUM 🚀"
        summary = f"Momentum ridicat: {bullish_pct}% din monedele scanate recent prezintă presiune puternică de cumpărare."
    elif bullish_pct >= 35:
        sentiment = "CONSOLIDATION / SELECTIVE ⚖️"
        summary = f"Piață mixtă: AI filtrează strict intrările, aprobând doar cele mai curate setup-uri ({bullish_pct}% bullish)."
    else:
        sentiment = "HIGH_RISK / CHOPPY ⚠️"
        summary = "Piață volatilă cu presiune crescută de vânzare. Modulul AI protejează capitalul și evită capcanele de lichiditate."

    return {
        "sentiment": sentiment,
        "bullish_pct": bullish_pct,
        "summary": summary
    }

@router.get("/analytics/performance")
async def get_performance_analytics(timeframe: str = "all"):
    """Returns detailed performance metrics and equity series (1h, 24h, 7d, 30d, all)."""
    analytics = await db.get_performance_analytics(timeframe)
    return {
        "success": True,
        "analytics": analytics
    }

async def websocket_broadcaster():
    """Background task to broadcast real-time state snapshots and equity points via WebSocket."""
    last_equity_snapshot = 0
    while True:
        try:
            now = time.time()
            # Record an equity snapshot point every 20 seconds
            if now - last_equity_snapshot >= 20:
                db._record_equity_snapshot()
                last_equity_snapshot = now

            if ws_manager.active_connections:
                state = await db.get_state()
                perf = await db.get_performance_analytics("all")
                await ws_manager.broadcast({
                    "type": "STATE_UPDATE",
                    "data": {
                        "initial_capital_usd": state.get("initial_capital_usd", config.paper_balance_usd),
                        "paper_balance_sol": state.get("paper_balance_sol"),
                        "paper_balance_usd": state.get("paper_balance_usd"),
                        "positions": state.get("positions"),
                        "trade_history": state.get("trade_history")[:40],
                        "scanned_tokens": state.get("scanned_tokens")[:60],
                        "activity_logs": state.get("activity_logs")[:40],
                        "stats": state.get("stats"),
                        "performance": perf,
                        "config": {
                            "auto_buy_enabled": config.auto_buy_enabled,
                            "scanner_active": config.scanner_active,
                            "trading_mode": config.trading_mode,
                            "ai_filtering_enabled": config.ai_filtering_enabled,
                            "min_ai_confidence": config.min_ai_confidence,
                            "ai_smart_exit_enabled": config.ai_smart_exit_enabled,
                            "break_even_enabled": config.break_even_enabled,
                            "break_even_trigger_percent": config.break_even_trigger_percent
                        }
                    }
                })
        except Exception as e:
            logger.debug(f"WS broadcast tick error: {e}")
        await asyncio.sleep(1.5)

