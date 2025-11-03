# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an experimental AI trading system that orchestrates 48+ specialized AI agents to analyze markets, execute strategies, and manage risk across cryptocurrency markets (primarily Solana). The project uses a modular agent architecture with unified LLM provider abstraction supporting Claude, GPT-4, DeepSeek, Groq, Gemini, and local Ollama models.

## ⭐ Primary Focus: Revival Scanner

**The main active project is the Revival Scanner** - a specialized system that identifies "second life" meme coin opportunities 72+ hours after launch using a 3-API hybrid architecture.

## Recent Changes (Last 30 Days)

### November 2025 - Paper Trading System

**New Feature: Comprehensive Paper Trading Simulation**
- **Purpose**: Track Revival Scanner performance over time with realistic execution simulation
- **Auto-execution**: Opens positions automatically when scanner finds tokens with score ≥ 0.4
- **Exit Strategy**: Multi-level take-profit (35% @ 40% sell, 75% @ 30% sell) + 20% stop-loss
- **Simulation**: Models Jupiter DEX fees (0.06%), slippage (2-10%), failed exits (5% chance)
- **Monitoring**: Background thread checks prices every 30 seconds, triggers exits automatically
- **Email Notifications**: Position open/close alerts with P&L details (Gmail SMTP)
- **Web Dashboard**: Dedicated Paper Trading tab with auto-refresh, flash animations, badges
- **LLM Insights**: AI-generated performance analysis using trade history

**Key Files:**
- `src/paper_trading/position_manager.py` - Core position lifecycle with CSV persistence
- `src/paper_trading/performance_analyzer.py` - Metrics calculation and LLM insights
- `src/paper_trading/email_notifier.py` - Gmail email notifications
- `src/agents/paper_trading_agent.py` - Main agent integrating with orchestrator
- Web UI: Added Paper Trading tab to `src/web_templates/index.html`

**Configuration** (src/config.py lines 120-164):
- `PAPER_TRADING_ENABLED = True` - Enable/disable paper trading
- `PAPER_TRADING_INITIAL_BALANCE = 10000` - $10K starting capital
- `PAPER_TRADING_POSITION_SIZE_USD = 1000` - $1K per trade
- `PAPER_TRADING_MAX_POSITIONS = 10` - Concurrent position limit
- `PAPER_TRADING_MIN_REVIVAL_SCORE = 0.4` - Aligned with scanner threshold
- Email settings: `PAPER_TRADING_EMAIL_ADDRESS`, `EMAIL_PASSWORD` in .env

**Data Persistence:**
- All data stored in CSV files: `src/data/paper_trading/`
  - `positions.csv` - Active positions (reloaded on restart)
  - `trades_history.csv` - Closed trades
  - `portfolio_snapshots.csv` - Portfolio value over time
- Survives server restarts - background monitoring resumes automatically

**Dashboard Features:**
- Portfolio summary (total value, cash balance, P&L, open positions)
- Active positions table (entry price, current price, P&L, remaining %)
- Trade history with color-coded exit badges (stop-loss, take-profit, failed, expired)
- Flash animations on new trades (green for profit, red for loss)
- Auto-refresh every 2 minutes when tab is active
- Performance metrics (win rate, profit factor, Sharpe ratio, max drawdown)

### October 2025 - Revival Scanner Optimizations

**Configuration Updates:**
- `MIN_AGE_HOURS`: 24h → **72h** (3 days - avoid early pump chaos)
- `MIN_VOLUME_1H`: $15K → **$500** (catch smaller revivals)
- `MAX_MARKET_CAP`: $20M → **$30M** (more room to grow)
- `HOLDER_CONCENTRATION_THRESHOLD`: 70% → **30%** (much tighter safety)

**Architecture Improvements:**
- **Native Meme List Bug Fix**: Fixed data.items vs data.tokens response structure
- **Increased Coverage**: Now fetches 1800-2000 pure memecoins (up from 400)
- **Liquidity Sorting**: Pass 1 prioritizes highest-liquidity tokens for safety
- **Social Sentiment Scoring**: New 10% weight using BirdEye on-chain metrics (no Twitter API needed)
- **Scoring Rebalance**: 50/30/20 → **60/15/15/10** (price/smart/volume/social)

**Result**: 100% pure memecoins, 4-5x better coverage, tighter safety filters

### Why Revival Trading vs Fresh Launches:
- **Lower Competition**: Not competing with sniper bots for 0-12 hour tokens
- **Better Risk/Reward**: Tokens already survived initial rug pull window
- **FREE APIs**: Works within free tier limits (BirdEye, Helius, DexScreener)
- **Higher Win Rate**: 30-40% vs 10-20% for fresh launches
- **Sustainable**: Pattern-based approach, not speed-based
- **No Maximum Age**: Revivals can happen at any time (removed 72h limit)

### Revival Scanner Architecture (5-Phase Pipeline)

The system uses a **5-phase pipeline**: 3 discovery phases to find candidate tokens, then 2 analysis phases to score and filter them.

**DISCOVERY PIPELINE (Phases 1-3):**

**Phase 1: BirdEye Native Meme Token Discovery**
- Uses `/defi/v3/token/meme/list` endpoint - guaranteed pure memecoins
- BirdEye has 5000+ memecoins available, supports liquidity sorting
- **Single Pass**: Top 2000 tokens sorted by liquidity - highest-liquidity, safest memecoins
- **Result**: ~2000 tokens, 100% pure memecoins (no keyword filtering needed!)
- Liquidity range: $20K-$17M, with 84% in the $20K-$100K revival sweet spot
- Covers pump.fun, Moonshot, Raydium, bonk.fun, and all major meme launchpads

**Phase 2: BirdEye Enhanced Pre-Filter**
- **Liquidity Filter**: Minimum $20K (from BirdEye `liquidity` field)
- **Market Cap Filter**: Maximum **$30M** (from BirdEye `mc` field)
- **Volume Filter**: Minimum $5K 1-hour volume (**NOTE: estimated as `volume_24h / 24`, not actual 1h data**)
- All filters use BirdEye data from Phase 1 - **no additional API calls**
- No memecoin detection needed (Phase 1 guarantees memecoins)
- **Result**: ~150-200 high-quality tokens ready for age check

**Phase 3: Helius Blockchain Age Verification**
- **Minimum age: 72 hours** (3 days - avoid early pump chaos)
- **Maximum age: 180 days** (6 months) - prevents analyzing years-old tokens
- Uses `src/helius_utils.py` with RPC calls: `getSignaturesForAddress` + `getTransaction`
- **Cost**: 2 RPC calls per token (2 Helius credits per token)
- **Rate limit**: 10 req/sec on Helius free tier (enforced with 0.1s delays)
- **Result**: Tokens in the 72h-6month "revival window"

**~~Old Phases 4 & 5: DexScreener Filters & Enrichment~~ REMOVED**
- **Why removed**: Redundant - already have liquidity/volume/market cap from BirdEye (Phase 2)
- **Social data**: Now calculated from BirdEye on-chain metrics (no DexScreener needed)
- **Benefit**: 200+ fewer API calls, faster execution, single source of truth

**ANALYSIS PIPELINE (Phases 4-5):**

**Phase 4: Security Filter**
- Stage 1 security filter removes scams via `stage1_security_filter.py`
- **GoPlus API**: Honeypot detection, mintability check, blacklist, ownership freeze
- **Holder distribution analysis**: Rejects if top 10 holders own **>30%** (via BirdEye `/defi/v3/token/holder`)
- Concurrent processing with ThreadPoolExecutor (up to 3 workers)

⚠️ **CRITICAL SECURITY BEHAVIOR:**

The security filter has a **"fail-open"** design - if GoPlus API is down or times out, tokens **PASS security checks by default** to avoid blocking the entire pipeline. This is intentional but means:

- **Monitor GoPlus API health** in error logs regularly
- **Verify API is working** before relying on security filter results
- **Consider manual review** for high-value opportunities
- **Check security_filter_*.json** outputs in `src/data/security_filter/` periodically

If GoPlus consistently fails, your security filter is effectively **disabled**. This is a known trade-off to keep the scanner running, but you should be aware of it. See Common Pitfalls #12 for details.

**Phase 5: Revival Pattern Detection**
- Handled by `revival_detector_agent.py`
- **Price pattern analysis**: Analyzes COMPLETE token history (not just recent 3 days)
  - Finds all-time high, floor, and current recovery across entire token lifetime
  - **Adaptive timeframe selection** (automatically adjusts based on token age):
    - **< 41 days old**: 1-hour candles (detailed short-term patterns)
    - **41-166 days old**: 4-hour candles (medium-term trends)
    - **> 166 days old**: 1-day candles (long-term perspective)
    - This prevents noise in analysis and matches token maturity stage
  - Detects "dump-floor-recovery" pattern (price fell to floor, now recovering)
- **Smart money analysis**: Via BirdEye `/defi/v2/tokens/top_traders` endpoint
  - Whale wallet detection (>$100K holdings)
  - Tracks top trader entry/exit patterns
- **Social sentiment scoring** (10% weight):
  - On-chain metrics: `uniqueWallet24h`, `watch`, `view24h`, `buy_percentage`
  - No Twitter API needed - uses BirdEye's on-chain data
- **Weighted scoring formula**: **60% price pattern + 15% smart money + 15% volume + 10% social**
- **Caching**: 5-minute cache in `RevivalDetectorAgent` to reduce redundant API calls

### Key Components:
- **Core Agents**: `revival_detector_agent.py`, `meme_scanner_orchestrator.py`, `stage1_security_filter.py`, `meme_notifier_agent.py`
- **Utility Modules**: `src/helius_utils.py`, `src/dexscreener_utils.py`
- **Web Dashboard**: `web_app.py` at http://localhost:8080 (port 8080, not 5000)
- **Documentation**:
  - `REVIVAL_SCANNER_PRD.md` - Complete strategy and product requirements
  - `QUICK_START_WEBAPP.md` - Get the web dashboard running in 2 minutes
  - `WEBAPP_README.md` - Full web dashboard feature documentation
  - `DASHBOARD_GUIDE.md` - Dashboard navigation and interpretation guide
  - `COMPLETE_SYSTEM_GUIDE.md` - End-to-end system architecture documentation
- **Quick Start**: Run `./start_webapp.sh` to launch the web dashboard

### Running Revival Scanner:
```bash
# Start web dashboard (auto-scans every 1 hour with paper trading)
./start_webapp.sh

# Run single scan manually (for testing)
PYTHONPATH=/Users/eamonblackwell/Meme\ Coin\ Trading\ Bot/moon-dev-ai-agents python3 src/agents/meme_scanner_orchestrator.py --once

# Test email notifications (optional)
python src/paper_trading/email_notifier.py

# View paper trading performance
python src/paper_trading/performance_analyzer.py
```

### API Requirements:
- **BirdEye API**: Native meme list, OHLCV, token overview, top traders, holder distribution (set `BIRDEYE_API_KEY` in .env)
  - All endpoints fully integrated with BirdEye Standard tier
  - Token Overview: `/defi/token_overview` - comprehensive metrics in one call
  - Top Traders: `/defi/v2/tokens/top_traders` - smart money analysis
  - Holder Distribution: `/defi/v3/token/holder` - concentration risk
  - Meme List: `/defi/v3/token/meme/list` - guaranteed pure memecoins
- **Helius RPC**: Blockchain age verification (set `HELIUS_RPC_ENDPOINT` in .env)
- **DexScreener**: NOT USED in primary pipeline (kept as fallback utility only)

### Critical Implementation Details

**BirdEye Native Meme List API:**
- **Response Structure**: Uses `data.items` (NOT `data.tokens` like generic tokenlist)
- **No Success Field**: API doesn't return `success: true/false`, check for empty items instead
- **Pagination**: 50 tokens per page, 5000+ tokens available total
- **Sorting Support**: Liquidity sorting works (`sort_by=liquidity`), volume/price sorting returns 400 errors
- **Rate Limiting**: 1 request/second (BirdEye Standard tier) - enforced with `time.sleep(1.0)`

**Optimal Phase 1 Pattern (UPDATED - Single Pass Top 2000):**
```python
# Single Pass: Top 2000 tokens by liquidity (optimized for revival trading)
# Result: 2000 tokens with $20K-$17M liquidity range
# - 1,681 tokens (84%) in $20K-$100K revival sweet spot
# - 100% pass the $20K liquidity filter (vs 8-15% with old dual-pass)
# - No dead tokens (old Pass 2 offset 1000 had mostly $0-$10K liquidity)
get_birdeye_meme_tokens(tokens_to_fetch=2000, sort_by='liquidity', start_offset=0)
```

**OLD Dual-Pass Strategy (DEPRECATED - DO NOT USE):**
```python
# This strategy was REPLACED in October 2025 - kept here for historical reference only
# OLD approach used two separate API calls with different strategies:

# OLD Pass 1: High-liquidity memecoins (too high, $100K+ minimum)
# get_birdeye_meme_tokens(tokens_to_fetch=1000, sort_by='liquidity', start_offset=0)

# OLD Pass 2: Sequential memecoins (mostly dead, $0-$10K liquidity)
# get_birdeye_meme_tokens(tokens_to_fetch=1000, sort_by=None, start_offset=1000)

# PROBLEM: Pass 2 fetched from unsorted list offset 1000, which contained
# mostly dead tokens with near-zero liquidity. 85-92% failed Phase 2 filter.

# CURRENT APPROACH: Single pass with top 2000 by liquidity (see above)
```

**API Response Field Mapping (Inconsistencies):**
```python
# BirdEye Native Meme List uses different field names than generic tokenlist:
liquidity = token_data.get('liquidity')      # Direct field (already a number)
volume_24h = token_data.get('volume_24h_usd')  # Note: _usd suffix
market_cap = token_data.get('market_cap')     # vs 'mc' in generic list

# DexScreener has nested structure:
liquidity = pair['liquidity']['usd']          # Nested under liquidity object
volume_24h = pair['volume']['h24']            # Nested under volume object
```

**Rate Limiting Strategy:**
- **BirdEye Standard**: 1 req/sec → `time.sleep(1.0)` between pages
- **Helius Free**: 10 req/sec → `time.sleep(0.1)` in batch operations
- **DexScreener Free**: 5 req/sec → `time.sleep(0.2)` in batch enrichment
- **Retry Logic**: Only implemented in `groq_model.py` with exponential backoff
- **HTTP 429 Handling**: BirdEye calls wait 60 seconds and retry once

### Legacy Agents (Not Actively Developed):
- `sniper_agent.py` - Fresh launch sniper (0-12 hours) - **Replaced by Revival Scanner**
- `solana_agent.py` - Coordinates sniper/tx agents - **Replaced by Revival Scanner**
- Old PRDs archived as `ARCHIVED_FRESH_LAUNCH_PRD.md` and `ARCHIVED_FRESH_LAUNCH_IMPLEMENTATION.md`

**When working on meme coin trading features, default to the Revival Scanner BirdEye-first approach unless specifically asked to work on legacy sniper agents.**

### Important BirdEye Integration Notes:
- **Always use BirdEye APIs first** for Revival Scanner features (token overview, top traders, holders)
- **DexScreener is fallback only** - use when BirdEye data unavailable
- **Token age** comes from BirdEye Token Overview `creationTime` field (Unix timestamp)
- **Smart money** uses Top Traders endpoint, not GMGN (GMGN completely removed)
- **Holder safety** checks via holder distribution endpoint (reject if top 10 **>30%**, tightened from 70%)
- **Native meme list** eliminates need for keyword filtering - all tokens are guaranteed memecoins
- **Social sentiment** uses BirdEye on-chain metrics (`uniqueWallet24h`, `watch`, `view24h`, `buy_percentage`) - no Twitter API needed

## Key Development Commands

### Environment Setup
```bash
# Use existing conda environment (DO NOT create new virtual environments)
conda activate tflow

# Install/update dependencies
pip install -r requirements.txt

# IMPORTANT: Update requirements.txt every time you add a new package
pip freeze > requirements.txt
```

### Running the System
```bash
# Run main orchestrator (controls multiple agents)
python src/main.py

# Run individual agents standalone
python src/agents/trading_agent.py
python src/agents/risk_agent.py
python src/agents/rbi_agent.py
python src/agents/chat_agent.py
# ... any agent in src/agents/ can run independently
```

### Backtesting
```bash
# Use backtesting.py library with pandas_ta or talib for indicators
# Sample OHLCV data available at:
# src/data/rbi/BTC-USD-15m.csv (or provide your own CSV data file)
```

## Architecture Overview

### Core Structure
```
src/
├── agents/              # 48+ specialized AI agents (each <800 lines)
├── models/              # LLM provider abstraction (ModelFactory pattern)
├── strategies/          # User-defined trading strategies
├── scripts/             # Standalone utility scripts
├── data/                # Agent outputs, memory, analysis results
├── config.py            # Global configuration (positions, risk limits, API settings)
├── main.py              # Main orchestrator for multi-agent loop
├── nice_funcs.py        # ~1,200 lines of shared trading utilities
├── nice_funcs_hl.py     # Hyperliquid-specific utilities
└── ezbot.py             # Legacy trading controller
```

### Agent Ecosystem

**Revival Scanner (Active)**: `revival_detector_agent`, `meme_scanner_orchestrator`, `stage1_security_filter`, `meme_notifier_agent`
**Trading Agents**: `trading_agent`, `strategy_agent`, `risk_agent`, `copybot_agent`
**Market Analysis**: `sentiment_agent`, `whale_agent`, `funding_agent`, `liquidation_agent`, `chartanalysis_agent`
**Content Creation**: `chat_agent`, `clips_agent`, `tweet_agent`, `video_agent`, `phone_agent`
**Strategy Development**: `rbi_agent` (Research-Based Inference - codes backtests from videos/PDFs), `research_agent`
**Other Specialized**: `tx_agent`, `million_agent`, `tiktok_agent`, `compliance_agent`
**Legacy/Archived**: `sniper_agent`, `solana_agent` (replaced by Revival Scanner)

Each agent can run independently or as part of the main orchestrator loop.

### LLM Integration (Model Factory)

Located at `src/models/model_factory.py` and `src/models/README.md`

**Unified Interface**: All agents use `ModelFactory.create_model()` for consistent LLM access
**Supported Providers**: Anthropic Claude (default), OpenAI, DeepSeek, Groq, Google Gemini, xAI (Grok), Ollama (local)
**Key Pattern**:
```python
from src.models.model_factory import ModelFactory

model = ModelFactory.create_model('anthropic')  # or 'openai', 'deepseek', 'groq', etc.
response = model.generate_response(system_prompt, user_content, temperature, max_tokens)
```

### Configuration Management

**Primary Config**: `src/config.py`
- Trading settings: `MONITORED_TOKENS`, `EXCLUDED_TOKENS`, position sizing (`usd_size`, `max_usd_order_size`)
- Risk management: `CASH_PERCENTAGE`, `MAX_POSITION_PERCENTAGE`, `MAX_LOSS_USD`, `MAX_GAIN_USD`, `MINIMUM_BALANCE_USD`
- Agent behavior: `SLEEP_BETWEEN_RUNS_MINUTES`, `ACTIVE_AGENTS` dict in `main.py`
- AI settings: `AI_MODEL`, `AI_MAX_TOKENS`, `AI_TEMPERATURE`
- Revival Scanner settings:
  - `MIN_LIQUIDITY_PREFILTER = 20000` - Initial liquidity filter
  - `MIN_LIQUIDITY_STRICT = 50000` - Strict liquidity after age check
  - `MIN_VOLUME_1H = 500` - Minimum 1-hour volume (**$500, reduced from $5K**)
  - `MIN_AGE_HOURS = 72` - Minimum token age (**3 days, increased from 24h**)
  - `MAX_AGE_HOURS = 4320` - Maximum token age (180 days / 6 months)
  - `MAX_MARKET_CAP = 30_000_000` - Maximum market cap (**$30M, increased from $20M**)
  - `HOLDER_CONCENTRATION_THRESHOLD = 30.0` - Max % top 10 holders (**tightened from 70%**)
  - `PRICE_PATTERN_WEIGHT = 0.60` - Revival scoring weight (**increased from 50%**)
  - `SMART_MONEY_WEIGHT = 0.15` - Revival scoring weight (**reduced from 30%**)
  - `VOLUME_WEIGHT = 0.15` - Revival scoring weight (**reduced from 20%**)
  - `SOCIAL_SENTIMENT_WEIGHT = 0.10` - Revival scoring weight (**NEW**)

**Environment Variables**: `.env` (see `.env_example`)
- **Revival Scanner APIs**: `BIRDEYE_API_KEY` (required), `RPC_ENDPOINT` (required - used as HELIUS_RPC_ENDPOINT for age verification)
- **Paper Trading**: `EMAIL_PASSWORD` (Gmail App Password for notifications - see https://support.google.com/accounts/answer/185833)
- Other Trading APIs: `MOONDEV_API_KEY`, `COINGECKO_API_KEY`
- AI Services: `ANTHROPIC_KEY`, `OPENAI_KEY`, `DEEPSEEK_KEY`, `GROQ_API_KEY`, `GEMINI_KEY`, `GROK_API_KEY`
- Blockchain: `SOLANA_PRIVATE_KEY`, `HYPER_LIQUID_ETH_PRIVATE_KEY`, `RPC_ENDPOINT`

### Shared Utilities

**`src/nice_funcs.py`** (~1,200 lines): Core trading functions
- Data: `token_overview()`, `token_price()`, `get_position()`, `get_data()` (OHLCV)
- Trading: `market_buy()`, `market_sell()`, `chunk_kill()`, `open_position()`
- Analysis: Technical indicators, PnL calculations, rug pull detection

**`src/helius_utils.py`**: Helius RPC blockchain utilities (Revival Scanner)
- `get_token_creation_timestamp()`: Query blockchain for token mint creation time
- `get_token_age_hours()`: Get accurate token age in hours
- `batch_get_token_ages()`: Process multiple tokens with rate limiting (10 req/sec)

**`src/dexscreener_utils.py`**: DexScreener social sentiment utilities (Revival Scanner)
- `get_token_social_data()`: Extract boosts, Twitter, Telegram, Discord, volume
- `batch_enrich_tokens()`: Process multiple tokens with rate limiting (5 req/sec)
- `get_social_score()`: Calculate social sentiment score (0-1)

**`src/agents/api.py`**: `MoonDevAPI` class for custom Moon Dev API endpoints
- `get_liquidation_data()`, `get_funding_data()`, `get_oi_data()`, `get_copybot_follow_list()`

### Data Flow Pattern

```
Config/Input → Agent Init → API Data Fetch → Data Parsing →
LLM Analysis (via ModelFactory) → Decision Output →
Result Storage (CSV/JSON in src/data/) → Optional Trade Execution
```

## Development Rules

### File Management
- **Keep files under 800 lines** - if longer, split into new files and update README
- **DO NOT move files without asking** - you can create new files but no moving
- **NEVER create new virtual environments** - use existing `conda activate tflow`
- **Update requirements.txt** after adding any new package

### Backtesting
- Use `backtesting.py` library (NOT their built-in indicators)
- Use `pandas_ta` or `talib` for technical indicators instead
- Sample data available at `src/data/rbi/BTC-USD-15m.csv` (or provide your own CSV file)

### Code Style
- **No fake/synthetic data** - always use real data or fail the script
- **Minimal error handling** - user wants to see errors, not over-engineered try/except blocks
- **No API key exposure** - never show keys from `.env` in output

### Agent Development Pattern

When creating new agents:
1. Inherit from base patterns in existing agents
2. Use `ModelFactory` for LLM access
3. Store outputs in `src/data/[agent_name]/`
4. Make agent independently executable (standalone script)
5. Add configuration to `config.py` if needed
6. Follow naming: `[purpose]_agent.py`

### Testing Strategies

Place strategy definitions in `src/strategies/` folder:
```python
class YourStrategy(BaseStrategy):
    name = "strategy_name"
    description = "what it does"

    def generate_signals(self, token_address, market_data):
        return {
            "action": "BUY"|"SELL"|"NOTHING",
            "confidence": 0-100,
            "reasoning": "explanation"
        }
```

## Important Context

### Risk-First Philosophy
- Risk Agent runs first in main loop before any trading decisions
- Configurable circuit breakers (`MAX_LOSS_USD`, `MINIMUM_BALANCE_USD`)
- AI confirmation for position-closing decisions (configurable via `USE_AI_CONFIRMATION`)

### Data Sources

**Revival Scanner (Primary - All BirdEye):**
1. **BirdEye API** - Primary data source for all revival scanner features:
   - Native meme token list (`/defi/v3/token/meme/list`)
   - Token overview with comprehensive metrics (`/defi/token_overview`)
   - OHLCV price data (`/defi/ohlcv`) via `get_data()` in `nice_funcs.py`
   - Top traders for smart money analysis (`/defi/v2/tokens/top_traders`)
   - Holder distribution for concentration risk (`/defi/v3/token/holder`)
2. **Helius RPC** - Blockchain queries for accurate token creation timestamps
3. **DexScreener API** - NOT USED in primary pipeline (fallback utility only)

**Other Trading Agents:**
5. **Moon Dev API** - Custom signals (liquidations, funding rates, OI, copybot data)
6. **CoinGecko API** - 15,000+ token metadata, market caps, sentiment

### Autonomous Execution
- Main loop runs every 15 minutes by default (`SLEEP_BETWEEN_RUNS_MINUTES`)
- Agents handle errors gracefully and continue execution
- Keyboard interrupt for graceful shutdown
- All agents log to console with color-coded output (termcolor)

### AI-Driven Strategy Generation (RBI Agent)
1. User provides: YouTube video URL / PDF / trading idea text
2. DeepSeek-R1 analyzes and extracts strategy logic
3. Generates backtesting.py compatible code
4. Executes backtest and returns performance metrics
5. Cost: ~$0.027 per backtest execution (~6 minutes)

## Common Patterns

### Adding New Agent
1. Create `src/agents/your_agent.py`
2. Implement standalone execution logic
3. Add to `ACTIVE_AGENTS` in `main.py` if needed for orchestration
4. Use `ModelFactory` for LLM calls
5. Store results in `src/data/your_agent/`

### Switching AI Models
Edit `config.py`:
```python
AI_MODEL = "claude-3-haiku-20240307"  # Fast, cheap
# AI_MODEL = "claude-3-sonnet-20240229"  # Balanced
# AI_MODEL = "claude-3-opus-20240229"  # Most powerful
```

Or use different models per agent via ModelFactory:
```python
model = ModelFactory.create_model('deepseek')  # Reasoning tasks
model = ModelFactory.create_model('groq')      # Fast inference
```

### Reading Market Data
```python
from src.nice_funcs import token_overview, get_ohlcv_data, token_price

# Get comprehensive token data
overview = token_overview(token_address)

# Get price history
ohlcv = get_ohlcv_data(token_address, timeframe='1H', days_back=3)

# Get current price
price = token_price(token_address)
```

## Non-Obvious Implementation Patterns

### Web App Integration (Callback Injection Pattern)
The web app uses **callback injection** to communicate with the orchestrator without tight coupling:
```python
# In web_app.py - callbacks injected into orchestrator
orchestrator.log_activity = log_activity
orchestrator.log_error = log_error
orchestrator.update_progress = update_progress

# In orchestrator - callbacks are optional
if self.log_activity:
    self.log_activity(message, level)  # Only logs if web app injected callback
```
This allows the orchestrator to run independently (CLI mode) or with web UI integration without code changes.

### Phase Token Tracking
The orchestrator stores tokens at each phase in `self.phase_tokens` dict for funnel visualization:
```python
self.phase_tokens = {
    'phase1_birdeye': [],           # Raw BirdEye tokens
    'phase2_prefiltered': [],       # After liquidity/MC/volume filter
    'phase3_aged': [],              # After Helius age check
    'phase4_security_passed': [],   # After security filter
    'phase5_revival_detected': []   # Final revival opportunities
}
```
This is used by the web dashboard's `/api/phases` endpoint to show conversion rates between phases.

### Data Deduplication Strategy
- **Phase 1** uses a dict with address as key: `all_tokens[token['address']] = token`
- This ensures each token address appears only once in the dataset
- No duplicate checking in later phases - assumes upstream data is already clean
- BirdEye API returns unique tokens, so deduplication is primarily defensive

### Configuration Anti-Patterns to Know
- **Duplicate settings**: `SLEEP_BETWEEN_RUNS_MINUTES` appears twice in config.py
- **Conflicting thresholds**: `MIN_LIQUIDITY_PREFILTER` ($20K) vs `MIN_LIQUIDITY_STRICT` ($50K) - only prefilter is used now
- **Hardcoded overrides**: Web app uses `scan_interval = 7200` instead of config value
- **Agent overrides**: Some agents override config settings locally (e.g., `trading_agent.py` sets `AI_MODEL_TYPE = 'xai'`)

### Error Handling Philosophy
Per the "minimal error handling" principle, the code deliberately lets errors surface:
- Most functions raise exceptions rather than return error codes
- **Exception**: Security filter returns `True` (passes) if GoPlus API fails - this is intentional to avoid blocking
- **Exception**: Revival detector returns `None` for failed API calls to gracefully skip tokens
- Web app background thread catches broad `Exception` to keep scanning loop alive

## Common Pitfalls to Avoid

1. **Virtual Environments**: NEVER create new venv/virtualenv - use `conda activate tflow` only
2. **API Keys**: Ensure all required keys in .env (BirdEye + Helius mandatory for Revival Scanner)
3. **Port Conflicts**: Web dashboard uses port 8080 - ensure not in use before starting
4. **PYTHONPATH**: When running orchestrator manually, set PYTHONPATH to project root
5. **Config Sync**: After changing config.py, restart any running agents for changes to take effect
6. **Temp Data**: Set `SAVE_OHLCV_DATA=True` in config.py to persist price data beyond session
7. **BirdEye Response Structure**: Native meme list uses `data.items`, generic tokenlist uses `data.tokens`
8. **Rate Limiting**: BirdEye Standard tier = 1 req/sec, Helius Free = 10 req/sec - respect these limits
9. **Volume Estimation**: Phase 2 estimates 1h volume as `volume_24h / 24` (naive averaging, not actual 1h data)
10. **Memory Leaks**: Long-running scans can accumulate memory in cache dicts and activity logs - restart periodically
11. **Thread Safety**: `scanner_state` dict in web_app.py is accessed from multiple threads without locks
12. **GoPlus Failures**: Security filter passes tokens by default if GoPlus API fails - verify API is working

## Data Directory Structure

```
src/data/
├── meme_scanner/          # Revival scanner scan results (CSV/JSON)
├── security_filter/       # Security check outputs (JSON with timestamps)
├── meme_notifier/         # Notification history
├── revival_detector/      # Revival pattern analysis results
├── paper_trading/         # Paper trading data (NEW - Nov 2025)
│   ├── positions.csv      # Active positions (survives restart)
│   ├── trades_history.csv # Closed trades with P&L
│   ├── portfolio_snapshots.csv  # Portfolio value over time
│   └── performance_metrics.json # Cached metrics + LLM insights
├── ohlcv/                 # Price history (TEMP unless SAVE_OHLCV_DATA=True)
├── rbi/                   # RBI agent strategy development
│   ├── [date_folders]/    # Dated strategy development sessions
│   ├── AI_GENERATED_STRATEGIES/
│   ├── AI_OPTIMIZED_STRATEGIES/
│   ├── FINAL_WINNING_STRATEGIES/
│   └── backtests/         # Backtest results tracking
├── code_runner/           # Code execution logs
├── charts/                # Generated chart images
└── [agent_name]/          # Per-agent output directories
```

**Data Persistence:**
- Most data auto-deleted on exit (via `atexit.register(cleanup_temp_data)`)
- Set `SAVE_OHLCV_DATA=True` in config.py to keep price history
- Agent output CSVs/JSONs persist by default
- **Paper trading data persists permanently** - positions survive server restarts

## Testing Approach

**No formal test framework** (pytest/unittest) used. Testing via:
- Standalone test scripts in project root (`test_*.py`)
- Manual agent execution verification
- Backtest validation for RBI-generated strategies
- Real-world API testing with `test_birdeye_api.py`

Run tests manually:
```bash
python test_revival_system.py
python test_simple_revival.py
python test_birdeye_api.py
```

## Performance and Scaling Considerations

### Current System Limits
- **Scan Cycle Time**: ~10-15 minutes for full 5-phase pipeline with 1800 tokens
- **Token Analysis Limit**: Orchestrator processes max 40 tokens in Phase 5 (Revival Detection)
- **Memory Usage**: Grows over time due to unbounded caches in `RevivalDetectorAgent` and orchestrator
- **Thread Model**: Single background thread for web app, no concurrent scans
- **API Cost**: Free tier limits (BirdEye 1 req/sec, Helius 10 req/sec) constrain throughput

### Optimization Opportunities
1. **Batch RPC Calls**: Helius age verification makes 2 RPC calls per token sequentially - could batch
2. **Parallel Security Checks**: Currently uses ThreadPoolExecutor with 3 workers - could increase
3. **Cache Expiration**: Add TTL to caches to prevent memory leaks (currently unbounded)
4. **Phase 2 Volume**: Use actual BirdEye 1h volume endpoint instead of `volume_24h / 24` estimation
5. **Token Limit**: Remove hardcoded 40-token limit in revival analysis (line 735 in orchestrator)

### Known Limitations
- **Volume Inaccuracy**: Phase 2 estimates 1h volume by dividing 24h volume by 24 (naive)
- **No Retry Logic**: Most API calls don't retry on failure (only Groq has exponential backoff)
- **Thread Safety**: Web app's `scanner_state` dict accessed from multiple threads without locks
- **Memory Leaks**: Caches and activity logs grow unbounded in long-running processes
- **Single Point of Failure**: GoPlus API failure passes all tokens (security filter disabled)

### Deployment Patterns
- **CLI Mode**: Run `python src/agents/meme_scanner_orchestrator.py --once` for single scans
- **Web Mode**: Run `./start_webapp.sh` for continuous 1-hour cycle scans with dashboard
- **Recommended**: Restart web app daily to clear accumulated memory from caches
- **Monitoring**: Check `activity_log` and `error_log` in web app for API failures
- **Paper Trading**: Background monitoring active when web app is running, resumes automatically on restart

## Additional Documentation

This project has extensive documentation beyond this file. Always check for dedicated documentation when working on specific features.

### Revival Scanner Documentation:
- **`REVIVAL_SCANNER_PRD.md`** - Complete product requirements and strategy details
- **`QUICK_START_WEBAPP.md`** - Get the web dashboard running in 2 minutes
- **`WEBAPP_README.md`** - Full web dashboard feature documentation
- **`DASHBOARD_GUIDE.md`** - Dashboard navigation and interpretation guide
- **`COMPLETE_SYSTEM_GUIDE.md`** - End-to-end system architecture and workflow

### Legacy/Archived Documentation:
- **`ARCHIVED_FRESH_LAUNCH_PRD.md`** - Original fresh launch strategy (pre-Revival Scanner)
- **`ARCHIVED_FRESH_LAUNCH_IMPLEMENTATION.md`** - Implementation details for legacy sniper agents

### Model Integration:
- **`src/models/README.md`** - Complete LLM provider documentation with usage examples

**Tip:** When working on specific features, check these documentation files first for detailed context and implementation guidance.

---

## Project Philosophy

This is an **experimental, educational project** demonstrating AI agent patterns through algorithmic trading:
- No guarantees of profitability (substantial risk of loss)
- Open source and free for learning
- YouTube-driven development with weekly updates
- Community-supported via Discord
- No token associated with project (avoid scams)

The goal is to democratize AI agent development and show practical multi-agent orchestration patterns that can be applied beyond trading.

**Development Philosophy**:
- Minimal error handling (let errors surface for debugging)
- No fake/synthetic data (always use real APIs or fail)
- Files kept under 800 lines (split if longer)
- Standalone agents (each can run independently)
- Configuration in `config.py` (centralized settings)
