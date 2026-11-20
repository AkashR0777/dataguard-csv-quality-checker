import json
from unittest.mock import patch

from backend.validator_handler import lambda_handler


def test_validator_handler_rejects_malformed_event():
    try:
        lambda_handler({}, None)
    except ValueError as exc:
        assert "S3 event" in str(exc)
    else:
        raise AssertionError("Expected malformed event to fail")


@patch("backend.validator_handler.s3")
def test_validator_handler_processes_encoded_key(mock_s3):
    mock_s3.get_object.return_value = {"Body": type("Body", (), {"read": lambda self: b"employee_id,name,age,salary,email\n1,Ada,36,100,a@example.com\n"})()}
    event = {"Records": [{"s3": {"bucket": {"name": "bucket"}, "object": {"key": "incoming%2Fjob-0123456789abcdef0123456789abcdef-employees.csv"}}}]}
    result = lambda_handler(event, None)
    assert result["status"] == "COMPLETED"
    stored = mock_s3.put_object.call_args.kwargs
    assert stored["Key"] == "reports/0123456789abcdef0123456789abcdef.json"
    assert json.loads(stored["Body"])["job_id"] == "0123456789abcdef0123456789abcdef"
