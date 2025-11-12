"""
🌙 Moon Dev's Paper Trading Position Manager
Built with love by Moon Dev 🚀

Manages paper trading positions with realistic execution simulation:
- Opens positions from Revival Scanner signals
- Tracks entry prices with fees and slippage
- Monitors positions and triggers exits
- Simulates Jupiter DEX execution conditions
"""

import os
import csv
import random
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd

# Import configuration
import sys
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
from src import config
from src.nice_funcs import token_price

# Import email notifier
try:
    from src.paper_trading.email_notifier import EmailNotifier
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    print("⚠️  Email notifier not available - notifications disabled")


class PositionManager:
    """Manages paper trading positions with CSV persistence"""

    @staticmethod
    def _default_log(message: str, level: str = 'info'):
        print(message)

    @staticmethod
    def _default_log_error(message: str):
        print(message)

    def __init__(self, log_fn=None, error_fn=None):
        """Initialize position manager with CSV file paths"""
        self._log = log_fn or self._default_log
        self._log_error = error_fn or self._default_log_error

        self.data_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'paper_trading')
        os.makedirs(self.data_dir, exist_ok=True)

        # CSV file paths
        self.positions_file = os.path.join(self.data_dir, 'positions.csv')
        self.trades_file = os.path.join(self.data_dir, 'trades_history.csv')
        self.portfolio_file = os.path.join(self.data_dir, 'portfolio_snapshots.csv')

        # Initialize CSV files if they don't exist
        self._initialize_csv_files()

        # Load positions into memory
        self.positions = self._load_positions()

        # Portfolio state
        self.cash_balance = config.PAPER_TRADING_INITIAL_BALANCE
        self._load_portfolio_state()

        # Initialize email notifier
        self.email_notifier = EmailNotifier() if EMAIL_AVAILABLE else None

        # Monitoring thread
        self.monitoring_active = False
        self.monitor_thread = None

    def _initialize_csv_files(self):
        """Create CSV files with headers if they don't exist"""
        # Positions CSV
        if not os.path.exists(self.positions_file):
            with open(self.positions_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'id', 'token_address', 'symbol', 'entry_price', 'entry_time',
                    'quantity_usd', 'remaining_pct', 'status', 'stop_loss_price',
                    'take_profit_1_price', 'take_profit_2_price', 'current_price',
                    'current_pnl_pct', 'last_updated'
                ])

        # Trades history CSV
        if not os.path.exists(self.trades_file):
            with open(self.trades_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'id', 'position_id', 'token_address', 'symbol', 'entry_price',
                    'entry_time', 'exit_price', 'exit_time', 'quantity_usd',
                    'exit_type', 'pnl_usd', 'pnl_pct', 'fees_paid', 'hold_days'
                ])

        # Portfolio snapshots CSV
        if not os.path.exists(self.portfolio_file):
            with open(self.portfolio_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'total_value_usd', 'cash_usd', 'positions_value_usd',
                    'open_positions_count', 'total_pnl_usd', 'total_pnl_pct'
                ])

    def _load_positions(self) -> Dict:
        """Load active positions from CSV"""
        positions = {}
        if os.path.exists(self.positions_file):
            df = pd.read_csv(self.positions_file)
            # Only load open positions
            active_df = df[df['status'] == 'open']
            for _, row in active_df.iterrows():
                positions[row['id']] = row.to_dict()
        return positions

    def _load_portfolio_state(self):
        """Load latest portfolio state to get current cash balance"""
        if os.path.exists(self.portfolio_file):
            df = pd.read_csv(self.portfolio_file)
            if len(df) > 0:
                latest = df.iloc[-1]
                self.cash_balance = float(latest['cash_usd'])

    def _save_position(self, position: Dict):
        """Save or update a position in CSV"""
        # Update in-memory
        self.positions[position['id']] = position

        # Load all positions
        if os.path.exists(self.positions_file):
            df = pd.read_csv(self.positions_file)
        else:
            df = pd.DataFrame()

        position_df = pd.DataFrame([position])

        if len(df) == 0:
            df = position_df
            columns = position_df.columns.tolist()
        else:
            columns = df.columns.tolist()

            if position['id'] in df['id'].values:
                df = df[df['id'] != position['id']]

            df = pd.concat([df, position_df], ignore_index=True, sort=False)

            # Preserve existing column order and include any new columns at the end
            for col in position_df.columns:
                if col not in columns:
                    columns.append(col)

            df = df.reindex(columns=columns)

        # Save
        df.to_csv(self.positions_file, index=False)

    def _save_trade(self, trade: Dict):
        """Append a completed trade to trades history"""
        df = pd.read_csv(self.trades_file) if os.path.exists(self.trades_file) else pd.DataFrame()
        df = pd.concat([df, pd.DataFrame([trade])], ignore_index=True)
        df.to_csv(self.trades_file, index=False)

    def _save_portfolio_snapshot(self):
        """Save current portfolio state snapshot"""
        positions_value = sum(
            p['quantity_usd'] * p['remaining_pct'] / 100.0 *
            (1 + p.get('current_pnl_pct', 0) / 100.0)
            for p in self.positions.values() if p['status'] == 'open'
        )

        total_value = self.cash_balance + positions_value
        initial_balance = config.PAPER_TRADING_INITIAL_BALANCE
        total_pnl_usd = total_value - initial_balance
        total_pnl_pct = (total_pnl_usd / initial_balance) * 100 if initial_balance > 0 else 0

        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'total_value_usd': total_value,
            'cash_usd': self.cash_balance,
            'positions_value_usd': positions_value,
            'open_positions_count': len([p for p in self.positions.values() if p['status'] == 'open']),
            'total_pnl_usd': total_pnl_usd,
            'total_pnl_pct': total_pnl_pct
        }

        df = pd.read_csv(self.portfolio_file) if os.path.exists(self.portfolio_file) else pd.DataFrame()
        df = pd.concat([df, pd.DataFrame([snapshot])], ignore_index=True)
        df.to_csv(self.portfolio_file, index=False)

    def open_position(self, token_address: str, symbol: str, revival_score: float) -> Optional[Dict]:
        """
        Open a new paper trading position with realistic execution simulation

        Returns position dict if successful, None if insufficient funds or limits exceeded
        """
        # Check position limits
        open_positions = len([p for p in self.positions.values() if p['status'] == 'open'])
        max_positions = config.PAPER_TRADING_MAX_POSITIONS
        if max_positions is not None and max_positions > 0 and open_positions >= max_positions:
            max_positions_text = max_positions if max_positions is not None else "Unlimited"
            self._log(f"❌ Cannot open position: max positions ({max_positions_text}) reached", 'warning')
            return None

        # Check cash balance
        position_size = config.PAPER_TRADING_POSITION_SIZE_USD
        if self.cash_balance < position_size:
            self._log(f"❌ Cannot open position: insufficient cash (${self.cash_balance:.2f} < ${position_size:.2f})", 'warning')
            return None

        # Get current market price
        try:
            market_price = token_price(token_address)
            if not market_price or market_price <= 0:
                self._log(f"❌ Cannot open position: invalid price for {symbol}", 'warning')
                return None
        except Exception as e:
            self._log_error(f"❌ Cannot open position: failed to get price for {symbol}: {e}")
            return None

        # Simulate entry execution with slippage
        slippage_pct = config.PAPER_TRADING_ENTRY_SLIPPAGE_PCT
        execution_price = market_price * (1 + slippage_pct / 100.0)

        # Calculate fees
        fee_pct = config.PAPER_TRADING_JUPITER_FEE_PCT
        entry_fee = position_size * (fee_pct / 100.0)

        # Net position size after fees
        net_position_size = position_size - entry_fee

        # Calculate stop-loss and take-profit prices
        stop_loss_price = execution_price * (1 + config.PAPER_TRADING_STOP_LOSS_PCT / 100.0)
        tp1_price = execution_price * (1 + config.PAPER_TRADING_TAKE_PROFIT_1_PCT / 100.0)
        tp2_price = execution_price * (1 + config.PAPER_TRADING_TAKE_PROFIT_2_PCT / 100.0)

        # Create position
        position_id = f"pos_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{token_address[:8]}"
        entry_time = datetime.now().isoformat()

        position = {
            'id': position_id,
            'token_address': token_address,
            'symbol': symbol,
            'entry_price': execution_price,
            'entry_time': entry_time,
            'quantity_usd': net_position_size,
            'remaining_pct': 100.0,
            'status': 'open',
            'stop_loss_price': stop_loss_price,
            'take_profit_1_price': tp1_price,
            'take_profit_2_price': tp2_price,
            'current_price': execution_price,
            'current_pnl_pct': 0.0,
            'last_updated': entry_time
        }

        # Deduct cash
        self.cash_balance -= position_size

        # Save position
        self._save_position(position)

        # Save portfolio snapshot
        self._save_portfolio_snapshot()

        self._log(f"✅ Opened position: {symbol} @ ${execution_price:.8f}", 'success')
        self._log(f"   Size: ${net_position_size:.2f} (after ${entry_fee:.2f} fees)", 'info')
        self._log(f"   Stop Loss: ${stop_loss_price:.8f} ({config.PAPER_TRADING_STOP_LOSS_PCT}%)", 'info')
        self._log(f"   Take Profit 1: ${tp1_price:.8f} (+{config.PAPER_TRADING_TAKE_PROFIT_1_PCT}%)", 'info')
        self._log(f"   Take Profit 2: ${tp2_price:.8f} (+{config.PAPER_TRADING_TAKE_PROFIT_2_PCT}%)", 'info')

        # Send email notification
        if self.email_notifier:
            self.email_notifier.notify_position_opened(position)

        return position

    def close_position(self, position_id: str, exit_type: str, current_price: float) -> Optional[Dict]:
        """
        Close a position (full or partial) with realistic execution simulation

        exit_type: 'stop_loss', 'take_profit_1', 'take_profit_2', 'time_based'

        Returns trade dict if successful, None if position not found or exit fails
        """
        if position_id not in self.positions:
            self._log(f"❌ Position {position_id} not found", 'warning')
            return None

        position = self.positions[position_id]

        if position['status'] != 'open':
            self._log(f"❌ Position {position_id} is not open", 'warning')
            return None

        # Determine exit slippage based on exit type
        if exit_type == 'stop_loss':
            slippage_pct = config.PAPER_TRADING_STOP_EXIT_SLIPPAGE_PCT
            # Simulate failed exit chance
            if random.random() < config.PAPER_TRADING_FAILED_EXIT_CHANCE:
                self._log(f"❌ Failed to exit {position['symbol']} - token frozen or no liquidity!", 'warning')
                # Mark as total loss
                execution_price = 0
                slippage_pct = 0
                exit_type = 'failed_exit'
            else:
                execution_price = current_price * (1 - slippage_pct / 100.0)
        else:
            slippage_pct = config.PAPER_TRADING_PROFIT_EXIT_SLIPPAGE_PCT
            execution_price = current_price * (1 - slippage_pct / 100.0)

        # Determine how much to sell
        if exit_type == 'take_profit_1':
            sell_pct = config.PAPER_TRADING_TAKE_PROFIT_1_SELL_PCT
        elif exit_type == 'take_profit_2':
            sell_pct = config.PAPER_TRADING_TAKE_PROFIT_2_SELL_PCT
        else:
            # Stop loss, time-based, or failed exit - close entire position
            sell_pct = position['remaining_pct']

        # Calculate exit value
        position_value = position['quantity_usd'] * (position['remaining_pct'] / 100.0)
        sell_value = position_value * (sell_pct / position['remaining_pct'])

        # Calculate P&L
        if exit_type == 'failed_exit':
            pnl_usd = -sell_value  # Total loss
            pnl_pct = -100.0
        else:
            pnl_pct = ((execution_price - position['entry_price']) / position['entry_price']) * 100
            pnl_usd = sell_value * (pnl_pct / 100.0)

        # Calculate exit fee
        exit_fee = (sell_value + pnl_usd) * (config.PAPER_TRADING_JUPITER_FEE_PCT / 100.0) if pnl_usd > 0 else 0
        net_pnl_usd = pnl_usd - exit_fee

        # Calculate hold time
        entry_time = datetime.fromisoformat(position['entry_time'])
        hold_days = (datetime.now() - entry_time).total_seconds() / 86400

        # Create trade record
        trade_id = f"trade_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{position['token_address'][:8]}"
        trade = {
            'id': trade_id,
            'position_id': position_id,
            'token_address': position['token_address'],
            'symbol': position['symbol'],
            'entry_price': position['entry_price'],
            'entry_time': position['entry_time'],
            'exit_price': execution_price,
            'exit_time': datetime.now().isoformat(),
            'quantity_usd': sell_value,
            'exit_type': exit_type,
            'pnl_usd': net_pnl_usd,
            'pnl_pct': pnl_pct,
            'fees_paid': exit_fee,
            'hold_days': hold_days
        }

        # Update cash balance
        self.cash_balance += sell_value + net_pnl_usd

        # Update position
        new_remaining_pct = position['remaining_pct'] - sell_pct
        if new_remaining_pct <= 0.01:  # Fully closed
            position['status'] = 'closed'
            position['remaining_pct'] = 0.0
        else:
            position['remaining_pct'] = new_remaining_pct

        position['last_updated'] = datetime.now().isoformat()

        # Save trade and position
        self._save_trade(trade)
        self._save_position(position)
        self._save_portfolio_snapshot()

        # Print results
        emoji = "🟢" if net_pnl_usd >= 0 else "🔴"
        self._log(f"{emoji} Closed {sell_pct:.0f}% of {position['symbol']} via {exit_type}", 'info')
        self._log(f"   Exit Price: ${execution_price:.8f}", 'info')
        self._log(f"   P&L: ${net_pnl_usd:.2f} ({pnl_pct:+.2f}%)", 'info')
        self._log(f"   Fees: ${exit_fee:.2f}", 'info')
        self._log(f"   Hold Time: {hold_days:.2f} days", 'info')

        # Send email notification
        if self.email_notifier:
            self.email_notifier.notify_position_closed(trade)

        return trade

    def update_position_price(self, position_id: str, current_price: float):
        """Update position with current price and P&L"""
        if position_id not in self.positions:
            return

        position = self.positions[position_id]
        if position['status'] != 'open':
            return

        # Calculate current P&L
        pnl_pct = ((current_price - position['entry_price']) / position['entry_price']) * 100

        position['current_price'] = current_price
        position['current_pnl_pct'] = pnl_pct
        position['last_updated'] = datetime.now().isoformat()

        self._save_position(position)

    def check_exit_conditions(self, position_id: str, current_price: float) -> Optional[str]:
        """
        Check if position should be exited based on current price

        Returns exit_type if exit needed, None otherwise
        """
        if position_id not in self.positions:
            return None

        position = self.positions[position_id]
        if position['status'] != 'open':
            return None

        # Check stop-loss
        if current_price <= position['stop_loss_price']:
            return 'stop_loss'

        # Check take-profit levels (only if not already partially closed)
        if position['remaining_pct'] >= 100:
            if current_price >= position['take_profit_1_price']:
                return 'take_profit_1'
        elif position['remaining_pct'] >= 60:  # After TP1, still have >60%
            if current_price >= position['take_profit_2_price']:
                return 'take_profit_2'

        # Check time-based exit
        entry_time = datetime.fromisoformat(position['entry_time'])
        hold_days = (datetime.now() - entry_time).total_seconds() / 86400
        if hold_days >= config.PAPER_TRADING_MAX_HOLD_DAYS:
            return 'time_based'

        return None

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions"""
        return [p for p in self.positions.values() if p['status'] == 'open']

    def get_portfolio_summary(self) -> Dict:
        """Get current portfolio summary"""
        open_positions = self.get_open_positions()

        positions_value = sum(
            p['quantity_usd'] * p['remaining_pct'] / 100.0 *
            (1 + p.get('current_pnl_pct', 0) / 100.0)
            for p in open_positions
        )

        total_value = self.cash_balance + positions_value
        initial_balance = config.PAPER_TRADING_INITIAL_BALANCE
        total_pnl_usd = total_value - initial_balance
        total_pnl_pct = (total_pnl_usd / initial_balance) * 100 if initial_balance > 0 else 0

        return {
            'total_value_usd': total_value,
            'cash_usd': self.cash_balance,
            'positions_value_usd': positions_value,
            'open_positions_count': len(open_positions),
            'total_pnl_usd': total_pnl_usd,
            'total_pnl_pct': total_pnl_pct,
            'last_updated': datetime.now().isoformat()
        }

    def reset_paper_trading(self):
        """Reset paper trading to initial state"""
        # Close all positions
        for position in list(self.positions.values()):
            if position['status'] == 'open':
                position['status'] = 'closed'
                position['remaining_pct'] = 0.0
                self._save_position(position)

        # Reset cash balance
        self.cash_balance = config.PAPER_TRADING_INITIAL_BALANCE
        self._save_portfolio_snapshot()

        self._log(f"♻️ Paper trading reset to ${config.PAPER_TRADING_INITIAL_BALANCE:.2f}", 'info')
