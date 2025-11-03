#!/usr/bin/env python3
"""
Test script to verify BirdEye meme list liquidity data quality
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

def get_birdeye_meme_tokens(tokens_to_fetch=100, sort_by='liquidity', start_offset=0):
    """
    Fetch meme tokens from BirdEye API
    """
    base_url = "https://public-api.birdeye.so/defi/v3/token/meme/list"

    headers = {
        'X-API-KEY': BIRDEYE_API_KEY,
        'x-chain': 'solana',
    }

    all_tokens = []
    tokens_fetched = 0
    page_size = 50  # BirdEye default page size

    print(f"\nFetching {tokens_to_fetch} tokens (sort_by={sort_by}, offset={start_offset})...")

    while tokens_fetched < tokens_to_fetch:
        try:
            params = {
                'chain': 'solana',
                'offset': start_offset + tokens_fetched,
                'limit': min(page_size, tokens_to_fetch - tokens_fetched)
            }

            # Add sorting if specified
            if sort_by:
                params['sort_by'] = sort_by
                params['sort_type'] = 'desc'

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
                print(f"No more tokens available at offset {start_offset + tokens_fetched}")
                break

            for token in items:
                token_info = {
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

            print(f"Fetched {tokens_fetched}/{tokens_to_fetch} tokens...")

            # Rate limiting
            time.sleep(1.0)  # BirdEye standard tier: 1 request per second

        except Exception as e:
            print(f"Error fetching tokens: {e}")
            break

    return all_tokens

def analyze_liquidity_data(tokens, pass_name):
    """
    Analyze liquidity values in the token list
    """
    df = pd.DataFrame(tokens)

    print(f"\n{'='*60}")
    print(f"Analysis for {pass_name}")
    print(f"{'='*60}")

    # Basic stats
    print(f"Total tokens: {len(df)}")

    # Liquidity analysis
    liquidity_values = df['liquidity'].values
    zero_liquidity = (liquidity_values == 0).sum()
    null_liquidity = df['liquidity'].isna().sum()
    low_liquidity = ((liquidity_values > 0) & (liquidity_values < 20000)).sum()
    medium_liquidity = ((liquidity_values >= 20000) & (liquidity_values < 100000)).sum()
    high_liquidity = (liquidity_values >= 100000).sum()

    print(f"\nLiquidity Distribution:")
    print(f"  Zero liquidity: {zero_liquidity} ({zero_liquidity/len(df)*100:.1f}%)")
    print(f"  Null liquidity: {null_liquidity} ({null_liquidity/len(df)*100:.1f}%)")
    print(f"  0 < liquidity < $20K: {low_liquidity} ({low_liquidity/len(df)*100:.1f}%)")
    print(f"  $20K <= liquidity < $100K: {medium_liquidity} ({medium_liquidity/len(df)*100:.1f}%)")
    print(f"  liquidity >= $100K: {high_liquidity} ({high_liquidity/len(df)*100:.1f}%)")

    # Would fail Phase 2 filter
    fail_phase2 = ((liquidity_values < 20000) | df['liquidity'].isna()).sum()
    print(f"\nWould FAIL Phase 2 ($20K filter): {fail_phase2} ({fail_phase2/len(df)*100:.1f}%)")

    # Top and bottom liquidity values
    print(f"\nLiquidity Stats:")
    print(f"  Min: ${df['liquidity'].min():,.2f}")
    print(f"  Max: ${df['liquidity'].max():,.2f}")
    print(f"  Mean: ${df['liquidity'].mean():,.2f}")
    print(f"  Median: ${df['liquidity'].median():,.2f}")

    # Show top 10 by liquidity
    print(f"\nTop 10 tokens by liquidity:")
    top_10 = df.nlargest(10, 'liquidity')[['symbol', 'liquidity', 'volume_24h', 'market_cap']]
    for idx, row in top_10.iterrows():
        print(f"  {row['symbol']}: Liq=${row['liquidity']:,.0f}, Vol=${row['volume_24h']:,.0f}, MC=${row['market_cap']:,.0f}")

    # Show bottom 10 non-zero liquidity
    non_zero = df[df['liquidity'] > 0]
    if len(non_zero) > 0:
        print(f"\nBottom 10 tokens with non-zero liquidity:")
        bottom_10 = non_zero.nsmallest(10, 'liquidity')[['symbol', 'liquidity', 'volume_24h', 'market_cap']]
        for idx, row in bottom_10.iterrows():
            print(f"  {row['symbol']}: Liq=${row['liquidity']:,.0f}, Vol=${row['volume_24h']:,.0f}, MC=${row['market_cap']:,.0f}")

    return df

def main():
    """
    Main test function
    """
    print("BirdEye Meme List Liquidity Test")
    print("=" * 60)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Test Pass 1: Liquidity-sorted tokens (first 200)
    print("\n[PASS 1] Fetching liquidity-sorted tokens...")
    pass1_tokens = get_birdeye_meme_tokens(
        tokens_to_fetch=200,
        sort_by='liquidity',
        start_offset=0
    )

    if pass1_tokens:
        df_pass1 = analyze_liquidity_data(pass1_tokens, "Pass 1: Liquidity-Sorted")

        # Save to CSV
        csv_path1 = f"/Users/eamonblackwell/Meme Coin Trading Bot/moon-dev-ai-agents/src/data/birdeye_liquidity_test_pass1_{timestamp}.csv"
        df_pass1.to_csv(csv_path1, index=False)
        print(f"\nPass 1 data saved to: {csv_path1}")

    # Test Pass 2: Unsorted tokens (offset 1000)
    print("\n[PASS 2] Fetching unsorted tokens from offset 1000...")
    pass2_tokens = get_birdeye_meme_tokens(
        tokens_to_fetch=200,
        sort_by=None,  # No sorting
        start_offset=1000
    )

    if pass2_tokens:
        df_pass2 = analyze_liquidity_data(pass2_tokens, "Pass 2: Unsorted (offset 1000)")

        # Save to CSV
        csv_path2 = f"/Users/eamonblackwell/Meme Coin Trading Bot/moon-dev-ai-agents/src/data/birdeye_liquidity_test_pass2_{timestamp}.csv"
        df_pass2.to_csv(csv_path2, index=False)
        print(f"\nPass 2 data saved to: {csv_path2}")

    # Combined analysis
    if pass1_tokens and pass2_tokens:
        print("\n" + "=" * 60)
        print("COMBINED ANALYSIS")
        print("=" * 60)

        all_tokens = pass1_tokens + pass2_tokens
        df_combined = pd.DataFrame(all_tokens)

        # Remove duplicates by address
        df_combined = df_combined.drop_duplicates(subset='address')
        print(f"Total unique tokens: {len(df_combined)}")

        # Overall failure rate
        liquidity_values = df_combined['liquidity'].values
        fail_phase2 = ((liquidity_values < 20000) | df_combined['liquidity'].isna()).sum()
        print(f"\nTokens that would FAIL Phase 2 ($20K filter):")
        print(f"  {fail_phase2} out of {len(df_combined)} ({fail_phase2/len(df_combined)*100:.1f}%)")

        # Save combined data
        csv_path_combined = f"/Users/eamonblackwell/Meme Coin Trading Bot/moon-dev-ai-agents/src/data/birdeye_liquidity_test_combined_{timestamp}.csv"
        df_combined.to_csv(csv_path_combined, index=False)
        print(f"\nCombined data saved to: {csv_path_combined}")

        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        print(f"Check the CSV files to see individual token liquidity values")

if __name__ == "__main__":
    main()