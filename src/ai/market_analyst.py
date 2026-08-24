"""
AI Market Analyst & Smart Entry Screener
Performs quantitative momentum scoring, volume velocity analysis, and buy-pressure verification.
"""
import logging
import time
from typing import Dict, Any, Optional
from config import config
from src.ai.llm_client import llm_client

logger = logging.getLogger("MarketAnalyst")

class MarketAnalyst:
    async def analyze_token(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates token market dynamics and decides if entering a trade is opportune.
        Returns full analysis report with AI Confidence Score, Action Signal, and Thesis.
        """
        pair_data = token_data.get("pair_data", {})
        safety_data = token_data.get("safety", {})
        
        # 1. Extract raw market variables
        price_usd = float(token_data.get("price_usd", 0) or 0)
        liquidity_usd = float(token_data.get("liquidity_usd", 0) or 0)
        volume_24h = float(token_data.get("volume_24h", 0) or 0)
        change_5m = float(token_data.get("price_change_5m", 0) or 0)
        change_1h = float(token_data.get("price_change_1h", 0) or 0)
        change_24h = float(token_data.get("price_change_24h", 0) or 0)
        safety_score = float(safety_data.get("safety_score", 100) or 100)
        
        # Transactions breakdown (DexScreener txns object)
        txns = pair_data.get("txns", {})
        txns_5m = txns.get("m5", {})
        txns_1h = txns.get("h1", {})
        txns_24h = txns.get("h24", {})
        
        buys_5m = int(txns_5m.get("buys", 0) or 0)
        sells_5m = int(txns_5m.get("sells", 0) or 0)
        buys_1h = int(txns_1h.get("buys", 0) or 0)
        sells_1h = int(txns_1h.get("sells", 0) or 0)
        
        # 2. Calculate Quantitative Metrics
        # A) Buy vs Sell Pressure (%)
        total_txns_5m = buys_5m + sells_5m
        if total_txns_5m > 0:
            buy_ratio_pct = (buys_5m / total_txns_5m) * 100.0
        else:
            total_txns_1h = buys_1h + sells_1h
            if total_txns_1h > 0:
                buy_ratio_pct = (buys_1h / total_txns_1h) * 100.0
            else:
                # Estimate from price change
                buy_ratio_pct = 70.0 if change_5m > 0 else (40.0 if change_5m < 0 else 50.0)

        # B) Volume Spike Ratio (Velocity)
        vol_5m = float(pair_data.get("volume", {}).get("m5", 0) or 0)
        if volume_24h > 0 and vol_5m > 0:
            # Expected 5m volume if evenly distributed = volume_24h / 288
            expected_5m = volume_24h / 288.0
            volume_spike_ratio = min(15.0, max(0.5, vol_5m / expected_5m)) if expected_5m > 0 else 1.0
        else:
            volume_spike_ratio = 1.2 if change_5m > 2.0 else 1.0

        # C) Liquidity-to-FDV Health
        fdv = float(token_data.get("fdv", 0) or 0)
        liq_to_fdv_ratio = (liquidity_usd / fdv) if fdv > 0 else 0.2

        # 3. AI Scoring Algorithm (0 to 100)
        confidence = 50  # baseline
        reasons = []

        # Anti-Rug Safety Baseline
        if safety_score < config.min_safety_score:
            confidence -= 40
            reasons.append(f"Scor de securitate scăzut ({safety_score}/100)")
        else:
            confidence += int((safety_score - 50) * 0.3)

        # Buy Pressure Impact
        if buy_ratio_pct >= 75.0:
            confidence += 20
            reasons.append(f"Presiune puternică de cumpărare ({buy_ratio_pct:.0f}% buys)")
        elif buy_ratio_pct >= 60.0:
            confidence += 10
            reasons.append(f"Cumpărători activi ({buy_ratio_pct:.0f}% buys)")
        elif buy_ratio_pct < 45.0:
            confidence -= 25
            reasons.append(f"Vânzătorii domină tranzacțiile ({100 - buy_ratio_pct:.0f}% sells)")

        # Momentum & Volume Velocity
        if volume_spike_ratio >= 2.0 and change_5m > 0:
            confidence += 15
            reasons.append(f"Spike de volum activ ({volume_spike_ratio:.1f}x)")
        elif change_5m > 10.0 and buy_ratio_pct > 65.0:
            confidence += 10
            reasons.append("Breakout confirmat pe 5m")

        # Anti-FOMO Filter (Avoid buying peak of a massive dump candle or exhausted pump)
        if change_5m > 150.0 or (change_24h > 1000.0 and change_5m < -15.0):
            confidence -= 35
            reasons.append("Risc ridicat de FOMO / epuizare de trend")

        # Liquidity Filter
        if liquidity_usd >= config.min_liquidity_usd * 2:
            confidence += 10
        elif liquidity_usd < config.min_liquidity_usd:
            confidence -= 20
            reasons.append("Lichiditate sub pragul minim")

        confidence = max(0, min(100, confidence))

        # Determine AI Action Signal
        min_tx_count = buys_5m + sells_5m
        if confidence >= 85 and safety_score >= config.min_safety_score and buy_ratio_pct >= 68 and liquidity_usd >= config.min_liquidity_usd:
            signal = "STRONG_BUY"
        elif confidence >= config.min_ai_confidence and safety_score >= config.min_safety_score and buy_ratio_pct >= 60 and liquidity_usd >= config.min_liquidity_usd:
            signal = "BUY"
        elif confidence >= 55:
            signal = "WATCH"
        else:
            signal = "SKIP"

        is_approved = (
            signal in ["BUY", "STRONG_BUY"]
            and confidence >= config.min_ai_confidence
            and safety_score >= config.min_safety_score
            and liquidity_usd >= config.min_liquidity_usd
            and buy_ratio_pct >= 60.0
        )


        metrics_summary = {
            "buy_ratio_pct": round(buy_ratio_pct, 1),
            "volume_spike_ratio": round(volume_spike_ratio, 2),
            "liquidity_usd": liquidity_usd,
            "safety_score": safety_score,
            "signal": signal,
            "reason": "; ".join(reasons)
        }

        # Synthesize trading thesis
        thesis = await llm_client.generate_token_thesis(token_data, metrics_summary)

        return {
            "signal": signal,
            "confidence_score": confidence,
            "is_approved_for_entry": is_approved,
            "buy_ratio_pct": round(buy_ratio_pct, 1),
            "volume_spike_ratio": round(volume_spike_ratio, 2),
            "reasons": reasons,
            "thesis": thesis,
            "evaluated_at": time.time()
        }

market_analyst = MarketAnalyst()
