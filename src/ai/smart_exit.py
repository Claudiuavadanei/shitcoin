"""
AI Smart Exit & Dynamic Profit Protector
Continuously analyzes open positions to detect buyer exhaustion, whale dumps, and dynamically trail profits.
"""
import logging
import time
from typing import Dict, Any, Tuple, Optional
from config import config


logger = logging.getLogger("SmartExit")

class SmartExitManager:
    def evaluate_position(self, position: Dict[str, Any], current_price: float, token_details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Real-time position health assessment.
        Returns:
            should_exit (bool): True if smart exit should be triggered immediately.
            exit_reason (str): Natural language rationale for the exit.
            adjusted_trailing_stop (float): Dynamically optimized trailing stop level.
        """
        if not config.ai_smart_exit_enabled:
            return {"should_exit": False, "exit_reason": "", "adjusted_trailing_stop": position.get("trailing_stop_price", 0)}

        entry_price = position.get("entry_price", current_price)
        peak_price = max(position.get("peak_price", entry_price), current_price)
        pnl_pct = ((current_price - entry_price) / entry_price * 100.0) if entry_price > 0 else 0.0
        peak_pnl_pct = ((peak_price - entry_price) / entry_price * 100.0) if entry_price > 0 else 0.0

        current_trailing = position.get("trailing_stop_price", 0.0)
        adjusted_trailing = current_trailing
        
        # 1. Profit Maximizer: Dynamic Trailing Stop Adjustment on High Runners
        # If position gained > 25%, tighten trailing stop from 5% to 3.5% from peak to lock in gains
        if peak_pnl_pct >= 50.0:
            # Lock in at least 70% of gains
            locked_profit_floor = entry_price + ((peak_price - entry_price) * 0.70)
            if locked_profit_floor > adjusted_trailing:
                adjusted_trailing = locked_profit_floor
        elif peak_pnl_pct >= 20.0:
            # Lock in at least 50% of gains
            locked_profit_floor = entry_price + ((peak_price - entry_price) * 0.50)
            if locked_profit_floor > adjusted_trailing:
                adjusted_trailing = locked_profit_floor

        # 2. Smart Buyer Exhaustion Exit
        # If position was up nicely (>10%) and has retraced, or token_details show seller dominance
        if token_details:
            pair_data = token_details.get("pair_data", {})
            txns_5m = pair_data.get("txns", {}).get("m5", {})
            buys_5m = int(txns_5m.get("buys", 0) or 0)
            sells_5m = int(txns_5m.get("sells", 0) or 0)
            
            # If heavy sell dump detected (e.g. 5m sells > 3x buys) while in profit
            if (buys_5m + sells_5m) >= 6 and sells_5m > (buys_5m * 2.5) and pnl_pct > 5.0:
                return {
                    "should_exit": True,
                    "exit_reason": f"AI SMART EXIT: Epuizare Cumpărători & Vânzări Masive ({sells_5m} sells vs {buys_5m} buys) ⚡",
                    "adjusted_trailing_stop": adjusted_trailing
                }

        # 3. Rapid Momentum Decay Exit
        # If price retraced sharply from peak (>10% drop from peak) while still in profit, secure gains early
        if peak_pnl_pct >= 25.0 and current_price < (peak_price * 0.88):
            return {
                "should_exit": True,
                "exit_reason": f"AI SMART EXIT: Securizare Profit la Retragere de Trend (+{pnl_pct:.1f}% salvat) 🛡️",
                "adjusted_trailing_stop": adjusted_trailing
            }

        return {
            "should_exit": False,
            "exit_reason": "",
            "adjusted_trailing_stop": adjusted_trailing
        }

smart_exit = SmartExitManager()
