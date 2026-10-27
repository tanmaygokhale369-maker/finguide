"""
Spending Analysis service.

Brick 11 scope: deterministic, read-only analysis over a user's existing
Transaction rows (Brick 10). No AI/LLM involvement, no writes, no new
table — every call recomputes fresh from `transactions`, so there is
nothing to go stale and nothing extra to keep reproducible beyond the
transactions themselves (Transaction rows are immutable-by-id: a PATCH
changes a row in place, so a past analysis is not "replayable" the way
Brick 09's metric history is — that guarantee is out of scope here and
not claimed).

Per Architecture v1.1 LOCK: "Patterns are observations, not automatic
financial advice." Nothing in this module produces a
recommendation, a suggestion, or advice text — only labeled numbers.
Turning these observations into recommendations is Brick 12's job, and
must go through the full Safety & Suitability gate (Brick 13) before
reaching a user.

Date ranges are always explicit and required (never defaulted) — see
the API layer, which rejects a request with no start_date/end_date
rather than silently picking "this month" or "all time".

Heuristics below (recurring-expense and unusual-spending detection) are
not specified anywhere in the docs. As with Brick 10's category
taxonomy, these are reasonable, clearly-documented starter
definitions — not a claimed standard — and are easy to change later.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date as date_type
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionCategory, TransactionType

ANALYSIS_VERSION = "v1"

# A category is "recurring" when the same category shows the same exact
# amount in at least this many distinct months within the requested range.
# Exact-amount match (not "similar") is a deliberate, documented choice —
# it avoids guessing a similarity threshold that isn't specified anywhere.
RECURRING_MIN_MONTHS = 2

# A transaction is "unusual" when its amount exceeds this multiple of its
# category's mean amount within the requested range, and the category has
# enough history to make a mean meaningful.
UNUSUAL_DEVIATION_MULTIPLIER = Decimal("2")
UNUSUAL_MIN_CATEGORY_SAMPLES = 3

# Trend detection splits the date range into two equal-length halves and
# compares total expenses between them. A change smaller than this
# percentage is reported as STABLE rather than a direction, to avoid
# reporting noise as a trend.
TREND_STABLE_BAND_PCT = Decimal("5")


def _q(value: Decimal) -> Decimal:
    """Round to 2 decimal places, matching the Numeric(14, 2) money columns."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CategoryTotal:
    category: TransactionCategory
    type: TransactionType
    total: Decimal
    transaction_count: int


@dataclass(frozen=True)
class MonthlyTotal:
    month: str  # "YYYY-MM"
    income_total: Decimal
    expense_total: Decimal
    net: Decimal


@dataclass(frozen=True)
class RecurringExpense:
    category: TransactionCategory
    amount: Decimal
    months: list[str]


@dataclass(frozen=True)
class UnusualTransaction:
    transaction_id: uuid.UUID
    category: TransactionCategory
    amount: Decimal
    category_average: Decimal
    transaction_date: date_type


@dataclass(frozen=True)
class Trend:
    status: str  # INCREASING | DECREASING | STABLE | INSUFFICIENT_DATA
    first_period_expense_total: Decimal | None
    second_period_expense_total: Decimal | None
    change_pct: Decimal | None


@dataclass(frozen=True)
class SpendingAnalysis:
    start_date: date_type
    end_date: date_type
    has_data: bool
    transaction_count: int
    income_total: Decimal
    expense_total: Decimal
    net: Decimal
    category_totals: list[CategoryTotal]
    monthly_totals: list[MonthlyTotal]
    recurring_expenses: list[RecurringExpense]
    unusual_transactions: list[UnusualTransaction]
    trend: Trend
    analysis_version: str = ANALYSIS_VERSION


def _month_key(d: date_type) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def analyze_spending(
    db: Session,
    user_id: uuid.UUID,
    start_date: date_type,
    end_date: date_type,
) -> SpendingAnalysis:
    if end_date < start_date:
        raise ValueError("end_date cannot be before start_date")

    transactions: list[Transaction] = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
        )
        .order_by(Transaction.transaction_date.asc())
        .all()
    )

    if not transactions:
        return SpendingAnalysis(
            start_date=start_date,
            end_date=end_date,
            has_data=False,
            transaction_count=0,
            income_total=Decimal("0.00"),
            expense_total=Decimal("0.00"),
            net=Decimal("0.00"),
            category_totals=[],
            monthly_totals=[],
            recurring_expenses=[],
            unusual_transactions=[],
            trend=Trend(
                status="INSUFFICIENT_DATA",
                first_period_expense_total=None,
                second_period_expense_total=None,
                change_pct=None,
            ),
        )

    income_total = Decimal("0.00")
    expense_total = Decimal("0.00")

    category_sums: dict[tuple[TransactionCategory, TransactionType], Decimal] = defaultdict(lambda: Decimal("0"))
    category_counts: dict[tuple[TransactionCategory, TransactionType], int] = defaultdict(int)

    month_income: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    month_expense: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    # category -> amount -> set of months it occurred in (for recurring detection)
    category_amount_months: dict[TransactionCategory, dict[Decimal, set[str]]] = defaultdict(lambda: defaultdict(set))

    # category -> list of expense transactions (for unusual-spending detection)
    expense_by_category: dict[TransactionCategory, list[Transaction]] = defaultdict(list)

    for t in transactions:
        key = (t.category, t.type)
        category_sums[key] += t.amount
        category_counts[key] += 1

        month = _month_key(t.transaction_date)
        if t.type == TransactionType.INCOME:
            income_total += t.amount
            month_income[month] += t.amount
        else:
            expense_total += t.amount
            month_expense[month] += t.amount
            category_amount_months[t.category][t.amount].add(month)
            expense_by_category[t.category].append(t)

    category_totals = [
        CategoryTotal(category=cat, type=typ, total=_q(total), transaction_count=category_counts[(cat, typ)])
        for (cat, typ), total in sorted(category_sums.items(), key=lambda kv: (kv[0][1].value, kv[0][0].value))
    ]

    all_months = sorted(set(month_income) | set(month_expense))
    monthly_totals = [
        MonthlyTotal(
            month=m,
            income_total=_q(month_income[m]),
            expense_total=_q(month_expense[m]),
            net=_q(month_income[m] - month_expense[m]),
        )
        for m in all_months
    ]

    recurring_expenses = [
        RecurringExpense(category=cat, amount=_q(amount), months=sorted(months))
        for cat, amounts in category_amount_months.items()
        for amount, months in amounts.items()
        if len(months) >= RECURRING_MIN_MONTHS
    ]
    recurring_expenses.sort(key=lambda r: (r.category.value, r.amount))

    unusual_transactions: list[UnusualTransaction] = []
    for cat, txns in expense_by_category.items():
        if len(txns) < UNUSUAL_MIN_CATEGORY_SAMPLES:
            continue
        category_avg = sum((t.amount for t in txns), Decimal("0")) / len(txns)
        threshold = category_avg * UNUSUAL_DEVIATION_MULTIPLIER
        for t in txns:
            if t.amount > threshold:
                unusual_transactions.append(
                    UnusualTransaction(
                        transaction_id=t.id,
                        category=cat,
                        amount=_q(t.amount),
                        category_average=_q(category_avg),
                        transaction_date=t.transaction_date,
                    )
                )
    unusual_transactions.sort(key=lambda u: u.transaction_date)

    trend = _compute_trend(start_date, end_date, transactions)

    return SpendingAnalysis(
        start_date=start_date,
        end_date=end_date,
        has_data=True,
        transaction_count=len(transactions),
        income_total=_q(income_total),
        expense_total=_q(expense_total),
        net=_q(income_total - expense_total),
        category_totals=category_totals,
        monthly_totals=monthly_totals,
        recurring_expenses=recurring_expenses,
        unusual_transactions=unusual_transactions,
        trend=trend,
    )


def _compute_trend(start_date: date_type, end_date: date_type, transactions: list[Transaction]) -> Trend:
    span_days = (end_date - start_date).days
    # A trend needs two distinguishable halves; a single-day or very short
    # range can't be split meaningfully.
    if span_days < 1:
        return Trend(status="INSUFFICIENT_DATA", first_period_expense_total=None, second_period_expense_total=None, change_pct=None)

    midpoint_ordinal = start_date.toordinal() + span_days // 2
    midpoint = date_type.fromordinal(midpoint_ordinal)

    first_total = Decimal("0")
    second_total = Decimal("0")
    for t in transactions:
        if t.type != TransactionType.EXPENSE:
            continue
        if t.transaction_date <= midpoint:
            first_total += t.amount
        else:
            second_total += t.amount

    if first_total == 0 and second_total == 0:
        return Trend(status="INSUFFICIENT_DATA", first_period_expense_total=_q(first_total), second_period_expense_total=_q(second_total), change_pct=None)

    if first_total == 0:
        # Any spending appearing from nothing is an increase, but a
        # percentage change is undefined (division by zero) — report the
        # direction without a fabricated percentage.
        return Trend(status="INCREASING", first_period_expense_total=_q(first_total), second_period_expense_total=_q(second_total), change_pct=None)

    change_pct = ((second_total - first_total) / first_total) * Decimal("100")
    change_pct_q = change_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if abs(change_pct) <= TREND_STABLE_BAND_PCT:
        status = "STABLE"
    elif change_pct > 0:
        status = "INCREASING"
    else:
        status = "DECREASING"

    return Trend(
        status=status,
        first_period_expense_total=_q(first_total),
        second_period_expense_total=_q(second_total),
        change_pct=change_pct_q,
    )
