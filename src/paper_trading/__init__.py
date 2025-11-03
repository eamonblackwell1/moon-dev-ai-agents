"""
🌙 Moon Dev's Paper Trading Module
Built with love by Moon Dev 🚀

This module provides paper trading simulation for the Revival Scanner,
allowing traders to test strategies with realistic execution simulation
before risking real capital.
"""

# Lazy imports to avoid dependency issues
def __getattr__(name):
    if name == 'PositionManager':
        from .position_manager import PositionManager
        return PositionManager
    elif name == 'PerformanceAnalyzer':
        from .performance_analyzer import PerformanceAnalyzer
        return PerformanceAnalyzer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ['PositionManager', 'PerformanceAnalyzer']
