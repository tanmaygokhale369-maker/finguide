from decimal import Decimal

from app.models.financial_profile import FinancialProfile
from app.models.metric_status import MetricStatus
from app.services.metrics_service import (
    calculate_debt_to_income_ratio,
    calculate_emergency_fund_coverage_months,
    calculate_expense_to_income_ratio,
    calculate_savings_ratio,
    compute_metrics,
)


def _profile(**kwargs) -> FinancialProfile:
    """A FinancialProfile instance not bound to a session — fine for
    testing pure calculation functions that only read attributes."""
    return FinancialProfile(**kwargs)


def test_expense_to_income_ratio_computed():
    profile = _profile(monthly_income=Decimal("50000"), fixed_expenses=Decimal("15000"), variable_expenses=Decimal("10000"))
    result = calculate_expense_to_income_ratio(profile)
    assert result.status == MetricStatus.COMPUTED
    assert result.value == Decimal("0.5")


def test_savings_ratio_computed():
    profile = _profile(monthly_income=Decimal("50000"), fixed_expenses=Decimal("15000"), variable_expenses=Decimal("10000"))
    result = calculate_savings_ratio(profile)
    assert result.status == MetricStatus.COMPUTED
    assert result.value == Decimal("0.5")


def test_savings_ratio_and_expense_ratio_sum_to_one():
    profile = _profile(monthly_income=Decimal("72000"), fixed_expenses=Decimal("20000"), variable_expenses=Decimal("13000"))
    savings = calculate_savings_ratio(profile)
    expenses = calculate_expense_to_income_ratio(profile)
    assert savings.value + expenses.value == Decimal("1")


def test_debt_to_income_ratio_computed():
    profile = _profile(debt=Decimal("500000"), monthly_income=Decimal("50000"))
    result = calculate_debt_to_income_ratio(profile)
    assert result.status == MetricStatus.COMPUTED
    assert result.value == Decimal("10")  # 10 months of income


def test_emergency_fund_coverage_computed():
    profile = _profile(
        emergency_fund_amount=Decimal("75000"), fixed_expenses=Decimal("15000"), variable_expenses=Decimal("10000")
    )
    result = calculate_emergency_fund_coverage_months(profile)
    assert result.status == MetricStatus.COMPUTED
    assert result.value == Decimal("3")


def test_missing_input_is_incomplete_not_silently_zero():
    """Core data rule: a missing input must never be treated as 0."""
    profile = _profile(monthly_income=Decimal("50000"), fixed_expenses=None, variable_expenses=Decimal("10000"))
    result = calculate_expense_to_income_ratio(profile)
    assert result.status == MetricStatus.INCOMPLETE
    assert result.value is None
    assert "fixed_expenses" in result.missing_inputs


def test_all_missing_inputs_are_listed():
    profile = _profile(monthly_income=None, fixed_expenses=None, variable_expenses=None)
    result = calculate_savings_ratio(profile)
    assert result.status == MetricStatus.INCOMPLETE
    assert set(result.missing_inputs) == {"monthly_income", "fixed_expenses", "variable_expenses"}


def test_zero_income_is_not_computable_not_crash_or_infinite():
    profile = _profile(monthly_income=Decimal("0"), fixed_expenses=Decimal("5000"), variable_expenses=Decimal("1000"))
    result = calculate_expense_to_income_ratio(profile)
    assert result.status == MetricStatus.NOT_COMPUTABLE
    assert result.value is None


def test_zero_expenses_emergency_fund_is_not_computable():
    profile = _profile(emergency_fund_amount=Decimal("10000"), fixed_expenses=Decimal("0"), variable_expenses=Decimal("0"))
    result = calculate_emergency_fund_coverage_months(profile)
    assert result.status == MetricStatus.NOT_COMPUTABLE


def test_formula_and_calculation_version_are_present():
    profile = _profile(monthly_income=Decimal("50000"), fixed_expenses=Decimal("10000"), variable_expenses=Decimal("5000"))
    result = calculate_savings_ratio(profile)
    assert result.formula
    assert result.calculation_version == "v1"


def test_input_values_are_exact_string_representations_not_floats():
    """Traceability requirement: inputs must be exactly reproducible,
    which means Decimal-exact strings, never float."""
    profile = _profile(monthly_income=Decimal("50000.10"), fixed_expenses=Decimal("10000.05"), variable_expenses=Decimal("5000"))
    result = calculate_savings_ratio(profile)
    assert result.input_values["monthly_income"] == "50000.10"
    assert result.input_values["fixed_expenses"] == "10000.05"


def test_compute_metrics_returns_all_four_metrics():
    profile = _profile(
        monthly_income=Decimal("50000"),
        fixed_expenses=Decimal("15000"),
        variable_expenses=Decimal("10000"),
        debt=Decimal("100000"),
        emergency_fund_amount=Decimal("30000"),
    )
    results = compute_metrics(profile)
    names = {r.metric_name for r in results}
    assert names == {
        "expense_to_income_ratio",
        "savings_ratio",
        "debt_to_income_ratio",
        "emergency_fund_coverage_months",
    }
    assert all(r.status == MetricStatus.COMPUTED for r in results)


def test_compute_metrics_on_empty_profile_is_all_incomplete():
    profile = _profile()
    results = compute_metrics(profile)
    assert all(r.status == MetricStatus.INCOMPLETE for r in results)
    assert all(r.value is None for r in results)
