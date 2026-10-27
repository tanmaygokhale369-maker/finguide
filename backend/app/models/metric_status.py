"""
MetricStatus — outcome of attempting to compute one derived metric.

Distinct from ValidationStatus (Brick 08), which describes extracted
chat data. This describes a calculation attempt against FinancialProfile
fields, which are user-confirmed rather than extracted/inferred.
"""

import enum


class MetricStatus(str, enum.Enum):
    COMPUTED = "COMPUTED"
    INCOMPLETE = "INCOMPLETE"  # one or more required inputs are missing (NULL)
    NOT_COMPUTABLE = "NOT_COMPUTABLE"  # inputs present but the formula is undefined (e.g. divide by zero)
