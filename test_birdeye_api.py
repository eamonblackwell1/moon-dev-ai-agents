#!/usr/bin/env python3
"""
🔬 BirdEye API Capability Testing Script
Tests the native meme token list API to determine optimal configuration

Tests:
1. Maximum native meme list size (pagination limits)
2. Sorting support (sort_by parameter)
3. Memecoin filter accuracy on generic tokens

This will help us achieve 100% pure memecoins with maximum coverage.
"""

import os
import sys
import time
import requests
from termcolor import colored
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BIRDEYE_API_KEY = os.getenv('BIRDEYE_API_KEY')
if not BIRDEYE_API_KEY:
    print(colored("❌ BIRDEYE_API_KEY not found in .env", "red"))
    sys.exit(1)

HEADERS = {'X-API-KEY': BIRDEYE_API_KEY}

print(colored("🔬 BirdEye API Capability Testing", "cyan", attrs=['bold']))
print(colored("=" * 60, "cyan"))

# ============================================================================
# TEST 1: Native Meme List Size & Pagination Limits
# ============================================================================

def test_native_meme_list_size():
    """
    Test how many tokens are available in the native meme list.
    Paginate until API returns empty results.
    """
    print(colored("\n📊 TEST 1: Native Meme List Size & Pagination", "yellow", attrs=['bold']))
    print(colored("-" * 60, "yellow"))

    offset = 0
    limit = 50
    total_tokens = 0
    all_symbols = []

    while True:
        url = f"https://public-api.birdeye.so/defi/v3/token/meme/list?chain=solana&offset={offset}&limit={limit}"

        print(colored(f"  Fetching offset {offset}...", "cyan"), end=" ")

        try:
            response = requests.get(url, headers=HEADERS, timeout=15)

            if response.status_code == 429:
                print(colored("⚠️ Rate limited, waiting 60s...", "yellow"))
                time.sleep(60)
                continue

            if response.status_code != 200:
                print(colored(f"❌ HTTP {response.status_code}", "red"))
                break

            data = response.json()

            # Native meme list API does NOT have 'success' field
            # It returns data.items (NOT data.tokens)

            tokens = data.get('data', {}).get('items', [])

            if not tokens:
                print(colored("✅ End of list (empty response)", "green"))
                break

            batch_size = len(tokens)
            total_tokens += batch_size
            all_symbols.extend([t.get('symbol', 'Unknown') for t in tokens])

            print(colored(f"✅ Got {batch_size} tokens (total: {total_tokens})", "green"))

            # If we got fewer than requested, we've reached the end
            if batch_size < limit:
                print(colored(f"  📍 Last page (partial batch: {batch_size}/{limit})", "cyan"))
                break

            offset += limit
            time.sleep(1.0)  # Rate limiting: 1 req/sec

            # Safety limit to prevent infinite loops
            if offset >= 5000:
                print(colored(f"  ⚠️ Safety limit reached at offset {offset}", "yellow"))
                break

        except Exception as e:
            print(colored(f"❌ Error: {str(e)}", "red"))
            break

    print(colored(f"\n✅ RESULT: Native meme list has {total_tokens} tokens", "green", attrs=['bold']))
    print(colored(f"   Sample symbols: {', '.join(all_symbols[:20])}...", "cyan"))

    return total_tokens


# ============================================================================
# TEST 2: Sorting Support
# ============================================================================

def test_sorting_support():
    """
    Test if native meme list supports sort_by parameter.
    Try different sorting strategies.
    """
    print(colored("\n🔀 TEST 2: Sorting Support", "yellow", attrs=['bold']))
    print(colored("-" * 60, "yellow"))

    sort_options = [
        ('liquidity', 'Liquidity (High to Low)'),
        ('v24hUSD', '24h Volume'),
        ('v1hUSD', '1h Volume'),
        ('mc', 'Market Cap'),
        ('v24hChangePercent', '24h Price Change %'),
    ]

    results = {}

    for sort_by, description in sort_options:
        print(colored(f"\n  Testing sort_by={sort_by} ({description})...", "cyan"))

        # Test with sort parameter
        url = f"https://public-api.birdeye.so/defi/v3/token/meme/list?chain=solana&sort_by={sort_by}&sort_type=desc&offset=0&limit=10"

        try:
            response = requests.get(url, headers=HEADERS, timeout=15)

            if response.status_code == 429:
                print(colored("    ⚠️ Rate limited, waiting 60s...", "yellow"))
                time.sleep(60)
                response = requests.get(url, headers=HEADERS, timeout=15)

            if response.status_code != 200:
                print(colored(f"    ❌ HTTP {response.status_code}", "red"))
                results[sort_by] = False
                time.sleep(1.0)
                continue

            data = response.json()

            # Native meme list uses data.items, not data.tokens

            tokens = data.get('data', {}).get('items', [])

            if not tokens:
                print(colored(f"    ❌ No tokens returned", "red"))
                results[sort_by] = False
                time.sleep(1.0)
                continue

            # Check if tokens appear sorted
            values = [t.get(sort_by, 0) for t in tokens if sort_by in t]

            if len(values) > 1:
                is_sorted = all(values[i] >= values[i+1] for i in range(len(values)-1))

                if is_sorted:
                    print(colored(f"    ✅ WORKS! Top value: {values[0]:,.2f}", "green"))
                    print(colored(f"       Sample: {', '.join([t.get('symbol', '?') for t in tokens[:5]])}", "cyan"))
                    results[sort_by] = True
                else:
                    print(colored(f"    ⚠️ Sorting unclear (values: {values[:3]}...)", "yellow"))
                    results[sort_by] = 'unclear'
            else:
                print(colored(f"    ⚠️ Not enough data to verify sorting", "yellow"))
                results[sort_by] = 'unclear'

            time.sleep(1.0)  # Rate limiting

        except Exception as e:
            print(colored(f"    ❌ Error: {str(e)}", "red"))
            results[sort_by] = False

    # Summary
    print(colored(f"\n📊 SORTING SUPPORT SUMMARY:", "green", attrs=['bold']))
    for sort_by, status in results.items():
        if status == True:
            print(colored(f"   ✅ {sort_by}: SUPPORTED", "green"))
        elif status == 'unclear':
            print(colored(f"   ⚠️ {sort_by}: UNCLEAR", "yellow"))
        else:
            print(colored(f"   ❌ {sort_by}: NOT SUPPORTED", "red"))

    return results


# ============================================================================
# TEST 3: Memecoin Filter Accuracy
# ============================================================================

def test_memecoin_filter_accuracy():
    """
    Test the accuracy of is_likely_memecoin() filter on generic tokenlist.
    Sample 50 tokens from generic list and manually categorize.
    """
    print(colored("\n🎯 TEST 3: Memecoin Filter Accuracy", "yellow", attrs=['bold']))
    print(colored("-" * 60, "yellow"))

    # Import the filter function
    sys.path.append('/Users/eamonblackwell/Meme Coin Trading Bot/moon-dev-ai-agents')
    from src.agents.meme_scanner_orchestrator import MemeScannerOrchestrator

    orchestrator = MemeScannerOrchestrator()

    # Fetch 50 tokens from generic list (high volume = likely interesting)
    url = f"https://public-api.birdeye.so/defi/tokenlist?chain=solana&sort_by=v24hUSD&sort_type=desc&offset=0&limit=50"

    print(colored("  Fetching 50 high-volume tokens from generic list...", "cyan"))

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)

        if response.status_code != 200:
            print(colored(f"  ❌ HTTP {response.status_code}", "red"))
            return None

        data = response.json()

        if not data.get('success'):
            print(colored(f"  ❌ API returned success=false", "red"))
            return None

        tokens = data.get('data', {}).get('tokens', [])

        if not tokens:
            print(colored(f"  ❌ No tokens returned", "red"))
            return None

        print(colored(f"  ✅ Got {len(tokens)} tokens\n", "green"))

        # Test filter on each token
        classified_meme = []
        classified_non_meme = []

        for token in tokens:
            symbol = token.get('symbol', '')
            name = token.get('name', '')

            is_meme = orchestrator.is_likely_memecoin(symbol, name)

            if is_meme:
                classified_meme.append((symbol, name))
            else:
                classified_non_meme.append((symbol, name))

        # Display results
        print(colored(f"📊 FILTER RESULTS:", "cyan", attrs=['bold']))
        print(colored(f"   Classified as MEMECOIN: {len(classified_meme)}", "green"))
        print(colored(f"   Classified as NON-MEMECOIN: {len(classified_non_meme)}", "red"))
        print(colored(f"   Memecoin %: {len(classified_meme)/len(tokens)*100:.1f}%", "yellow"))

        print(colored(f"\n✅ MEMECOINS ({len(classified_meme)}):", "green"))
        for symbol, name in classified_meme[:20]:
            print(colored(f"   {symbol:<12} - {name}", "cyan"))

        print(colored(f"\n❌ NON-MEMECOINS ({len(classified_non_meme)}):", "red"))
        for symbol, name in classified_non_meme[:20]:
            print(colored(f"   {symbol:<12} - {name}", "cyan"))

        return {
            'total': len(tokens),
            'memecoins': len(classified_meme),
            'non_memecoins': len(classified_non_meme),
            'memecoin_percentage': len(classified_meme)/len(tokens)*100
        }

    except Exception as e:
        print(colored(f"  ❌ Error: {str(e)}", "red"))
        return None


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print(colored("\n🚀 Starting API capability tests...\n", "cyan"))

    # Run all tests
    native_list_size = test_native_meme_list_size()

    time.sleep(2)  # Pause between tests

    sorting_results = test_sorting_support()

    time.sleep(2)

    filter_accuracy = test_memecoin_filter_accuracy()

    # Final Summary
    print(colored("\n" + "=" * 60, "cyan"))
    print(colored("🎯 FINAL SUMMARY", "cyan", attrs=['bold']))
    print(colored("=" * 60, "cyan"))

    print(colored(f"\n1️⃣ Native Meme List Size: {native_list_size} tokens", "green"))

    print(colored(f"\n2️⃣ Sorting Support:", "green"))
    supported_sorts = [k for k, v in sorting_results.items() if v == True]
    if supported_sorts:
        print(colored(f"   ✅ Supported: {', '.join(supported_sorts)}", "green"))
    else:
        print(colored(f"   ❌ No sorting support detected", "red"))

    if filter_accuracy:
        print(colored(f"\n3️⃣ Memecoin Filter Accuracy:", "green"))
        print(colored(f"   {filter_accuracy['memecoin_percentage']:.1f}% of high-volume tokens classified as memecoins", "cyan"))

    # Recommendations based on results
    print(colored(f"\n💡 RECOMMENDATIONS:", "yellow", attrs=['bold']))

    if native_list_size >= 1000:
        print(colored(f"   ✅ Native list has {native_list_size} tokens - can achieve 1000+ pure memecoins!", "green"))
        if supported_sorts:
            print(colored(f"   ✅ Use multiple sort strategies on native list for max coverage", "green"))
        else:
            print(colored(f"   ⚠️ Fetch sequentially up to {native_list_size} tokens", "yellow"))
    elif native_list_size >= 500:
        print(colored(f"   ⚠️ Native list has {native_list_size} tokens - supplement with filtered generic lists", "yellow"))
    else:
        print(colored(f"   ❌ Native list only has {native_list_size} tokens - need hybrid approach", "red"))

    print(colored(f"\n✅ Tests complete! Results will guide optimal Phase 1 implementation.", "green", attrs=['bold']))
    print()
