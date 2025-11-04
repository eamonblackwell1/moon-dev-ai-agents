"""
🌙 Moon Dev's Configuration File
Built with love by Moon Dev 🚀
"""

# 💰 Trading Configuration
USDC_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # Never trade or close
SOL_ADDRESS = "So11111111111111111111111111111111111111111"   # Never trade or close

# Create a list of addresses to exclude from trading/closing
EXCLUDED_TOKENS = [USDC_ADDRESS, SOL_ADDRESS]

# Token List for Trading 📋
MONITORED_TOKENS = [
    '9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump',    # 🌬️ FART
    # 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',    # 💵 USDC
    'HeLp6NuQkmYB4pYWo2zYs22mESHXPQYzXbB8n4V98jwC',    # 🤖 AI16Z
    # 'v62Jv9pwMTREWV9f6TetZfMafV254vo99p7HSF25BPr',     # 🎮 GG Solana
    # 'KENJSUYLASHUMfHyy5o4Hp2FdNqZg1AsUPhfH2kYvEP',   # GRIFFAIN
    # '8x5VqbHA8D7NkD52uNuS5nnt3PwA3pLD34ymskeSo2Wn',    # 🧠 ZEREBRO
    # 'Df6yfrKC8kZE3KNkrHERKzAetSxbrWeniQfyJY4Jpump',    # 😎 CHILL GUY
    # 'ED5nyyWEzpPPiWimP8vYm7sD7TD3LAt3Q3gRTWHzPJBY',    # 🌙 MOODENG
    # 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm',    # 🐕 WIF
]

# Moon Dev's Token Trading List 🚀
# Each token is carefully selected by Moon Dev for maximum moon potential! 🌙
tokens_to_trade = MONITORED_TOKENS  # Using the same list for trading

# Token and wallet settings
symbol = '9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump'
address = '4wgfCBf2WwLSRKLef9iW7JXZ2AfkxUxGM4XcKpHm3Sin' # YOUR WALLET ADDRESS HERE

# Position sizing 🎯
usd_size = 25  # Size of position to hold
max_usd_order_size = 3  # Max order size
tx_sleep = 30  # Sleep between transactions
slippage = 199  # Slippage settings

# Risk Management Settings 🛡️
CASH_PERCENTAGE = 20  # Minimum % to keep in USDC as safety buffer (0-100)
MAX_POSITION_PERCENTAGE = 30  # Maximum % allocation per position (0-100)
STOPLOSS_PRICE = 1 # NOT USED YET 1/5/25    
BREAKOUT_PRICE = .0001 # NOT USED YET 1/5/25
SLEEP_AFTER_CLOSE = 600  # Prevent overtrading

MAX_LOSS_GAIN_CHECK_HOURS = 12  # How far back to check for max loss/gain limits (in hours)
SLEEP_BETWEEN_RUNS_MINUTES = 15  # How long to sleep between agent runs 🕒


# Max Loss/Gain Settings FOR RISK AGENT 1/5/25
USE_PERCENTAGE = False  # If True, use percentage-based limits. If False, use USD-based limits

# USD-based limits (used if USE_PERCENTAGE is False)
MAX_LOSS_USD = 25  # Maximum loss in USD before stopping trading
MAX_GAIN_USD = 25 # Maximum gain in USD before stopping trading

# USD MINIMUM BALANCE RISK CONTROL
MINIMUM_BALANCE_USD = 50  # If balance falls below this, risk agent will consider closing all positions
USE_AI_CONFIRMATION = True  # If True, consult AI before closing positions. If False, close immediately on breach

# Percentage-based limits (used if USE_PERCENTAGE is True)
MAX_LOSS_PERCENT = 5  # Maximum loss as percentage (e.g., 20 = 20% loss)
MAX_GAIN_PERCENT = 5  # Maximum gain as percentage (e.g., 50 = 50% gain)

# Transaction settings ⚡
slippage = 199  # 500 = 5% and 50 = .5% slippage
PRIORITY_FEE = 100000  # ~0.02 USD at current SOL prices
orders_per_open = 3  # Multiple orders for better fill rates

# Market maker settings 📊
buy_under = .0946
sell_over = 1

# Data collection settings 📈
DAYSBACK_4_DATA = 3
DATA_TIMEFRAME = '1H'  # 1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 8H, 12H, 1D, 3D, 1W, 1M
SAVE_OHLCV_DATA = False  # 🌙 Set to True to save data permanently, False will only use temp data during run

# AI Model Settings 🤖
AI_MODEL = "claude-3-haiku-20240307"  # Model Options:
                                     # - claude-3-haiku-20240307 (Fast, efficient Claude model)
                                     # - claude-3-sonnet-20240229 (Balanced Claude model)
                                     # - claude-3-opus-20240229 (Most powerful Claude model)
AI_MAX_TOKENS = 1024  # Max tokens for response
AI_TEMPERATURE = 0.7  # Creativity vs precision (0-1)

# Trading Strategy Agent Settings - MAY NOT BE USED YET 1/5/25
ENABLE_STRATEGIES = True  # Set this to True to use strategies
STRATEGY_MIN_CONFIDENCE = 0.7  # Minimum confidence to act on strategy signals

# Sleep time between main agent runs
SLEEP_BETWEEN_RUNS_MINUTES = 15  # How long to sleep between agent runs 🕒

# in our nice_funcs in token over view we look for minimum trades last hour
MIN_TRADES_LAST_HOUR = 2

# Revival Scanner Settings 🔄 (Single-Pass Top 2000 Strategy)
BIRDEYE_TOKENS_PER_SORT = 2000  # Total tokens to fetch (top 2000 by liquidity - optimized for revival trading)
BIRDEYE_TOKENS_PER_PAGE = 50  # Max tokens per BirdEye API call (API limit is 50, NOT 100)
BIRDEYE_USE_NATIVE_MEME_LIST = True  # Use native /defi/v3/token/meme/list (guarantees pure memecoins)
MIN_LIQUIDITY_PREFILTER = 20000  # $20K minimum liquidity (Phase 2 - BirdEye filter)
MIN_LIQUIDITY_STRICT = 50000  # $50K minimum liquidity (DEPRECATED - no longer used, kept for backward compatibility)
MIN_VOLUME_1H = 500  # $500 minimum 1-hour volume (Phase 2 - applied via 24h volume estimation = $12K/day)
MIN_AGE_HOURS = 72  # Minimum token age in hours (Phase 3 - 3 days, avoid early pump chaos)
MAX_AGE_HOURS = 4320  # Maximum token age in hours (Phase 3 - 180 days / 6 months)
MAX_MARKET_CAP = 30_000_000  # $30M maximum market cap (Phase 2 - BirdEye filter)

# Social Sentiment Settings 📱
MIN_UNIQUE_WALLETS_24H = 100  # Minimum unique wallets for community legitimacy
MIN_WATCHLIST_COUNT = 50  # Minimum watchlist count for social interest
HOLDER_CONCENTRATION_THRESHOLD = 30.0  # Max % that top 10 holders can own (reduced from 70% for safety)

# Revival Pattern Scoring Weights ⚖️
PRICE_PATTERN_WEIGHT = 0.60  # 60% - Price dump-floor-recovery pattern (most important)
SMART_MONEY_WEIGHT = 0.15  # 15% - Whale wallet accumulation (reduced from 30%)
VOLUME_WEIGHT = 0.15  # 15% - Volume patterns and velocity
SOCIAL_SENTIMENT_WEIGHT = 0.10  # 10% - BirdEye social metrics (holder growth, watchlist, etc.)

# Paper Trading Settings 📊
PAPER_TRADING_ENABLED = True  # Enable paper trading simulation
PAPER_TRADING_INITIAL_BALANCE = 10000  # $10K starting capital
PAPER_TRADING_POSITION_SIZE_USD = 1000  # $1K per trade
PAPER_TRADING_MAX_POSITIONS = 10  # Max concurrent positions
PAPER_TRADING_MIN_REVIVAL_SCORE = 0.4  # Minimum score to trade (0-1) - aligned with scanner display threshold

# Paper Trading Exit Strategy 🎯
PAPER_TRADING_STOP_LOSS_PCT = -20  # -20% stop loss
PAPER_TRADING_TAKE_PROFIT_1_PCT = 35  # +35% first profit target
PAPER_TRADING_TAKE_PROFIT_1_SELL_PCT = 40  # Sell 40% of position at first target
PAPER_TRADING_TAKE_PROFIT_2_PCT = 75  # +75% second profit target
PAPER_TRADING_TAKE_PROFIT_2_SELL_PCT = 30  # Sell 30% of position at second target
PAPER_TRADING_MAX_HOLD_DAYS = 5  # Auto-exit after 5 days if targets not hit

# Paper Trading Execution Simulation ⚙️
PAPER_TRADING_ENTRY_SLIPPAGE_PCT = 2  # 2% slippage on entry buys
PAPER_TRADING_PROFIT_EXIT_SLIPPAGE_PCT = 2  # 2% slippage on profit-taking exits
PAPER_TRADING_STOP_EXIT_SLIPPAGE_PCT = 10  # 10% slippage on stop-loss exits (panic selling)
PAPER_TRADING_JUPITER_FEE_PCT = 0.06  # 0.06% Jupiter swap fee per trade
PAPER_TRADING_FAILED_EXIT_CHANCE = 0.05  # 5% chance of failed exit (token frozen/no liquidity)
PAPER_TRADING_PRICE_CHECK_INTERVAL = 30  # Check prices every 30 seconds

# ============================================================================
# Production Deployment Settings 🚀
# ============================================================================
# Web App Configuration
WEB_APP_PORT = int(os.getenv('PORT', 8080))  # Railway sets PORT env variable
WEB_APP_BASE_URL = os.getenv('WEB_APP_BASE_URL', 'http://localhost:8080')  # Set to Railway URL in production
FLASK_ENV = os.getenv('FLASK_ENV', 'development')  # 'production' or 'development'
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'  # Debug mode (off by default)

# Paper Trading Email Notifications 📧
PAPER_TRADING_EMAIL_ENABLED = True  # Enable email notifications
PAPER_TRADING_EMAIL_ADDRESS = ""  # Your email address (set this!)
PAPER_TRADING_EMAIL_SMTP_SERVER = "smtp.gmail.com"  # Gmail SMTP (change if using different provider)
PAPER_TRADING_EMAIL_SMTP_PORT = 587  # TLS port
PAPER_TRADING_EMAIL_USERNAME = ""  # Usually same as email address
# NOTE: Set EMAIL_PASSWORD in .env file for security (not here!)

# Notification Preferences 🔔
PAPER_TRADING_NOTIFY_POSITION_OPENED = True  # Email when position opens
PAPER_TRADING_NOTIFY_STOP_LOSS = True  # Email when stop-loss triggers
PAPER_TRADING_NOTIFY_TAKE_PROFIT = True  # Email when take-profit triggers
PAPER_TRADING_NOTIFY_FAILED_EXIT = True  # Email on failed exit (CRITICAL)
PAPER_TRADING_NOTIFY_DAILY_SUMMARY = True  # Daily summary at end of day
PAPER_TRADING_NOTIFY_WEEKLY_REPORT = True  # Weekly performance report

# Notification Timing ⏰
PAPER_TRADING_DAILY_SUMMARY_TIME = "23:59"  # Time for daily summary (24-hour format)
PAPER_TRADING_WEEKLY_REPORT_DAY = 6  # Day of week for weekly report (0=Monday, 6=Sunday)
PAPER_TRADING_WEEKLY_REPORT_TIME = "20:00"  # Time for weekly report (24-hour format)

# Real-Time Clips Agent Settings 🎬
REALTIME_CLIPS_ENABLED = True
REALTIME_CLIPS_OBS_FOLDER = '/Volumes/Moon 26/OBS'  # Your OBS recording folder
REALTIME_CLIPS_AUTO_INTERVAL = 120  # Check every N seconds (120 = 2 minutes)
REALTIME_CLIPS_LENGTH = 2  # Minutes to analyze per check
REALTIME_CLIPS_AI_MODEL = 'groq'  # Model type: groq, openai, claude, deepseek, xai, ollama
REALTIME_CLIPS_AI_MODEL_NAME = None  # None = use default for model type
REALTIME_CLIPS_TWITTER = True  # Auto-open Twitter compose after clip

# Future variables (not active yet) 🔮
sell_at_multiple = 3
USDC_SIZE = 1
limit = 49
timeframe = '15m'
stop_loss_perctentage = -.24
EXIT_ALL_POSITIONS = False
DO_NOT_TRADE_LIST = ['777']
CLOSED_POSITIONS_TXT = '777'
minimum_trades_in_last_hour = 777
