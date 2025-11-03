#!/usr/bin/env python3
"""
Test script to fetch top 2000 tokens by liquidity from BirdEye
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BIRDEYE_API_KEY = os.getenv('BIRDEYE_API_KEY')
if not BIRDEYE_API_KEY:
    print("Error: BIRDEYE_API_KEY not found in .env")
    exit(1)

def get_birdeye_meme_tokens_by_liquidity(tokens_to_fetch=2000):
    """
    Fetch top N meme tokens sorted by liquidity from BirdEye API
    """
    base_url = "https://public-api.birdeye.so/defi/v3/token/meme/list"

    headers = {
        'X-API-KEY': BIRDEYE_API_KEY,
        'x-chain': 'solana',
    }

    all_tokens = []
    tokens_fetched = 0
    page_size = 50  # BirdEye default page size

    print(f"\nFetching top {tokens_to_fetch} tokens sorted by liquidity...")
    print("=" * 60)

    while tokens_fetched < tokens_to_fetch:
        try:
            params = {
                'chain': 'solana',
                'offset': tokens_fetched,
                'limit': min(page_size, tokens_to_fetch - tokens_fetched),
                'sort_by': 'liquidity',
                'sort_type': 'desc'
            }

            response = requests.get(base_url, headers=headers, params=params, timeout=30)

            if response.status_code == 429:
                print("Rate limited, waiting 60 seconds...")
                time.sleep(60)
                continue

            if response.status_code != 200:
                print(f"Error: API returned status {response.status_code}")
                print(f"Response: {response.text}")
                break

            data = response.json()

            # Check response structure
            if 'data' not in data:
                print(f"Unexpected response structure: {data}")
                break

            # BirdEye uses data.items for meme list
            items = data.get('data', {}).get('items', [])

            if not items:
                print(f"No more tokens available at offset {tokens_fetched}")
                break

            for token in items:
                token_info = {
                    'rank': tokens_fetched + 1,  # Add rank for clarity
                    'address': token.get('address', 'N/A'),
                    'symbol': token.get('symbol', 'N/A'),
                    'name': token.get('name', 'N/A'),
                    'liquidity': token.get('liquidity', 0),
                    'volume_24h': token.get('volume_24h_usd', 0),
                    'market_cap': token.get('market_cap', 0),
                    'price': token.get('price', 0),
                    'price_change_24h': token.get('price_change_24h', 0),
                }
                all_tokens.append(token_info)
                tokens_fetched += 1

            # Progress update every 200 tokens
            if tokens_fetched % 200 == 0:
                print(f"Fetched {tokens_fetched}/{tokens_to_fetch} tokens...")
                if all_tokens:
                    latest = all_tokens[-1]
                    print(f"  Latest: {latest['symbol']} - Liquidity: ${latest['liquidity']:,.0f}")

            # Rate limiting
            time.sleep(1.0)  # BirdEye standard tier: 1 request per second

        except Exception as e:
            print(f"Error fetching tokens: {e}")
            break

    return all_tokens

def analyze_liquidity_distribution(tokens):
    """
    Analyze the liquidity distribution of fetched tokens
    """
    df = pd.DataFrame(tokens)

    print("\n" + "=" * 60)
    print("LIQUIDITY DISTRIBUTION ANALYSIS")
    print("=" * 60)

    # Basic stats
    print(f"\nTotal tokens fetched: {len(df)}")

    # Liquidity buckets for revival strategy
    liquidity_values = df['liquidity'].values

    # Define buckets
    buckets = [
        ("Dead (<$1K)", 0, 1000),
        ("Very Low ($1K-$5K)", 1000, 5000),
        ("Low ($5K-$10K)", 5000, 10000),
        ("Borderline ($10K-$20K)", 10000, 20000),
        ("Revival Sweet Spot ($20K-$50K)", 20000, 50000),
        ("Good Liquidity ($50K-$100K)", 50000, 100000),
        ("High Liquidity ($100K-$500K)", 100000, 500000),
        ("Very High ($500K-$1M)", 500000, 1000000),
        ("Established ($1M+)", 1000000, float('inf'))
    ]

    print("\nTokens by Liquidity Range:")
    print("-" * 50)

    for bucket_name, min_val, max_val in buckets:
        if max_val == float('inf'):
            count = (liquidity_values >= min_val).sum()
        else:
            count = ((liquidity_values >= min_val) & (liquidity_values < max_val)).sum()

        percentage = (count / len(df)) * 100 if len(df) > 0 else 0
        print(f"{bucket_name:30} {count:5} tokens ({percentage:5.1f}%)")

    # Key thresholds
    print("\nKey Threshold Analysis:")
    print("-" * 50)

    pass_20k_filter = (liquidity_values >= 20000).sum()
    fail_20k_filter = (liquidity_values < 20000).sum()

    print(f"Pass $20K filter: {pass_20k_filter} tokens ({pass_20k_filter/len(df)*100:.1f}%)")
    print(f"Fail $20K filter: {fail_20k_filter} tokens ({fail_20k_filter/len(df)*100:.1f}%)")

    # Find the sweet spot range
    sweet_spot = df[(df['liquidity'] >= 20000) & (df['liquidity'] <= 100000)]
    print(f"\nRevival Sweet Spot ($20K-$100K): {len(sweet_spot)} tokens")

    # Show where the cliff is
    print("\nLiquidity at Key Positions:")
    print("-" * 50)

    positions = [1, 100, 200, 500, 1000, 1500, 2000]
    for pos in positions:
        if pos <= len(df):
            token = df.iloc[pos-1]
            print(f"Token #{pos:4}: {token['symbol']:10} - ${token['liquidity']:,.0f}")

    # Stats
    print("\nStatistical Summary:")
    print("-" * 50)
    print(f"Min liquidity:    ${df['liquidity'].min():,.2f}")
    print(f"Max liquidity:    ${df['liquidity'].max():,.2f}")
    print(f"Mean liquidity:   ${df['liquidity'].mean():,.2f}")
    print(f"Median liquidity: ${df['liquidity'].median():,.2f}")

    # Show distribution of top vs bottom
    print("\nTop 10 by Liquidity:")
    print("-" * 50)
    top_10 = df.head(10)[['rank', 'symbol', 'liquidity', 'volume_24h', 'market_cap']]
    for idx, row in top_10.iterrows():
        print(f"#{row['rank']:4} {row['symbol']:10} Liq=${row['liquidity']:>12,.0f} Vol=${row['volume_24h']:>12,.0f}")

    print("\nBottom 10 (of those fetched):")
    print("-" * 50)
    bottom_10 = df.tail(10)[['rank', 'symbol', 'liquidity', 'volume_24h', 'market_cap']]
    for idx, row in bottom_10.iterrows():
        print(f"#{row['rank']:4} {row['symbol']:10} Liq=${row['liquidity']:>12,.0f} Vol=${row['volume_24h']:>12,.0f}")

    return df

def main():
    """
    Main test function
    """
    print("BirdEye Top 2000 Tokens by Liquidity Test")
    print("=" * 60)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Fetch top 2000 by liquidity
    tokens = get_birdeye_meme_tokens_by_liquidity(tokens_to_fetch=2000)

    if tokens:
        df = analyze_liquidity_distribution(tokens)

        # Save to CSV
        csv_path = f"/Users/eamonblackwell/Meme Coin Trading Bot/moon-dev-ai-agents/src/data/birdeye_top_2000_liquidity_{timestamp}.csv"
        df.to_csv(csv_path, index=False)
        print(f"\n" + "=" * 60)
        print(f"Data saved to: {csv_path}")

        # Recommendations based on findings
        print("\n" + "=" * 60)
        print("RECOMMENDATIONS")
        print("=" * 60)

        # Find optimal range for revival trading
        revival_range = df[(df['liquidity'] >= 20000) & (df['liquidity'] <= 100000)]
        if len(revival_range) > 0:
            start_rank = revival_range.iloc[0]['rank']
            end_rank = revival_range.iloc[-1]['rank']
            print(f"\n1. For Revival Trading ($20K-$100K liquidity):")
            print(f"   Focus on ranks {start_rank}-{end_rank} (approximately)")
            print(f"   This gives you {len(revival_range)} potential candidates")

        # Check if we need all 2000
        if len(df) >= 2000:
            last_token = df.iloc[-1]
            if last_token['liquidity'] < 10000:
                print(f"\n2. Token #2000 has only ${last_token['liquidity']:,.0f} liquidity")
                print(f"   Consider fetching fewer tokens (maybe 1000-1500)")

        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)

if __name__ == "__main__":
    main()