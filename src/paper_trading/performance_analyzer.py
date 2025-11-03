"""
🌙 Moon Dev's Paper Trading Performance Analyzer
Built with love by Moon Dev 🚀

Analyzes paper trading performance and generates insights:
- Win rate, average gain/loss, profit factor
- Sharpe ratio, max drawdown, risk metrics
- Performance by revival score bands
"""

import os
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

# Add parent directory to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src import config


class PerformanceAnalyzer:
    """Analyzes paper trading performance and generates insights"""

    def __init__(self, data_dir: Optional[str] = None):
        """Initialize performance analyzer"""
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'paper_trading')

        self.data_dir = data_dir
        self.trades_file = os.path.join(data_dir, 'trades_history.csv')
        self.portfolio_file = os.path.join(data_dir, 'portfolio_snapshots.csv')
        self.metrics_file = os.path.join(data_dir, 'performance_metrics.json')

    def calculate_metrics(self) -> Dict:
        """
        Calculate comprehensive performance metrics

        Returns dict with all performance stats
        """
        # Load trades
        if not os.path.exists(self.trades_file):
            return self._empty_metrics()

        trades_df = pd.read_csv(self.trades_file)

        if len(trades_df) == 0:
            return self._empty_metrics()

        # Filter out failed exits from win/loss calculations
        valid_trades = trades_df[trades_df['exit_type'] != 'failed_exit']
        failed_exits = trades_df[trades_df['exit_type'] == 'failed_exit']

        # Basic metrics
        total_trades = len(valid_trades)
        if total_trades == 0:
            return self._empty_metrics()

        winning_trades = len(valid_trades[valid_trades['pnl_usd'] > 0])
        losing_trades = len(valid_trades[valid_trades['pnl_usd'] <= 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # P&L metrics
        total_pnl = valid_trades['pnl_usd'].sum()
        avg_gain = valid_trades[valid_trades['pnl_usd'] > 0]['pnl_pct'].mean() if winning_trades > 0 else 0
        avg_loss = valid_trades[valid_trades['pnl_usd'] <= 0]['pnl_pct'].mean() if losing_trades > 0 else 0

        # Profit factor (total gains / total losses)
        total_gains = valid_trades[valid_trades['pnl_usd'] > 0]['pnl_usd'].sum()
        total_losses = abs(valid_trades[valid_trades['pnl_usd'] <= 0]['pnl_usd'].sum())
        profit_factor = (total_gains / total_losses) if total_losses > 0 else float('inf')

        # Hold time analysis
        avg_hold_days = valid_trades['hold_days'].mean()
        median_hold_days = valid_trades['hold_days'].median()

        # Exit type breakdown
        exit_types = valid_trades['exit_type'].value_counts().to_dict()

        # Sharpe ratio (requires portfolio snapshots)
        sharpe_ratio = self._calculate_sharpe_ratio()

        # Max drawdown
        max_drawdown_pct = self._calculate_max_drawdown()

        # Failed exits
        failed_exit_count = len(failed_exits)
        failed_exit_loss = abs(failed_exits['pnl_usd'].sum()) if len(failed_exits) > 0 else 0

        # Best and worst trades
        best_trade = valid_trades.nlargest(1, 'pnl_pct').iloc[0] if len(valid_trades) > 0 else None
        worst_trade = valid_trades.nsmallest(1, 'pnl_pct').iloc[0] if len(valid_trades) > 0 else None

        metrics = {
            'last_updated': datetime.now().isoformat(),
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl_usd': total_pnl,
            'avg_gain_pct': avg_gain,
            'avg_loss_pct': avg_loss,
            'profit_factor': profit_factor,
            'avg_hold_days': avg_hold_days,
            'median_hold_days': median_hold_days,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown_pct': max_drawdown_pct,
            'exit_types': exit_types,
            'failed_exits': failed_exit_count,
            'failed_exit_loss_usd': failed_exit_loss,
            'best_trade': {
                'symbol': best_trade['symbol'],
                'pnl_pct': best_trade['pnl_pct'],
                'pnl_usd': best_trade['pnl_usd'],
                'exit_type': best_trade['exit_type']
            } if best_trade is not None else None,
            'worst_trade': {
                'symbol': worst_trade['symbol'],
                'pnl_pct': worst_trade['pnl_pct'],
                'pnl_usd': worst_trade['pnl_usd'],
                'exit_type': worst_trade['exit_type']
            } if worst_trade is not None else None
        }

        return metrics

    def _empty_metrics(self) -> Dict:
        """Return empty metrics dict"""
        return {
            'last_updated': datetime.now().isoformat(),
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'total_pnl_usd': 0.0,
            'avg_gain_pct': 0.0,
            'avg_loss_pct': 0.0,
            'profit_factor': 0.0,
            'avg_hold_days': 0.0,
            'median_hold_days': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown_pct': 0.0,
            'exit_types': {},
            'failed_exits': 0,
            'failed_exit_loss_usd': 0.0,
            'best_trade': None,
            'worst_trade': None
        }

    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio from portfolio snapshots"""
        if not os.path.exists(self.portfolio_file):
            return 0.0

        portfolio_df = pd.read_csv(self.portfolio_file)
        if len(portfolio_df) < 2:
            return 0.0

        # Calculate returns
        portfolio_df['returns'] = portfolio_df['total_value_usd'].pct_change()

        # Remove NaN
        returns = portfolio_df['returns'].dropna()

        if len(returns) == 0:
            return 0.0

        # Calculate Sharpe ratio (annualized)
        # Assuming snapshots are taken at regular intervals
        mean_return = returns.mean()
        std_return = returns.std()

        if std_return == 0:
            return 0.0

        # Annualize (assuming daily snapshots)
        sharpe_ratio = (mean_return / std_return) * np.sqrt(365)

        return sharpe_ratio

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from portfolio snapshots"""
        if not os.path.exists(self.portfolio_file):
            return 0.0

        portfolio_df = pd.read_csv(self.portfolio_file)
        if len(portfolio_df) < 2:
            return 0.0

        # Calculate cumulative max
        portfolio_df['cummax'] = portfolio_df['total_value_usd'].cummax()

        # Calculate drawdown
        portfolio_df['drawdown'] = (portfolio_df['total_value_usd'] - portfolio_df['cummax']) / portfolio_df['cummax'] * 100

        max_drawdown = portfolio_df['drawdown'].min()

        return max_drawdown

    def save_metrics(self) -> Dict:
        """
        Calculate metrics and save to file

        Returns:
            Complete metrics dict
        """
        print("📊 Calculating performance metrics...")

        # Calculate metrics
        metrics = self.calculate_metrics()

        # Save to file
        with open(self.metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)

        print(f"✅ Metrics saved to {self.metrics_file}")

        return metrics

    def load_metrics(self) -> Dict:
        """Load metrics from file"""
        if not os.path.exists(self.metrics_file):
            return self._empty_metrics()

        with open(self.metrics_file, 'r') as f:
            metrics = json.load(f)

        return metrics

    def print_summary(self, metrics: Optional[Dict] = None):
        """Print formatted performance summary"""
        if metrics is None:
            metrics = self.load_metrics()

        print("\n" + "=" * 60)
        print("📊 PAPER TRADING PERFORMANCE SUMMARY")
        print("=" * 60)

        print(f"\n📈 Overall Performance:")
        print(f"   Total Trades: {metrics['total_trades']}")
        print(f"   Win Rate: {metrics['win_rate']:.1f}%")
        print(f"   Total P&L: ${metrics['total_pnl_usd']:.2f}")
        print(f"   Profit Factor: {metrics['profit_factor']:.2f}")

        print(f"\n💰 Trade Analysis:")
        print(f"   Winning Trades: {metrics['winning_trades']}")
        print(f"   Average Gain: {metrics['avg_gain_pct']:+.2f}%")
        print(f"   Losing Trades: {metrics['losing_trades']}")
        print(f"   Average Loss: {metrics['avg_loss_pct']:+.2f}%")

        print(f"\n📊 Risk Metrics:")
        print(f"   Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"   Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
        print(f"   Avg Hold Time: {metrics['avg_hold_days']:.1f} days")

        print(f"\n🚪 Exit Types:")
        for exit_type, count in metrics.get('exit_types', {}).items():
            print(f"   {exit_type}: {count}")

        if metrics.get('failed_exits', 0) > 0:
            print(f"\n⚠️  Failed Exits: {metrics['failed_exits']} (${metrics['failed_exit_loss_usd']:.2f} lost)")

        if metrics.get('best_trade'):
            bt = metrics['best_trade']
            print(f"\n🏆 Best Trade:")
            print(f"   {bt['symbol']}: {bt['pnl_pct']:+.2f}% (${bt['pnl_usd']:.2f}) via {bt['exit_type']}")

        if metrics.get('worst_trade'):
            wt = metrics['worst_trade']
            print(f"\n💥 Worst Trade:")
            print(f"   {wt['symbol']}: {wt['pnl_pct']:+.2f}% (${wt['pnl_usd']:.2f}) via {wt['exit_type']}")

        print("\n" + "=" * 60)


def main():
    """
    Standalone test mode for performance analyzer

    Usage:
        python src/paper_trading/performance_analyzer.py
    """
    print("=" * 60)
    print("🌙 Moon Dev's Performance Analyzer - Standalone Mode")
    print("=" * 60)

    analyzer = PerformanceAnalyzer()

    # Calculate and save metrics
    metrics = analyzer.save_metrics()

    # Print summary
    analyzer.print_summary(metrics)


if __name__ == "__main__":
    main()
