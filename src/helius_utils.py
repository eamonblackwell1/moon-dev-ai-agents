"""
Helius RPC utilities for blockchain token age verification
"""
import time
import requests
import json
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime, timedelta
from termcolor import colored
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import threading

# Cache configuration
CACHE_FILE = Path(__file__).parent / "data" / "token_age_cache.json"
CACHE_EXPIRY_HOURS = 24  # Cache entries expire after 24 hours

# Rate limiting for Helius
class RateLimiter:
    """Thread-safe rate limiter for Helius API (10 req/sec)"""
    def __init__(self, max_per_second=10):
        self.max_per_second = max_per_second
        self.min_interval = 1.0 / max_per_second  # 0.1 seconds for 10 req/sec
        self.last_request_time = 0
        self.lock = Lock()

    def wait_if_needed(self):
        """Wait if necessary to respect rate limit"""
        with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                time.sleep(sleep_time)
            self.last_request_time = time.time()

# Global rate limiter instance
helius_rate_limiter = RateLimiter(max_per_second=10)

def load_age_cache() -> Dict:
    """Load token age cache from disk"""
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(colored(f"⚠️ Could not load cache: {str(e)}", "yellow"))
    return {}

def save_age_cache(cache: Dict):
    """Save token age cache to disk"""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(colored(f"⚠️ Could not save cache: {str(e)}", "yellow"))

def get_cached_age(mint_address: str, cache: Dict) -> Optional[float]:
    """Get token age from cache if valid"""
    if mint_address not in cache:
        return None

    entry = cache[mint_address]
    cached_time = datetime.fromisoformat(entry['timestamp'])

    # Check if cache is still valid
    if datetime.now() - cached_time < timedelta(hours=CACHE_EXPIRY_HOURS):
        return entry['age_hours']

    return None

def get_token_creation_timestamp(mint_address: str, rpc_url: str) -> Optional[int]:
    """
    Get token creation timestamp from Solana blockchain using Helius RPC

    Args:
        mint_address: Token mint address (base58 string)
        rpc_url: Helius RPC endpoint URL with API key

    Returns:
        Unix timestamp (seconds) of token creation, or None if failed

    Method:
        1. Call getSignaturesForAddress to get first transaction signature
        2. Call getTransaction to get block time

    Cost: 2 Helius credits (1 per RPC call)
    """
    try:
        # Rate limit the first request
        helius_rate_limiter.wait_if_needed()

        # Step 1: Get the oldest signature for this mint address
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [
                mint_address,
                {
                    "limit": 1000  # Max limit to find oldest transaction
                }
            ]
        }

        response = requests.post(rpc_url, json=payload, timeout=15)

        if response.status_code != 200:
            print(colored(f"❌ Helius RPC error: HTTP {response.status_code}", "red"))
            return None

        data = response.json()

        if 'error' in data:
            print(colored(f"❌ RPC error: {data['error']}", "red"))
            return None

        signatures = data.get('result', [])

        if not signatures:
            return None

        # Get the oldest signature (last in the list, as they're returned newest-first)
        oldest_sig = signatures[-1]['signature']

        # Rate limit the second request
        helius_rate_limiter.wait_if_needed()

        # Step 2: Get transaction details to extract block time
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "getTransaction",
            "params": [
                oldest_sig,
                {
                    "encoding": "json",
                    "maxSupportedTransactionVersion": 0
                }
            ]
        }

        response = requests.post(rpc_url, json=payload, timeout=15)

        if response.status_code != 200:
            return None

        data = response.json()

        if 'error' in data:
            return None

        # Extract block time (Unix timestamp in seconds)
        result = data.get('result', {})
        block_time = result.get('blockTime')

        return block_time

    except Exception as e:
        return None

def get_token_age_hours(mint_address: str, rpc_url: str) -> Optional[float]:
    """
    Get token age in hours

    Args:
        mint_address: Token mint address
        rpc_url: Helius RPC endpoint URL

    Returns:
        Age in hours, or None if failed
    """
    creation_timestamp = get_token_creation_timestamp(mint_address, rpc_url)

    if creation_timestamp is None:
        return None

    # Calculate age in hours
    current_time = time.time()
    age_seconds = current_time - creation_timestamp
    age_hours = age_seconds / 3600

    return age_hours

def batch_get_token_ages(mint_addresses: List[str], rpc_url: str, rate_limit_delay: float = 0.1) -> Dict[str, float]:
    """
    Get ages for multiple tokens efficiently using parallel processing with caching

    Args:
        mint_addresses: List of token mint addresses
        rpc_url: Helius RPC endpoint URL
        rate_limit_delay: Not used anymore (kept for compatibility)

    Returns:
        Dictionary mapping {address: age_hours}

    Rate Limiting:
        Helius FREE tier: 10 requests/second
        We use a thread-safe rate limiter

    Cost:
        2 credits per token (only for uncached tokens)
    """
    results = {}
    failed_count = 0

    # Load cache
    cache = load_age_cache()
    cached_count = 0
    tokens_to_fetch = []

    # Check cache first
    print(colored(f"\n⏰ Checking ages for {len(mint_addresses)} tokens...", "cyan"))
    for mint_address in mint_addresses:
        cached_age = get_cached_age(mint_address, cache)
        if cached_age is not None:
            results[mint_address] = cached_age
            cached_count += 1
        else:
            tokens_to_fetch.append(mint_address)

    if cached_count > 0:
        print(colored(f"   ✨ Found {cached_count} tokens in cache (instant lookup!)", "green"))

    if not tokens_to_fetch:
        print(colored(f"   🎉 All {len(mint_addresses)} tokens found in cache!", "green"))
        return results

    print(colored(f"   📡 Fetching {len(tokens_to_fetch)} new tokens via Helius...", "yellow"))

    # Calculate optimal worker count
    # With 10 req/sec and 2 requests per token, we can process 5 tokens/sec
    # So we want enough workers to keep the pipeline full
    max_workers = min(20, len(tokens_to_fetch))  # Up to 20 workers

    print(colored(f"   Using {max_workers} parallel workers with rate limiting (10 req/sec)!", "yellow"))

    def check_single_token(mint_address: str, index: int, total: int) -> tuple:
        """Worker function to check a single token's age"""
        try:
            # The rate limiter is inside get_token_age_hours
            age_hours = get_token_age_hours(mint_address, rpc_url)

            if age_hours is not None:
                print(colored(f"  [{index}/{total}] {mint_address[:8]}... = {age_hours:.1f}h", "green"))
                return (mint_address, age_hours)
            else:
                print(colored(f"  [{index}/{total}] {mint_address[:8]}... = failed", "grey"))
                return (mint_address, None)

        except Exception as e:
            print(colored(f"  ❌ Error processing {mint_address[:8]}...: {str(e)}", "red"))
            return (mint_address, None)

    # Process tokens in parallel
    new_ages = {}  # Track newly fetched ages
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(check_single_token, addr, i+1, len(tokens_to_fetch)): addr
            for i, addr in enumerate(tokens_to_fetch)
        }

        # Process as they complete
        for future in as_completed(futures):
            mint_address = futures[future]
            try:
                addr, age = future.result()
                if age is not None:
                    results[addr] = age
                    new_ages[addr] = age
                else:
                    failed_count += 1
            except Exception as e:
                print(colored(f"  ❌ Failed to process {mint_address}: {str(e)}", "red"))
                failed_count += 1

    # Calculate and display timing
    elapsed = time.time() - start_time
    tokens_per_sec = len(tokens_to_fetch) / elapsed if elapsed > 0 else 0

    print(colored(f"   ⏱️ Processed {len(tokens_to_fetch)} tokens in {elapsed:.1f}s ({tokens_per_sec:.1f} tokens/sec)", "cyan"))

    # Update cache with new ages
    if new_ages:
        timestamp = datetime.now().isoformat()
        for addr, age in new_ages.items():
            cache[addr] = {
                'age_hours': age,
                'timestamp': timestamp
            }
        save_age_cache(cache)
        print(colored(f"   💾 Saved {len(new_ages)} new token ages to cache", "green"))

    # Summary
    success_count = len(results)
    print(colored(f"   ✅ Success: {success_count}/{len(mint_addresses)} tokens", "green"))
    if failed_count > 0:
        print(colored(f"   ❌ Failed: {failed_count} tokens", "red"))

    return results

# Test function
def main():
    """Test the Helius utilities"""
    # Example Helius RPC endpoint (you need to add your API key)
    rpc_url = "https://mainnet.helius-rpc.com/?api-key=YOUR_KEY_HERE"

    # Example token addresses (replace with real ones)
    test_addresses = [
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
        "So11111111111111111111111111111111111111112",     # SOL
    ]

    print(colored("🚀 Testing Helius token age utilities...", "cyan", attrs=['bold']))

    # Test batch processing
    ages = batch_get_token_ages(test_addresses, rpc_url)

    for addr, age in ages.items():
        if age is not None:
            print(colored(f"  {addr[:8]}... is {age:.1f} hours old", "green"))
        else:
            print(colored(f"  {addr[:8]}... failed to get age", "red"))

if __name__ == "__main__":
    main()