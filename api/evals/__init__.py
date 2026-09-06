"""Eval package: golden dataset + bootstrap helpers.

Importing from this package is the canonical way to access the eval cases::

    from evals.golden_dataset import CASES, EvalCase

Both the cases list and the pydantic model are re-exported here for
convenience.
"""

from evals.golden_dataset import CASES, EvalCase

__all__ = ["CASES", "EvalCase"]
