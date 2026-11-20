import json
from unittest.mock import patch

from backend import api_handler


@patch.object(api_handler.s3, "generate_presigned_url", return_value="https://example.test/upload")
def test_upload_url_validates_and_returns_job(mock_url):
    event = {
        "body": json.dumps({"filename": "employees.csv", "content_type": "text/csv", "file_size": 100}),
    }
    response = api_handler.upload_url(event)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["job_id"]) == 32
    assert body["upload_url"] == "https://example.test/upload"
    mock_url.assert_called_once()


def test_upload_url_rejects_path_traversal():
    event = {"body": json.dumps({"filename": "../secrets.csv", "content_type": "text/csv", "file_size": 100})}
    assert api_handler.upload_url(event)["statusCode"] == 400


def test_invalid_job_id_is_rejected():
    response = api_handler.lambda_handler({
        "httpMethod": "GET",
        "resource": "/jobs/{job_id}",
        "pathParameters": {"job_id": "not-valid"},
    }, None)
    assert response["statusCode"] == 400
