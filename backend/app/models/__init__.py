"""
Import every model here so a single `import app.models` registers all
tables on Base.metadata — required for Alembic's autogenerate and for
`Base.metadata.create_all` in tests to see every table.
"""

from app.models.conversation import Conversation
from app.models.derived_metric import DerivedMetric
from app.models.extracted_field import ExtractedField
from app.models.evidence import ExternalEvidence
from app.models.feedback import ConsentRecord, EvaluationRecord, RecommendationAuditEvent, RecommendationFeedback, SafetyIncident
from app.models.financial_profile import FinancialProfile
from app.models.holding import MutualFundHolding
from app.models.holding_activity import HoldingActivity
from app.models.message import Message, MessageRole
from app.models.metric_status import MetricStatus
from app.models.recommendation import (
    Recommendation,
    RecommendationCategory,
    RecommendationRiskLevel,
    RecommendationState,
)
from app.models.transaction import Transaction, TransactionCategory, TransactionType
from app.models.user import User
from app.models.validation_status import ValidationStatus

__all__ = [
    "User",
    "FinancialProfile",
    "MutualFundHolding",
    "HoldingActivity",
    "Transaction",
    "TransactionType",
    "TransactionCategory",
    "Conversation",
    "Message",
    "MessageRole",
    "ExtractedField",
    "ValidationStatus",
    "DerivedMetric",
    "MetricStatus",
    "Recommendation",
    "RecommendationCategory",
    "RecommendationRiskLevel",
    "RecommendationState",
    "ExternalEvidence",
    "RecommendationFeedback",
    "SafetyIncident",
    "EvaluationRecord",
    "RecommendationAuditEvent",
    "ConsentRecord",
]
