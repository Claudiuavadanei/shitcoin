"""
Anti-Rug & Token Safety Screener
Analyzes token contracts, liquidity locks, mint/freeze authorities, holder distributions, and tax rates.
"""
import aiohttp
import asyncio
import logging
from typing import Dict, Any, List, Optional
from config import config

logger = logging.getLogger("SafetyChecker")

class SafetyChecker:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=8),
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
        return self.session

    async def check_token(self, chain: str, token_address: str, pair_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Comprehensive anti-rug audit for a token on Solana or EVM (BSC, Base, Ethereum).
        Returns detailed safety report with 0-100 safety score.
        """
        chain_lower = chain.lower()
        
        if chain_lower == "solana":
            return await self._check_solana_token(token_address, pair_data)
        else:
            return await self._check_evm_token(chain_lower, token_address, pair_data)

    async def _check_solana_token(self, token_address: str, pair_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        session = await self._get_session()
        flags = []
        warnings = []
        
        # Default baseline scores & stats
        mint_auth_disabled = True
        freeze_auth_disabled = True
        lp_burned_pct = 100.0
        top10_holding_pct = 15.0
        dev_holding_pct = 3.0
        buy_tax = 0.0
        sell_tax = 0.0
        liquidity_usd = 0.0
        volume_usd = 0.0

        if pair_data:
            liquidity_usd = float(pair_data.get("liquidity", {}).get("usd", 0) or 0)
            volume_usd = float(pair_data.get("volume", {}).get("h24", 0) or 0)
            
            # Check dex info
            dex_id = pair_data.get("dexId", "").lower()
            if "pump" in dex_id:
                # Pump.fun tokens have no mint/freeze auth and standard mechanics
                mint_auth_disabled = True
                freeze_auth_disabled = True
                lp_burned_pct = 100.0
                flags.append("Pump.fun launch (Fixed Supply, No Mint/Freeze)")

        # Query RugCheck API for Solana tokens
        try:
            url = f"https://api.rugcheck.xyz/v1/tokens/{token_address}/report"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    
                    # Mint authority
                    mint_auth = data.get("token", {}).get("mintAuthority")
                    mint_auth_disabled = (mint_auth is None)
                    if not mint_auth_disabled:
                        warnings.append("Mint Authority is ACTIVE (Dev can mint more tokens!)")
                    
                    # Freeze authority
                    freeze_auth = data.get("token", {}).get("freezeAuthority")
                    freeze_auth_disabled = (freeze_auth is None)
                    if not freeze_auth_disabled:
                        warnings.append("Freeze Authority is ACTIVE (Dev can freeze user wallets!)")
                        
                    # Top holders
                    top_holders = data.get("topHolders", [])
                    if top_holders:
                        top10_sum = sum(h.get("pct", 0) for h in top_holders[:10])
                        top10_holding_pct = round(top10_sum, 2)
                        if top_holders:
                            dev_holding_pct = round(top_holders[0].get("pct", 0), 2)
                            
                    # LP lock/burn
                    markets = data.get("markets", [])
                    if markets:
                        lp_data = markets[0].get("lp", {})
                        lp_burned_pct = float(lp_data.get("lpLockedPct", 0) or lp_data.get("lpBurnedPct", 0) or 100)
                        
                    # RugCheck risks
                    risks = data.get("risks", [])
                    for r in risks:
                        r_name = r.get("name", "")
                        r_level = r.get("level", "")
                        if r_level in ["danger", "warn"]:
                            warnings.append(f"{r_name} ({r.get('description', '')})")
                else:
                    flags.append("RugCheck API report unavailable (using DEX pair heuristics)")
        except Exception as e:
            logger.debug(f"RugCheck lookup failed for {token_address}: {e}")
            flags.append("Heuristic evaluation active")

        # Query Solana RPC for Token-2022 extensions & hidden transfer fee tax check
        is_token_2022 = False
        token_2022_tax_pct = 0.0
        has_permanent_delegate = False
        if config.token_2022_tax_check:
            try:
                rpc_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getAccountInfo",
                    "params": [
                        token_address,
                        {"encoding": "jsonParsed", "commitment": "confirmed"}
                    ]
                }
                async with session.post(config.solana_rpc_url, json=rpc_payload, timeout=aiohttp.ClientTimeout(total=2.0)) as rpc_resp:
                    if rpc_resp.status == 200:
                        rpc_data = await rpc_resp.json(content_type=None)
                        val = rpc_data.get("result", {}).get("value")
                        if val:
                            owner = val.get("owner", "")
                            if owner == "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb":
                                is_token_2022 = True
                                flags.append("Token-2022 Standard Mint")
                                parsed_data = val.get("data", {}).get("parsed", {}).get("info", {})
                                extensions = parsed_data.get("extensions", [])
                                for ext in extensions:
                                    ext_type = ext.get("extension")
                                    ext_state = ext.get("state", {})
                                    if ext_type == "transferFeeConfig":
                                        fee_bps = int(ext_state.get("newerTransferFee", {}).get("transferFeeBasisPoints", 0) or ext_state.get("olderTransferFee", {}).get("transferFeeBasisPoints", 0) or 0)
                                        token_2022_tax_pct = fee_bps / 100.0
                                        if token_2022_tax_pct > 0:
                                            warnings.append(f"🚨 Token-2022 Transfer Fee Active (Tax: {token_2022_tax_pct}%)")
                                            buy_tax = max(buy_tax, token_2022_tax_pct)
                                            sell_tax = max(sell_tax, token_2022_tax_pct)
                                    elif ext_type == "permanentDelegate":
                                        has_permanent_delegate = True
                                        warnings.append("🚨 Token-2022 Permanent Delegate (Dev can burn/confiscate tokens)")
                                    elif ext_type == "defaultAccountState":
                                        if ext_state.get("accountState") == "frozen":
                                            warnings.append("🚨 Token-2022 Default Frozen (Buyer tokens auto-locked)")
            except Exception as e:
                logger.debug(f"Token-2022 RPC lookup exception for {token_address}: {e}")


        # Evaluate Safety Score (0 to 100)
        score = 100
        
        if not mint_auth_disabled:
            score -= 35
        if not freeze_auth_disabled:
            score -= 30
        if token_2022_tax_pct > 0:
            score -= 50
        if has_permanent_delegate:
            score -= 40
        if dev_holding_pct > config.max_dev_holding_percent:
            penalty = min(25, int((dev_holding_pct - config.max_dev_holding_percent) * 1.5))
            score -= penalty
            warnings.append(f"Top holder has {dev_holding_pct}% of supply (> {config.max_dev_holding_percent}%)")
        if top10_holding_pct > 50.0:
            score -= 15
            warnings.append(f"Top 10 holders control {top10_holding_pct}% of supply")
        if lp_burned_pct < 80.0:
            score -= 20
            warnings.append(f"Only {lp_burned_pct}% LP locked/burned")
        if liquidity_usd < config.min_liquidity_usd:
            score -= 15
            warnings.append(f"Low Liquidity: ${liquidity_usd:,.0f} (< ${config.min_liquidity_usd:,.0f})")
        if volume_usd < config.min_volume_usd:
            score -= 10
            warnings.append(f"Low Volume: ${volume_usd:,.0f} (< ${config.min_volume_usd:,.0f})")

        score = max(0, min(100, score))
        
        # Risk assessment status
        if score >= 80:
            risk_level = "SAFE"
        elif score >= 60:
            risk_level = "MODERATE"
        elif score >= 40:
            risk_level = "HIGH_RISK"
        else:
            risk_level = "DANGEROUS"

        passed = (
            score >= config.min_safety_score
            and mint_auth_disabled
            and freeze_auth_disabled
            and token_2022_tax_pct <= config.max_buy_tax_percent
            and not has_permanent_delegate
            and dev_holding_pct <= (config.max_dev_holding_percent * 1.5)
            and liquidity_usd >= config.min_liquidity_usd
        )


        return {
            "token_address": token_address,
            "chain": "solana",
            "safety_score": score,
            "risk_level": risk_level,
            "passed_filters": passed,
            "mint_auth_disabled": mint_auth_disabled,
            "freeze_auth_disabled": freeze_auth_disabled,
            "lp_burned_pct": lp_burned_pct,
            "top10_holding_pct": top10_holding_pct,
            "dev_holding_pct": dev_holding_pct,
            "buy_tax_pct": buy_tax,
            "sell_tax_pct": sell_tax,
            "liquidity_usd": liquidity_usd,
            "volume_usd": volume_usd,
            "warnings": warnings,
            "flags": flags
        }

    async def _check_evm_token(self, chain: str, token_address: str, pair_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        session = await self._get_session()
        flags = []
        warnings = []
        
        chain_ids = {
            "bsc": "56",
            "base": "8453",
            "ethereum": "1",
            "arbitrum": "42161",
            "polygon": "137"
        }
        chain_id = chain_ids.get(chain, "56")
        
        mint_auth_disabled = True
        lp_burned_pct = 95.0
        top10_holding_pct = 20.0
        dev_holding_pct = 4.0
        buy_tax = 0.0
        sell_tax = 0.0
        is_honeypot = False
        liquidity_usd = 0.0
        volume_usd = 0.0

        if pair_data:
            liquidity_usd = float(pair_data.get("liquidity", {}).get("usd", 0) or 0)
            volume_usd = float(pair_data.get("volume", {}).get("h24", 0) or 0)

        # Query GoPlus Security API for EVM
        try:
            url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={token_address.lower()}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
                if resp.status == 200:
                    res = await resp.json(content_type=None)

                    result = res.get("result", {}).get(token_address.lower(), {})
                    if result:
                        is_honeypot = result.get("is_honeypot") == "1"
                        buy_tax = float(result.get("buy_tax", 0) or 0) * 100
                        sell_tax = float(result.get("sell_tax", 0) or 0) * 100
                        
                        is_mintable = result.get("is_mintable") == "1"
                        mint_auth_disabled = not is_mintable
                        if is_mintable:
                            warnings.append("Contract is MINTABLE (Dev can create infinite tokens)")
                            
                        is_proxy = result.get("is_proxy") == "1"
                        if is_proxy:
                            warnings.append("Contract is an Upgradable PROXY")
                            
                        cannot_sell_all = result.get("cannot_sell_all") == "1"
                        if cannot_sell_all:
                            warnings.append("Contract prevents selling 100% of tokens (Partial Honeypot)")
                            
                        if is_honeypot:
                            warnings.append("CRITICAL: Token is identified as a HONEYPOT (Cannot Sell)!")
                            
                        holders = result.get("holders", [])
                        if holders:
                            top10_sum = sum(float(h.get("percent", 0) or 0) * 100 for h in holders[:10])
                            top10_holding_pct = round(top10_sum, 2)
                            if holders:
                                dev_holding_pct = round(float(holders[0].get("percent", 0) or 0) * 100, 2)
                        
                        lp_holders = result.get("lp_holders", [])
                        if lp_holders:
                            # Locked / burned LP estimation
                            burn_sum = sum(float(h.get("percent", 0) or 0) * 100 for h in lp_holders if h.get("is_locked") == 1 or "dead" in h.get("address", "").lower() or "0x000" in h.get("address", "").lower())
                            lp_burned_pct = round(burn_sum, 2) if burn_sum > 0 else 90.0
                else:
                    flags.append("GoPlus API unavailable (using heuristic safety checks)")
        except Exception as e:
            logger.debug(f"GoPlus check error for {token_address}: {e}")
            flags.append("Heuristic evaluation active")

        # Score calculation
        score = 100
        if is_honeypot:
            score = 0
            warnings.append("CONFIRMED HONEYPOT")
        
        if buy_tax > config.max_buy_tax_percent:
            score -= int((buy_tax - config.max_buy_tax_percent) * 2)
            warnings.append(f"High Buy Tax: {buy_tax:.1f}% (> {config.max_buy_tax_percent}%)")
            
        if sell_tax > config.max_sell_tax_percent:
            score -= int((sell_tax - config.max_sell_tax_percent) * 3)
            warnings.append(f"High Sell Tax: {sell_tax:.1f}% (> {config.max_sell_tax_percent}%)")

        if not mint_auth_disabled:
            score -= 30
            
        if dev_holding_pct > config.max_dev_holding_percent:
            score -= min(25, int((dev_holding_pct - config.max_dev_holding_percent) * 1.5))
            warnings.append(f"Top holder controls {dev_holding_pct}% of supply")

        if liquidity_usd < config.min_liquidity_usd:
            score -= 15
            warnings.append(f"Low Liquidity: ${liquidity_usd:,.0f}")
            
        if volume_usd < config.min_volume_usd:
            score -= 10
            warnings.append(f"Low Volume: ${volume_usd:,.0f}")

        score = max(0, min(100, score))
        
        if score >= 80:
            risk_level = "SAFE"
        elif score >= 60:
            risk_level = "MODERATE"
        elif score >= 40:
            risk_level = "HIGH_RISK"
        else:
            risk_level = "DANGEROUS"

        passed = (
            score >= config.min_safety_score
            and not is_honeypot
            and buy_tax <= config.max_buy_tax_percent
            and sell_tax <= config.max_sell_tax_percent
            and liquidity_usd >= config.min_liquidity_usd
        )

        return {
            "token_address": token_address,
            "chain": chain,
            "safety_score": score,
            "risk_level": risk_level,
            "passed_filters": passed,
            "mint_auth_disabled": mint_auth_disabled,
            "freeze_auth_disabled": True,
            "lp_burned_pct": lp_burned_pct,
            "top10_holding_pct": top10_holding_pct,
            "dev_holding_pct": dev_holding_pct,
            "buy_tax_pct": buy_tax,
            "sell_tax_pct": sell_tax,
            "liquidity_usd": liquidity_usd,
            "volume_usd": volume_usd,
            "warnings": warnings,
            "flags": flags
        }

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

safety_checker = SafetyChecker()
