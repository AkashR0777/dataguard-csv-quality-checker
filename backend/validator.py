
"""Pure-Python CSV validation engine used locally and by the validator Lambda."""
from __future__ import annotations

import csv
import io
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any


def _issue(
    row: int,
    column: str,
    issue_type: str,
    value: Any,
    description: str,
) -> dict[str, Any]:
    return {
        "row": row,
        "column": column,
        "issue_type": issue_type,
        "value": value,
        "description": description,
    }


def validate_csv(
    content: str,
    schema: dict[str, dict[str, Any]],
) -> dict[str, Any]:

    if not content.strip():
        raise ValueError("CSV file is empty.")

    try:
        reader = csv.DictReader(io.StringIO(content, newline=""))
        columns = reader.fieldnames

        if not columns or any(
            column is None or not column.strip()
            for column in columns
        ):
            raise ValueError("CSV header is missing or malformed.")

        if len(columns) != len(set(columns)):
            raise ValueError("CSV contains duplicate column names.")

        rows = list(reader)

    except csv.Error as exc:
        raise ValueError(f"Malformed CSV: {exc}") from exc

    expected = set(schema)
    actual = set(columns)
    issues: list[dict[str, Any]] = []

    for column in sorted(expected - actual):
        issues.append(
            _issue(
                1, column, "MISSING_COLUMN", None,
                f"Required column '{column}' is missing.",
            )
        )

    for column in sorted(actual - expected):
        issues.append(
            _issue(
                1, column, "UNEXPECTED_COLUMN", None,
                f"Column '{column}' is not part of the configured schema.",
            )
        )

    seen_rows: set[tuple[str, ...]] = set()
    seen_employee_ids: set[str] = set()

    for index, row in enumerate(rows, start=2):

        signature = tuple(
            (row.get(column) or "").strip()
            for column in columns
        )

        if signature in seen_rows:
            issues.append(
                _issue(
                    index, "", "DUPLICATE_ROW", None,
                    "Duplicate of an earlier data row.",
                )
            )

        seen_rows.add(signature)

        for column, rule in schema.items():

            if column not in actual:
                continue

            value = (row.get(column) or "").strip()

            if not value:
                if rule.get("required"):
                    issues.append(
                        _issue(
                            index, column, "MISSING_VALUE", None,
                            f"{column} is required but is missing.",
                        )
                    )
                continue

            kind = rule.get("type")
            valid = True
            description = f"Expected {kind} value."

            if kind == "integer":
                valid = bool(re.fullmatch(r"[+-]?\d+", value))

                if valid and rule.get("positive"):
                    valid = int(value) > 0
                    description = "Value should be a positive integer."

            elif kind == "decimal":
                try:
                    number = Decimal(value)
                    valid = number.is_finite()

                    if valid and rule.get("positive"):
                        valid = number > 0

                    description = "Value should be a positive number."

                except InvalidOperation:
                    valid = False

            elif kind == "boolean":
                valid = value.lower() in {
                    "true", "false", "yes", "no", "1", "0"
                }

            elif kind == "email":
                valid = bool(
                    re.fullmatch(
                        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                        value,
                    )
                )
                description = "Invalid email address format."

            if not valid:
                issues.append(
                    _issue(
                        index, column, "INVALID_VALUE", value,
                        description,
                    )
                )

        # Detect repeated employee IDs, even when other columns differ.
        employee_id = (row.get("employee_id") or "").strip()

        if employee_id and "employee_id" in actual:
            if employee_id in seen_employee_ids:
                issues.append(
                    _issue(
                        index, "employee_id", "DUPLICATE_VALUE",
                        employee_id,
                        "Employee ID is already used by an earlier row.",
                    )
                )

            seen_employee_ids.add(employee_id)

    duplicate_rows = sum(
        1 for issue in issues
        if issue["issue_type"] in {"DUPLICATE_ROW", "DUPLICATE_VALUE"}
    )

    missing_values = sum(
        1 for issue in issues
        if issue["issue_type"] == "MISSING_VALUE"
    )

    invalid_values = sum(
        1 for issue in issues
        if issue["issue_type"] == "INVALID_VALUE"
    )

    invalid_row_numbers = {
        issue["row"]
        for issue in issues
        if issue["row"] > 1
        and issue["issue_type"] in {
            "MISSING_VALUE",
            "INVALID_VALUE",
            "DUPLICATE_ROW",
            "DUPLICATE_VALUE",
        }
    }

    score = (
        round(max(0, 100 - (
            len(invalid_row_numbers) / len(rows) * 100
        )))
        if rows else 0
    )

    return {
        "status": "ISSUES_FOUND" if issues else "COMPLETED",
        "total_rows": len(rows),
        "valid_rows": len(rows) - len(invalid_row_numbers),
        "invalid_rows": len(invalid_row_numbers),
        "duplicate_rows": duplicate_rows,
        "missing_values": missing_values,
        "invalid_values": invalid_values,
        "missing_columns": sorted(expected - actual),
        "unexpected_columns": sorted(actual - expected),
        "quality_score": score,
        "issues": issues,
    }
