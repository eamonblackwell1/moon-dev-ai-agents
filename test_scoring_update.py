#!/usr/bin/env python3
"""
Test script to verify the updated revival scoring system
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import PRICE_PATTERN_WEIGHT, SMART_MONEY_WEIGHT, VOLUME_WEIGHT, SOCIAL_SENTIMENT_WEIGHT

print("=" * 60)
print("REVIVAL SCORING SYSTEM - WEIGHT VERIFICATION")
print("=" * 60)

# Display the weights
print(f"\nConfigured Weights:")
print(f"  Price Pattern Weight:    {PRICE_PATTERN_WEIGHT:.2f} ({PRICE_PATTERN_WEIGHT*100:.0f}%)")
print(f"  Smart Money Weight:      {SMART_MONEY_WEIGHT:.2f} ({SMART_MONEY_WEIGHT*100:.0f}%)")
print(f"  Volume Weight:           {VOLUME_WEIGHT:.2f} ({VOLUME_WEIGHT*100:.0f}%)")
print(f"  Social Sentiment Weight: {SOCIAL_SENTIMENT_WEIGHT:.2f} ({SOCIAL_SENTIMENT_WEIGHT*100:.0f}%)")
print(f"  TOTAL:                   {PRICE_PATTERN_WEIGHT + SMART_MONEY_WEIGHT + VOLUME_WEIGHT + SOCIAL_SENTIMENT_WEIGHT:.2f}")

# Simulate a scoring scenario
print("\n" + "=" * 60)
print("EXAMPLE SCORING SIMULATION")
print("=" * 60)

# Example scores for a hypothetical token
price_score = 0.7    # Good price pattern
smart_score = 0.0    # No whales (typical for small caps)
volume_score = 0.8   # Good volume
social_score = 0.6   # Moderate social interest

print(f"\nExample Token Scores:")
print(f"  Price Pattern Score:  {price_score:.2f}")
print(f"  Smart Money Score:    {smart_score:.2f}")
print(f"  Volume Score:         {volume_score:.2f}")
print(f"  Social Sentiment:     {social_score:.2f}")

# Calculate with OLD weights (for comparison)
old_weights = {
    'price': 0.60,
    'smart': 0.15,  # This was the old weight
    'volume': 0.15,
    'social': 0.10   # This was the old weight
}

old_revival_score = (
    price_score * old_weights['price'] +
    smart_score * old_weights['smart'] +
    volume_score * old_weights['volume'] +
    social_score * old_weights['social']
)

# Calculate with NEW weights
new_revival_score = (
    price_score * PRICE_PATTERN_WEIGHT +
    smart_score * SMART_MONEY_WEIGHT +
    volume_score * VOLUME_WEIGHT +
    social_score * SOCIAL_SENTIMENT_WEIGHT
)

print(f"\n" + "-" * 40)
print(f"Revival Score Comparison:")
print(f"  OLD Formula (60/15/15/10): {old_revival_score:.3f}")
print(f"  NEW Formula (60/0/15/25):  {new_revival_score:.3f}")
print(f"  Difference:                +{(new_revival_score - old_revival_score):.3f}")

# Show pass/fail with threshold
threshold = 0.4
print(f"\n" + "-" * 40)
print(f"Pass Threshold: {threshold:.2f}")
print(f"  OLD Formula: {'✅ PASS' if old_revival_score >= threshold else '❌ FAIL'}")
print(f"  NEW Formula: {'✅ PASS' if new_revival_score >= threshold else '❌ FAIL'}")

# Explain the change impact
print(f"\n" + "=" * 60)
print("IMPACT OF CHANGES:")
print("=" * 60)
print("1. Smart Money (0% weight) no longer affects score")
print("   - Removes bias against small-cap tokens without whales")
print("2. Social Sentiment (25% weight) has more influence")
print("   - Better reflects community interest for small caps")
print("3. Volume scoring simplified")
print("   - Only checks $50K threshold, no redundant buy/sell check")

print("\nTokens with strong community interest but no whales")
print("will now score higher and be more likely to pass!")
print("=" * 60)