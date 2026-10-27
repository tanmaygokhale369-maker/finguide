"""
Financial Calculation Engine.

Brick 09 scope: deterministic derived metrics computed from a user's
FinancialProfile — never by an LLM, per Architecture v1.1 LOCK. Every
metric is computed in application code and persisted with its
full traceability chain: Input Data -> Formula -> Calculation Version ->
Result -> Timestamp.

Metrics implemented (from the plan's "Possible derived metrics" list):
- expense_to_income_ratio
- savings_ratio
- debt_to_income_ratio
- emergency_fund_coverage_months

"Liquidity indicators" from the same list is intentionally NOT
implemented here — the docs don't define what it means (unlike the
other four, which have standard, unambiguous formulas), and inventing a
formula for an unspecified metric would violate the "do not invent
requirements" rule. It can be added once a concrete definition exists.

Note on debt_to_income_ratio: this uses total debt BALANCE divided by
monthly income (expressed as "months of income"), not the
industry-standard monthly-PAYMENT-based DTI — FinancialProfile only
captures a debt balance, not a monthly payment amount. This is a
deliberate, documented limitation, not a silent approximation.

Reads from FinancialProfile only (Brick 05's explicit, user-confirmed
source of truth) — never from raw chat-extracted data (Brick 07/08),
which requires its own separate, explicit path into the profile that
does not exist yet. This keeps the "nothing writes to FinancialProfile
except the explicit profile API" invariant intact.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, DivisionByZero, InvalidOperation

from sqlalchemy.orm import Session

from app.models.derived_metric import DerivedMetric
from app.models.financial_profile import FinancialProfile
from app.models.metric_status import MetricStatus

CALCULATION_VERSION = "v1"


@dataclass(frozen=True)
class MetricResult:
    metric_name: str
    status: MetricStatus
    value: Decimal | None
    formula: str
    input_values: dict[str, str]  # Decimal -> str for exact, JSON-safe representation
    missing_inputs: list[str]
    calculation_version: str = CALCULATION_VERSION


def _safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    try:
        return numerator / denominator
    except (DivisionByZero, InvalidOperation, ZeroDivisionError):
        return None


def _require(profile: FinancialProfile, *field_names: str) -> tuple[dict[str, Decimal | None], list[str]]:
    values = {name: getattr(profile, name) for name in field_names}
    missing = [name for name, value in values.items() if value is None]
    return values, missing


def _input_strings(values: dict[str, Decimal | None]) -> dict[str, str]:
    return {name: (str(value) if value is not None else "null") for name, value in values.items()}


def calculate_expense_to_income_ratio(profile: FinancialProfile) -> MetricResult:
    formula = "(fixed_expenses + variable_expenses) / monthly_income"
    values, missing = _require(profile, "fixed_expenses", "variable_expenses", "monthly_income")

    if missing:
        return MetricResult("expense_to_income_ratio", MetricStatus.INCOMPLETE, None, formula, _input_strings(values), missing)

    total_expenses = values["fixed_expenses"] + values["variable_expenses"]
    ratio = _safe_divide(total_expenses, values["monthly_income"])
    if ratio is None:
        return MetricResult(
            "expense_to_income_ratio", MetricStatus.NOT_COMPUTABLE, None, formula, _input_strings(values), []
        )
    return MetricResult("expense_to_income_ratio", MetricStatus.COMPUTED, ratio, formula, _input_strings(values), [])


def calculate_savings_ratio(profile: FinancialProfile) -> MetricResult:
    formula = "(monthly_income - fixed_expenses - variable_expenses) / monthly_income"
    values, missing = _require(profile, "monthly_income", "fixed_expenses", "variable_expenses")

    if missing:
        return MetricResult("savings_ratio", MetricStatus.INCOMPLETE, None, formula, _input_strings(values), missing)

    net = values["monthly_income"] - values["fixed_expenses"] - values["variable_expenses"]
    ratio = _safe_divide(net, values["monthly_income"])
    if ratio is None:
        return MetricResult("savings_ratio", MetricStatus.NOT_COMPUTABLE, None, formula, _input_strings(values), [])
    return MetricResult("savings_ratio", MetricStatus.COMPUTED, ratio, formula, _input_strings(values), [])


def calculate_debt_to_income_ratio(profile: FinancialProfile) -> MetricResult:
    formula = "debt / monthly_income  (total debt balance, expressed in months of income — not a payment-based DTI)"
    values, missing = _require(profile, "debt", "monthly_income")

    if missing:
        return MetricResult("debt_to_income_ratio", MetricStatus.INCOMPLETE, None, formula, _input_strings(values), missing)

    ratio = _safe_divide(values["debt"], values["monthly_income"])
    if ratio is None:
        return MetricResult(
            "debt_to_income_ratio", MetricStatus.NOT_COMPUTABLE, None, formula, _input_strings(values), []
        )
    return MetricResult("debt_to_income_ratio", MetricStatus.COMPUTED, ratio, formula, _input_strings(values), [])


def calculate_emergency_fund_coverage_months(profile: FinancialProfile) -> MetricResult:
    formula = "emergency_fund_amount / (fixed_expenses + variable_expenses)"
    values, missing = _require(profile, "emergency_fund_amount", "fixed_expenses", "variable_expenses")

    if missing:
        return MetricResult(
            "emergency_fund_coverage_months", MetricStatus.INCOMPLETE, None, formula, _input_strings(values), missing
        )

    total_expenses = values["fixed_expenses"] + values["variable_expenses"]
    months = _safe_divide(values["emergency_fund_amount"], total_expenses)
    if months is None:
        return MetricResult(
            "emergency_fund_coverage_months", MetricStatus.NOT_COMPUTABLE, None, formula, _input_strings(values), []
        )
    return MetricResult(
        "emergency_fund_coverage_months", MetricStatus.COMPUTED, months, formula, _input_strings(values), []
    )


METRIC_CALCULATORS = [
    calculate_expense_to_income_ratio,
    calculate_savings_ratio,
    calculate_debt_to_income_ratio,
    calculate_emergency_fund_coverage_months,
]


def compute_metrics(profile: FinancialProfile) -> list[MetricResult]:
    """Pure computation, no DB writes — used directly by tests and by
    compute_and_store_metrics below."""
    return [calculator(profile) for calculator in METRIC_CALCULATORS]


def compute_and_store_metrics(db: Session, profile: FinancialProfile) -> tuple[uuid.UUID, list[DerivedMetric]]:
    """
    Computes every metric fresh from the profile's current state and
    persists one immutable DerivedMetric row per metric, all sharing a
    new computation_id. Rows are never updated — this is what "profile
    versioning" means here: the full history of what these metrics
    looked like at any point in time is preserved, even as the
    underlying FinancialProfile continues to change.
    """
    computation_id = uuid.uuid4()
    results = compute_metrics(profile)

    rows = []
    for result in results:
        row = DerivedMetric(
            user_id=profile.user_id,
            financial_profile_id=profile.id,
            computation_id=computation_id,
            metric_name=result.metric_name,
            status=result.status,
            value=result.value,
            formula=result.formula,
            input_values=result.input_values,
            missing_inputs=result.missing_inputs,
            calculation_version=result.calculation_version,
        )
        db.add(row)
        rows.append(row)

    db.commit()
    for row in rows:
        db.refresh(row)
    return computation_id, rows


def get_latest_computation(db: Session, user_id: uuid.UUID) -> tuple[uuid.UUID, list[DerivedMetric]] | None:
    latest = (
        db.query(DerivedMetric)
        .filter(DerivedMetric.user_id == user_id)
        .order_by(DerivedMetric.created_at.desc())
        .first()
    )
    if latest is None:
        return None
    rows = (
        db.query(DerivedMetric)
        .filter(DerivedMetric.user_id == user_id, DerivedMetric.computation_id == latest.computation_id)
        .all()
    )
    return latest.computation_id, rows


def list_computation_history(db: Session, user_id: uuid.UUID) -> list[tuple[uuid.UUID, datetime]]:
    """Returns (computation_id, calculated_at) for every past computation,
    most recent first — one row per computation, not per metric."""
    rows = (
        db.query(DerivedMetric.computation_id, DerivedMetric.created_at)
        .filter(DerivedMetric.user_id == user_id)
        .distinct(DerivedMetric.computation_id)
        .order_by(DerivedMetric.computation_id, DerivedMetric.created_at.desc())
        .all()
    )
    # `distinct(col)` in Postgres requires the distinct column to lead
    # ORDER BY, which prevents ordering by created_at directly — sort in
    # Python instead for a clean, most-recent-first list.
    return sorted(rows, key=lambda r: r[1], reverse=True)


def get_computation_by_id(db: Session, user_id: uuid.UUID, computation_id: uuid.UUID) -> list[DerivedMetric]:
    return (
        db.query(DerivedMetric)
        .filter(DerivedMetric.user_id == user_id, DerivedMetric.computation_id == computation_id)
        .all()
    )
