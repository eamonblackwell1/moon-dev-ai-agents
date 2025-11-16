#!/usr/bin/env python3
"""
Test script to verify Phase 5 scoring improvements are working
Tests that all 4 scoring components (price, smart, volume, social) are calculated properly
"""

import os
import sys
from termcolor import colored
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment
load_dotenv()

def test_revival_scoring():
    """Test that Phase 5 revival scoring works with enriched data"""

    print(colored("\n🧪 Testing Phase 5 Scoring Improvements", "cyan", attrs=['bold']))
    print(colored("=" * 60, "cyan"))

    # Import after path setup
    from src.agents.revival_detector_agent import RevivalDetectorAgent

    # Initialize agent
    print(colored("\n1. Initializing Revival Detector Agent...", "yellow"))
    agent = RevivalDetectorAgent()

    # Create a test token with all required fields
    # This simulates the enriched data from Phase 2
    test_token = {
        'address': '9JhFqCA21MoAXs2PTaeqNQp2XngPn1PgYr2rsEVCpump',  # Claude Opus token
        'symbol': 'OPUS',
        'name': 'Claude Opus',
        'liquidity': 1156548,
        'market_cap': 14620,
        'volume_24h': 47826043821,
        'age_hours': 96.5,  # 4 days old (passes 72h minimum)

        # NEW enriched fields from BirdEye Token Overview
        'buy1h': 150,
        'sell1h': 100,
        'trade1h': 250,
        'uniqueWallet24h': 500,
        'watch': 75,
        'view24h': 1200,
        'buy_percentage': 60,
        'buys_24h': 3600,  # 150 * 24
        'sells_24h': 2400,  # 100 * 24
        'holder': 2500,
        'price_change_24h': 15.5
    }

    print(colored("\n2. Testing revival score calculation with enriched data...", "yellow"))
    print(colored(f"   Token: {test_token['symbol']} ({test_token['name']})", "grey"))
    print(colored(f"   Address: {test_token['address']}", "grey"))

    # Calculate revival score
    result = agent.calculate_revival_score(
        test_token['address'],
        provided_data=test_token
    )

    if result:
        revival_score = result.get('revival_score', 0)
        price_score = result.get('price_score', 0)
        smart_score = result.get('smart_score', 0)
        volume_score = result.get('volume_score', 0)
        social_score = result.get('social_score', 0)

        print(colored("\n✅ Scoring Results:", "green", attrs=['bold']))
        print(colored(f"   • Revival Score: {revival_score:.2f}", "green"))
        print(colored(f"   • Price Score:   {price_score:.2f}", "cyan"))
        print(colored(f"   • Smart Score:   {smart_score:.2f}", "cyan"))
        print(colored(f"   • Volume Score:  {volume_score:.2f}", "cyan"))
        print(colored(f"   • Social Score:  {social_score:.2f}", "cyan"))

        # Check if all components are working
        failures = []
        if price_score == 0:
            failures.append("Price score is 0 - price analysis may have failed")
        if smart_score == 0:
            failures.append("Smart score is 0 - Top Traders API may be failing")
        if volume_score == 0:
            failures.append("Volume score is 0 - missing buys_24h/sells_24h data")
        if social_score == 0:
            failures.append("Social score is 0 - missing social metric fields")

        if failures:
            print(colored("\n⚠️ Issues Detected:", "yellow", attrs=['bold']))
            for issue in failures:
                print(colored(f"   • {issue}", "yellow"))
        else:
            print(colored("\n🎉 All scoring components are working!", "green", attrs=['bold']))

        # Test volume scoring specifically
        print(colored("\n3. Testing Volume Score Components:", "yellow"))
        print(colored(f"   • 24h Volume: ${test_token['volume_24h']:,.0f}", "grey"))
        print(colored(f"   • Buys 24h: {test_token['buys_24h']}", "grey"))
        print(colored(f"   • Sells 24h: {test_token['sells_24h']}", "grey"))
        print(colored(f"   • Expected volume score: 1.0 (volume > $50K and buys > sells)", "grey"))
        print(colored(f"   • Actual volume score: {volume_score:.2f}", "green" if volume_score > 0 else "red"))

        # Test social scoring specifically
        print(colored("\n4. Testing Social Score Components:", "yellow"))
        print(colored(f"   • Unique Wallets 24h: {test_token['uniqueWallet24h']}", "grey"))
        print(colored(f"   • Trade 1h: {test_token['trade1h']}", "grey"))
        print(colored(f"   • Watch: {test_token['watch']}", "grey"))
        print(colored(f"   • View 24h: {test_token['view24h']}", "grey"))
        print(colored(f"   • Buy %: {test_token['buy_percentage']}%", "grey"))
        print(colored(f"   • Expected social score: ~0.85 (high activity across all metrics)", "grey"))
        print(colored(f"   • Actual social score: {social_score:.2f}", "green" if social_score > 0 else "red"))

    else:
        print(colored("\n❌ Failed to calculate revival score!", "red"))

    print(colored("\n" + "=" * 60, "cyan"))

    # Now test with missing fields (simulating old behavior)
    print(colored("\n5. Testing with minimal data (old Phase 2 output)...", "yellow"))

    minimal_token = {
        'address': '9JhFqCA21MoAXs2PTaeqNQp2XngPn1PgYr2rsEVCpump',
        'symbol': 'OPUS',
        'name': 'Claude Opus',
        'liquidity': 1156548,
        'market_cap': 14620,
        'volume_24h': 47826043821
        # Missing: age_hours, buy1h, sell1h, uniqueWallet24h, etc.
    }

    result2 = agent.calculate_revival_score(
        minimal_token['address'],
        provided_data=minimal_token
    )

    if result2:
        print(colored("\n⚠️ Minimal Data Results (simulating old behavior):", "yellow"))
        print(colored(f"   • Revival Score: {result2.get('revival_score', 0):.2f}", "yellow"))
        print(colored(f"   • Price Score:   {result2.get('price_score', 0):.2f}", "cyan"))
        print(colored(f"   • Smart Score:   {result2.get('smart_score', 0):.2f}", "cyan"))
        print(colored(f"   • Volume Score:  {result2.get('volume_score', 0):.2f}", "cyan"))
        print(colored(f"   • Social Score:  {result2.get('social_score', 0):.2f}", "cyan"))
        print(colored("   (Should see warnings about missing fields above)", "grey"))

    print(colored("\n✅ Test Complete!", "green", attrs=['bold']))
    print(colored("   The improvements should allow all 4 score components to work", "green"))
    print(colored("   when tokens are enriched with BirdEye Token Overview data.", "green"))

if __name__ == "__main__":
    test_revival_scoring()