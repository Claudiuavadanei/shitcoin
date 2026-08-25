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
        """High-speed multi-chain discovery engine querying GeckoTerminal and DexScreener."""
        session = await self._get_session()
        discovered: List[Dict[str, Any]] = []

        # Feed 1: Top Liquid & Trending Raydium/DEX Pools Feed (Solana)
        active_chains = ["solana"] if config.trading_mode == "LIVE" else config.enabled_chains
        for chain in active_chains:
            network = "solana" if chain == "solana" else ("bsc" if chain == "bsc" else "base")
            endpoints = [
                f"https://api.geckoterminal.com/api/v2/networks/{network}/trending_pools",
                f"https://api.geckoterminal.com/api/v2/networks/{network}/pools",
                f"https://api.geckoterminal.com/api/v2/networks/{network}/new_pools"
            ]
            for ep in endpoints:
                try:
                    async with session.get(ep, timeout=aiohttp.ClientTimeout(total=3.5)) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            pools = data.get("data", [])
                            for pool in pools[:10]:
                                attr = pool.get("attributes", {})
                                base_token_id = pool.get("relationships", {}).get("base_token", {}).get("data", {}).get("id", "")
                                token_addr = base_token_id.split("_")[-1] if "_" in base_token_id else ""
                                if not token_addr or token_addr in self.seen_tokens:
                                    continue
                                
                                liquidity_usd = float(attr.get("reserve_in_usd", 0) or 0)
                                vol_dict = attr.get("volume_usd", {})
                                volume_24h = float(vol_dict.get("h24", vol_dict.get("h1", 0)) or 0)
                                
                                # Strict Quality Filter: Only Established Pools ($40k+ Liq & $15k+ Volume)
                                if liquidity_usd < config.min_liquidity_usd or volume_24h < (config.min_volume_usd * 0.5):
                                    continue

                                pair_addr = attr.get("address", "")
                                name_raw = attr.get("name", "Token / SOL")
                                symbol = name_raw.split(" / ")[0] if " / " in name_raw else name_raw
                                price_usd = float(attr.get("base_token_price_usd", 0) or 0)
                                dex_id = pool.get("relationships", {}).get("dex", {}).get("data", {}).get("id", "raydium")
                                
                                txns = attr.get("transactions", {}).get("h1", {})
                                buys = int(txns.get("buys", 0) or 0)
                                sells = int(txns.get("sells", 0) or 0)
                                
                                pool_info = {
                                    "token_address": token_addr,
                                    "name": symbol,
                                    "symbol": symbol,
                                    "chain": chain,
                                    "dex_id": dex_id,
                                    "pair_address": pair_addr,
                                    "price_usd": price_usd,
                                    "price_native": float(attr.get("base_token_price_native_currency", 0) or 0),
                                    "liquidity_usd": liquidity_usd,
                                    "volume_24h": volume_24h,
                                    "fdv": float(attr.get("fdv_usd", 0) or 0),
                                    "price_change_5m": float(attr.get("price_change_percentage", {}).get("m5", 0) or 0),
                                    "price_change_1h": float(attr.get("price_change_percentage", {}).get("h1", 0) or 0),
                                    "price_change_24h": float(attr.get("price_change_percentage", {}).get("h24", 0) or 0),
                                    "created_at_ms": int(time.time() * 1000) - (3600 * 1000),  # Established token
                                    "discovered_at": time.time(),
                                    "url": f"https://dexscreener.com/{chain}/{pair_addr}" if pair_addr else f"https://dexscreener.com/{chain}/{token_addr}",
                                    "pair_data": {
                                        "chainId": chain,
                                        "dexId": dex_id,
                                        "pairAddress": pair_addr,
                                        "baseToken": {"address": token_addr, "name": symbol, "symbol": symbol},
                                        "priceUsd": str(price_usd),
                                        "txns": {"h1": {"buys": buys, "sells": sells}, "m5": {"buys": buys, "sells": sells}},
                                        "volume": {"h24": volume_24h, "h1": volume_24h},
                                        "liquidity": {"usd": liquidity_usd}
                                    }
                                }
                                discovered.append(pool_info)
                except Exception as e:
                    logger.debug(f"GeckoTerminal endpoint error for {ep}: {e}")

        # Feed 2: DexScreener Profiles Fallback
        if len(discovered) < 3:
            try:
                url_profiles = "https://api.dexscreener.com/token-profiles/latest/v1"
                async with session.get(url_profiles, timeout=aiohttp.ClientTimeout(total=3.0)) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        if isinstance(data, list):
                            addrs = [item.get("tokenAddress") for item in data[:6] if item.get("tokenAddress") and item.get("tokenAddress") not in self.seen_tokens]
                            if addrs:
                                tasks = [self.fetch_token_details("", a) for a in addrs]
                                res_list = await asyncio.gather(*tasks, return_exceptions=True)
                                for res in res_list:
                                    if isinstance(res, dict) and res:
                                        if config.trading_mode == "LIVE" and res.get("chain") != "solana":
                                            continue
                                        if res.get("liquidity_usd", 0) >= config.min_liquidity_usd:
                                            discovered.append(res)

            except Exception as e:
                logger.debug(f"DexScreener profiles fallback error: {e}")


        return discovered


    async def fetch_token_details(self, chain: str, token_address: str) -> Optional[Dict[str, Any]]:
        """Fetches full pair metadata, liquidity, volume, and current price with multi-source fallback."""
        session = await self._get_session()
        # Source 1: DexScreener Token Pairs
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=6.5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        def get_pair_liq(p):
                            liq = p.get("liquidity") if isinstance(p, dict) else None
                            if isinstance(liq, dict):
                                return float(liq.get("usd", 0) or 0)
                            return 0.0

                        best_pair = max(pairs, key=get_pair_liq)
                        base_token = best_pair.get("baseToken", {}) if isinstance(best_pair, dict) else {}
                        price_usd = float(best_pair.get("priceUsd", 0) or 0)
                        price_native = float(best_pair.get("priceNative", 0) or 0)
                        liq_obj = best_pair.get("liquidity") if isinstance(best_pair, dict) else None
                        liquidity_usd = float(liq_obj.get("usd", 0) or 0) if isinstance(liq_obj, dict) else 0.0

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
            logger.debug(f"DexScreener detail query exception for {token_address}: {e}")

        # Source 2: GeckoTerminal Fallback
        try:
            url_gecko = f"https://api.geckoterminal.com/api/v2/networks/solana/tokens/{token_address}"
            async with session.get(url_gecko, timeout=aiohttp.ClientTimeout(total=5.0)) as g_resp:
                if g_resp.status == 200:
                    g_data = await g_resp.json(content_type=None)
                    attr = g_data.get("data", {}).get("attributes", {})
                    if attr:
                        price_usd = float(attr.get("price_usd", 0) or 0)
                        return {
                            "token_address": token_address,
                            "name": attr.get("name", "Unknown Token"),
                            "symbol": attr.get("symbol", "TOKEN"),
                            "chain": "solana",
                            "dex_id": "raydium",
                            "pair_address": "",
                            "price_usd": price_usd,
                            "price_native": 0.0,
                            "liquidity_usd": float(attr.get("total_reserve_in_usd", 10000.0) or 10000.0),
                            "volume_24h": float(attr.get("volume_usd", {}).get("h24", 0) or 0),
                            "fdv": float(attr.get("fdv_usd", 0) or 0),
                            "price_change_5m": 0.0,
                            "price_change_1h": 0.0,
                            "price_change_24h": 0.0,
                            "created_at_ms": int(time.time() * 1000),
                            "discovered_at": time.time(),
                            "url": f"https://dexscreener.com/solana/{token_address}",
                            "pair_data": {"chainId": "solana"}
                        }
        except Exception as e:
            logger.debug(f"GeckoTerminal fallback error for {token_address}: {e}")

        # Source 3: Direct Jupiter Routing Fallback (For ultra-fresh Raydium/Pump tokens)
        try:
            url_jup = f"https://api.jup.ag/swap/v1/quote?inputMint=So11111111111111111111111111111111111111112&outputMint={token_address}&amount=100000000&slippageBps=500&restrictIntermediateTokens=true"
            async with session.get(url_jup, timeout=aiohttp.ClientTimeout(total=5.0)) as j_resp:
                if j_resp.status == 200:
                    j_data = await j_resp.json(content_type=None)
                    out_amount = float(j_data.get("outAmount", 0) or 0)
                    if out_amount > 0:
                        usd_val = float(j_data.get("swapUsdValue", 9.6) or 9.6)
                        price_usd = (usd_val / out_amount) if out_amount > 0 else 0.000001
                        route_plan = j_data.get("routePlan", [])
                        dex_label = route_plan[0].get("swapInfo", {}).get("label", "Raydium") if route_plan else "Jupiter"
                        return {
                            "token_address": token_address,
                            "name": f"Solana Token ({dex_label})",
                            "symbol": "SOLANA",
                            "chain": "solana",
                            "dex_id": dex_label.lower(),
                            "pair_address": "",
                            "price_usd": price_usd,
                            "price_native": 0.0,
                            "liquidity_usd": 15000.0,
                            "volume_24h": 5000.0,
                            "fdv": 50000.0,
                            "price_change_5m": 0.0,
                            "price_change_1h": 0.0,
                            "price_change_24h": 0.0,
                            "created_at_ms": int(time.time() * 1000),
                            "discovered_at": time.time(),
                            "url": f"https://dexscreener.com/solana/{token_address}",
                            "pair_data": {"chainId": "solana", "dexId": dex_label}
                        }
        except Exception as e:
            logger.debug(f"Jupiter fallback error for {token_address}: {e}")

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
                        data = await resp.json(content_type=None)
                        pairs = data.get("pairs", [])
                        # Group pairs by baseToken address and pick only the HIGHEST liquidity pool
                        token_best_pairs: Dict[str, Dict[str, Any]] = {}
                        for pair in pairs:
                            base_addr = pair.get("baseToken", {}).get("address")
                            if not base_addr:
                                continue
                            liq_usd = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                            # Reject fake pools with 0 or negligible liquidity
                            if liq_usd < 200.0 and len(pairs) > 1:
                                continue
                            
                            curr_best = token_best_pairs.get(base_addr)
                            if not curr_best or liq_usd > float(curr_best.get("liquidity", {}).get("usd", 0) or 0):
                                token_best_pairs[base_addr] = pair

                        for base_addr, best_p in token_best_pairs.items():
                            price_usd = float(best_p.get("priceUsd", 0) or 0)
                            if price_usd > 0:
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
