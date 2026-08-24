"""
Trading Engine & Position Manager
Executes paper trading / live trades and manages active positions with Take Profit, Trailing Stop, and Stop Loss.
"""
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from config import config
from src.storage.database import db
from src.scanner.market_scanner import scanner
from src.security.safety_checker import safety_checker
from src.ai.market_analyst import market_analyst
from src.ai.smart_exit import smart_exit

logger = logging.getLogger("TradingEngine")

class TradingEngine:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.running = False
        
        # Connect scanner callbacks
        scanner.register_token_callback(self.on_token_discovered)
        scanner.register_price_callback(self.on_price_updated)

    async def start(self):
        self.running = True
        logger.info(
            "Trading Engine started. Mode: %s | Auto-Buy: %s | AI-Filter: %s (Min Conf: %d%%)",
            config.trading_mode, config.auto_buy_enabled, config.ai_filtering_enabled, config.min_ai_confidence
        )
        await db.add_log(
            "INFO",
            f"Trading Engine started [{config.trading_mode} MODE] | AI Smart Sniper: {'ENABLED' if config.ai_filtering_enabled else 'OFF'} | Min Conf: {config.min_ai_confidence}%"
        )
        asyncio.create_task(self._position_watchdog_loop())

    async def stop(self):
        self.running = False
        await db.add_log("INFO", "Trading Engine paused")

    async def on_token_discovered(self, token_data: Dict[str, Any]):
        """Triggered automatically whenever a new token is scanned and audited."""
        if not config.auto_buy_enabled or not config.scanner_active or not self.running:
            return

        safety = token_data.get("safety", {})
        passed = safety.get("passed_filters", False)
        score = safety.get("safety_score", 0)

        # Check safety filters first
        if not passed or score < config.min_safety_score:
            return

        token_address = token_data.get("token_address")
        chain = token_data.get("chain", "solana")
        symbol = token_data.get("symbol", "TOKEN")

        # Check AI Market Intelligence Decision
        if config.ai_filtering_enabled:
            ai_data = token_data.get("ai")
            if not ai_data:
                ai_data = await market_analyst.analyze_token(token_data)
                token_data["ai"] = ai_data

            is_approved = ai_data.get("is_approved_for_entry", False)
            signal = ai_data.get("signal", "SKIP")
            confidence = ai_data.get("confidence_score", 0)

            if not is_approved or confidence < config.min_ai_confidence:
                logger.info(
                    "AI Market Screener filtered out %s (%s). Signal: %s (%d%%) | Thesis: %s",
                    symbol, chain.upper(), signal, confidence, ai_data.get("thesis", "")
                )
                return

            logger.info("🧠 AI SMART SNIPE APPROVED for %s | Signal: %s (%d%%) | Thesis: %s", symbol, signal, confidence, ai_data.get("thesis"))

        logger.info("Auto-snipe triggered for token %s (%s) with safety score %d", symbol, token_address, score)
        await self.buy_token(token_address, chain, token_details=token_data)


    async def buy_token(self, token_address: str, chain: str = "solana", amount_usd: Optional[float] = None, token_details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Opens a new position in Paper or Live trading mode."""
        async with self.lock:
            # Check existing position
            existing = await db.get_position(token_address)
            if existing:
                msg = f"Already holding open position for {token_address}"
                logger.warning(msg)
                return {"success": False, "error": msg}

            # Check max positions
            active_positions = await db.get_active_positions()
            if len(active_positions) >= config.max_open_positions:
                msg = f"Maximum open positions limit ({config.max_open_positions}) reached"
                logger.warning(msg)
                await db.add_log("WARN", msg)
                return {"success": False, "error": msg}

            # Fetch fresh token details if not provided
            if not token_details or token_details.get("price_usd", 0) <= 0:
                token_details = await scanner.fetch_token_details(chain, token_address)
                if not token_details:
                    msg = f"Could not fetch market price and liquidity for {token_address}"
                    logger.error(msg)
                    return {"success": False, "error": msg}

            price_usd = token_details.get("price_usd", 0.0)
            if price_usd <= 0:
                msg = f"Invalid token price ($0) for {token_address}"
                return {"success": False, "error": msg}

            # Determine buy amount
            buy_usd = amount_usd if amount_usd is not None else config.buy_amount_usd
            buy_sol = config.buy_amount_sol

            state = await db.get_state()
            if config.trading_mode == "PAPER":
                if state.get("paper_balance_usd", 0) < buy_usd:
                    msg = f"Insufficient paper USD balance (${state.get('paper_balance_usd', 0):.2f} < ${buy_usd:.2f})"
                    await db.add_log("ERROR", msg)
                    return {"success": False, "error": msg}

            # Calculate token quantity
            # Apply simulated slippage (e.g. 0.5% - 1.5%)
            slippage_factor = 1.0 - (min(config.max_slippage_percent, 1.0) / 100.0)
            token_amount = (buy_usd / price_usd) * slippage_factor

            # Calculate target exit prices
            tp_target = price_usd * (1.0 + (config.take_profit_percent / 100.0))
            sl_target = price_usd * (1.0 - (config.stop_loss_percent / 100.0))
            trailing_stop_init = price_usd * (1.0 - (config.trailing_stop_offset_percent / 100.0))

            safety_info = token_details.get("safety", {})
            if not safety_info:
                safety_info = await safety_checker.check_token(chain, token_address, token_details.get("pair_data"))

            ai_info = token_details.get("ai", {})
            if not ai_info and config.ai_filtering_enabled:
                ai_info = await market_analyst.analyze_token(token_details)

            position = {
                "token_address": token_address,
                "name": token_details.get("name", "Unknown"),
                "symbol": token_details.get("symbol", "TOKEN"),
                "chain": chain,
                "dex_id": token_details.get("dex_id", ""),
                "pair_address": token_details.get("pair_address", ""),
                "entry_price": price_usd,
                "current_price": price_usd,
                "peak_price": price_usd,
                "trailing_stop_price": trailing_stop_init,
                "take_profit_target_price": tp_target,
                "stop_loss_target_price": sl_target,
                "invested_usd": buy_usd,
                "invested_sol": buy_sol,
                "token_amount": token_amount,
                "open_time": time.time(),
                "safety_score": safety_info.get("safety_score", 100),
                "risk_level": safety_info.get("risk_level", "SAFE"),
                "ai_signal": ai_info.get("signal", "BUY"),
                "ai_confidence": ai_info.get("confidence_score", 80),
                "ai_thesis": ai_info.get("thesis", "Momentum confirmat"),
                "break_even_activated": False,
                "pnl_usd": 0.0,
                "pnl_pct": 0.0,
                "status": "OPEN",
                "mode": config.trading_mode,
                "url": token_details.get("url", f"https://dexscreener.com/{chain}/{token_address}")
            }

            await db.add_position(position)
            
            log_msg = f"🚀 SNIPED {position['symbol']} on {chain.upper()} @ ${price_usd:.8f} | Invested: ${buy_usd:.2f} | TP: +{config.take_profit_percent}% | SL: -{config.stop_loss_percent}%"
            await db.add_log("SUCCESS", log_msg, {"token": token_address, "price": price_usd, "invested": buy_usd, "thesis": position["ai_thesis"]})
            logger.info(log_msg)

            return {"success": True, "position": position}

    async def on_price_updated(self, token_address: str, current_price: float):
        """Called whenever a new price tick arrives for an active position."""
        pos = await db.get_position(token_address)
        if not pos or pos.get("status") != "OPEN":
            return

        entry_price = pos.get("entry_price", 0.0)
        if entry_price <= 0 or current_price <= 0:
            return

        # Calculate PnL
        pnl_pct = ((current_price - entry_price) / entry_price) * 100.0
        invested_usd = pos.get("invested_usd", 0.0)
        pnl_usd = invested_usd * (pnl_pct / 100.0)

        peak_price = max(pos.get("peak_price", entry_price), current_price)
        trailing_stop_price = pos.get("trailing_stop_price", 0.0)
        stop_loss_target_price = pos.get("stop_loss_target_price", entry_price * (1.0 - (config.stop_loss_percent / 100.0)))
        be_activated = pos.get("break_even_activated", False)

        # 0. RUG-PULL & CATASTROPHIC DUMP DETECTION (Realistic Market Simulation)
        if current_price < (entry_price * 0.15) or current_price <= 1e-11:
            rug_reason = "RUG_PULL / DUMPED 💀"
            await self._exit_position(pos, current_price, -invested_usd, -100.0, rug_reason)
            return

        # 1. AUTO BREAK-EVEN LOCK (Turns potential losses into guaranteed risk-free trades)
        if config.break_even_enabled and not be_activated:
            if pnl_pct >= config.break_even_trigger_percent:
                be_stop = entry_price * (1.0 + (config.break_even_offset_percent / 100.0))
                if be_stop > stop_loss_target_price:
                    stop_loss_target_price = be_stop
                    be_activated = True
                    be_log = f"🔒 BREAK-EVEN ACTIVATED for {pos['symbol']} (+{pnl_pct:.1f}%). Stop Loss raised to +{config.break_even_offset_percent}% floor (${be_stop:.8f})."
                    await db.add_log("SUCCESS", be_log, {"token": token_address, "pnl_pct": pnl_pct})
                    logger.info(be_log)

        # 2. Dynamic Trailing Stop Calculation (Only for runners with >= +10% peak profit)
        if config.trailing_stop_enabled and peak_price >= (entry_price * 1.10):
            calculated_stop = peak_price * (1.0 - (config.trailing_stop_offset_percent / 100.0))
            # Trailing stop floor must be at least entry_price + 3% guaranteed profit
            min_trailing_floor = entry_price * 1.03
            calculated_stop = max(calculated_stop, min_trailing_floor)
            if calculated_stop > trailing_stop_price:
                trailing_stop_price = calculated_stop

        # 3. AI Smart Exit Evaluation
        if config.ai_smart_exit_enabled:
            smart_eval = smart_exit.evaluate_position(pos, current_price)
            if smart_eval.get("should_exit"):
                exit_reason = smart_eval.get("exit_reason", "AI_SMART_EXIT ⚡")
                await self._exit_position(pos, current_price, pnl_usd, pnl_pct, exit_reason)
                return
            if smart_eval.get("adjusted_trailing_stop", 0) > trailing_stop_price:
                trailing_stop_price = smart_eval["adjusted_trailing_stop"]

        # Check Exit Triggers
        # A. Take Profit Target Reached
        if current_price >= pos["take_profit_target_price"]:
            await self._exit_position(pos, current_price, pnl_usd, pnl_pct, "TAKE_PROFIT 🎯")
            return

        # B. Trailing Stop Trigger (Only if trade gained at least +10% peak profit)
        if config.trailing_stop_enabled and peak_price >= (entry_price * 1.10):
            if current_price <= trailing_stop_price:
                await self._exit_position(pos, current_price, pnl_usd, pnl_pct, "TRAILING_STOP 🛡️")
                return

        # C. Break-Even or Hard Stop Loss Trigger
        if current_price <= stop_loss_target_price:
            reason = "BREAK_EVEN_EXIT 🔒" if be_activated else "STOP_LOSS 🛑"
            await self._exit_position(pos, current_price, pnl_usd, pnl_pct, reason)
            return

        # Update position tracking
        await db.update_position(token_address, {
            "current_price": current_price,
            "peak_price": peak_price,
            "trailing_stop_price": trailing_stop_price,
            "stop_loss_target_price": stop_loss_target_price,
            "break_even_activated": be_activated,
            "pnl_usd": round(pnl_usd, 4),
            "pnl_pct": round(pnl_pct, 2)
        })



    async def _position_watchdog_loop(self):
        """Monitors position hold times, sudden liquidity pulls (anti-rug), and timeout exits."""
        while self.running:
            try:
                positions = await db.get_active_positions()
                now = time.time()
                for pos in positions:
                    token_addr = pos["token_address"]
                    chain = pos.get("chain", "solana")
                    open_time = pos.get("open_time", now)
                    elapsed_min = (now - open_time) / 60.0
                    invested_usd = pos.get("invested_usd", 0.0)

                    # 1. Sudden Liquidity Drain / Rug-Pull Check
                    try:
                        token_details = await scanner.fetch_token_details(chain, token_addr)
                        if token_details:
                            curr_liq = token_details.get("liquidity_usd", 999999.0)
                            if curr_liq < 300.0:  # Dev pulled LP!
                                await self._exit_position(pos, 0.0, -invested_usd, -100.0, "RUG_PULL (LP Drained to $0) 💀")
                                continue
                    except Exception:
                        pass

                    # 2. Check max hold time timeout
                    if elapsed_min >= config.max_hold_time_minutes:
                        curr_price = pos.get("current_price", pos.get("entry_price", 0))
                        pnl_pct = pos.get("pnl_pct", 0.0)
                        pnl_usd = pos.get("pnl_usd", 0.0)
                        await self._exit_position(pos, curr_price, pnl_usd, pnl_pct, f"TIMEOUT (Held {int(elapsed_min)}m) ⏱️")
            except Exception as e:
                logger.error(f"Error in watchdog loop: {e}")
            await asyncio.sleep(5.0)



    async def _exit_position(self, pos: Dict[str, Any], exit_price: float, profit_usd: float, profit_pct: float, reason: str):
        """Closes a position, updates virtual balances and writes to trade ledger."""
        token_address = pos["token_address"]
        invested_usd = pos.get("invested_usd", 0.0)
        invested_sol = pos.get("invested_sol", 0.0)
        
        returned_usd = max(0.0, invested_usd + profit_usd)
        # Approximate returned sol proportionally
        sol_multiplier = (returned_usd / invested_usd) if invested_usd > 0 else 1.0
        returned_sol = invested_sol * sol_multiplier

        exit_data = {
            "exit_price": exit_price,
            "returned_usd": round(returned_usd, 4),
            "returned_sol": round(returned_sol, 4),
            "profit_usd": round(profit_usd, 4),
            "profit_pct": round(profit_pct, 2),
            "exit_reason": reason,
            "status": "CLOSED"
        }

        closed_trade = await db.close_position(token_address, exit_data)
        
        is_win = profit_usd >= 0
        log_type = "SUCCESS" if is_win else "ERROR"
        sign = "+" if profit_usd >= 0 else ""
        log_msg = f"💰 CLOSED {pos.get('symbol')} | Reason: {reason} | Exit: ${exit_price:.8f} | PnL: {sign}${profit_usd:.2f} ({sign}{profit_pct:.2f}%)"
        
        await db.add_log(log_type, log_msg, exit_data)
        logger.info(log_msg)
        return closed_trade

    async def sell_position(self, token_address: str, reason: str = "MANUAL_SELL 👤") -> Dict[str, Any]:
        """Manually closes an open position."""
        pos = await db.get_position(token_address)
        if not pos:
            return {"success": False, "error": f"Position {token_address} not found"}

        curr_price = pos.get("current_price", pos.get("entry_price", 0.0))
        entry_price = pos.get("entry_price", curr_price)
        pnl_pct = ((curr_price - entry_price) / entry_price * 100.0) if entry_price > 0 else 0.0
        invested_usd = pos.get("invested_usd", 0.0)
        pnl_usd = invested_usd * (pnl_pct / 100.0)

        closed = await self._exit_position(pos, curr_price, pnl_usd, pnl_pct, reason)
        return {"success": True, "trade": closed}

    async def panic_sell_all(self) -> Dict[str, Any]:
        """Emergency sells all open positions."""
        positions = await db.get_active_positions()
        results = []
        for pos in positions:
            res = await self.sell_position(pos["token_address"], reason="PANIC_SELL_ALL 🚨")
            results.append(res)
        await db.add_log("WARN", f"🚨 Panic Sell triggered: Closed {len(results)} positions")
        return {"success": True, "closed_count": len(results)}

trading_engine = TradingEngine()
