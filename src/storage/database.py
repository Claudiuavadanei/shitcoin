import json
import asyncio
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from config import DATA_DIR, config

DB_FILE = DATA_DIR / "bot_state.json"

class BotDatabase:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.data: Dict[str, Any] = {
            "initial_capital_usd": config.paper_balance_usd,
            "initial_capital_sol": config.paper_balance_sol,
            "paper_balance_sol": config.paper_balance_sol,
            "paper_balance_usd": config.paper_balance_usd,
            "positions": {},       # token_address -> position dict
            "trade_history": [],   # list of closed trades
            "scanned_tokens": [],  # list of discovered tokens (recent 100)
            "activity_logs": [],   # recent log messages
            "equity_history": [
                {
                    "timestamp": time.time(),
                    "time_str": time.strftime("%H:%M"),
                    "total_equity_usd": config.paper_balance_usd,
                    "profit_usd": 0.0,
                    "roi_pct": 0.0,
                    "open_positions": 0,
                    "trades_count": 0
                }
            ],
            "stats": {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "total_profit_usd": 0.0,
                "total_profit_pct": 0.0,
                "best_trade_pct": 0.0,
                "worst_trade_pct": 0.0
            }
        }
        self._load_from_disk()


    def _load_from_disk(self):
        if DB_FILE.exists():
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    for key in self.data:
                        if key in loaded:
                            self.data[key] = loaded[key]
            except Exception as e:
                print(f"[Database] Error loading from disk: {e}")

    def _save_to_disk(self):
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"[Database] Error saving to disk: {e}")

    async def get_state(self) -> Dict[str, Any]:
        async with self.lock:
            return dict(self.data)

    async def get_active_positions(self) -> List[Dict[str, Any]]:
        async with self.lock:
            return list(self.data["positions"].values())

    async def get_position(self, token_address: str) -> Optional[Dict[str, Any]]:
        async with self.lock:
            if token_address in self.data["positions"]:
                return self.data["positions"][token_address]
            addr_lower = token_address.lower()
            for k, v in self.data["positions"].items():
                if k.lower() == addr_lower:
                    return v
            return None

    async def add_position(self, position: Dict[str, Any]):
        async with self.lock:
            token_address = position["token_address"]
            self.data["positions"][token_address] = position
            # Deduct virtual balance if paper trading
            cost_usd = position.get("invested_usd", 0.0)
            cost_sol = position.get("invested_sol", 0.0)
            self.data["paper_balance_usd"] = max(0.0, self.data["paper_balance_usd"] - cost_usd)
            self.data["paper_balance_sol"] = max(0.0, self.data["paper_balance_sol"] - cost_sol)
            self._record_equity_snapshot()
            self._save_to_disk()

    async def update_position(self, token_address: str, updates: Dict[str, Any]):
        async with self.lock:
            target_key = token_address
            if target_key not in self.data["positions"]:
                addr_lower = token_address.lower()
                for k in self.data["positions"].keys():
                    if k.lower() == addr_lower:
                        target_key = k
                        break
            if target_key in self.data["positions"]:
                self.data["positions"][target_key].update(updates)
                self._save_to_disk()

    async def close_position(self, token_address: str, exit_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with self.lock:
            target_key = token_address
            if target_key not in self.data["positions"]:
                addr_lower = token_address.lower()
                for k in self.data["positions"].keys():
                    if k.lower() == addr_lower:
                        target_key = k
                        break
            if target_key not in self.data["positions"]:
                return None
            
            pos = self.data["positions"].pop(target_key)
            closed_trade = {**pos, **exit_data, "closed_at": time.time()}

            
            # Update virtual balance with return
            returned_usd = exit_data.get("returned_usd", 0.0)
            returned_sol = exit_data.get("returned_sol", 0.0)
            profit_usd = exit_data.get("profit_usd", 0.0)
            profit_pct = exit_data.get("profit_pct", 0.0)
            
            self.data["paper_balance_usd"] += returned_usd
            self.data["paper_balance_sol"] += returned_sol
            
            # Update stats
            stats = self.data["stats"]
            stats["total_trades"] += 1
            if profit_usd >= 0:
                stats["winning_trades"] += 1
            else:
                stats["losing_trades"] += 1
            
            stats["total_profit_usd"] += profit_usd
            stats["best_trade_pct"] = max(stats["best_trade_pct"], profit_pct)
            stats["worst_trade_pct"] = min(stats["worst_trade_pct"], profit_pct)
            
            self.data["trade_history"].insert(0, closed_trade)
            if len(self.data["trade_history"]) > 300:
                self.data["trade_history"] = self.data["trade_history"][:300]
            
            self._record_equity_snapshot()
            self._save_to_disk()
            return closed_trade

    def _record_equity_snapshot(self):
        """Records a point on the equity curve."""
        cash_usd = self.data.get("paper_balance_usd", 1500.0)
        positions_val = sum(
            pos.get("invested_usd", 0.0) + pos.get("pnl_usd", 0.0)
            for pos in self.data.get("positions", {}).values()
        )
        total_equity = cash_usd + positions_val
        init_cap = self.data.get("initial_capital_usd", 1500.0)
        roi_pct = ((total_equity - init_cap) / init_cap) * 100.0 if init_cap > 0 else 0.0
        profit_usd = total_equity - init_cap

        snapshot = {
            "timestamp": time.time(),
            "time_str": time.strftime("%H:%M:%S"),
            "date_str": time.strftime("%Y-%m-%d"),
            "total_equity_usd": round(total_equity, 2),
            "cash_usd": round(cash_usd, 2),
            "positions_value_usd": round(positions_val, 2),
            "profit_usd": round(profit_usd, 2),
            "roi_pct": round(roi_pct, 2),
            "open_positions": len(self.data.get("positions", {})),
            "trades_count": len(self.data.get("trade_history", []))
        }
        
        if "equity_history" not in self.data:
            self.data["equity_history"] = []
        
        self.data["equity_history"].append(snapshot)
        if len(self.data["equity_history"]) > 600:
            self.data["equity_history"] = self.data["equity_history"][-600:]

    async def get_performance_analytics(self, timeframe: str = "all") -> Dict[str, Any]:
        """Computes comprehensive performance statistics and equity series for any timeframe."""
        async with self.lock:
            now = time.time()
            tf_seconds = {
                "1h": 3600,
                "24h": 86400,
                "7d": 7 * 86400,
                "30d": 30 * 86400,
                "all": now  # all time
            }
            cutoff = now - tf_seconds.get(timeframe.lower(), now)

            # Filter equity points
            eq_history = self.data.get("equity_history", [])
            filtered_eq = [pt for pt in eq_history if pt.get("timestamp", 0) >= cutoff]
            if not filtered_eq and eq_history:
                filtered_eq = [eq_history[-1]]

            # Current live equity
            cash_usd = self.data.get("paper_balance_usd", 1500.0)
            positions_val = sum(
                pos.get("invested_usd", 0.0) + pos.get("pnl_usd", 0.0)
                for pos in self.data.get("positions", {}).values()
            )
            current_equity = cash_usd + positions_val
            init_cap = self.data.get("initial_capital_usd", 1500.0)

            # Starting point for this timeframe
            start_equity = filtered_eq[0].get("total_equity_usd", init_cap) if filtered_eq else init_cap
            period_profit_usd = current_equity - start_equity
            period_roi_pct = ((current_equity - start_equity) / start_equity) * 100.0 if start_equity > 0 else 0.0
            all_time_roi_pct = ((current_equity - init_cap) / init_cap) * 100.0 if init_cap > 0 else 0.0

            # Filter trades in period
            trades = self.data.get("trade_history", [])
            period_trades = [t for t in trades if t.get("closed_at", 0) >= cutoff]
            
            wins = [t for t in period_trades if t.get("profit_usd", 0) >= 0]
            losses = [t for t in period_trades if t.get("profit_usd", 0) < 0]
            
            win_count = len(wins)
            loss_count = len(losses)
            total_trades_period = len(period_trades)
            win_rate = (win_count / total_trades_period * 100.0) if total_trades_period > 0 else 0.0

            gross_profit = sum(t.get("profit_usd", 0) for t in wins)
            gross_loss = abs(sum(t.get("profit_usd", 0) for t in losses))
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)
            
            avg_win = (gross_profit / win_count) if win_count > 0 else 0.0
            avg_loss = (gross_loss / loss_count) if loss_count > 0 else 0.0

            return {
                "timeframe": timeframe.upper(),
                "initial_capital_usd": round(init_cap, 2),
                "period_start_equity_usd": round(start_equity, 2),
                "current_equity_usd": round(current_equity, 2),
                "period_profit_usd": round(period_profit_usd, 2),
                "period_roi_pct": round(period_roi_pct, 2),
                "all_time_roi_pct": round(all_time_roi_pct, 2),
                "total_trades": total_trades_period,
                "winning_trades": win_count,
                "losing_trades": loss_count,
                "win_rate_pct": round(win_rate, 1),
                "profit_factor": round(profit_factor, 2),
                "avg_win_usd": round(avg_win, 2),
                "avg_loss_usd": round(avg_loss, 2),
                "equity_series": filtered_eq[-100:]  # last 100 curve points
            }

    async def add_scanned_token(self, token: Dict[str, Any]):
        async with self.lock:
            token_addr = token.get("token_address")
            if not token_addr:
                return

            for i, existing in enumerate(self.data["scanned_tokens"]):
                if existing.get("token_address") == token_addr:
                    self.data["scanned_tokens"][i].update({
                        "price_usd": token.get("price_usd", existing.get("price_usd")),
                        "liquidity_usd": token.get("liquidity_usd", existing.get("liquidity_usd")),
                        "volume_24h": token.get("volume_24h", existing.get("volume_24h")),
                        "price_change_5m": token.get("price_change_5m", existing.get("price_change_5m")),
                        "ai": token.get("ai", existing.get("ai")),
                        "last_updated": time.time()
                    })
                    self._save_to_disk()
                    return

            self.data["scanned_tokens"].insert(0, token)
            if len(self.data["scanned_tokens"]) > 100:
                self.data["scanned_tokens"] = self.data["scanned_tokens"][:100]
            self._save_to_disk()

    async def add_log(self, level: str, message: str, meta: Optional[Dict] = None):
        async with self.lock:
            log_item = {
                "id": str(time.time()),
                "timestamp": time.strftime("%H:%M:%S"),
                "level": level,
                "message": message,
                "meta": meta or {}
            }
            self.data["activity_logs"].insert(0, log_item)
            if len(self.data["activity_logs"]) > 150:
                self.data["activity_logs"] = self.data["activity_logs"][:150]
            self._save_to_disk()
            return log_item

    async def reset_paper_balance(self, sol: float = 10.0, usd: float = 1500.0):
        async with self.lock:
            self.data["paper_balance_sol"] = sol
            self.data["paper_balance_usd"] = usd
            self._record_equity_snapshot()
            self._save_to_disk()

    async def full_reset(self, sol: float = 10.0, usd: float = 1500.0):
        async with self.lock:
            self.data["initial_capital_usd"] = usd
            self.data["initial_capital_sol"] = sol
            self.data["paper_balance_sol"] = sol
            self.data["paper_balance_usd"] = usd
            self.data["positions"] = {}
            self.data["trade_history"] = []
            self.data["equity_history"] = [
                {
                    "timestamp": time.time(),
                    "time_str": time.strftime("%H:%M:%S"),
                    "date_str": time.strftime("%Y-%m-%d"),
                    "total_equity_usd": usd,
                    "cash_usd": usd,
                    "positions_value_usd": 0.0,
                    "profit_usd": 0.0,
                    "roi_pct": 0.0,
                    "open_positions": 0,
                    "trades_count": 0
                }
            ]
            self.data["stats"] = {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "total_profit_usd": 0.0,
                "total_profit_pct": 0.0,
                "best_trade_pct": 0.0,
                "worst_trade_pct": 0.0
            }
            self._save_to_disk()

db = BotDatabase()


