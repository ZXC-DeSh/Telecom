from dataclasses import dataclass

from app.application.use_cases.analysis_jobs import (
    FailUnfinishedAnalysisJobs,
    GetAnalysisStatus,
    GetCurrentAnalysis,
    RunAnalysis,
)
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
from app.infrastructure.repositories.analysis_jobs import AnalysisJobRepositoryAdapter
from app.infrastructure.repositories.calls import CallRepositoryAdapter
from app.infrastructure.repositories.dashboard import DashboardRepositoryAdapter
from app.infrastructure.repositories.fraud_alerts import (
    FraudAlertRepositoryAdapter,
)
from app.infrastructure.repositories.health import (
    DatabaseReadinessRepositoryAdapter,
    ModelReadinessRepositoryAdapter,
)
from app.infrastructure.repositories.models import (
    CallRiskAssessmentRepositoryAdapter,
    CatBoostModelAdapter,
)
from app.infrastructure.repositories.subscribers import (
    SubscriberRepositoryAdapter,
)
from app.infrastructure.services.analysis_jobs import AnalysisJobService
from app.infrastructure.services.call_risk_assessments import (
    CallRiskAssessmentService,
)
from app.infrastructure.services.calls import CallService
from app.infrastructure.services.dashboard import DashboardService
from app.infrastructure.services.database_health import (
    DatabaseHealthService,
)
from app.infrastructure.services.fraud_alerts import FraudAlertService
from app.infrastructure.services.subscribers import SubscriberService


@dataclass(slots=True)
class Container:
    settings: Settings
    database: Database
    check_service_health: CheckServiceHealth
    get_dashboard_summary: GetDashboardSummary
    dashboard_repository: DashboardRepositoryAdapter
    list_calls: ListCalls
    get_call: GetCall
    predict_fraud: PredictFraud
    run_analysis: RunAnalysis
    process_analysis: ProcessAnalysis
    get_analysis_status: GetAnalysisStatus
    get_current_analysis: GetCurrentAnalysis
    fail_unfinished_analysis_jobs: FailUnfinishedAnalysisJobs
    get_subscriber_profile: GetSubscriberProfile
    list_fraud_alerts: ListFraudAlerts
    get_model_info: GetModelInfo

    @classmethod
    def build(cls, settings: Settings | None = None) -> "Container":
        settings = settings or get_settings()
        database = Database(settings)
        calls = CallRepositoryAdapter(CallService(database))
        call_assessments = CallRiskAssessmentRepositoryAdapter(
            CallRiskAssessmentService(database)
        )
        predictor = CatBoostPredictor(settings, calls)
        model_repository = CatBoostModelAdapter(predictor)
        analysis_repository = AnalysisJobRepositoryAdapter(AnalysisJobService(database))
        predict_fraud = PredictFraud(model_repository, calls, call_assessments)
        database_readiness = DatabaseReadinessRepositoryAdapter(
            DatabaseHealthService(database)
        )
        model_readiness = ModelReadinessRepositoryAdapter(predictor)
        dashboard_repository = DashboardRepositoryAdapter(DashboardService(database))
        subscriber_repository = SubscriberRepositoryAdapter(SubscriberService(database))
        fraud_alert_repository = FraudAlertRepositoryAdapter(
            FraudAlertService(database)
        )
        return cls(
            settings=settings,
            database=database,
            check_service_health=CheckServiceHealth(
                database=database_readiness,
                model=model_readiness,
            ),
            get_dashboard_summary=GetDashboardSummary(dashboard_repository),
            dashboard_repository=dashboard_repository,
            list_calls=ListCalls(calls),
            get_call=GetCall(calls),
            predict_fraud=predict_fraud,
            run_analysis=RunAnalysis(analysis_repository),
            process_analysis=ProcessAnalysis(
                analysis_repository, calls, predict_fraud, dashboard_repository
            ),
            get_analysis_status=GetAnalysisStatus(analysis_repository),
            get_current_analysis=GetCurrentAnalysis(analysis_repository),
            fail_unfinished_analysis_jobs=FailUnfinishedAnalysisJobs(
                analysis_repository
            ),
            get_subscriber_profile=GetSubscriberProfile(subscriber_repository),
            list_fraud_alerts=ListFraudAlerts(fraud_alert_repository),
            get_model_info=GetModelInfo(model_repository),
        )

    def close(self) -> None:
        self.database.close()
