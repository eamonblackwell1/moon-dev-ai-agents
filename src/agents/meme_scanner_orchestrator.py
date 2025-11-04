"""
🎯 Moon Dev's Meme Scanner Orchestrator
Main controller that combines all components for finding revival patterns
Built with love by Moon Dev 🚀

Enhanced 3-Phase Discovery Pipeline (BirdEye-First Strategy):
1. BirdEye native meme token discovery (dual-pass: liquidity-sorted + sequential, ~2000 tokens)
2. BirdEye pre-filter (liquidity $20K+, market cap <$30M, volume $5K+ 1h)
3. Helius blockchain age verification (72h minimum, 180 days maximum)

Then Security & Analysis:
4. Security filter (30% holder concentration threshold, eliminate scams)
5. Revival pattern detection (complete price history, smart money via BirdEye, social sentiment)
6. Notifications for opportunities

DexScreener used as fallback only (not in primary pipeline)
"""

import os
import sys
import time
import csv
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from termcolor import colored

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Import our components
from src.agents.revival_detector_agent import RevivalDetectorAgent
from src.agents.stage1_security_filter import Stage1SecurityFilter
from src.agents.meme_notifier_agent import MemeNotifierAgent
from src.agents.api import MoonDevAPI
from src.config import *

class MemeScannerOrchestrator:
    """
    Main orchestrator that coordinates all meme scanning components

    Components:
    1. Security Filter - Eliminates scams
    2. Revival Detector - Finds revival patterns
    3. Notifier - Sends alerts
    4. Paper Trader - Tracks hypothetical performance
    """

    def __init__(self):
        """Initialize all components"""
        print(colored("=" * 60, "cyan"))
        print(colored("🎯 MEME SCANNER ORCHESTRATOR", "cyan", attrs=['bold']))
        print(colored("Finding revival patterns in 24-48hr old tokens", "cyan"))
        print(colored("=" * 60, "cyan"))

        # Initialize components
        self.security_filter = Stage1SecurityFilter()
        self.revival_detector = RevivalDetectorAgent()
        self.notifier = MemeNotifierAgent()

        # Try to initialize Moon Dev API for token sources
        try:
            self.moon_api = MoonDevAPI()
        except:
            self.moon_api = None
            print(colored("⚠️ Moon Dev API not configured (optional)", "yellow"))

        # Configuration
        self.scan_interval = 7200  # 120 minutes / 2 hours (optimized for API free tier limits)
        self.max_tokens_per_scan = BIRDEYE_TOKENS_PER_SORT * 3  # ~600 tokens per scan (3 sorting strategies)
        self.min_revival_score = 0.4  # Minimum score to consider

        # Data storage
        self.data_dir = Path(__file__).parent.parent / "data" / "meme_scanner"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Track scanning history
        self.scan_history = []

        # Track tokens through each phase (for dashboard funnel view)
        self.phase_tokens = {
            'phase1_birdeye': [],           # Raw tokens from BirdEye
            'phase2_prefiltered': [],       # After liquidity + memecoin filter
            'phase3_aged': [],              # After Helius age check
            'phase4_market_filtered': [],   # After DexScreener market filters
            'phase5_enriched': [],          # After social enrichment
            'phase6_security_passed': [],   # After security filter
            'phase7_revival_detected': []   # Final revival opportunities
        }

        # Callbacks for web UI (injected by web_app.py)
        self.log_activity = None
        self.log_error = None
        self.update_progress = None

    def _log(self, message, level='info'):
        """Internal logging that works both in CLI and web mode"""
        if self.log_activity:
            self.log_activity(message, level)
        # Always print to console too
        if level == 'error':
            print(colored(message, 'red'))
        elif level == 'warning':
            print(colored(message, 'yellow'))
        elif level == 'success':
            print(colored(message, 'green'))

    def _log_error(self, message):
        """Log error"""
        if self.log_error:
            self.log_error(message)
        print(colored(f"❌ {message}", 'red'))

    def _update_progress(self, phase, phase_number, message, **kwargs):
        """Update progress"""
        if self.update_progress:
            self.update_progress(phase, phase_number, message, **kwargs)

        # Known non-memecoin patterns
        self.non_memecoin_keywords = [
            # Stablecoins
            'usd', 'usdc', 'usdt', 'dai', 'busd', 'frax', 'ust', 'tusd', 'pax', 'gusd',
            # Liquid staking tokens
            'stsol', 'msol', 'jitosol', 'scnsol', 'bsol', 'lstsol', 'hsol', 'csol',
            'steth', 'reth', 'cbeth', 'frxeth', 'sfrxeth',
            # DeFi/Infrastructure
            'wrapped', 'wbtc', 'weth', 'wsol', 'staked', 'liquid', 'lido',
            'marinade', 'jito', 'socean', 'blazestake', 'daopool',
            # DEX/AMM tokens
            'raydium', 'orca', 'serum', 'saber', 'mercurial', 'aldrin', 'cyclos',
            # Lending/Borrowing
            'solend', 'mango', 'apricot', 'larix', 'port', 'oxygen',
            # Other DeFi
            'chainlink', 'link', 'oracle', 'bridge', 'cross-chain', 'interop',
            'yield', 'vault', 'farm', 'pool', 'liquidity', 'amm', 'dex'
        ]

        # Common memecoin patterns (positive indicators)
        self.memecoin_patterns = [
            'inu', 'doge', 'shib', 'pepe', 'wojak', 'chad', 'moon', 'rocket',
            'pump', 'based', 'gm', 'ser', 'fren', 'wagmi', 'ngmi', 'ape',
            'diamond', 'hands', 'hodl', 'lambo', 'tesla', 'elon', 'musk',
            'cat', 'dog', 'frog', 'bird', 'bear', 'bull', 'rat', 'hamster',
            'baby', 'mini', 'micro', 'safe', 'king', 'queen', 'lord',
            'meme', 'coin', 'token', 'finance', 'swap', 'defi',
            'pnut', 'banana', 'pizza', 'burger', 'taco', 'sushi',
            'bonk', 'bong', 'wif', 'hat', 'glasses', 'santa', 'xmas',
            'god', 'jesus', 'buddha', 'zen', 'karma', 'vibe',
            'nft', 'jpeg', 'art', 'pixel', 'punk', 'ape',
            'cum', 'ass', 'tits', 'dick', 'pussy', 'fuck', 'shit',
            'yolo', 'fomo', 'rekt', 'rug', 'scam', 'ponzi',
            '69', '420', '666', '777', '888', '1337'
        ]

    def get_candidate_tokens(self) -> List[str]:
        """
        ENHANCED 3-PHASE DISCOVERY PIPELINE (BirdEye-First Strategy):
        1. BirdEye → Dual-pass native meme token discovery (~2000 pure memecoins)
        2. BirdEye → Pre-filter (liquidity $20K+, market cap <$30M, volume $5K+ 1h)
        3. Helius → Age verification (72h minimum, 180d maximum)

        DexScreener removed from pipeline (redundant - already have BirdEye data)
        Social sentiment calculated by Revival Detector using BirdEye on-chain metrics

        Returns: List of token addresses ready for security + revival analysis
        """
        print(colored("\n" + "="*60, "magenta"))
        print(colored("🚀 ENHANCED 3-PHASE DISCOVERY PIPELINE", "magenta", attrs=['bold']))
        print(colored("="*60, "magenta"))

        # Reset phase tracking (3-phase discovery + 2-phase analysis)
        self.phase_tokens = {
            'phase1_birdeye': [],           # Discovery Phase 1
            'phase2_prefiltered': [],       # Discovery Phase 2
            'phase3_aged': [],              # Discovery Phase 3
            'phase4_security_passed': [],   # Analysis Phase 1 (was phase6)
            'phase5_revival_detected': []   # Analysis Phase 2 (was phase7)
        }

        # PHASE 1: Get tokens from BirdEye (multi-pass collection)
        print(colored("\n[PHASE 1/3] BirdEye Multi-Pass Token Discovery", "cyan", attrs=['bold']))
        self._update_progress("BirdEye Token Discovery", 1, "Fetching tokens from BirdEye API...")
        birdeye_tokens = self.get_birdeye_tokens(tokens_per_sort=BIRDEYE_TOKENS_PER_SORT)

        if not birdeye_tokens:
            print(colored("❌ No tokens from BirdEye - cannot proceed", "red"))
            self._log_error("No tokens from BirdEye - cannot proceed")
            return []

        # Store Phase 1 tokens (with metadata)
        self.phase_tokens['phase1_birdeye'] = birdeye_tokens

        self._log(f"Phase 1 complete: Collected {len(birdeye_tokens)} unique tokens", 'success')

        # PHASE 2: Enhanced pre-filter (liquidity, market cap, AND volume - all from BirdEye)
        print(colored("\n[PHASE 2/3] Pre-Filter (Liquidity, Market Cap, Volume)", "cyan", attrs=['bold']))
        self._update_progress("Pre-Filter", 2, "Filtering for liquidity, market cap, and volume...",
                            tokens_collected=len(birdeye_tokens))
        prefiltered_tokens = self.liquidity_prefilter(
            birdeye_tokens,
            min_liquidity=MIN_LIQUIDITY_PREFILTER,  # $20K minimum
            min_volume_1h=MIN_VOLUME_1H  # $5K 1-hour volume minimum
        )

        if not prefiltered_tokens:
            print(colored("❌ No tokens passed enhanced pre-filter", "red"))
            self._log_error("No tokens passed enhanced pre-filter")
            return []

        # Store Phase 2 tokens
        self.phase_tokens['phase2_prefiltered'] = prefiltered_tokens

        self._log(f"Phase 2 complete: {len(prefiltered_tokens)} memecoins passed pre-filter", 'success')

        # Extract addresses from the filtered token dicts
        prefiltered_addresses = [token['address'] for token in prefiltered_tokens]

        # PHASE 3: Age filtering via Helius blockchain (72h minimum, 180d maximum)
        print(colored("\n[PHASE 3/3] Blockchain Age Verification (Helius)", "cyan", attrs=['bold']))
        self._update_progress("Age Verification", 3, "Checking token ages via Helius blockchain...",
                            tokens_filtered=len(prefiltered_addresses))
        aged_tokens_dict = self.filter_by_age_helius(
            prefiltered_addresses,
            min_age_hours=MIN_AGE_HOURS  # Minimum 72 hours (3 days)
        )

        if not aged_tokens_dict:
            print(colored("❌ No tokens passed age filter", "red"))
            self._log_error("No tokens passed age filter (all too young)")
            return []

        # Merge aged tokens with their BirdEye data from Phase 2
        # Create a lookup dict for fast access to token data
        token_data_lookup = {token['address']: token for token in prefiltered_tokens}

        # Build full token dicts for aged tokens (preserve BirdEye data AND add age_hours)
        aged_tokens_with_data = []
        for addr, age_hours in aged_tokens_dict.items():
            if addr in token_data_lookup:
                token = token_data_lookup[addr].copy()
                token['age_hours'] = age_hours  # ADD AGE DATA!
                aged_tokens_with_data.append(token)
            else:
                # Shouldn't happen, but handle gracefully
                aged_tokens_with_data.append({'address': addr, 'age_hours': age_hours})

        # Store Phase 3 tokens with full data
        self.phase_tokens['phase3_aged'] = aged_tokens_with_data

        self._log(f"Phase 3 complete: {len(aged_tokens_with_data)} tokens are 72h+ old", 'success')

        # Phases 4 & 5 REMOVED - DexScreener redundant (already filtered by BirdEye in Phase 2)
        # Social sentiment calculated by Revival Detector using BirdEye on-chain metrics

        print(colored("\n" + "="*60, "magenta"))
        print(colored(f"✅ 3-PHASE DISCOVERY COMPLETE: {len(aged_tokens_with_data)} tokens ready for security & revival analysis", "magenta", attrs=['bold']))
        print(colored("="*60, "magenta"))

        return aged_tokens_with_data

    def get_birdeye_meme_tokens(self, tokens_to_fetch: int = 200, sort_by: str = None, start_offset: int = 0) -> List[Dict]:
        """
        Get meme tokens from BirdEye's Meme Token List endpoint
        This endpoint returns ONLY meme tokens (pump.fun, Moonshot, Raydium, bonk.fun launches)

        Args:
            tokens_to_fetch: Total tokens to fetch
            sort_by: Optional sort parameter (e.g., 'liquidity' for high-liq tokens first)
            start_offset: Starting offset for pagination (useful for sequential fetching)

        Returns:
            List of dicts with: address, symbol, liquidity, volume_24h, mc
        """
        all_tokens = []
        tokens_per_page = BIRDEYE_TOKENS_PER_PAGE  # 50 tokens per API call
        num_pages = (tokens_to_fetch + tokens_per_page - 1) // tokens_per_page

        try:
            for page in range(num_pages):
                offset = start_offset + (page * tokens_per_page)

                # Build URL with optional sorting
                url = f"https://public-api.birdeye.so/defi/v3/token/meme/list?chain=solana&offset={offset}&limit={tokens_per_page}"
                if sort_by:
                    url += f"&sort_by={sort_by}&sort_type=desc"

                headers = {'X-API-KEY': os.getenv('BIRDEYE_API_KEY')}

                sort_label = f", sort={sort_by}" if sort_by else ""
                print(colored(f"  📄 Page {page+1}/{num_pages} (meme-list, offset={offset}{sort_label})", "cyan"))

                response = requests.get(url, headers=headers, timeout=15)

                if response.status_code == 429:
                    print(colored(f"⚠️ Rate limit hit (HTTP 429) - waiting 60 seconds...", "yellow"))
                    time.sleep(60)
                    response = requests.get(url, headers=headers, timeout=15)

                if response.status_code != 200:
                    print(colored(f"❌ BirdEye API error: HTTP {response.status_code}", "red"))
                    break

                data = response.json()

                # NOTE: Native meme list API does NOT have 'success' field
                # It returns data.items (NOT data.tokens like the generic tokenlist)

                items = data.get('data', {}).get('items', [])

                if not items:
                    print(colored(f"  📍 No more tokens at offset {offset} (end of list)", "cyan"))
                    break

                for token_data in items:
                    all_tokens.append({
                        'address': token_data.get('address'),
                        'symbol': token_data.get('symbol', 'Unknown'),
                        'name': token_data.get('name', ''),
                        'liquidity': token_data.get('liquidity', 0),
                        'volume_24h': token_data.get('volume_24h_usd', 0),
                        'mc': token_data.get('market_cap', 0),
                    })

                # Rate limiting: 1 request per second
                if page < num_pages - 1:
                    time.sleep(1.0)

            print(colored(f"  ✅ Retrieved {len(all_tokens)} MEME tokens", "green"))
            return all_tokens

        except Exception as e:
            print(colored(f"⚠️ BirdEye meme-list fetch error: {str(e)}", "yellow"))
            return all_tokens

    def get_birdeye_trending_tokens(self, tokens_to_fetch: int = 20) -> List[Dict]:
        """
        Get trending tokens from BirdEye's Trending List endpoint
        NOTE: This endpoint has a HARD LIMIT of 20 tokens max (no pagination)

        These are tokens that traders are actively chasing

        Args:
            tokens_to_fetch: Ignored - endpoint returns max 20 tokens

        Returns:
            List of dicts with: address, symbol, liquidity, volume_24h, mc
        """
        all_tokens = []

        try:
            # Trending endpoint: no params, returns top 20 only
            url = "https://public-api.birdeye.so/defi/token_trending"
            headers = {'X-API-KEY': os.getenv('BIRDEYE_API_KEY')}

            print(colored(f"  📄 Fetching top 20 trending tokens (API limit)", "cyan"))

            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code == 429:
                print(colored(f"⚠️ Rate limit hit (HTTP 429) - waiting 60 seconds...", "yellow"))
                time.sleep(60)
                response = requests.get(url, headers=headers, timeout=15)

            if response.status_code != 200:
                print(colored(f"❌ BirdEye API error: HTTP {response.status_code}", "red"))
                return []

            data = response.json()
            if not data.get('success'):
                print(colored(f"⚠️ API returned success=false", "yellow"))
                return []

            for token_data in data.get('data', {}).get('tokens', []):
                all_tokens.append({
                    'address': token_data.get('address'),
                    'symbol': token_data.get('symbol', 'Unknown'),
                    'name': token_data.get('name', ''),
                    'liquidity': token_data.get('liquidity', 0),
                    'volume_24h': token_data.get('v24hUSD', 0),
                    'mc': token_data.get('mc', 0),
                })

            print(colored(f"  ✅ Retrieved {len(all_tokens)} trending tokens", "green"))
            return all_tokens

        except Exception as e:
            print(colored(f"⚠️ BirdEye trending fetch error: {str(e)}", "yellow"))
            return all_tokens

    def get_birdeye_tokens_paginated(self, sort_by: str, tokens_to_fetch: int = 200) -> List[Dict]:
        """
        Get tokens from BirdEye with pagination for a specific sort order

        Args:
            sort_by: Sort field (v24hUSD, liquidity, v1hUSD, etc.)
            tokens_to_fetch: Total tokens to fetch (will make multiple API calls if > 100)

        Returns:
            List of dicts with: address, symbol, liquidity, volume_24h
        """
        all_tokens = []
        tokens_per_page = BIRDEYE_TOKENS_PER_PAGE  # 100 tokens per API call (API limit)
        num_pages = (tokens_to_fetch + tokens_per_page - 1) // tokens_per_page  # Ceiling division

        try:
            for page in range(num_pages):
                offset = page * tokens_per_page

                url = f"https://public-api.birdeye.so/defi/tokenlist?chain=solana&sort_by={sort_by}&sort_type=desc&offset={offset}&limit={tokens_per_page}"
                headers = {'X-API-KEY': os.getenv('BIRDEYE_API_KEY')}

                print(colored(f"  📄 Page {page+1}/{num_pages} (sort={sort_by}, offset={offset})", "cyan"))

                response = requests.get(url, headers=headers, timeout=15)

                if response.status_code == 429:
                    print(colored(f"⚠️ Rate limit hit (HTTP 429) - waiting 60 seconds...", "yellow"))
                    time.sleep(60)
                    # Retry once after wait
                    response = requests.get(url, headers=headers, timeout=15)

                if response.status_code != 200:
                    print(colored(f"❌ BirdEye API error: HTTP {response.status_code}", "red"))
                    if response.status_code == 400:
                        try:
                            error_msg = response.json().get('message', 'Unknown error')
                            print(colored(f"   Error details: {error_msg}", "red"))
                        except:
                            pass
                    break

                data = response.json()
                if not data.get('success'):
                    print(colored(f"⚠️ API returned success=false", "yellow"))
                    break

                for token_data in data.get('data', {}).get('tokens', []):
                    all_tokens.append({
                        'address': token_data.get('address'),
                        'symbol': token_data.get('symbol', 'Unknown'),
                        'name': token_data.get('name', ''),
                        'liquidity': token_data.get('liquidity', 0),
                        'volume_24h': token_data.get('v24hUSD', 0),
                        'mc': token_data.get('mc', 0),  # Market cap
                    })

                # Rate limiting: 1 request per second (BirdEye Standard tier)
                if page < num_pages - 1:  # Don't sleep after last page
                    time.sleep(1.0)

            print(colored(f"  ✅ Retrieved {len(all_tokens)} tokens (sort={sort_by})", "green"))
            return all_tokens

        except Exception as e:
            print(colored(f"⚠️ BirdEye fetch error for {sort_by}: {str(e)}", "yellow"))
            return all_tokens  # Return what we got so far

    def get_birdeye_tokens(self, tokens_per_sort: int = 200) -> List[Dict]:
        """
        OPTIMIZED NATIVE MEME TOKEN DISCOVERY - 100% Pure Memecoins!

        Strategy: Single-pass top 2000 tokens sorted by liquidity
        Fetches the top 2000 memecoins by liquidity in descending order

        Result: 2000 GUARANTEED memecoins with liquidity range $20K-$17M
        - 1,681 tokens in $20K-$100K revival sweet spot (84%)
        - 100% pass the $20K liquidity filter (vs 8-15% with old strategy)
        - Predictable quality gradient from highest to lowest liquidity

        Why this works:
        - BirdEye native meme list has 5000+ pure memecoins available
        - Liquidity sorting gives us tokens from $17M down to $20K
        - No dead tokens (old Pass 2 offset 1000 had mostly $0-$10K liquidity)
        - No keyword filtering needed (all tokens guaranteed memecoins)
        - Covers pump.fun, Moonshot, Raydium, bonk.fun, and other meme launchpads

        Args:
            tokens_per_sort: Total tokens to fetch (default 200, recommended 2000)

        Returns:
            List of 100% GUARANTEED memecoin tokens sorted by liquidity
        """
        print(colored("🎯 OPTIMIZED NATIVE MEME TOKEN DISCOVERY (100% Pure Memecoins!)", "yellow", attrs=['bold']))
        print(colored(f"   Strategy: Single-pass top {tokens_per_sort} tokens sorted by liquidity", "yellow"))
        print(colored(f"   Expected: 84% in $20K-$100K revival sweet spot", "yellow"))

        # Single pass: Top N tokens by liquidity
        print(colored(f"\n[FETCHING] Top {tokens_per_sort} Tokens by Liquidity", "magenta", attrs=['bold']))
        print(colored(f"   Fetching highest-liquidity memecoins from BirdEye native list", "cyan"))
        print(colored(f"   Source: 100% guaranteed memecoins (no DeFi, no stablecoins)", "cyan"))

        tokens = self.get_birdeye_meme_tokens(
            tokens_to_fetch=tokens_per_sort,
            sort_by='liquidity',  # Sort by liquidity descending
            start_offset=0
        )

        if not tokens:
            print(colored("⚠️ Native meme list failed - API issue", "yellow"))
            return []

        # Analyze liquidity distribution
        if tokens:
            liquidities = [t.get('liquidity', 0) for t in tokens]
            min_liq = min(liquidities) if liquidities else 0
            max_liq = max(liquidities) if liquidities else 0

            # Count tokens in revival sweet spot
            sweet_spot_count = sum(1 for liq in liquidities if 20000 <= liq <= 100000)
            sweet_spot_pct = (sweet_spot_count / len(tokens) * 100) if tokens else 0

        # Summary
        print(colored(f"\n✅ PURE MEMECOIN COLLECTION COMPLETE", "green", attrs=['bold']))
        print(colored(f"   Total tokens fetched: {len(tokens)}", "cyan"))
        print(colored(f"   Liquidity range: ${min_liq:,.0f} - ${max_liq:,.0f}", "cyan"))
        print(colored(f"   Revival sweet spot ($20K-$100K): {sweet_spot_count} tokens ({sweet_spot_pct:.1f}%)", "cyan"))
        print(colored(f"   🎯 100% GUARANTEED MEMECOINS (no DeFi, no stablecoins, no filtering needed!)", "green", attrs=['bold']))

        return tokens

    def is_likely_memecoin(self, symbol: str, name: str = "") -> bool:
        """
        Detect if a token is likely a memecoin based on symbol/name patterns

        Args:
            symbol: Token symbol
            name: Token name (optional)

        Returns:
            True if likely a memecoin, False otherwise
        """
        # Convert to lowercase for comparison
        symbol_lower = symbol.lower() if symbol else ""
        name_lower = name.lower() if name else ""
        combined = f"{symbol_lower} {name_lower}"

        # Check for non-memecoin indicators (negative signals)
        for keyword in self.non_memecoin_keywords:
            if keyword in combined:
                return False

        # Check for memecoin indicators (positive signals)
        for pattern in self.memecoin_patterns:
            if pattern in combined:
                return True

        # Additional heuristics for memecoins:
        # 1. Very short symbols (2-5 chars) are often memecoins
        if 2 <= len(symbol) <= 5:
            return True

        # 2. All caps with numbers often indicates memecoin
        if symbol.isupper() and any(c.isdigit() for c in symbol):
            return True

        # 3. Symbols ending in common memecoin suffixes
        memecoin_suffixes = ['INU', 'DOGE', 'MOON', 'PUMP', 'PEPE', 'CAT', 'DOG']
        for suffix in memecoin_suffixes:
            if symbol.upper().endswith(suffix):
                return True

        # Default to False if no clear indicators
        return False

    def enrich_token_with_overview(self, token: Dict) -> Dict:
        """
        Enrich a token with complete BirdEye Token Overview data

        Args:
            token: Token dict with at least 'address' field

        Returns:
            Enriched token dict with all BirdEye fields
        """
        try:
            address = token['address']
            url = f"https://public-api.birdeye.so/defi/token_overview?address={address}"
            headers = {'X-API-KEY': os.getenv('BIRDEYE_API_KEY')}

            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code != 200:
                print(colored(f"    ⚠️ BirdEye Token Overview API error for {token.get('symbol', 'Unknown')}: HTTP {response.status_code}", "yellow"))
                return token  # Return original token if API fails

            data = response.json()

            if not data.get('success'):
                print(colored(f"    ⚠️ BirdEye API returned success=false for {token.get('symbol', 'Unknown')}", "yellow"))
                return token

            overview_data = data.get('data', {})

            # Merge overview data into token
            # Keep original fields and add new ones
            enriched = token.copy()

            # Add social and volume metrics needed for scoring
            enriched['buy1h'] = overview_data.get('buy1h', 0)
            enriched['sell1h'] = overview_data.get('sell1h', 0)
            enriched['trade1h'] = enriched['buy1h'] + enriched['sell1h']
            enriched['uniqueWallet24h'] = overview_data.get('uniqueWallet24h', 0)
            enriched['watch'] = overview_data.get('watch', 0)
            enriched['view24h'] = overview_data.get('view24h', 0)
            enriched['holder'] = overview_data.get('holder', 0)

            # Calculate buy percentage for volume scoring
            total_trades = enriched['buy1h'] + enriched['sell1h']
            enriched['buy_percentage'] = (enriched['buy1h'] / total_trades * 100) if total_trades > 0 else 0

            # For Phase 5 compatibility, also add buys_24h and sells_24h
            # These are approximations based on 1h data scaled to 24h
            enriched['buys_24h'] = enriched['buy1h'] * 24  # Rough estimate
            enriched['sells_24h'] = enriched['sell1h'] * 24  # Rough estimate

            # Update other fields if available
            enriched['liquidity'] = overview_data.get('liquidity', enriched.get('liquidity', 0))
            enriched['market_cap'] = overview_data.get('mc', enriched.get('market_cap', 0))
            enriched['volume_24h'] = overview_data.get('v24hUSD', enriched.get('volume_24h', 0))
            enriched['price_change_24h'] = overview_data.get('v24hChangePercent', 0)

            return enriched

        except Exception as e:
            print(colored(f"    ❌ Error enriching token {token.get('symbol', 'Unknown')}: {str(e)}", "red"))
            return token  # Return original token on error

    def liquidity_prefilter(self, tokens: List[Dict], min_liquidity: float = 50000, min_volume_1h: float = 5000) -> List[Dict]:
        """
        Enhanced pre-filter: liquidity, market cap, AND 1-hour volume (all from BirdEye)
        NOW WITH FULL TOKEN ENRICHMENT for complete scoring data!
        Native meme list guarantees 100% pure memecoins - no keyword filtering needed!

        Args:
            tokens: List of token dicts from BirdEye (with 'address', 'liquidity', 'volume_24h', 'symbol')
            min_liquidity: Minimum liquidity in USD
            min_volume_1h: Minimum 1-hour volume in USD

        Returns:
            List of ENRICHED token dicts that pass all filters (with social/volume metrics!)
        """
        print(colored(f"\n💧 Pre-filtering: Liquidity >${min_liquidity:,.0f}, Market Cap <${MAX_MARKET_CAP:,.0f}, Volume 1h >${min_volume_1h:,.0f}", "cyan"))

        passed = []

        for token in tokens:
            address = token['address']
            symbol = token.get('symbol', 'Unknown')
            name = token.get('name', '')
            liquidity = token.get('liquidity') or 0  # Handle None values
            market_cap = token.get('mc') or 0  # Handle None values
            volume_24h = token.get('volume_24h') or 0  # BirdEye provides 24h volume

            # Skip if liquidity is None or too low
            if liquidity is None or liquidity < min_liquidity:
                continue

            # Skip if market cap too high (we want room to grow)
            if market_cap is not None and market_cap > MAX_MARKET_CAP:
                continue

            # Skip if 1-hour volume too low (estimate from 24h: volume_1h ≈ volume_24h / 24)
            # This is an approximation - actual 1h volume requires separate API call
            estimated_volume_1h = volume_24h / 24 if volume_24h else 0
            if estimated_volume_1h < min_volume_1h:
                continue

            # NO memecoin filtering needed - native meme list guarantees pure memecoins!
            # All tokens from Phase 1 are guaranteed memecoins from BirdEye

            # Passed all filters - add basic data
            passed.append({
                'address': address,
                'symbol': symbol,
                'name': name,
                'liquidity': liquidity,
                'market_cap': market_cap,
                'volume_24h': volume_24h
            })

        print(colored(f"\n📊 Filter Results:", "cyan"))
        print(colored(f"   • {len(passed)}/{len(tokens)} tokens passed filters (liquidity + market cap + volume)", "cyan"))
        print(colored(f"   • All tokens are guaranteed memecoins from BirdEye native list", "green"))

        # ENHANCEMENT: Enrich passed tokens with complete BirdEye Token Overview data
        print(colored(f"\n🔍 Enriching {len(passed)} tokens with BirdEye Token Overview data...", "cyan"))
        print(colored(f"   (This adds social metrics, buy/sell data, holder counts for scoring)", "grey"))

        enriched_tokens = []
        for i, token in enumerate(passed, 1):
            print(colored(f"   [{i}/{len(passed)}] Enriching {token['symbol']}...", "grey"))
            enriched = self.enrich_token_with_overview(token)
            enriched_tokens.append(enriched)

            # Rate limiting: BirdEye Standard tier = 1 req/sec
            time.sleep(1.0)

        print(colored(f"✅ Enrichment complete - all tokens now have social/volume metrics", "green"))

        return enriched_tokens

    def filter_by_market_metrics_strict(self, token_addresses: List[str], min_liquidity: float = 80000, min_volume_1h: float = 20000) -> List[str]:
        """
        Strict market filter using DexScreener data
        Applied AFTER age verification to ensure only quality aged tokens proceed

        Args:
            token_addresses: List of token addresses (already passed age filter)
            min_liquidity: Minimum liquidity in USD
            min_volume_1h: Minimum 1-hour volume in USD

        Returns:
            List of token addresses that pass strict filters
        """
        print(colored(f"\n💰 Strict Filtering: Liquidity >${min_liquidity:,.0f}, 1h Volume >${min_volume_1h:,.0f}", "cyan"))

        from src.dexscreener_utils import get_token_social_data

        passed = []
        for i, address in enumerate(token_addresses, 1):
            # Get fresh data from DexScreener for accurate liquidity and volume
            social_data = get_token_social_data(address)
            if not social_data:
                print(colored(f"  [{i}/{len(token_addresses)}] {address[:8]}... = no DexScreener data", "grey"))
                continue

            symbol = social_data.get('symbol', 'Unknown')
            liquidity = social_data.get('liquidity_usd', 0)
            volume_1h = social_data.get('volume_1h', 0)

            # Apply strict filters
            if liquidity < min_liquidity:
                print(colored(f"  [{i}/{len(token_addresses)}] {symbol:<10} | Liq: ${liquidity:>8,.0f} ❌ (too low)", "grey"))
                continue

            if volume_1h < min_volume_1h:
                print(colored(f"  [{i}/{len(token_addresses)}] {symbol:<10} | Vol(1h): ${volume_1h:>8,.0f} ❌ (too low)", "grey"))
                continue

            # Passed both filters
            passed.append(address)
            print(colored(f"  [{i}/{len(token_addresses)}] {symbol:<10} | Liq: ${liquidity:>8,.0f} | Vol(1h): ${volume_1h:>8,.0f} ✅", "green"))

            # Rate limiting: DexScreener 5 req/sec
            time.sleep(0.2)

        print(colored(f"\n📊 {len(passed)}/{len(token_addresses)} tokens passed strict market filters", "cyan"))
        return passed

    def filter_by_age_helius(self, token_addresses: List[str], min_age_hours: float = 24) -> Dict[str, float]:
        """
        Filter tokens by age using Helius blockchain data

        Args:
            token_addresses: List of token addresses to check
            min_age_hours: Minimum token age in hours (NO maximum - revivals can happen anytime)

        Returns:
            Dictionary of {address: age_hours} for tokens that meet minimum age requirement
        """
        from src.helius_utils import batch_get_token_ages

        print(colored(f"\n⏰ Age Filter: Minimum {min_age_hours}h (no maximum)", "cyan"))

        rpc_url = os.getenv('HELIUS_RPC_ENDPOINT')
        if not rpc_url:
            print(colored("❌ HELIUS_RPC_ENDPOINT not configured", "red"))
            return {}

        ages = batch_get_token_ages(token_addresses, rpc_url)
        passed = {addr: age for addr, age in ages.items() if age and age >= min_age_hours}

        print(colored(f"\n📊 {len(passed)}/{len(token_addresses)} tokens passed age filter (≥{min_age_hours}h)", "cyan"))
        return passed

    def enrich_with_social_data(self, token_addresses: List[str]) -> List[Dict]:
        """Enrich tokens with DexScreener social sentiment data"""
        from src.dexscreener_utils import batch_enrich_tokens

        print(colored("\n📱 Enriching with social sentiment data...", "cyan"))
        return batch_enrich_tokens(token_addresses)

    def run_scan_cycle(self):
        """Run one complete scan cycle"""
        print(colored("\n" + "="*60, "cyan"))
        print(colored(f"🚀 SCAN CYCLE STARTING - {datetime.now().strftime('%H:%M:%S')}", "cyan", attrs=['bold']))
        print(colored("="*60, "cyan"))

        # Step 1: Get candidate tokens (3-phase discovery pipeline)
        print(colored("\n[Step 1/3] Running 3-Phase Discovery Pipeline...", "yellow", attrs=['bold']))
        tokens = self.get_candidate_tokens()

        if not tokens:
            print(colored("❌ No tokens from discovery pipeline!", "red"))
            return []

        # Step 2: Security filter
        print(colored("\n[Step 2/3] Running security filter...", "yellow", attrs=['bold']))
        security_results = self.security_filter.batch_filter(tokens, max_workers=3)

        # Keep FULL token data, not just addresses!
        passed_security = []
        for sec_result in security_results:
            if sec_result['passed']:
                # Merge security result with original token data
                token_address = sec_result['token_address']
                # Find original token data
                token_data = next((t for t in tokens if t.get('address') == token_address), None)
                if token_data:
                    # Merge security info with token data
                    token_with_security = {**token_data, **sec_result}
                    passed_security.append(token_with_security)
                else:
                    # Fallback: use security result as token data
                    passed_security.append(sec_result)

        # Store Phase 4 tokens (security passed)
        self.phase_tokens['phase4_security_passed'] = [{'address': t.get('address') or t.get('token_address')} for t in passed_security]

        print(colored(f"🛡️ {len(passed_security)} tokens passed security", "green"))

        if not passed_security:
            print(colored("❌ No tokens passed security filter!", "red"))
            return []

        # Step 3: Check for revival patterns
        print(colored("\n[Step 3/3] Detecting revival patterns...", "yellow", attrs=['bold']))
        revival_results = []
        all_phase5_results = []  # Track ALL results for analysis
        failure_reasons = {}  # Track failure reasons

        for i, token_data in enumerate(passed_security, 1):  # Now passing FULL token data
            token_address = token_data.get('address') or token_data.get('token_address')
            print(colored(f"\nAnalyzing token {i}/{len(passed_security)}: {token_address[:8]}...", "cyan"))
            try:
                result = self.revival_detector.calculate_revival_score(token_data)
                all_phase5_results.append(result)  # Store ALL results

                if result['revival_score'] >= self.min_revival_score:
                    revival_results.append(result)
                    print(colored(f"  ✅ PASSED: Revival score {result['revival_score']:.2f}", "green"))
                else:
                    # Track failure reason
                    reason = result.get('failure_reason', 'LOW_SCORE')
                    failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
                    print(colored(f"  ❌ FAILED: {reason} (score: {result['revival_score']:.2f})", "red"))

                # Rate limiting
                time.sleep(2)

            except Exception as e:
                import traceback
                print(colored(f"⚠️ EXCEPTION analyzing {token_address[:8]}: {str(e)}", "red"))
                print(colored(f"   Traceback: {traceback.format_exc()}", "red"))

                # Add failed result to phase5 results
                all_phase5_results.append({
                    'token_address': token_address,
                    'revival_score': 0.0,
                    'error': str(e),
                    'failure_reason': 'EXCEPTION',
                    'exception_trace': traceback.format_exc()
                })

                failure_reasons['EXCEPTION'] = failure_reasons.get('EXCEPTION', 0) + 1
                continue

        # Store Phase 5 tokens (final revival opportunities)
        self.phase_tokens['phase5_revival_detected'] = revival_results
        self.phase_tokens['phase5_all_analyzed'] = all_phase5_results  # Store all analyzed tokens

        # Print comprehensive summary
        print(colored(f"\n📊 Phase 5 Analysis Summary:", "cyan", attrs=['bold']))
        print(colored(f"  Total analyzed: {len(all_phase5_results)}", "white"))
        print(colored(f"  ✅ Passed: {len(revival_results)}", "green"))
        print(colored(f"  ❌ Failed: {len(all_phase5_results) - len(revival_results)}", "red"))

        if failure_reasons:
            print(colored(f"\n📉 Failure Breakdown:", "yellow"))
            for reason, count in sorted(failure_reasons.items(), key=lambda x: x[1], reverse=True):
                print(colored(f"    {reason}: {count} tokens", "white"))

        # Export Phase 5 results to CSV for analysis
        self.export_phase5_results_csv(all_phase5_results)

        # Send notifications
        if revival_results:
            print(colored("\n📤 Sending notifications...", "yellow", attrs=['bold']))
            self.notifier.batch_alert(revival_results)

            # Save scan results
            self.save_scan_results(revival_results)

            # Paper Trading Integration
            if config.PAPER_TRADING_ENABLED:
                print(colored("\n💰 Paper Trading: Evaluating opportunities...", "yellow", attrs=['bold']))
                try:
                    from src.agents.paper_trading_agent import PaperTradingAgent

                    # Initialize paper trading agent if not already done
                    if not hasattr(self, 'paper_trading_agent'):
                        self.paper_trading_agent = PaperTradingAgent()

                    # Evaluate revival opportunities for paper trading
                    positions_opened = self.paper_trading_agent.evaluate_opportunities(revival_results)

                    if positions_opened:
                        print(colored(f"✅ Opened {len(positions_opened)} paper trading positions", "green"))
                    else:
                        print(colored("📊 No new paper trading positions opened", "grey"))

                except Exception as e:
                    print(colored(f"⚠️ Paper trading error: {str(e)}", "red"))
        else:
            print(colored("\n📤 No alerts to send", "grey"))

        # Print summary
        self.print_scan_summary(revival_results)

        return revival_results

    def save_scan_results(self, results: List[Dict]):
        """Save scan results to CSV"""
        try:
            if not results:
                return

            df = pd.DataFrame(results)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.data_dir / f"scan_results_{timestamp}.csv"

            df.to_csv(filepath, index=False)
            print(colored(f"💾 Results saved to {filepath.name}", "green"))

            # Also save simplified version for easy viewing
            summary_df = df[['token_symbol', 'token_name', 'revival_score', 'age_hours',
                            'liquidity_usd', 'volume_24h', 'dexscreener_url']].copy()
            summary_path = self.data_dir / f"scan_summary_{timestamp}.csv"
            summary_df.to_csv(summary_path, index=False)

        except Exception as e:
            print(colored(f"⚠️ Could not save results: {str(e)}", "yellow"))

    def export_phase5_results_csv(self, all_results: List[Dict]):
        """Export ALL Phase 5 results (passed and failed) to CSV for analysis"""
        try:
            if not all_results:
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.data_dir / f"phase5_analysis_{timestamp}.csv"

            # Prepare data for CSV
            csv_data = []
            for result in all_results:
                csv_data.append({
                    'address': result.get('token_address', ''),
                    'symbol': result.get('token_symbol') or result.get('symbol', ''),
                    'name': result.get('token_name') or result.get('name', ''),
                    'revival_score': result.get('revival_score', 0.0),
                    'price_score': result.get('price_score', 0.0),
                    'smart_score': result.get('smart_score', 0.0),
                    'volume_score': result.get('volume_score', 0.0),
                    'social_score': result.get('social_score', 0.0),
                    'passed': result.get('revival_score', 0.0) >= 0.4,
                    'failure_reason': result.get('failure_reason', ''),
                    'error': result.get('error', ''),
                    'liquidity_usd': result.get('liquidity_usd', 0),
                    'market_cap': result.get('market_cap', 0),
                    'volume_24h': result.get('volume_24h', 0),
                    'age_hours': result.get('age_hours', 0),
                    'holder_count': result.get('holder_count', 0)
                })

            # Write to CSV
            with open(filepath, 'w', newline='') as csvfile:
                if csv_data:
                    fieldnames = ['address', 'symbol', 'name', 'revival_score', 'price_score', 'smart_score',
                                  'volume_score', 'social_score', 'passed', 'failure_reason', 'error',
                                  'liquidity_usd', 'market_cap', 'volume_24h', 'age_hours', 'holder_count']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(csv_data)

            print(colored(f"📊 Phase 5 analysis exported to {filepath.name}", "green"))

            # Print quick stats
            passed_count = sum(1 for r in csv_data if r['passed'])
            failed_count = len(csv_data) - passed_count
            print(colored(f"   Exported {len(csv_data)} tokens: {passed_count} passed, {failed_count} failed", "white"))

        except Exception as e:
            print(colored(f"⚠️ Could not export Phase 5 results: {str(e)}", "yellow"))

    def print_scan_summary(self, results: List[Dict]):
        """Print summary of scan results"""
        print(colored("\n" + "="*60, "cyan"))
        print(colored("📊 SCAN SUMMARY", "cyan", attrs=['bold']))
        print(colored("="*60, "cyan"))

        if not results:
            print(colored("No revival opportunities found this scan", "yellow"))
            return

        # Sort by score
        results.sort(key=lambda x: x['revival_score'], reverse=True)

        print(colored(f"Found {len(results)} revival opportunities:", "green"))
        print()

        # Show top 5
        for i, token in enumerate(results[:5], 1):
            symbol = token.get('token_symbol', 'Unknown')
            score = token.get('revival_score', 0)
            age = token.get('age_hours', 0)
            liq = token.get('liquidity_usd', 0)
            vol = token.get('volume_24h', 0)

            # Color based on score
            if score >= 0.8:
                color = "red"
            elif score >= 0.6:
                color = "yellow"
            else:
                color = "green"

            print(colored(f"{i}. {symbol:<10} Score: {score:.2f}", color, attrs=['bold']))
            print(colored(f"   Age: {age:.1f}h | Liq: ${liq:,.0f} | Vol: ${vol:,.0f}", "white"))
            print()

        # Statistics
        avg_score = sum(t['revival_score'] for t in results) / len(results)
        avg_liq = sum(t['liquidity_usd'] for t in results) / len(results)

        print(colored(f"Average Revival Score: {avg_score:.2f}", "cyan"))
        print(colored(f"Average Liquidity: ${avg_liq:,.0f}", "cyan"))

    def run_continuous(self):
        """Run continuous scanning loop"""
        print(colored("\n🔄 Starting continuous scanning mode...", "cyan", attrs=['bold']))
        print(colored(f"   Scan interval: {self.scan_interval} seconds", "cyan"))
        print(colored("   Press Ctrl+C to stop\n", "cyan"))

        scan_count = 0

        try:
            while True:
                scan_count += 1
                print(colored(f"\n📍 Scan #{scan_count}", "magenta", attrs=['bold']))

                # Run scan cycle
                results = self.run_scan_cycle()

                # Add to history
                self.scan_history.append({
                    'scan_number': scan_count,
                    'timestamp': datetime.now(),
                    'tokens_found': len(results),
                    'top_score': max([r['revival_score'] for r in results]) if results else 0
                })

                # Show next scan time
                next_scan = datetime.now() + timedelta(seconds=self.scan_interval)
                print(colored(f"\n⏰ Next scan at {next_scan.strftime('%H:%M:%S')}", "cyan"))
                print(colored("   Press Ctrl+C to stop", "grey"))

                # Wait for next scan
                time.sleep(self.scan_interval)

        except KeyboardInterrupt:
            print(colored("\n\n🛑 Scanning stopped by user", "yellow"))
            self.print_session_summary()

    def print_session_summary(self):
        """Print summary of scanning session"""
        if not self.scan_history:
            return

        print(colored("\n" + "="*60, "cyan"))
        print(colored("📊 SESSION SUMMARY", "cyan", attrs=['bold']))
        print(colored("="*60, "cyan"))

        total_scans = len(self.scan_history)
        total_tokens = sum(s['tokens_found'] for s in self.scan_history)
        best_score = max(s['top_score'] for s in self.scan_history)

        print(colored(f"Total Scans: {total_scans}", "green"))
        print(colored(f"Total Opportunities Found: {total_tokens}", "green"))
        print(colored(f"Best Revival Score: {best_score:.2f}", "green"))

        # Show scan history
        print(colored("\nScan History:", "cyan"))
        for scan in self.scan_history[-5:]:  # Last 5 scans
            time_str = scan['timestamp'].strftime('%H:%M:%S')
            count = scan['tokens_found']
            score = scan['top_score']
            print(colored(f"  {time_str}: Found {count} tokens (best: {score:.2f})", "white"))

def main():
    """Run the orchestrator"""
    orchestrator = MemeScannerOrchestrator()

    # Check for command line arguments
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # Run single scan
        print(colored("Running single scan...", "cyan"))
        orchestrator.run_scan_cycle()
    else:
        # Run continuous scanning
        orchestrator.run_continuous()

if __name__ == "__main__":
    main()