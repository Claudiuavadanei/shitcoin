"""
Global Configuration & Runtime Settings for Crypto Sniper & Trading Bot
"""
import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

class BotConfig(BaseModel):
    # Server settings
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8080")))
    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))

    # Mode: Default to LIVE
    trading_mode: str = Field(default_factory=lambda: os.getenv("TRADING_MODE", "LIVE").upper())

    
    # Virtual balances for Paper Trading
    paper_balance_sol: float = Field(default_factory=lambda: float(os.getenv("PAPER_BALANCE_SOL", "10.0")))
    paper_balance_usd: float = Field(default_factory=lambda: float(os.getenv("PAPER_BALANCE_USD", "1500.0")))

    # Automation Switch
    auto_buy_enabled: bool = Field(default_factory=lambda: os.getenv("AUTO_BUY_ENABLED", "false").lower() == "true")
    scanner_active: bool = True
    
    # Position Sizing (Calibrated for strict capital preservation)
    buy_amount_sol: float = Field(default_factory=lambda: float(os.getenv("BUY_AMOUNT_SOL", "0.03")))
    buy_amount_usd: float = Field(default_factory=lambda: float(os.getenv("BUY_AMOUNT_USD", "3.0")))
    min_wallet_sol_reserve: float = Field(default_factory=lambda: float(os.getenv("MIN_WALLET_SOL_RESERVE", "0.5")))
    max_open_positions: int = Field(default_factory=lambda: int(os.getenv("MAX_OPEN_POSITIONS", "10")))
    max_slippage_percent: float = 3.0


    # Profit & Risk Strategy (Targets optimized for 70%+ Win Rate)
    take_profit_percent: float = Field(default_factory=lambda: float(os.getenv("TAKE_PROFIT_PERCENT", "18.0")))
    break_even_enabled: bool = Field(default_factory=lambda: os.getenv("BREAK_EVEN_ENABLED", "true").lower() == "true")
    break_even_trigger_percent: float = Field(default_factory=lambda: float(os.getenv("BREAK_EVEN_TRIGGER_PERCENT", "4.0")))
    break_even_offset_percent: float = Field(default_factory=lambda: float(os.getenv("BREAK_EVEN_OFFSET_PERCENT", "1.0")))
    trailing_stop_enabled: bool = Field(default_factory=lambda: os.getenv("TRAILING_STOP_ENABLED", "true").lower() == "true")
    trailing_stop_offset_percent: float = Field(default_factory=lambda: float(os.getenv("TRAILING_STOP_OFFSET_PERCENT", "4.0")))
    stop_loss_percent: float = Field(default_factory=lambda: float(os.getenv("STOP_LOSS_PERCENT", "8.0")))
    max_hold_time_minutes: int = Field(default_factory=lambda: int(os.getenv("MAX_HOLD_TIME_MINUTES", "45")))

    # Safety & Anti-Rug Thresholds (Calibrated for safe Solana trading)
    min_liquidity_usd: float = Field(default_factory=lambda: float(os.getenv("MIN_LIQUIDITY_USD", "35000.0")))
    min_volume_usd: float = Field(default_factory=lambda: float(os.getenv("MIN_VOLUME_USD", "1500.0")))
    max_dev_holding_percent: float = Field(default_factory=lambda: float(os.getenv("MAX_DEV_HOLDING_PERCENT", "15.0")))
    max_buy_tax_percent: float = Field(default_factory=lambda: float(os.getenv("MAX_BUY_TAX_PERCENT", "5.0")))
    max_sell_tax_percent: float = Field(default_factory=lambda: float(os.getenv("MAX_SELL_TAX_PERCENT", "5.0")))
    min_safety_score: int = Field(default_factory=lambda: int(os.getenv("MIN_SAFETY_SCORE", "85")))
    
    # AI Market Intelligence & Smart Assistant Settings
    ai_filtering_enabled: bool = Field(default_factory=lambda: os.getenv("AI_FILTERING_ENABLED", "true").lower() == "true")
    min_ai_confidence: int = Field(default_factory=lambda: int(os.getenv("MIN_AI_CONFIDENCE", "85")))
    ai_smart_exit_enabled: bool = Field(default_factory=lambda: os.getenv("AI_SMART_EXIT_ENABLED", "true").lower() == "true")
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))



    # Chains to scan (Only solana when live trading with Solana wallet)
    enabled_chains: list[str] = Field(default_factory=lambda: [c.strip() for c in os.getenv("ENABLED_CHAINS", "solana").split(",") if c.strip()])


    # Solana Live Execution & MEV Infrastructure
    solana_rpc_url: str = Field(default_factory=lambda: os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"))
    solana_ws_url: str = Field(default_factory=lambda: os.getenv("SOLANA_WS_URL", "wss://api.mainnet-beta.solana.com"))
    solana_private_key: str = Field(default_factory=lambda: os.getenv("SOLANA_PRIVATE_KEY", ""))
    
    # Jito MEV Bundle Settings (Dynamic Tip Floor Support)
    jito_mev_enabled: bool = Field(default_factory=lambda: os.getenv("JITO_MEV_ENABLED", "true").lower() == "true")
    jito_tip_sol: float = Field(default_factory=lambda: float(os.getenv("JITO_TIP_SOL", "0.001")))
    min_jito_tip_sol: float = Field(default_factory=lambda: float(os.getenv("MIN_JITO_TIP_SOL", "0.0001")))
    max_jito_tip_sol: float = Field(default_factory=lambda: float(os.getenv("MAX_JITO_TIP_SOL", "0.005")))
    jito_tip_percentile: int = Field(default_factory=lambda: int(os.getenv("JITO_TIP_PERCENTILE", "50")))
    jito_tip_floor_url: str = Field(default_factory=lambda: os.getenv("JITO_TIP_FLOOR_URL", "https://bundles.jito.wtf/api/v1/bundles/tip_floor"))
    jito_block_engine_url: str = Field(default_factory=lambda: os.getenv("JITO_BLOCK_ENGINE_URL", "https://mainnet.block-engine.jito.wtf"))
    
    # Dynamic Priority Fees & Slippage
    dynamic_priority_fee_enabled: bool = Field(default_factory=lambda: os.getenv("DYNAMIC_PRIORITY_FEE_ENABLED", "true").lower() == "true")
    priority_fee_timeout_ms: int = Field(default_factory=lambda: int(os.getenv("PRIORITY_FEE_TIMEOUT_MS", "350")))
    max_priority_fee_micro_lamports: int = Field(default_factory=lambda: int(os.getenv("MAX_PRIORITY_FEE_MICRO_LAMPORTS", "250000")))
    min_priority_fee_micro_lamports: int = Field(default_factory=lambda: int(os.getenv("MIN_PRIORITY_FEE_MICRO_LAMPORTS", "25000")))
    max_slippage_percent: float = Field(default_factory=lambda: float(os.getenv("MAX_SLIPPAGE_PERCENT", "3.5")))
    
    # Token-2022 Anti-Rug Scanner & Network Resiliency
    token_2022_tax_check: bool = Field(default_factory=lambda: os.getenv("TOKEN_2022_TAX_CHECK", "true").lower() == "true")
    tx_retry_limit: int = Field(default_factory=lambda: int(os.getenv("TX_RETRY_LIMIT", "5")))
    tx_confirm_timeout_sec: int = Field(default_factory=lambda: int(os.getenv("TX_CONFIRM_TIMEOUT_SEC", "8")))

    # EVM Live Settings (Optional)
    evm_rpc_url: str = Field(default_factory=lambda: os.getenv("EVM_RPC_URL", "https://bsc-dataseed.binance.org/"))
    evm_private_key: str = Field(default_factory=lambda: os.getenv("EVM_PRIVATE_KEY", ""))

# Global Singleton Config Instance
config = BotConfig()


