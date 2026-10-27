from threading import Lock

from app.domain.entities.dashboard import (
    DashboardSummary,
    RiskDistribution,
    TimelinePoint,
)
from app.infrastructure.database.connection import Database
from app.infrastructure.database.query import Sort

_DASHBOARD_FIELDS = (
    "total_calls",
    "analyzed_calls",
    "suspicious_calls",
    "suspicious_subscribers",
    "low",
    "medium",
    "high",
    "critical",
    "period_from",
    "period_to",
    "timeline_timestamp",
    "day_total_calls",
    "day_suspicious_calls",
)


class DashboardService:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._refresh_lock = Lock()
        self._refresh_status = "idle"

    @property
    def refresh_status(self) -> str:
        return self._refresh_status

    def refresh_summary_cache(self) -> None:
        with self._refresh_lock:
            self._refresh_status = "refreshing"
            try:
                self._database.refresh_dashboard_summary_cache()
            except Exception:
                self._refresh_status = "failed"
                raise
            self._refresh_status = "idle"

    def get_summary(self) -> DashboardSummary:
        rows = self._database.select_all(
            "public.dashboard_summary_view",
            _DASHBOARD_FIELDS,
            order_by=(Sort("timeline_timestamp"),),
        )
        if not rows:
            raise RuntimeError("Представление сводки не вернуло результат")

        (
            total_calls,
            analyzed_calls,
            suspicious_calls,
            suspicious_subscribers,
            low,
            medium,
            high,
            critical,
            period_from,
            period_to,
            _,
            _,
            _,
        ) = rows[0]
        timeline = []
        for row in rows:
            timestamp, day_total, day_suspicious = row[10:13]
            if timestamp is not None:
                timeline.append(
                    TimelinePoint(
                        timestamp=timestamp,
                        total_calls=day_total,
                        suspicious_calls=day_suspicious,
                    )
                )
        return DashboardSummary(
            total_calls=total_calls,
            analyzed_calls=analyzed_calls,
            suspicious_calls=suspicious_calls,
            suspicious_subscribers=suspicious_subscribers,
            risk_distribution=RiskDistribution(
                low=low, medium=medium, high=high, critical=critical
            ),
            period_from=period_from,
            period_to=period_to,
            timeline=tuple(timeline),
        )
