"""
Spending Analysis schemas — Brick 11.

Read-only response shapes for app/services/spending_analysis_service.py.
There is no Create/Update schema: this brick has no writable resource,
only a computed view over existing transactions (same pattern as Brick
08's validation.py).
"""

import uuid
from datetime import date as date_type
from decimal import Decimal

from app.schemas.common import ApiBaseModel


class CategoryTotalRead(ApiBaseModel):
    category: str
    type: str
    total: Decimal
    transaction_count: int


class MonthlyTotalRead(ApiBaseModel):
    month: str
    income_total: Decimal
    expense_total: Decimal
    net: Decimal


class RecurringExpenseRead(ApiBaseModel):
    category: str
    amount: Decimal
    months: list[str]


class UnusualTransactionRead(ApiBaseModel):
    transaction_id: uuid.UUID
    category: str
    amount: Decimal
    category_average: Decimal
    transaction_date: date_type


class TrendRead(ApiBaseModel):
    status: str
    first_period_expense_total: Decimal | None
    second_period_expense_total: Decimal | None
    change_pct: Decimal | None


class SpendingAnalysisRead(ApiBaseModel):
    start_date: date_type
    end_date: date_type
    has_data: bool
    transaction_count: int
    income_total: Decimal
    expense_total: Decimal
    net: Decimal
    category_totals: list[CategoryTotalRead]
    monthly_totals: list[MonthlyTotalRead]
    recurring_expenses: list[RecurringExpenseRead]
    unusual_transactions: list[UnusualTransactionRead]
    trend: TrendRead
    analysis_version: str
