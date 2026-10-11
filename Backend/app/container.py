from dataclasses import dataclass

from app.application.use_cases.analysis_jobs import GetAnalysisStatus, RunAnalysis
from app.application.use_cases.check_service_health import CheckServiceHealth
from app.application.use_cases.get_dashboard_summary import GetDashboardSummary
from app.application.use_cases.get_call import GetCall
from app.application.use_cases.get_model_info import GetModelInfo
from app.application.use_cases.get_subscriber_profile import GetSubscriberProfile
from app.application.use_cases.list_calls import ListCalls
from app.application.use_cases.list_fraud_alerts import ListFraudAlerts
from app.application.use_cases.predict_fraud import PredictFraud
from app.core.config import Settings, get_settings
from app.infrastructure.database.connection import Database
from app.infrastructure.database.health_repository import HealthRepository
from app.infrastructure.database.postgres_call_repository import PostgresCallRepository
from app.infrastructure.database.analysis_job_repository import (
    UnconfiguredAnalysisJobRepository,
)
from app.infrastructure.database.dashboard_repository import UnconfiguredDashboardRepository
from app.infrastructure.database.fraud_alert_repository import (
    UnconfiguredFraudAlertRepository,
)
from app.infrastructure.database.subscriber_repository import (
    UnconfiguredSubscriberRepository,
)
from app.infrastructure.ml.catboost_predictor import CatBoostPredictor


@dataclass(slots=True)
class Container:
    settings: Settings
    database: Database
    check_service_health: CheckServiceHealth
    get_dashboard_summary: GetDashboardSummary
    list_calls: ListCalls
    get_call: GetCall
    predict_fraud: PredictFraud
    run_analysis: RunAnalysis
    get_analysis_status: GetAnalysisStatus
    get_subscriber_profile: GetSubscriberProfile
    list_fraud_alerts: ListFraudAlerts
    get_model_info: GetModelInfo

    @classmethod
    def build(cls, settings: Settings | None = None) -> "Container":
        settings = settings or get_settings()
        database = Database(settings)
        calls = PostgresCallRepository(database)
        predictor = CatBoostPredictor()
        health_repository = HealthRepository(database)
        dashboard_repository = UnconfiguredDashboardRepository()
        analysis_repository = UnconfiguredAnalysisJobRepository()
        subscriber_repository = UnconfiguredSubscriberRepository()
        fraud_alert_repository = UnconfiguredFraudAlertRepository()
        return cls(
            settings=settings,
            database=database,
            check_service_health=CheckServiceHealth(health_repository, predictor),
            get_dashboard_summary=GetDashboardSummary(dashboard_repository),
            list_calls=ListCalls(calls),
            get_call=GetCall(calls),
            predict_fraud=PredictFraud(predictor, calls),
            run_analysis=RunAnalysis(analysis_repository),
            get_analysis_status=GetAnalysisStatus(analysis_repository),
            get_subscriber_profile=GetSubscriberProfile(subscriber_repository),
            list_fraud_alerts=ListFraudAlerts(fraud_alert_repository),
            get_model_info=GetModelInfo(predictor),
        )

    def close(self) -> None:
        self.database.close()

