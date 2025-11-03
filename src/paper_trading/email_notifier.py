"""
🌙 Moon Dev's Paper Trading Email Notifier
Built with love by Moon Dev 🚀

Sends email notifications for paper trading events:
- Position opened/closed
- Stop-loss/take-profit triggers
- Daily summaries
- Weekly performance reports
"""

import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Optional

# Add parent directory to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src import config
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class EmailNotifier:
    """Sends email notifications for paper trading events"""

    def __init__(self):
        """Initialize email notifier"""
        self.enabled = config.PAPER_TRADING_EMAIL_ENABLED
        self.email_address = config.PAPER_TRADING_EMAIL_ADDRESS
        self.smtp_server = config.PAPER_TRADING_EMAIL_SMTP_SERVER
        self.smtp_port = config.PAPER_TRADING_EMAIL_SMTP_PORT
        self.username = config.PAPER_TRADING_EMAIL_USERNAME or self.email_address
        self.password = os.getenv('EMAIL_PASSWORD', '')

        # Notification preferences
        self.notify_position_opened = config.PAPER_TRADING_NOTIFY_POSITION_OPENED
        self.notify_stop_loss = config.PAPER_TRADING_NOTIFY_STOP_LOSS
        self.notify_take_profit = config.PAPER_TRADING_NOTIFY_TAKE_PROFIT
        self.notify_failed_exit = config.PAPER_TRADING_NOTIFY_FAILED_EXIT

    def _send_email(self, subject: str, body: str, is_html: bool = False) -> bool:
        """
        Send an email

        Args:
            subject: Email subject
            body: Email body (plain text or HTML)
            is_html: Whether body is HTML

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            print("📧 Email notifications disabled in config")
            return False

        if not self.email_address:
            print("❌ Email address not configured")
            return False

        if not self.password:
            print("❌ Email password not set in .env file")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_address
            msg['To'] = self.email_address
            msg['Subject'] = subject

            # Attach body
            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))

            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()  # Secure connection
                server.login(self.username, self.password)
                server.send_message(msg)

            print(f"✅ Email sent: {subject}")
            return True

        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            return False

    def notify_position_opened(self, position: Dict) -> bool:
        """Send notification when a position is opened"""
        if not self.notify_position_opened:
            return False

        subject = f"🟢 Paper Position Opened: {position['symbol']}"

        body = f"""
Paper Trading Position Opened

Symbol: {position['symbol']}
Entry Price: ${position['entry_price']:.8f}
Position Size: ${position['quantity_usd']:.2f}
Stop Loss: ${position['stop_loss_price']:.8f} ({config.PAPER_TRADING_STOP_LOSS_PCT}%)
Take Profit 1: ${position['take_profit_1_price']:.8f} (+{config.PAPER_TRADING_TAKE_PROFIT_1_PCT}%)
Take Profit 2: ${position['take_profit_2_price']:.8f} (+{config.PAPER_TRADING_TAKE_PROFIT_2_PCT}%)

Entry Time: {position['entry_time']}

View dashboard: http://localhost:8080
"""

        return self._send_email(subject, body)

    def notify_position_closed(self, trade: Dict) -> bool:
        """Send notification when a position is closed"""
        exit_type = trade['exit_type']

        # Check if this type of exit should trigger notification
        if exit_type == 'stop_loss' and not self.notify_stop_loss:
            return False
        if exit_type in ['take_profit_1', 'take_profit_2'] and not self.notify_take_profit:
            return False
        if exit_type == 'failed_exit' and not self.notify_failed_exit:
            return False

        # Determine emoji based on exit type
        if trade['pnl_usd'] >= 0:
            emoji = "🟢"
            result = "PROFIT"
        else:
            emoji = "🔴"
            result = "LOSS"

        if exit_type == 'failed_exit':
            emoji = "⚠️"
            result = "FAILED EXIT"

        subject = f"{emoji} Paper Trade Closed: {trade['symbol']} ({trade['pnl_pct']:+.2f}%)"

        body = f"""
Paper Trading Position Closed - {result}

Symbol: {trade['symbol']}
Exit Type: {exit_type}

Entry Price: ${trade['entry_price']:.8f}
Exit Price: ${trade['exit_price']:.8f}
Position Size: ${trade['quantity_usd']:.2f}

P&L: ${trade['pnl_usd']:.2f} ({trade['pnl_pct']:+.2f}%)
Fees Paid: ${trade['fees_paid']:.2f}
Hold Time: {trade['hold_days']:.1f} days

Entry Time: {trade['entry_time']}
Exit Time: {trade['exit_time']}

View dashboard: http://localhost:8080
"""

        return self._send_email(subject, body)

    def notify_daily_summary(self, summary: Dict) -> bool:
        """Send daily summary email"""
        if not config.PAPER_TRADING_NOTIFY_DAILY_SUMMARY:
            return False

        date = datetime.now().strftime('%B %d, %Y')
        subject = f"📊 Daily Paper Trading Summary - {date}"

        # Calculate daily stats
        portfolio_value = summary.get('portfolio_value', 0)
        daily_pnl = summary.get('daily_pnl', 0)
        daily_pnl_pct = summary.get('daily_pnl_pct', 0)
        cash_balance = summary.get('cash_balance', 0)
        open_positions = summary.get('open_positions', 0)
        trades_today = summary.get('trades_today', 0)
        winners_today = summary.get('winners_today', 0)
        losers_today = summary.get('losers_today', 0)
        best_trade = summary.get('best_trade')
        worst_trade = summary.get('worst_trade')

        pnl_emoji = "🟢" if daily_pnl >= 0 else "🔴"

        body = f"""
Daily Paper Trading Summary - {date}

PORTFOLIO OVERVIEW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Value: ${portfolio_value:.2f}
Cash Balance: ${cash_balance:.2f}
Open Positions: {open_positions}

TODAY'S PERFORMANCE {pnl_emoji}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Daily P&L: ${daily_pnl:.2f} ({daily_pnl_pct:+.2f}%)
Trades Closed: {trades_today}
Winners: {winners_today}
Losers: {losers_today}
Win Rate: {(winners_today / trades_today * 100) if trades_today > 0 else 0:.1f}%
"""

        if best_trade:
            body += f"""
BEST TRADE TODAY 🏆
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{best_trade['symbol']}: {best_trade['pnl_pct']:+.2f}% (${best_trade['pnl_usd']:.2f})
"""

        if worst_trade:
            body += f"""
WORST TRADE TODAY 💥
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{worst_trade['symbol']}: {worst_trade['pnl_pct']:+.2f}% (${worst_trade['pnl_usd']:.2f})
"""

        body += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

View full dashboard: http://localhost:8080
"""

        return self._send_email(subject, body)

    def notify_weekly_report(self, report: Dict) -> bool:
        """Send weekly performance report"""
        if not config.PAPER_TRADING_NOTIFY_WEEKLY_REPORT:
            return False

        week_end = datetime.now().strftime('%B %d, %Y')
        subject = f"📈 Weekly Paper Trading Report - Week ending {week_end}"

        metrics = report.get('metrics', {})
        insights = report.get('insights', 'No insights available')

        body = f"""
Weekly Paper Trading Report
Week Ending: {week_end}

PERFORMANCE SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Trades: {metrics.get('total_trades', 0)}
Win Rate: {metrics.get('win_rate', 0):.1f}%
Total P&L: ${metrics.get('total_pnl_usd', 0):.2f}
Profit Factor: {metrics.get('profit_factor', 0):.2f}

RISK METRICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}
Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%
Avg Hold Time: {metrics.get('avg_hold_days', 0):.1f} days

TRADE ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Winning Trades: {metrics.get('winning_trades', 0)}
Average Gain: {metrics.get('avg_gain_pct', 0):.2f}%

Losing Trades: {metrics.get('losing_trades', 0)}
Average Loss: {metrics.get('avg_loss_pct', 0):.2f}%

AI INSIGHTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{insights}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

View full performance: http://localhost:8080
"""

        return self._send_email(subject, body)


def main():
    """
    Test email notifier

    Usage:
        python src/paper_trading/email_notifier.py
    """
    print("=" * 60)
    print("🌙 Moon Dev's Email Notifier - Test Mode")
    print("=" * 60)

    notifier = EmailNotifier()

    if not notifier.email_address:
        print("\n❌ Error: Email address not configured in config.py")
        print("   Set PAPER_TRADING_EMAIL_ADDRESS in src/config.py")
        return

    if not notifier.password:
        print("\n❌ Error: Email password not set")
        print("   Add EMAIL_PASSWORD to your .env file")
        return

    # Test position opened notification
    test_position = {
        'symbol': 'TEST',
        'entry_price': 0.00001234,
        'quantity_usd': 1000,
        'stop_loss_price': 0.00000987,
        'take_profit_1_price': 0.00001667,
        'take_profit_2_price': 0.00002160,
        'entry_time': datetime.now().isoformat()
    }

    print("\n📧 Sending test notification...")
    success = notifier.notify_position_opened(test_position)

    if success:
        print("✅ Test email sent successfully!")
        print(f"   Check your inbox at: {notifier.email_address}")
    else:
        print("❌ Failed to send test email")


if __name__ == "__main__":
    main()
