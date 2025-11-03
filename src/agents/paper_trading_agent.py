"""
🌙 Moon Dev's Paper Trading Agent
Built with love by Moon Dev 🚀

Automated paper trading agent that:
- Evaluates Revival Scanner opportunities
- Opens positions based on revival scores
- Monitors positions in real-time
- Executes stop-loss and take-profit exits
- Simulates realistic Jupiter DEX execution
"""

import os
import sys
import time
import threading
from datetime import datetime
from typing import List, Dict

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from paper_trading.position_manager import PositionManager
from nice_funcs import token_price


class PaperTradingAgent:
    """
    Paper trading agent that simulates live trading with realistic execution

    Features:
    - Automatic position opening from Revival Scanner signals
    - Real-time price monitoring every 30 seconds
    - Automatic exit on stop-loss/take-profit triggers
    - Time-based exits after max hold period
    - Realistic fee and slippage simulation
    """

    def __init__(self):
        """Initialize paper trading agent"""
        self.position_manager = PositionManager()
        self.monitoring_active = False
        self.monitor_thread = None

        print("🤖 Paper Trading Agent initialized")
        print(f"   Initial Balance: ${config.PAPER_TRADING_INITIAL_BALANCE:,.2f}")
        print(f"   Position Size: ${config.PAPER_TRADING_POSITION_SIZE_USD:,.2f}")
        print(f"   Max Positions: {config.PAPER_TRADING_MAX_POSITIONS}")
        print(f"   Min Revival Score: {config.PAPER_TRADING_MIN_REVIVAL_SCORE}")

    def evaluate_opportunities(self, opportunities: List[Dict]) -> List[Dict]:
        """
        Evaluate Revival Scanner opportunities and open positions

        Args:
            opportunities: List of tokens from Phase 5 revival detection

        Returns:
            List of positions opened
        """
        if not opportunities:
            print("📊 No revival opportunities to evaluate")
            return []

        print(f"\n📊 Evaluating {len(opportunities)} revival opportunities for paper trading...")

        positions_opened = []

        for opp in opportunities:
            # Extract token data
            token_address = opp.get('address')
            symbol = opp.get('symbol', 'UNKNOWN')
            revival_score = float(opp.get('revival_score', 0))

            # Check if meets minimum score threshold
            if revival_score < config.PAPER_TRADING_MIN_REVIVAL_SCORE:
                print(f"⏭️  Skipping {symbol}: score {revival_score:.2f} < {config.PAPER_TRADING_MIN_REVIVAL_SCORE}")
                continue

            # Check if already have a position
            existing_positions = self.position_manager.get_open_positions()
            if any(p['token_address'] == token_address for p in existing_positions):
                print(f"⏭️  Skipping {symbol}: already have open position")
                continue

            # Try to open position
            print(f"\n🎯 Opening paper position: {symbol} (score: {revival_score:.2f})")
            position = self.position_manager.open_position(
                token_address=token_address,
                symbol=symbol,
                revival_score=revival_score
            )

            if position:
                positions_opened.append(position)
                print(f"✅ Position opened for {symbol}")
            else:
                print(f"❌ Failed to open position for {symbol}")

        print(f"\n✅ Opened {len(positions_opened)} paper trading positions")

        # Start monitoring if we have positions and monitoring not active
        if positions_opened and not self.monitoring_active:
            self.start_monitoring()

        return positions_opened

    def start_monitoring(self):
        """Start background thread to monitor positions"""
        if self.monitoring_active:
            print("⚠️  Monitoring already active")
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_positions, daemon=True)
        self.monitor_thread.start()
        print("🔄 Started position monitoring")

    def stop_monitoring(self):
        """Stop background monitoring thread"""
        if not self.monitoring_active:
            return

        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("⏸️  Stopped position monitoring")

    def _monitor_positions(self):
        """
        Background thread that monitors positions and triggers exits

        Runs continuously every PRICE_CHECK_INTERVAL seconds
        """
        print(f"👀 Monitoring positions every {config.PAPER_TRADING_PRICE_CHECK_INTERVAL} seconds...")

        while self.monitoring_active:
            try:
                open_positions = self.position_manager.get_open_positions()

                if not open_positions:
                    print("💤 No open positions to monitor")
                    time.sleep(config.PAPER_TRADING_PRICE_CHECK_INTERVAL)
                    continue

                print(f"\n🔍 Checking {len(open_positions)} positions...")

                for position in open_positions:
                    position_id = position['id']
                    token_address = position['token_address']
                    symbol = position['symbol']

                    # Get current price
                    try:
                        current_price = token_price(token_address)
                        if not current_price or current_price <= 0:
                            print(f"⚠️  Invalid price for {symbol}, skipping check")
                            continue
                    except Exception as e:
                        print(f"❌ Failed to get price for {symbol}: {e}")
                        continue

                    # Update position with current price
                    self.position_manager.update_position_price(position_id, current_price)

                    # Calculate current P&L
                    pnl_pct = ((current_price - position['entry_price']) / position['entry_price']) * 100

                    # Check if exit conditions met
                    exit_type = self.position_manager.check_exit_conditions(position_id, current_price)

                    if exit_type:
                        print(f"\n🚨 Exit trigger for {symbol}: {exit_type}")
                        print(f"   Entry: ${position['entry_price']:.8f}")
                        print(f"   Current: ${current_price:.8f}")
                        print(f"   P&L: {pnl_pct:+.2f}%")

                        # Execute exit
                        trade = self.position_manager.close_position(
                            position_id=position_id,
                            exit_type=exit_type,
                            current_price=current_price
                        )

                        if trade:
                            print(f"✅ Exit executed successfully")
                    else:
                        # Just log current status
                        print(f"   {symbol}: ${current_price:.8f} ({pnl_pct:+.2f}%)")

                # Sleep until next check
                time.sleep(config.PAPER_TRADING_PRICE_CHECK_INTERVAL)

            except Exception as e:
                print(f"❌ Error in monitoring loop: {e}")
                time.sleep(config.PAPER_TRADING_PRICE_CHECK_INTERVAL)

    def get_portfolio_summary(self) -> Dict:
        """Get current portfolio summary"""
        return self.position_manager.get_portfolio_summary()

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions"""
        return self.position_manager.get_open_positions()

    def manual_close_position(self, position_id: str) -> bool:
        """
        Manually close a position (for testing or emergency exits)

        Returns True if successful, False otherwise
        """
        positions = self.position_manager.get_open_positions()
        position = next((p for p in positions if p['id'] == position_id), None)

        if not position:
            print(f"❌ Position {position_id} not found or already closed")
            return False

        # Get current price
        try:
            current_price = token_price(position['token_address'])
            if not current_price or current_price <= 0:
                print(f"❌ Cannot close: invalid price for {position['symbol']}")
                return False
        except Exception as e:
            print(f"❌ Cannot close: failed to get price: {e}")
            return False

        # Close position
        trade = self.position_manager.close_position(
            position_id=position_id,
            exit_type='manual',
            current_price=current_price
        )

        if trade:
            print(f"✅ Manually closed position {position['symbol']}")
            return True
        else:
            print(f"❌ Failed to close position {position['symbol']}")
            return False

    def reset(self):
        """Reset paper trading to initial state"""
        self.stop_monitoring()
        self.position_manager.reset_paper_trading()
        print("♻️ Paper trading reset complete")


def main():
    """
    Standalone test mode for paper trading agent

    Usage:
        python src/agents/paper_trading_agent.py
    """
    print("=" * 60)
    print("🌙 Moon Dev's Paper Trading Agent - Standalone Test Mode")
    print("=" * 60)

    # Initialize agent
    agent = PaperTradingAgent()

    # Create mock opportunity for testing
    mock_opportunity = {
        'address': 'HeLp6NuQkmYB4pYWo2zYs22mESHXPQYzXbB8n4V98jwC',  # AI16Z
        'symbol': 'AI16Z',
        'revival_score': 0.75,
        'liquidity_usd': 100000,
        'market_cap': 5000000,
        'volume_24h': 50000
    }

    # Evaluate opportunity
    print("\n" + "=" * 60)
    print("Testing position opening with mock revival opportunity...")
    print("=" * 60)

    positions = agent.evaluate_opportunities([mock_opportunity])

    if positions:
        print(f"\n✅ Opened {len(positions)} position(s)")

        # Show portfolio summary
        print("\n" + "=" * 60)
        print("Portfolio Summary:")
        print("=" * 60)
        summary = agent.get_portfolio_summary()
        for key, value in summary.items():
            if isinstance(value, float):
                print(f"{key}: ${value:,.2f}")
            else:
                print(f"{key}: {value}")

        # Monitor for 2 minutes in test mode
        print("\n" + "=" * 60)
        print("Monitoring positions for 2 minutes (test mode)...")
        print("Press Ctrl+C to stop early")
        print("=" * 60)

        try:
            time.sleep(120)  # Monitor for 2 minutes
        except KeyboardInterrupt:
            print("\n⏹️  Monitoring stopped by user")

        # Stop monitoring
        agent.stop_monitoring()

        print("\n" + "=" * 60)
        print("Final Portfolio Summary:")
        print("=" * 60)
        summary = agent.get_portfolio_summary()
        for key, value in summary.items():
            if isinstance(value, float):
                print(f"{key}: ${value:,.2f}")
            else:
                print(f"{key}: {value}")

    else:
        print("\n❌ No positions opened")

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
