"""
🛡️ Stage 1 Security Filter - Moon Dev's Fast Security Check
Quickly eliminates honeypots, scams, and dangerous tokens
Built with love by Moon Dev 🚀

This filter is FAST (< 10 seconds) and uses:
- BirdEye data (passed from orchestrator)
- GoPlus Security API (1000 requests/day free)
"""

import os
import sys
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from termcolor import colored
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

class Stage1SecurityFilter:
    """
    Fast security filter to eliminate obvious scams

    Checks:
    1. Honeypot detection (GoPlus)
    2. Mintable tokens (can create infinite supply)
    3. Liquidity minimums (from BirdEye data)
    4. Basic security score
    """

    def __init__(self):
        """Initialize the security filter"""
        print(colored("🛡️ Stage 1 Security Filter initialized!", "green"))

        # Configuration
        self.min_liquidity = 5000  # $5K minimum
        self.min_volume = 5000     # $5K daily volume minimum
        self.min_security_score = 60  # GoPlus score minimum

        # GoPlus API (get free key at https://gopluslabs.io)
        self.goplus_api_key = os.getenv('GOPLUS_API_KEY', '')  # Optional - works without key too

        # Data storage
        self.data_dir = Path(__file__).parent.parent / "data" / "security_filter"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def check_goplus_security(self, token_address: str) -> Tuple[bool, Dict]:
        """
        Check token security using GoPlus API

        Returns:
            (passed, details) - Whether it passed security checks
        """
        try:
            # GoPlus API - works without key but with lower rate limits
            url = "https://api.gopluslabs.io/api/v1/token_security/sol"
            params = {'contract_addresses': token_address}
            headers = {}

            if self.goplus_api_key:
                headers['Authorization'] = f'Bearer {self.goplus_api_key}'

            response = requests.get(url, params=params, headers=headers, timeout=10)

            if response.status_code != 200:
                # GoPlus might be rate limited, not critical
                return True, {'warning': 'GoPlus unavailable, skipping security check'}

            data = response.json()

            # Check if result exists and is not None
            if 'result' not in data or data['result'] is None:
                return True, {'warning': 'No security data available - result is None'}

            # Check if token exists in result
            if token_address.lower() not in data['result']:
                return True, {'warning': 'Token not found in GoPlus database'}

            security_info = data['result'][token_address.lower()]

            # Critical security checks
            is_honeypot = security_info.get('is_honeypot', '0') == '1'
            is_mintable = security_info.get('is_mintable', '0') == '1'
            has_blacklist = security_info.get('is_blacklisted', '0') == '1'
            can_freeze = security_info.get('can_take_back_ownership', '0') == '1'

            # Calculate security score
            risk_factors = 0
            if is_honeypot: risk_factors += 100  # Instant fail
            if is_mintable: risk_factors += 50   # Very bad
            if has_blacklist: risk_factors += 30  # Bad
            if can_freeze: risk_factors += 20     # Concerning

            security_score = max(0, 100 - risk_factors)

            passed = (
                not is_honeypot and
                not is_mintable and
                security_score >= self.min_security_score
            )

            details = {
                'is_honeypot': is_honeypot,
                'is_mintable': is_mintable,
                'has_blacklist': has_blacklist,
                'can_freeze': can_freeze,
                'security_score': security_score,
                'holder_count': security_info.get('holder_count', 'unknown'),
                'owner_address': security_info.get('owner_address', 'unknown')
            }

            return passed, details

        except Exception as e:
            # If GoPlus fails, don't block the token (it's optional)
            return True, {'warning': f'GoPlus check failed: {str(e)}'}

    def quick_filter(self, token_input) -> Dict:
        """
        Run complete security filter on a token

        Args:
            token_input: Either a token address (str) OR a dict with BirdEye data

        Returns:
            Dictionary with pass/fail and all details
        """
        # Handle both string addresses and dict inputs
        if isinstance(token_input, dict):
            token_address = token_input.get('address')
            has_birdeye_data = True
            # Extract liquidity and volume from BirdEye data
            liquidity_usd = token_input.get('liquidity') or token_input.get('liquidity_usd', 0)
            volume_24h = token_input.get('volume_24h') or token_input.get('volume_24h_usd', 0)
        else:
            token_address = token_input
            has_birdeye_data = False
            liquidity_usd = 0
            volume_24h = 0

        print(colored(f"\n🔍 Security check: {token_address[:8]}...", "cyan"))

        result = {
            'token_address': token_address,
            'passed': False,
            'checks': {},
            'liquidity_usd': liquidity_usd,
            'volume_24h': volume_24h
        }

        # Step 1: Liquidity/Volume check using BirdEye data
        if has_birdeye_data:
            liq_vol_passed = liquidity_usd >= self.min_liquidity and volume_24h >= self.min_volume

            result['checks']['liquidity_volume'] = {
                'passed': liq_vol_passed,
                'details': {
                    'liquidity_usd': liquidity_usd,
                    'volume_24h': volume_24h,
                    'source': 'BirdEye'
                }
            }

            if not liq_vol_passed:
                print(colored(f"  ❌ Failed liquidity/volume (Liq: ${liquidity_usd:,.0f}, Vol: ${volume_24h:,.0f})", "red"))
                result['failure_reason'] = f'Failed liquidity/volume requirements (Liq: ${liquidity_usd:,.0f} < ${self.min_liquidity}, Vol: ${volume_24h:,.0f} < ${self.min_volume})'
                return result

            print(colored(f"  ✅ Passed liquidity/volume (BirdEye - Liq: ${liquidity_usd:,.0f}, Vol: ${volume_24h:,.0f})", "green"))
        else:
            # No BirdEye data available - skip liquidity check
            print(colored(f"  ⚠️ No BirdEye data provided, skipping liquidity/volume check", "yellow"))
            result['checks']['liquidity_volume'] = {
                'passed': True,
                'details': {
                    'warning': 'No BirdEye data provided',
                    'source': 'None'
                }
            }

        # Step 2: GoPlus security check (optional but recommended)
        goplus_passed, goplus_details = self.check_goplus_security(token_address)
        result['checks']['goplus'] = {
            'passed': goplus_passed,
            'details': goplus_details
        }

        if not goplus_passed:
            print(colored(f"  ❌ Failed security check (honeypot/mintable)", "red"))
            result['failure_reason'] = f'Failed security requirements: honeypot={goplus_details.get("is_honeypot")}, mintable={goplus_details.get("is_mintable")}'
            return result

        if 'warning' in goplus_details:
            print(colored(f"  ⚠️ Security: {goplus_details['warning']}", "yellow"))
        else:
            print(colored(f"  ✅ Passed security (Score: {goplus_details.get('security_score', 'N/A')})", "green"))

        # All checks passed!
        result['passed'] = True
        print(colored(f"  🎯 Token PASSED security filter!", "green", attrs=['bold']))

        return result

    def batch_filter(self, token_inputs: List, max_workers: int = 3) -> List[Dict]:
        """
        Filter multiple tokens in parallel for speed

        Args:
            token_inputs: List of token addresses (strings) or token dicts with BirdEye data
            max_workers: Number of parallel threads (reduced from 5 to 3 for stability)

        Returns:
            List of results, sorted by liquidity
        """
        print(colored(f"\n🚀 Batch filtering {len(token_inputs)} tokens...", "cyan", attrs=['bold']))

        results = []
        passed_count = 0

        # Use thread pool for parallel processing
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_token = {
                executor.submit(self.quick_filter, token_input): token_input
                for token_input in token_inputs
            }

            # Process completed tasks
            for future in as_completed(future_to_token):
                token_input = future_to_token[future]
                try:
                    result = future.result()
                    results.append(result)
                    if result['passed']:
                        passed_count += 1
                except Exception as e:
                    # Extract address for error message
                    addr = token_input if isinstance(token_input, str) else token_input.get('address', 'unknown')
                    print(colored(f"❌ Error checking {addr}: {str(e)}", "red"))
                    results.append({
                        'token_address': addr,
                        'passed': False,
                        'error': str(e)
                    })

        # Sort by liquidity (highest first)
        passed_tokens = [r for r in results if r['passed']]
        passed_tokens.sort(key=lambda x: x.get('liquidity_usd', 0), reverse=True)

        # Print summary
        print(colored(f"\n📊 Security Filter Results:", "green", attrs=['bold']))
        print(colored(f"   Passed: {passed_count}/{len(token_inputs)} tokens", "green"))

        if passed_tokens:
            print(colored(f"\n🏆 Top Secured Tokens:", "yellow"))
            for i, token in enumerate(passed_tokens[:5], 1):
                print(colored(f"   {i}. {token['token_address'][:8]}... - Liq: ${token.get('liquidity_usd', 0):,.0f}", "yellow"))

        # Save results
        self.save_results(results)

        return results

    def save_results(self, results: List[Dict]):
        """Save filter results to JSON"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filepath = self.data_dir / f"security_filter_{timestamp}.json"

            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2)

            print(colored(f"💾 Results saved to {filepath}", "green"))

        except Exception as e:
            print(colored(f"⚠️ Could not save results: {str(e)}", "yellow"))

def main():
    """Test the security filter"""
    filter = Stage1SecurityFilter()

    # Example tokens to test (replace with real addresses)
    test_tokens = [
        # Add some token addresses here for testing
        # You can get these from DexScreener
    ]

    if test_tokens:
        results = filter.batch_filter(test_tokens)

        # Show passed tokens
        passed = [r for r in results if r['passed']]
        print(colored(f"\n✅ {len(passed)} tokens passed security filter", "green"))
    else:
        print(colored("⚠️ No test tokens provided. Add some Solana token addresses to test.", "yellow"))

if __name__ == "__main__":
    main()