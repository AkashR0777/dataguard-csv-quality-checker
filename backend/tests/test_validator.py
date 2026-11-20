from backend.config import EMPLOYEE_SCHEMA
from backend.validator import validate_csv


def test_valid_csv_has_no_issues():
    report = validate_csv("employee_id,name,age,salary,email\n1,Ada,36,100,ada@example.com\n", EMPLOYEE_SCHEMA)
    assert report["status"] == "COMPLETED"
    assert report["quality_score"] == 100


def test_missing_invalid_and_duplicate_values_are_reported():
    content = "employee_id,name,age,salary,email\n1,,36,100,a@example.com\n2,Grace,37,-2,g@example.com\n2,Grace,37,-2,g@example.com\n"
    report = validate_csv(content, EMPLOYEE_SCHEMA)
    types = {issue["issue_type"] for issue in report["issues"]}
    assert {"MISSING_VALUE", "INVALID_VALUE", "DUPLICATE_ROW"} <= types


def test_missing_column_is_reported():
    report = validate_csv("employee_id,name\n1,Ada\n", EMPLOYEE_SCHEMA)
    assert "salary" in report["missing_columns"]
    assert any(issue["issue_type"] == "MISSING_COLUMN" for issue in report["issues"])


def test_empty_csv_is_rejected():
    try:
        validate_csv("  ", EMPLOYEE_SCHEMA)
    except ValueError as exc:
        assert "empty" in str(exc).lower()
    else:
        raise AssertionError("Expected empty CSV to be rejected")
