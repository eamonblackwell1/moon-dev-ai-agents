"""
🌐 Moon Dev's Revival Scanner Web App
Beautiful web interface for the meme coin revival detection system
Built with love by Moon Dev 🚀
"""

from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
import sys
import os
import json
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Import our agents
from src.agents.revival_detector_agent import RevivalDetectorAgent
from src.agents.stage1_security_filter import Stage1SecurityFilter
from src.agents.meme_notifier_agent import MemeNotifierAgent
from src.agents.meme_scanner_orchestrator import MemeScannerOrchestrator

# Import config constants for phase descriptions
from src.config import (
    MIN_LIQUIDITY_PREFILTER,
    MIN_LIQUIDITY_STRICT,
    MIN_VOLUME_1H,
    MIN_AGE_HOURS,
    MAX_MARKET_CAP
)

app = Flask(__name__,
            template_folder='web_templates',
            static_folder='web_static')
CORS(app)  # Allow cross-origin requests

# Global state
scanner_state = {
    'running': False,
    'current_scan': None,
    'results': [],
    'scan_count': 0,
    'last_scan_time': None,
    'settings': {
        'scan_interval': 3600,  # 60 minutes / 1 hour (safe for BirdEye Starter tier - uses ~36% of monthly API limit)
        'min_revival_score': 0.4,
        'auto_scan': False
    },
    'progress': {
        'phase': '',
        'phase_number': 0,
        'total_phases': 5,
        'message': '',
        'tokens_collected': 0,
        'tokens_filtered': 0,
        'scan_start_time': None,
        'current_step': ''
    },
    'activity_log': [],
    'error_log': [],
    'phase_stats': {}
}

scanner_thread = None
orchestrator = None

def log_activity(message, level='info'):
    """Add message to activity log"""
    scanner_state['activity_log'].append({
        'timestamp': datetime.now().isoformat(),
        'message': message,
        'level': level
    })
    # Keep only last 500 entries
    if len(scanner_state['activity_log']) > 500:
        scanner_state['activity_log'] = scanner_state['activity_log'][-500:]

def log_error(message):
    """Add error to error log"""
    scanner_state['error_log'].append({
        'timestamp': datetime.now().isoformat(),
        'message': message
    })
    log_activity(f"ERROR: {message}", 'error')
    # Keep only last 200 errors
    if len(scanner_state['error_log']) > 200:
        scanner_state['error_log'] = scanner_state['error_log'][-200:]

def update_progress(phase, phase_number, message, tokens_collected=None, tokens_filtered=None, step=''):
    """Update scan progress"""
    scanner_state['progress']['phase'] = phase
    scanner_state['progress']['phase_number'] = phase_number
    scanner_state['progress']['message'] = message
    scanner_state['progress']['current_step'] = step

    if tokens_collected is not None:
        scanner_state['progress']['tokens_collected'] = tokens_collected
    if tokens_filtered is not None:
        scanner_state['progress']['tokens_filtered'] = tokens_filtered

    log_activity(f"[Phase {phase_number}/5] {message}")

def init_orchestrator():
    """Initialize the orchestrator"""
    global orchestrator
    if orchestrator is None:
        orchestrator = MemeScannerOrchestrator()
        # Inject callback functions
        orchestrator.log_activity = log_activity
        orchestrator.log_error = log_error
        orchestrator.update_progress = update_progress
    return orchestrator

def background_scanner():
    """Background thread for continuous scanning"""
    global scanner_state, orchestrator

    orchestrator = init_orchestrator()

    while scanner_state['running']:
        try:
            print(f"🔄 Starting scan #{scanner_state['scan_count'] + 1}")

            # Reset progress
            scanner_state['progress']['scan_start_time'] = datetime.now().isoformat()
            scanner_state['current_scan'] = 'running'
            scanner_state['last_scan_time'] = datetime.now().isoformat()

            log_activity(f"Starting scan #{scanner_state['scan_count'] + 1}", 'info')

            # Run scan
            results = orchestrator.run_scan_cycle()

            # Update results
            scanner_state['results'] = results
            scanner_state['scan_count'] += 1
            scanner_state['current_scan'] = 'completed'

            log_activity(f"Scan completed - found {len(results)} opportunities", 'success')

            # Wait for next scan
            time.sleep(scanner_state['settings']['scan_interval'])

        except Exception as e:
            print(f"❌ Scanner error: {str(e)}")
            log_error(str(e))
            scanner_state['current_scan'] = f'error: {str(e)}'
            time.sleep(60)  # Wait 1 minute on error

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Get scanner status"""
    return jsonify({
        'running': scanner_state['running'],
        'current_scan': scanner_state['current_scan'],
        'scan_count': scanner_state['scan_count'],
        'last_scan_time': scanner_state['last_scan_time'],
        'settings': scanner_state['settings'],
        'results_count': len(scanner_state['results']),
        'progress': scanner_state['progress'],
        'phase_stats': scanner_state['phase_stats']
    })

@app.route('/api/activity')
def get_activity():
    """Get recent activity log (last 100 entries)"""
    return jsonify({
        'activity': scanner_state['activity_log'][-100:],
        'count': len(scanner_state['activity_log'])
    })

@app.route('/api/errors')
def get_errors():
    """Get error log"""
    return jsonify({
        'errors': scanner_state['error_log'][-50:],
        'count': len(scanner_state['error_log'])
    })

@app.route('/api/results')
def get_results():
    """Get latest scan results"""
    min_score = request.args.get('min_score', 0.4, type=float)

    # Filter by minimum score
    filtered_results = [
        r for r in scanner_state['results']
        if r.get('revival_score', 0) >= min_score
    ]

    # Sort by score
    filtered_results.sort(key=lambda x: x.get('revival_score', 0), reverse=True)

    return jsonify({
        'results': filtered_results,
        'total': len(scanner_state['results']),
        'filtered': len(filtered_results)
    })

@app.route('/api/scan/start', methods=['POST'])
def start_scanner():
    """Start continuous scanning"""
    global scanner_state, scanner_thread

    if scanner_state['running']:
        return jsonify({'error': 'Scanner already running'}), 400

    scanner_state['running'] = True
    scanner_state['settings']['auto_scan'] = True

    # Start background thread
    scanner_thread = threading.Thread(target=background_scanner, daemon=True)
    scanner_thread.start()

    return jsonify({
        'status': 'started',
        'message': 'Scanner started successfully'
    })

@app.route('/api/scan/stop', methods=['POST'])
def stop_scanner():
    """Stop continuous scanning"""
    global scanner_state

    scanner_state['running'] = False
    scanner_state['settings']['auto_scan'] = False

    return jsonify({
        'status': 'stopped',
        'message': 'Scanner stopped successfully'
    })

@app.route('/api/scan/once', methods=['POST'])
def scan_once():
    """Run a single scan"""
    try:
        orchestrator = init_orchestrator()

        # Reset progress and logs
        scanner_state['progress']['scan_start_time'] = datetime.now().isoformat()
        scanner_state['current_scan'] = 'running'
        scanner_state['last_scan_time'] = datetime.now().isoformat()
        scanner_state['phase_stats'] = {}

        log_activity(f"Starting manual scan", 'info')

        # Run single scan
        results = orchestrator.run_scan_cycle()

        # Update state
        scanner_state['results'] = results
        scanner_state['scan_count'] += 1
        scanner_state['current_scan'] = 'completed'

        log_activity(f"Scan completed - found {len(results)} opportunities", 'success')

        return jsonify({
            'status': 'success',
            'results': results,
            'count': len(results)
        })

    except Exception as e:
        log_error(str(e))
        scanner_state['current_scan'] = f'error: {str(e)}'
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    """Get or update settings"""
    if request.method == 'POST':
        data = request.json

        if 'scan_interval' in data:
            scanner_state['settings']['scan_interval'] = int(data['scan_interval'])
        if 'min_revival_score' in data:
            scanner_state['settings']['min_revival_score'] = float(data['min_revival_score'])

        return jsonify({
            'status': 'updated',
            'settings': scanner_state['settings']
        })

    return jsonify(scanner_state['settings'])

@app.route('/api/token/<address>')
def get_token_details(address):
    """Get detailed info for a specific token"""
    try:
        detector = RevivalDetectorAgent()
        result = detector.calculate_revival_score(address)

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/api/history')
def get_history():
    """Get scan history from saved files"""
    try:
        data_dir = Path(__file__).parent / "data" / "meme_scanner"

        if not data_dir.exists():
            return jsonify({'scans': []})

        # Get all scan result files
        scan_files = sorted(data_dir.glob("scan_results_*.csv"), reverse=True)[:10]

        history = []
        for scan_file in scan_files:
            import pandas as pd
            df = pd.read_csv(scan_file)

            history.append({
                'filename': scan_file.name,
                'timestamp': scan_file.stat().st_mtime,
                'token_count': len(df),
                'avg_score': df['revival_score'].mean() if len(df) > 0 else 0,
                'top_token': df.iloc[0].to_dict() if len(df) > 0 else None
            })

        return jsonify({'scans': history})

    except Exception as e:
        return jsonify({
            'error': str(e),
            'scans': []
        })

@app.route('/api/download/phase5/latest')
def download_latest_phase5():
    """Download the latest Phase 5 analysis CSV"""
    try:
        data_dir = Path(__file__).parent / "data" / "meme_scanner"

        if not data_dir.exists():
            return jsonify({'error': 'No scan data available'}), 404

        # Get the most recent phase5_analysis CSV file
        phase5_files = sorted(data_dir.glob("phase5_analysis_*.csv"), reverse=True)

        if not phase5_files:
            return jsonify({'error': 'No Phase 5 analysis files found'}), 404

        latest_file = phase5_files[0]

        # Send file as download
        return send_file(
            latest_file,
            as_attachment=True,
            download_name=latest_file.name,
            mimetype='text/csv'
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts')
def get_alerts():
    """Get recent alerts"""
    try:
        data_dir = Path(__file__).parent / "data" / "meme_notifier"
        today_file = data_dir / f"alerts_{datetime.now().strftime('%Y%m%d')}.csv"

        if not today_file.exists():
            return jsonify({'alerts': []})

        import pandas as pd
        df = pd.read_csv(today_file)

        # Convert to list of dicts
        alerts = df.to_dict('records')

        return jsonify({
            'alerts': alerts,
            'count': len(alerts)
        })

    except Exception as e:
        return jsonify({
            'error': str(e),
            'alerts': []
        })

@app.route('/api/phases')
def get_phases():
    """Get token counts and samples for each phase of the scanning pipeline (5-phase structure)"""
    try:
        if orchestrator is None:
            return jsonify({
                'error': 'Scanner not initialized',
                'phases': []
            })

        phase_data = []
        phase_tokens = orchestrator.phase_tokens

        # Phase 1: BirdEye Discovery (Native Meme List)
        phase1 = phase_tokens.get('phase1_birdeye', [])
        phase_data.append({
            'phase': 1,
            'name': 'BirdEye Discovery',
            'description': 'Native meme token list (2-pass: liquidity-sorted + sequential, ~2000 pure memecoins)',
            'count': len(phase1),
            'samples': [
                {
                    'symbol': t.get('symbol', 'Unknown'),
                    'address': t.get('address', ''),
                    'liquidity': t.get('liquidity', 0),
                    'volume_24h': t.get('volume_24h', 0),
                    'market_cap': t.get('mc', 0)
                } for t in phase1[:10]  # First 10 tokens
            ]
        })

        # Phase 2: Pre-filtered (Liquidity, Market Cap, Volume - all from BirdEye)
        phase2 = phase_tokens.get('phase2_prefiltered', [])
        phase_data.append({
            'phase': 2,
            'name': 'Pre-Filter',
            'description': f'Liquidity >${MIN_LIQUIDITY_PREFILTER:,}, Market Cap <${MAX_MARKET_CAP:,}, Volume 1h >${MIN_VOLUME_1H:,}',
            'count': len(phase2),
            'samples': [
                {
                    'symbol': t.get('symbol', 'Unknown'),
                    'address': t.get('address', ''),
                    'liquidity': t.get('liquidity', 0),
                    'market_cap': t.get('market_cap', 0),
                    'volume_24h': t.get('volume_24h', 0)
                } for t in phase2[:10]
            ]
        })

        # Phase 3: Age Verified (Helius Blockchain)
        phase3 = phase_tokens.get('phase3_aged', [])
        phase_data.append({
            'phase': 3,
            'name': 'Age Verification',
            'description': f'Minimum {MIN_AGE_HOURS}h old (no maximum)',
            'count': len(phase3),
            'samples': [
                {
                    'address': t.get('address', ''),
                } for t in phase3[:10]
            ]
        })

        # Phase 4: Security Passed
        phase4 = phase_tokens.get('phase4_security_passed', [])
        phase_data.append({
            'phase': 4,
            'name': 'Security Filter',
            'description': 'Passed Stage 1 security checks (scam detection)',
            'count': len(phase4),
            'samples': [
                {
                    'address': t.get('address', ''),
                } for t in phase4[:10]
            ]
        })

        # Phase 5: Revival Detected
        phase5 = phase_tokens.get('phase5_revival_detected', [])
        phase_data.append({
            'phase': 5,
            'name': 'Revival Opportunities',
            'description': 'Final opportunities with revival scores ≥0.4',
            'count': len(phase5),
            'samples': [
                {
                    'symbol': t.get('token_symbol', 'Unknown'),
                    'address': t.get('token_address', ''),
                    'revival_score': t.get('revival_score', 0),
                    'price_score': t.get('price_score', 0),
                    'smart_score': t.get('smart_score', 0)
                } for t in phase5[:10]
            ]
        })

        return jsonify({
            'phases': phase_data,
            'total_phases': 5
        })

    except Exception as e:
        return jsonify({
            'error': str(e),
            'phases': []
        })

# ==================== PAPER TRADING API ENDPOINTS ====================

# Global paper trading agent (initialized on demand)
paper_trading_agent = None
performance_analyzer = None

def init_paper_trading():
    """Initialize paper trading components"""
    global paper_trading_agent, performance_analyzer

    if paper_trading_agent is None:
        from src.agents.paper_trading_agent import PaperTradingAgent
        from src.paper_trading.performance_analyzer import PerformanceAnalyzer

        paper_trading_agent = PaperTradingAgent()
        performance_analyzer = PerformanceAnalyzer()
        log_activity("Paper trading agent initialized", 'info')

    return paper_trading_agent, performance_analyzer

@app.route('/api/paper/portfolio')
def paper_portfolio():
    """Get current paper trading portfolio summary"""
    try:
        agent, analyzer = init_paper_trading()
        summary = agent.get_portfolio_summary()

        return jsonify({
            'status': 'success',
            'portfolio': summary
        })

    except Exception as e:
        log_error(f"Paper trading portfolio error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/paper/positions')
def paper_positions():
    """Get open paper trading positions"""
    try:
        agent, analyzer = init_paper_trading()
        positions = agent.get_open_positions()

        return jsonify({
            'status': 'success',
            'positions': positions,
            'count': len(positions)
        })

    except Exception as e:
        log_error(f"Paper trading positions error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/paper/trades')
def paper_trades():
    """Get paper trading trade history"""
    try:
        import pandas as pd
        from pathlib import Path

        trades_file = Path(__file__).parent / 'data' / 'paper_trading' / 'trades_history.csv'

        if not trades_file.exists():
            return jsonify({
                'status': 'success',
                'trades': [],
                'count': 0
            })

        trades_df = pd.read_csv(trades_file)

        # Get pagination params
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))

        # Sort by exit time (most recent first)
        trades_df = trades_df.sort_values('exit_time', ascending=False)

        # Paginate
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_trades = trades_df.iloc[start_idx:end_idx]

        return jsonify({
            'status': 'success',
            'trades': page_trades.to_dict('records'),
            'count': len(trades_df),
            'page': page,
            'per_page': per_page,
            'total_pages': (len(trades_df) + per_page - 1) // per_page
        })

    except Exception as e:
        log_error(f"Paper trading trades error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/paper/metrics')
def paper_metrics():
    """Get paper trading performance metrics"""
    try:
        agent, analyzer = init_paper_trading()

        # Check if we should regenerate metrics
        regenerate = request.args.get('regenerate', 'false').lower() == 'true'

        if regenerate:
            metrics = analyzer.save_metrics()
        else:
            metrics = analyzer.load_metrics()

        return jsonify({
            'status': 'success',
            'metrics': metrics
        })

    except Exception as e:
        log_error(f"Paper trading metrics error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/paper/reset', methods=['POST'])
def paper_reset():
    """Reset paper trading to initial state"""
    try:
        agent, analyzer = init_paper_trading()
        agent.reset()

        log_activity("Paper trading reset", 'info')

        return jsonify({
            'status': 'success',
            'message': 'Paper trading reset successfully'
        })

    except Exception as e:
        log_error(f"Paper trading reset error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/paper/close/<position_id>', methods=['POST'])
def paper_close_position(position_id):
    """Manually close a paper trading position"""
    try:
        agent, analyzer = init_paper_trading()
        success = agent.manual_close_position(position_id)

        if success:
            log_activity(f"Manually closed position {position_id}", 'info')
            return jsonify({
                'status': 'success',
                'message': 'Position closed successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to close position'
            }), 400

    except Exception as e:
        log_error(f"Paper trading close position error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def main():
    """Run the web app"""
    print("="*60)
    print("🌐 Moon Dev's Revival Scanner Web App")
    print("="*60)
    print("\n🚀 Starting server...")
    print("📡 Dashboard will be available at: http://localhost:8080")
    print("⌨️  Press Ctrl+C to stop\n")

    # Create necessary directories
    Path(__file__).parent.joinpath('web_templates').mkdir(exist_ok=True)
    Path(__file__).parent.joinpath('web_static').mkdir(exist_ok=True)

    # Run Flask app
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)

if __name__ == '__main__':
    main()