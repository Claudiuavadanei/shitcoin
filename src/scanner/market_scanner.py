"""
Multi-Chain DEX Market Scanner (24/7 Non-Stop Resilient Engine)
Monitors new pairs, trending meme tokens, and live price updates across Solana, BSC, and Base.
Equipped with multi-source fallback rotation, rate-limit backoff, and auto-healing watchdogs.
"""
import aiohttp
import asyncio
import logging
import time
import traceback
from typing import Dict, Any, List, Optional, Callable
from config import config
from src.storage.database import db
from src.security.safety_checker import safety_checker
from src.ai.market_analyst import market_analyst

logger = logging.getLogger("MarketScanner")


class MarketScanner:
    def __init__(self):
        self.is_running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self.on_token_discovered_callbacks: List[Callable[[Dict[str, Any]], Any]] = []
        self.on_price_updated_callbacks: List[Callable[[str, float], Any]] = []
        self.seen_tokens: set = set()
        self.scan_interval = 4.0  # High-frequency continuous polling
        
        # 24/7 Watchdog and statistics
        self.total_scans = 0
        self.total_discovered = 0
        self.last_heartbeat = time.time()
        self.discovery_task: Optional[asyncio.Task] = None
        self.price_tracker_task: Optional[asyncio.Task] = None
        self.watchdog_task: Optional[asyncio.Task] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=12, connect=5)
            connector = aiohttp.TCPConnector(limit=50, ssl=False)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept": "application/json",
                    "Accept-Language": "en-US,en;q=0.9"
                }
            )
        return self.session

    def register_token_callback(self, cb: Callable[[Dict[str, Any]], Any]):
        self.on_token_discovered_callbacks.append(cb)

    def register_price_callback(self, cb: Callable[[str, float], Any]):
        self.on_price_updated_callbacks.append(cb)

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        logger.info("24/7 Market Scanner initializing with multi-source fallback and self-healing watchdogs...")
        await db.add_log("INFO", "24/7 Continuous Market Scanner activated [Solana, BSC, Base]")
        
        self.discovery_task = asyncio.create_task(self._discovery_loop())
        self.price_tracker_task = asyncio.create_task(self._price_tracker_loop())
        self.watchdog_task = asyncio.create_task(self._scanner_watchdog_loop())

    async def stop(self):
        self.is_running = False
        if self.discovery_task: self.discovery_task.cancel()
        if self.price_tracker_task: self.price_tracker_task.cancel()
        if self.watchdog_task: self.watchdog_task.cancel()
        if self.session and not self.session.closed:
            await self.session.close()
        await db.add_log("INFO", "Market Scanner paused")

    async def _scanner_watchdog_loop(self):
        """24/7 Supervisor that ensures loops never terminate and reports heartbeats."""
        while self.is_running:
            try:
                now = time.time()
                # Heartbeat every 5 minutes
                if now - self.last_heartbeat >= 300:
                    self.last_heartbeat = now
                    active_pos = len(await db.get_active_positions())
                    heartbeat_msg = f"💚 [24/7 Scanner Heartbeat] Scans: {self.total_scans} | Discovered: {self.total_discovered} | Open Positions: {active_pos}"
                    logger.info(heartbeat_msg)
                    await db.add_log("INFO", heartbeat_msg)

                # Restart discovery task if died
                if self.discovery_task and (self.discovery_task.done() or self.discovery_task.cancelled()):
                    logger.warning("Discovery task exited unexpectedly. Auto-reviving immediately for 24/7 uptime...")
                    self.discovery_task = asyncio.create_task(self._discovery_loop())

                # Restart price tracker task if died
                if self.price_tracker_task and (self.price_tracker_task.done() or self.price_tracker_task.cancelled()):
                    logger.warning("Price tracker task exited unexpectedly. Auto-reviving immediately...")
                    self.price_tracker_task = asyncio.create_task(self._price_tracker_loop())

            except Exception as e:
                logger.error(f"Watchdog error: {e}")

            await asyncio.sleep(10.0)

    async def _discovery_loop(self):
        """Continuous, unbreakable loop discovering new and trending pairs 24/7."""
        error_backoff = 2.0
        while self.is_running:
            try:
                if config.scanner_active:
                    self.total_scans += 1
                    tokens = await self._fetch_latest_tokens_multisource()
                    
                    for token in tokens:
                        if not self.is_running:
                            break
                        token_addr = token.get("token_address")
                        if not token_addr or token_addr in self.seen_tokens:
                            continue
                        
                        self.seen_tokens.add(token_addr)
                        self.total_discovered += 1
                        
                        # Memory protection: Keep seen tokens bounded for continuous fresh discovery
                        if len(self.seen_tokens) > 500:
                            self.seen_tokens = set(list(self.seen_tokens)[-250:])


                        # Perform safety & anti-rug screening
                        chain = token.get("chain", "solana")
                        pair_data = token.get("pair_data", {})
                        safety_report = await safety_checker.check_token(chain, token_addr, pair_data)
                        
                        pre_token = {**token, "safety": safety_report}
                        
                        # Perform AI Market Intelligence Analysis
                        ai_report = await market_analyst.analyze_token(pre_token)
                        enriched_token = {**pre_token, "ai": ai_report}
                        
                        await db.add_scanned_token(enriched_token)
                        
                        score = safety_report.get("safety_score", 0)
                        ai_conf = ai_report.get("confidence_score", 0)
                        ai_signal = ai_report.get("signal", "WAIT")
                        risk = safety_report.get("risk_level", "UNKNOWN")
                        log_level = "SUCCESS" if ai_signal in ["BUY", "STRONG_BUY"] else "INFO"
                        
                        await db.add_log(
                            log_level,
                            f"🤖 [{chain.upper()}] {token.get('symbol')} | AI: {ai_signal} ({ai_conf}%) | Safety: {score}/100 | Liq: ${token.get('liquidity_usd', 0):,.0f}",
                            {
                                "address": token_addr,
                                "ai_signal": ai_signal,
                                "ai_conf": ai_conf,
                                "thesis": ai_report.get("thesis", "")
                            }
                        )

                        # Trigger callbacks (auto-snipe + websocket broadcast)
                        for cb in self.on_token_discovered_callbacks:
                            try:
                                res = cb(enriched_token)
                                if asyncio.iscoroutine(res):
                                    await res
                            except Exception as cb_err:
                                logger.error(f"Error in token discovery callback: {cb_err}")


                    # Reset backoff on clean iteration
                    error_backoff = 2.0

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in 24/7 discovery loop: {e}\n{traceback.format_exc()}")
                error_backoff = min(15.0, error_backoff * 1.5)
                await asyncio.sleep(error_backoff)
            
            await asyncio.sleep(self.scan_interval)

    async def _price_tracker_loop(self):
        """Continuously update prices for active open positions 24/7."""
        while self.is_running:
            try:
                positions = await db.get_active_positions()
                if positions:
                    tokens_to_fetch = [p["token_address"] for p in positions]
                    price_map = await self.fetch_token_prices(tokens_to_fetch)
                    
                    for addr, price in price_map.items():
                        if price > 0:
                            for cb in self.on_price_updated_callbacks:
                                try:
                                    res = cb(addr, price)
                                    if asyncio.iscoroutine(res):
                                        await res
                                except Exception as cb_err:
                                    logger.error(f"Error in price callback: {cb_err}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in price tracker loop: {e}")
            
            await asyncio.sleep(2.5)

    async def _fetch_latest_tokens_multisource(self) -> List[Dict[str, Any]]:
        """Queries multiple redundant feeds with automatic rotation."""
        session = await self._get_session()
        discovered = []
        token_addresses_found = set()

        # Feed 1: DexScreener Latest Token Profiles
        try:
            url_profiles = "https://api.dexscreener.com/token-profiles/latest/v1"
            async with session.get(url_profiles) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        for item in data[:25]:
                            chain_id = item.get("chainId", "").lower()
                            if chain_id in config.enabled_chains:
                                token_addr = item.get("tokenAddress")
                                if token_addr and token_addr not in self.seen_tokens and token_addr not in token_addresses_found:
                                    token_addresses_found.add(token_addr)
        except Exception as e:
            logger.debug(f"DexScreener profiles query exception: {e}")

        # Feed 2: DexScreener Latest Boosts
        try:
            url_boosts = "https://api.dexscreener.com/token-boosts/latest/v1"
            async with session.get(url_boosts) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        for item in data[:20]:
                            chain_id = item.get("chainId", "").lower()
                            if chain_id in config.enabled_chains:
                                token_addr = item.get("tokenAddress")
                                if token_addr and token_addr not in self.seen_tokens and token_addr not in token_addresses_found:
                                    token_addresses_found.add(token_addr)
        except Exception as e:
            logger.debug(f"DexScreener boosts query exception: {e}")

        # Feed 3: DexScreener Rotating Live Search for Newly Created Pairs
        search_terms = ["solana", "pump", "raydium", "meme", "base", "wbnb", "pepe", "trump", "doge", "moon", "ai"]
        term = search_terms[self.total_scans % len(search_terms)]
        try:
            url_search = f"https://api.dexscreener.com/latest/dex/search?q={term}"
            async with session.get(url_search) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if isinstance(pairs, list):
                        for p in pairs[:15]:
                            chain_id = p.get("chainId", "").lower()
                            if chain_id in config.enabled_chains:
                                token_addr = p.get("baseToken", {}).get("address")
                                if token_addr and token_addr not in self.seen_tokens and token_addr not in token_addresses_found:
                                    token_addresses_found.add(token_addr)
        except Exception as e:
            logger.debug(f"DexScreener search error for {term}: {e}")

        # Feed 4: GeckoTerminal New Pools Fallback for Solana/BSC/Base
        if len(token_addresses_found) < 6:
            for chain in config.enabled_chains:
                network = "solana" if chain == "solana" else ("bsc" if chain == "bsc" else "base")
                try:
                    url_gecko = f"https://api.geckoterminal.com/api/v2/networks/{network}/new_pools"
                    async with session.get(url_gecko) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            pools = data.get("data", [])
                            for pool in pools[:10]:
                                base_token_id = pool.get("relationships", {}).get("base_token", {}).get("data", {}).get("id", "")
                                if "_" in base_token_id:
                                    addr = base_token_id.split("_")[-1]
                                    if addr and addr not in self.seen_tokens:
                                        token_addresses_found.add(addr)
                except Exception as e:
                    logger.debug(f"GeckoTerminal new pools query exception for {chain}: {e}")


        # Fetch detailed pair info for discovered token addresses
        for addr in list(token_addresses_found)[:15]:
            try:
                pair_info = await self.fetch_token_details("", addr)
                if pair_info:
                    discovered.append(pair_info)
            except Exception as e:
                logger.debug(f"Error fetching pair info for {addr}: {e}")

        return discovered

    async def fetch_token_details(self, chain: str, token_address: str) -> Optional[Dict[str, Any]]:
        """Fetches full pair metadata, liquidity, volume, and current price from DexScreener."""
        session = await self._get_session()
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        best_pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                        
                        base_token = best_pair.get("baseToken", {})
                        price_usd = float(best_pair.get("priceUsd", 0) or 0)
                        price_native = float(best_pair.get("priceNative", 0) or 0)
                        liquidity_usd = float(best_pair.get("liquidity", {}).get("usd", 0) or 0)
                        volume_24h = float(best_pair.get("volume", {}).get("h24", 0) or 0)
                        pair_created_at = best_pair.get("pairCreatedAt", int(time.time() * 1000))
                        detected_chain = best_pair.get("chainId", chain or "solana").lower()
                        
                        return {
                            "token_address": base_token.get("address", token_address),
                            "name": base_token.get("name", "Unknown Token"),
                            "symbol": base_token.get("symbol", "UNKNOWN"),
                            "chain": detected_chain,
                            "dex_id": best_pair.get("dexId", ""),
                            "pair_address": best_pair.get("pairAddress", ""),
                            "price_usd": price_usd,
                            "price_native": price_native,
                            "liquidity_usd": liquidity_usd,
                            "volume_24h": volume_24h,
                            "fdv": float(best_pair.get("fdv", 0) or 0),
                            "price_change_5m": float(best_pair.get("priceChange", {}).get("m5", 0) or 0),
                            "price_change_1h": float(best_pair.get("priceChange", {}).get("h1", 0) or 0),
                            "price_change_24h": float(best_pair.get("priceChange", {}).get("h24", 0) or 0),
                            "created_at_ms": pair_created_at,
                            "discovered_at": time.time(),
                            "url": best_pair.get("url", f"https://dexscreener.com/{detected_chain}/{token_address}"),
                            "pair_data": best_pair
                        }
        except Exception as e:
            logger.debug(f"Failed fetching details for token {token_address}: {e}")
        return None

    async def fetch_token_prices(self, token_addresses: List[str]) -> Dict[str, float]:
        """Batch queries token prices from DexScreener with GeckoTerminal redundant fallback."""
        if not token_addresses:
            return {}
            
        session = await self._get_session()
        price_map: Dict[str, float] = {}
        missing_addresses = set(token_addresses)
        
        # Feed 1: DexScreener Batch Price Endpoint
        chunks = [token_addresses[i:i + 30] for i in range(0, len(token_addresses), 30)]
        for chunk in chunks:
            try:
                addresses_str = ",".join(chunk)
                url = f"https://api.dexscreener.com/latest/dex/tokens/{addresses_str}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        pairs = data.get("pairs", [])
                        for pair in pairs:
                            base_addr = pair.get("baseToken", {}).get("address")
                            price_usd = float(pair.get("priceUsd", 0) or 0)
                            if base_addr and price_usd > 0:
                                price_map[base_addr] = price_usd
                                price_map[base_addr.lower()] = price_usd
                                missing_addresses.discard(base_addr)
                                for orig in chunk:
                                    if orig.lower() == base_addr.lower():
                                        missing_addresses.discard(orig)
            except Exception as e:
                logger.debug(f"DexScreener batch price error: {e}")

        # Feed 2: GeckoTerminal Redundant Fallback for any unmapped tokens
        if missing_addresses:
            for net in ["solana", "base", "bsc"]:
                try:
                    addrs_str = ",".join(list(missing_addresses)[:30])
                    gecko_url = f"https://api.geckoterminal.com/api/v2/simple/networks/{net}/token_price/{addrs_str}"
                    async with session.get(gecko_url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            prices = data.get("data", {}).get("attributes", {}).get("token_prices", {})
                            for addr_k, price_v in prices.items():
                                p_float = float(price_v or 0)
                                if p_float > 0:
                                    price_map[addr_k] = p_float
                                    price_map[addr_k.lower()] = p_float
                                    for orig in list(missing_addresses):
                                        if orig.lower() == addr_k.lower():
                                            price_map[orig] = p_float
                                            missing_addresses.discard(orig)
                except Exception as e:
                    logger.debug(f"GeckoTerminal fallback price error on {net}: {e}")

        return price_map



scanner = MarketScanner()
