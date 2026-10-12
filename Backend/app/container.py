from dataclasses import dataclass

from app.application.use_cases.analysis_jobs import GetAnalysisStatus, RunAnalysis
from app.application.use_cases.check_service_health import CheckServiceHealth
from app.application.use_cases.get_call import GetCall
from app.application.use_cases.get_dashboard_summary import GetDashboardSummary
from app.application.use_cases.get_model_info import GetModelInfo
from app.application.use_cases.get_subscriber_profile import GetSubscriberProfile
from app.application.use_cases.list_calls import ListCalls
from app.application.use_cases.list_fraud_alerts import ListFraudAlerts
from app.application.use_cases.predict_fraud import PredictFraud
from app.application.use_cases.process_analysis import ProcessAnalysis
from app.core.config import Settings, get_settings
from app.infrastructure.database.connection import Database
from app.infrastructure.ml.catboost_predictor import CatBoostPredictor
from app.infrastructure.repositories.analysis_jobs import PostgresAnalysisJobRepository
from app.infrastructure.repositories.calls import PostgresCallRepository
from app.infrastructure.repositories.dashboard import InfrastructureDashboardRepository
from app.infrastructure.repositories.fraud_alerts import (
    InfrastructureFraudAlertRepository,
)
from app.infrastructure.repositories.health import (
    DatabaseHealthRepository,
    ModelHealthRepository,
)
from app.infrastructure.repositories.models import (
    CatBoostRepository,
    PostgresCallRiskAssessmentRepository,
)
from app.infrastructure.repositories.subscribers import (
    InfrastructureSubscriberRepository,
)
from app.infrastructure.services.analysis_job_service import PostgresAnalysisJobService
from app.infrastructure.services.call_risk_assessment_service import (
    PostgresCallRiskAssessmentService,
)
from app.infrastructure.services.call_service import PostgresCallService
from app.infrastructure.services.dashboard_service import UnconfiguredDashboardService
from app.infrastructure.services.database_health_service import (
    PostgresDatabaseHealthService,
)
from app.infrastructure.services.fraud_alert_service import (
    UnconfiguredFraudAlertService,
)
from app.infrastructure.services.subscriber_service import UnconfiguredSubscriberService


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
    process_analysis: ProcessAnalysis
    get_analysis_status: GetAnalysisStatus
    get_subscriber_profile: GetSubscriberProfile
    list_fraud_alerts: ListFraudAlerts
    get_model_info: GetModelInfo

    @classmethod
    def build(cls, settings: Settings | None = None) -> "Container":
        settings = settings or get_settings()
        database = Database(settings)
        calls = PostgresCallRepository(PostgresCallService(database))
        call_assessments = PostgresCallRiskAssessmentRepository(
            PostgresCallRiskAssessmentService(database)
        )
        predictor = CatBoostPredictor(settings, calls)
        model_repository = CatBoostRepository(predictor)
        analysis_repository = PostgresAnalysisJobRepository(
            PostgresAnalysisJobService(database)
        )
        predict_fraud = PredictFraud(model_repository, calls, call_assessments)
        database_readiness = DatabaseHealthRepository(
            PostgresDatabaseHealthService(database)
        )
        model_readiness = ModelHealthRepository(predictor)
        dashboard_repository = InfrastructureDashboardRepository(
            UnconfiguredDashboardService()
        )
        subscriber_repository = InfrastructureSubscriberRepository(
            UnconfiguredSubscriberService()
        )
        fraud_alert_repository = InfrastructureFraudAlertRepository(
            UnconfiguredFraudAlertService()
        )
        return cls(
            settings=settings,
            database=database,
            check_service_health=CheckServiceHealth(
                database=database_readiness,
                model=model_readiness,
            ),
            get_dashboard_summary=GetDashboardSummary(dashboard_repository),
            list_calls=ListCalls(calls),
            get_call=GetCall(calls),
            predict_fraud=predict_fraud,
            run_analysis=RunAnalysis(analysis_repository),
            process_analysis=ProcessAnalysis(
                analysis_repository, calls, predict_fraud
            ),
            get_analysis_status=GetAnalysisStatus(analysis_repository),
            get_subscriber_profile=GetSubscriberProfile(subscriber_repository),
            list_fraud_alerts=ListFraudAlerts(fraud_alert_repository),
            get_model_info=GetModelInfo(model_repository),
        )

    def close(self) -> None:
        self.database.close()

