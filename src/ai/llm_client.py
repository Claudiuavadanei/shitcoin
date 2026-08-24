"""
AI Reasoning Client (Gemini API & Fast Algorithmic Synthesizer)
Generates real-time market rationale, trade theses, and natural language copilot responses.
"""
import aiohttp
import asyncio
import logging
from typing import Dict, Any, Optional
from config import config

logger = logging.getLogger("AICopilot")

class LLMClient:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Content-Type": "application/json"}
            )
        return self.session

    async def generate_token_thesis(self, token_data: Dict[str, Any], metrics: Dict[str, Any]) -> str:
        """
        Synthesizes a sharp, quantitative trading thesis for a token.
        Uses Gemini API if key is available, or fast built-in algorithmic reasoner.
        """
        symbol = token_data.get("symbol", "TOKEN")
        chain = token_data.get("chain", "solana").upper()
        buy_ratio = metrics.get("buy_ratio_pct", 50)
        volume_spike = metrics.get("volume_spike_ratio", 1.0)
        safety_score = metrics.get("safety_score", 100)
        liquidity = metrics.get("liquidity_usd", 0)
        signal = metrics.get("signal", "WAIT")
        action_reason = metrics.get("reason", "")

        # If Gemini API key is configured, query Gemini
        if config.gemini_api_key:
            try:
                prompt = (
                    f"You are an elite crypto sniper AI. Provide a 1-2 sentence quantitative trade thesis in Romanian "
                    f"for token {symbol} on {chain}. Data: Signal={signal}, Buy Ratio={buy_ratio:.1f}%, "
                    f"Vol Spike={volume_spike:.1f}x, Safety={safety_score}/100, Liquidity=${liquidity:,.0f}. "
                    f"Reason={action_reason}."
                )
                gemini_text = await self._query_gemini(prompt)
                if gemini_text:
                    return gemini_text
            except Exception as e:
                logger.debug(f"Gemini API query error: {e}")

        # High-precision local heuristic reasoning generator (0ms latency)
        if signal == "STRONG_BUY":
            return f"Presiune masivă de cumpărare ({buy_ratio:.0f}% buys), spike de volum de {volume_spike:.1f}x și lichiditate sănătoasă de ${liquidity:,.0f}. Toate filtrele de siguranță sunt validate ({safety_score}/100)."
        elif signal == "BUY":
            return f"Momentum ascendent cu {buy_ratio:.0f}% tranzacții de buy și volum activ. Risc calculat cu potențial ridicat de breakout pe {chain}."
        elif signal == "WATCH":
            return f"Volum în consolidare ({buy_ratio:.0f}% buys). Tokenul este monitorizat pentru confirmarea spargerii de volum înainte de intrare."
        else:
            return f"Semnal de precauție: {action_reason or 'Volum insuficient sau presiune de vânzare'}. Risc ridicat de scădere, intrarea a fost evitată."

    async def chat_copilot(self, query: str, context: Dict[str, Any]) -> str:
        """Handles natural language conversation with the user in the web UI."""
        if config.gemini_api_key:
            try:
                system_prompt = (
                    f"Ești Shitcoin Sniper AI Copilot, un asistent inteligent de tranzacționare crypto specializat pe Solana, BSC și Base. "
                    f"Răspunde scurt, profesionist și prietenos în limba română. "
                    f"Context bot curent: Poziții active={len(context.get('positions', {}))}, Total profit=${context.get('stats', {}).get('total_profit_usd', 0):.2f}, "
                    f"Mod={context.get('config', {}).get('trading_mode', 'PAPER')}, Auto-Buy={'Activ' if context.get('config', {}).get('auto_buy_enabled') else 'Oprit'}."
                )
                full_prompt = f"{system_prompt}\n\nÎntrebare utilizator: {query}"
                res = await self._query_gemini(full_prompt)
                if res:
                    return res
            except Exception as e:
                logger.debug(f"Gemini chat error: {e}")

        # Smart local conversational engine fallback
        q_lower = query.lower()
        active_pos = list(context.get("positions", {}).values())
        stats = context.get("stats", {})

        if "piata" in q_lower or "sentiment" in q_lower or "cum e" in q_lower:
            return f"📊 **Analiza Pieței**: Scanner-ul multi-chain monitorizează activ Solana, BSC și Base. Momentum-ul pe meme coins este activ, iar filtrele AI filtrează tokenii fără volum real sau cu presiune de vânzare."
        
        elif "pozit" in q_lower or "trade" in q_lower or "profit" in q_lower:
            if not active_pos:
                return f"În prezent nu avem poziții deschise. Total profit realizat în această sesiune: **${stats.get('total_profit_usd', 0):.2f}** ({stats.get('total_trades', 0)} tranzacții încheiate, Win Rate {stats.get('winning_trades', 0)}/{stats.get('total_trades', 0) or 1})."
            tokens_str = ", ".join([f"**{p.get('symbol')}** ({p.get('pnl_pct', 0):+.2f}%)" for p in active_pos[:5]])
            return f"Avem în prezent **{len(active_pos)} poziții active**: {tokens_str}. Toate pozițiile sunt monitorizate de modulul AI Smart Exit cu Trailing Stop dinamic."

        elif "strategie" in q_lower or "cum functionezi" in q_lower or "ajutor" in q_lower:
            return "🤖 **Strategia mea de analiză**: \n1. **Smart Entry**: Scanez DEX-urile și calculez raportul Buy/Sell Volume. Cumpăr doar pe tokeni cu scor AI ≥ 75% și lichiditate blocată.\n2. **Smart Exit**: Urmăresc volumul live. Dacă vânzătorii domină piața sau volumul scade brusc, ies imediat pentru a proteja câștigurile."

        return f"Am recepționat mesajul tău! Sistemul AI continuă să scaneze piața non-stop. În prezent avem {len(active_pos)} poziții active și un profit realizat de ${stats.get('total_profit_usd', 0):.2f}."

    async def _query_gemini(self, prompt: str) -> Optional[str]:
        session = await self._get_session()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={config.gemini_api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 200}
        }
        async with session.post(url, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        return None

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

llm_client = LLMClient()
