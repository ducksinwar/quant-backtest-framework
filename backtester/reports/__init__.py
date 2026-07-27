from backtester.reports._base import BaseReport
from backtester.reports.equity_curve import EquityCurveReport
from backtester.reports.trade_summary import TradeSummaryReport
from backtester.reports.metrics import MetricsReport
from backtester.reports.periodic_metrics import PeriodicMetricsReport
from backtester.reports.hit_ratio import HitRatioReport
from backtester.reports.drawdown_table import DrawdownTableReport
from backtester.reports.by_underlying import ByUnderlyingReport

REPORTS: dict[str, type[BaseReport]] = {
    "equity_curve": EquityCurveReport,
    "trade_summary": TradeSummaryReport,
    "metrics": MetricsReport,
    "periodic_metrics": PeriodicMetricsReport,
    "hit_ratio": HitRatioReport,
    "drawdown_table": DrawdownTableReport,
    "by_underlying": ByUnderlyingReport,
}
