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

    @staticmethod
    def _default_log(message: str, level: str = 'info'):
        """Fallback logger that prints to stdout"""
        print(message)

    @staticmethod
    def _default_log_error(message: str):
        """Fallback error logger that prints to stdout"""
        print(message)

    def __init__(self, log_fn=None, error_fn=None):
        """Initialize paper trading agent"""
        self._log = log_fn or self._default_log
        self._log_error = error_fn or self._default_log_error

        self.position_manager = PositionManager(
            log_fn=self._log,
            error_fn=self._log_error
        )
        self.monitoring_active = False
        self.monitor_thread = None

        self._log("🤖 Paper Trading Agent initialized", 'info')
        self._log(f"   Initial Balance: ${config.PAPER_TRADING_INITIAL_BALANCE:,.2f}", 'info')
        self._log(f"   Position Size: ${config.PAPER_TRADING_POSITION_SIZE_USD:,.2f}", 'info')
        max_positions = config.PAPER_TRADING_MAX_POSITIONS
        max_positions_text = max_positions if max_positions is not None else "Unlimited"
        self._log(f"   Max Positions: {max_positions_text}", 'info')
        self._log(f"   Min Revival Score: {config.PAPER_TRADING_MIN_REVIVAL_SCORE}", 'info')

        # Auto-resume monitoring if we have existing open positions
        open_positions = self.position_manager.get_open_positions()
        if open_positions:
            self._log(f"\n🔄 Found {len(open_positions)} existing positions - auto-resuming monitoring...", 'info')
            self.start_monitoring()

    def evaluate_opportunities(self, opportunities: List[Dict]) -> List[Dict]:
        """
        Evaluate Revival Scanner opportunities and open positions

        Args:
            opportunities: List of tokens from Phase 5 revival detection

        Returns:
            List of positions opened
        """
        if not opportunities:
            self._log("📊 No revival opportunities to evaluate", 'info')
            return []

        self._log(f"\n📊 Evaluating {len(opportunities)} revival opportunities for paper trading...", 'info')

        positions_opened = []

        for opp in opportunities:
            # Extract token data (match Revival Detector output format)
            token_address = opp.get('token_address')
            symbol = opp.get('token_symbol', opp.get('symbol', 'UNKNOWN'))
            revival_score = float(opp.get('revival_score', 0))

            # Validate token address
            if not token_address:
                self._log("⚠️  Skipping opportunity - missing token_address field", 'warning')
                self._log(f"    Available keys: {list(opp.keys())}", 'warning')
                continue

            # Check if meets minimum score threshold
            if revival_score < config.PAPER_TRADING_MIN_REVIVAL_SCORE:
                self._log(f"⏭️  Skipping {symbol}: score {revival_score:.2f} < {config.PAPER_TRADING_MIN_REVIVAL_SCORE}", 'info')
                continue

            # Check if already have a position
            existing_positions = self.position_manager.get_open_positions()
            if any(p['token_address'] == token_address for p in existing_positions):
                self._log(f"⏭️  Skipping {symbol}: already have open position", 'info')
                continue

            # Try to open position
            self._log(f"\n🎯 Opening paper position: {symbol} (score: {revival_score:.2f})", 'info')
            position = self.position_manager.open_position(
                token_address=token_address,
                symbol=symbol,
                revival_score=revival_score
            )

            if position:
                positions_opened.append(position)
                self._log(f"✅ Position opened for {symbol}", 'success')
            else:
                self._log(f"❌ Failed to open position for {symbol}", 'warning')

        self._log(f"\n✅ Opened {len(positions_opened)} paper trading positions", 'info')

        # Start monitoring if we have positions and monitoring not active
        if positions_opened and not self.monitoring_active:
            self.start_monitoring()

        return positions_opened

    def start_monitoring(self):
        """Start background thread to monitor positions"""
        if self.monitoring_active:
            self._log("⚠️  Monitoring already active", 'warning')
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_positions, daemon=True)
        self.monitor_thread.start()
        self._log("🔄 Started position monitoring", 'info')

    def stop_monitoring(self):
        """Stop background monitoring thread"""
        if not self.monitoring_active:
            return

        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self._log("⏸️  Stopped position monitoring", 'info')

    def _monitor_positions(self):
        """
        Background thread that monitors positions and triggers exits

        Runs continuously every PRICE_CHECK_INTERVAL seconds
        """
        self._log(f"👀 Monitoring positions every {config.PAPER_TRADING_PRICE_CHECK_INTERVAL} seconds...", 'info')

        while self.monitoring_active:
            try:
                open_positions = self.position_manager.get_open_positions()

                if not open_positions:
                    self._log("💤 No open positions to monitor", 'info')
                    time.sleep(config.PAPER_TRADING_PRICE_CHECK_INTERVAL)
                    continue

                self._log(f"\n🔍 Checking {len(open_positions)} positions...", 'info')

                for position in open_positions:
                    position_id = position['id']
                    token_address = position['token_address']
                    symbol = position['symbol']

                    # Get current price
                    try:
                        current_price = token_price(token_address)
                        if not current_price or current_price <= 0:
                            self._log(f"⚠️  Invalid price for {symbol}, skipping check", 'warning')
                            continue
                    except Exception as e:
                        self._log_error(f"❌ Failed to get price for {symbol}: {e}")
                        continue

                    # Update position with current price
                    self.position_manager.update_position_price(position_id, current_price)

                    # Calculate current P&L
                    pnl_pct = ((current_price - position['entry_price']) / position['entry_price']) * 100

                    # Check if exit conditions met
                    exit_type = self.position_manager.check_exit_conditions(position_id, current_price)

                    if exit_type:
                        self._log(f"\n🚨 Exit trigger for {symbol}: {exit_type}", 'warning')
                        self._log(f"   Entry: ${position['entry_price']:.8f}", 'info')
                        self._log(f"   Current: ${current_price:.8f}", 'info')
                        self._log(f"   P&L: {pnl_pct:+.2f}%", 'info')

                        # Execute exit
                        trade = self.position_manager.close_position(
                            position_id=position_id,
                            exit_type=exit_type,
                            current_price=current_price
                        )

                        if trade:
                            self._log("✅ Exit executed successfully", 'success')
                    else:
                        # Just log current status
                        self._log(f"   {symbol}: ${current_price:.8f} ({pnl_pct:+.2f}%)", 'info')

                # Sleep until next check
                time.sleep(config.PAPER_TRADING_PRICE_CHECK_INTERVAL)

            except Exception as e:
                self._log_error(f"❌ Error in monitoring loop: {e}")
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
            self._log("❌ Position {position_id} not found or already closed".format(position_id=position_id), 'warning')
            return False

        # Get current price
        try:
            current_price = token_price(position['token_address'])
            if not current_price or current_price <= 0:
                self._log(f"❌ Cannot close: invalid price for {position['symbol']}", 'warning')
                return False
        except Exception as e:
            self._log_error(f"❌ Cannot close: failed to get price: {e}")
            return False

        # Close position
        trade = self.position_manager.close_position(
            position_id=position_id,
            exit_type='manual',
            current_price=current_price
        )

        if trade:
            self._log(f"✅ Manually closed position {position['symbol']}", 'success')
            return True
        else:
            self._log(f"❌ Failed to close position {position['symbol']}", 'warning')
            return False

    def reset(self):
        """Reset paper trading to initial state"""
        self.stop_monitoring()
        self.position_manager.reset_paper_trading()
        self._log("♻️ Paper trading reset complete", 'info')


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

    # Create mock opportunity for testing (matches Revival Detector output format)
    mock_opportunity = {
        'token_address': 'HeLp6NuQkmYB4pYWo2zYs22mESHXPQYzXbB8n4V98jwC',  # AI16Z
        'token_symbol': 'AI16Z',
        'token_name': 'ai16z',
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
