"""API Gateway Lambda for upload URLs, job status, and report retrieval."""
from __future__ import annotations

import json
import os
import re
from pathlib import PurePosixPath
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

AWS_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    endpoint_url=f"https://s3.{AWS_REGION}.amazonaws.com",
    config=Config(signature_version="s3v4"),
)
BUCKET = os.environ.get("BUCKET_NAME", "")
INCOMING_PREFIX = os.environ.get("INCOMING_PREFIX", "incoming/")
REPORTS_PREFIX = os.environ.get("REPORTS_PREFIX", "reports/")
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", str(10 * 1024 * 1024)))
JOB_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def _response(status: int, body: object) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body),
    }


def _body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise ValueError("Request body must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise ValueError("Request body must be a JSON object.")
    return value


def _job_id(event: dict) -> str:
    value = event.get("pathParameters", {}).get("job_id", "")
    if not JOB_PATTERN.fullmatch(value):
        raise ValueError("Invalid job identifier.")
    return value


def _exists(key: str) -> bool:
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
            return False
        raise


def _incoming_exists(job_id: str) -> bool:
    result = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{INCOMING_PREFIX}job-{job_id}-", MaxKeys=1)
    return bool(result.get("Contents"))


def upload_url(event: dict) -> dict:
    data = _body(event)
    filename = data.get("filename")
    content_type = data.get("content_type") or "text/csv"
    file_size = data.get("file_size")
    if not isinstance(filename, str) or not filename.lower().endswith(".csv"):
        return _response(400, {"error": "filename must end with .csv"})
    if "/" in filename or "\\" in filename or filename in {".", ".."}:
        return _response(400, {"error": "filename must be a simple file name"})
    if content_type not in {"text/csv", "application/csv", "application/vnd.ms-excel"}:
        return _response(400, {"error": "unsupported content type"})
    if not isinstance(file_size, int) or file_size <= 0 or file_size > MAX_FILE_SIZE:
        return _response(400, {"error": f"file_size must be between 1 and {MAX_FILE_SIZE} bytes"})
    job_id = uuid4().hex
    key = f"{INCOMING_PREFIX}job-{job_id}-{PurePosixPath(filename).name}"
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=600,
        HttpMethod="PUT",
    )
    return _response(200, {
        "job_id": job_id,
        "upload_url": url,
        "upload_method": "PUT",
        "upload_headers": {"Content-Type": content_type},
    })


def job_status(event: dict) -> dict:
    job_id = _job_id(event)
    report_key = f"{REPORTS_PREFIX}{job_id}.json"
    if _exists(report_key):
        try:
            report = json.loads(s3.get_object(Bucket=BUCKET, Key=report_key)["Body"].read())
            return _response(200, {"job_id": job_id, "status": report.get("status", "COMPLETED")})
        except (json.JSONDecodeError, KeyError):
            return _response(502, {"error": "Stored report is malformed."})
    return _response(200, {"job_id": job_id, "status": "PROCESSING" if _incoming_exists(job_id) else "WAITING"})


def report(event: dict) -> dict:
    job_id = _job_id(event)
    key = f"{REPORTS_PREFIX}{job_id}.json"
    try:
        result = s3.get_object(Bucket=BUCKET, Key=key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
            return _response(404, {"error": "Report is not ready."})
        raise
    try:
        data = json.loads(result["Body"].read())
    except json.JSONDecodeError:
        return _response(502, {"error": "Stored report is malformed."})
    if data.get("job_id") != job_id:
        return _response(403, {"error": "Report does not belong to this job."})
    return _response(200, data)


def lambda_handler(event: dict, _context: object) -> dict:
    method = event.get("httpMethod", "")
    path = event.get("resource", "")
    try:
        if method == "POST" and path == "/upload-url":
            return upload_url(event)
        if method == "GET" and path == "/jobs/{job_id}":
            return job_status(event)
        if method == "GET" and path == "/jobs/{job_id}/report":
            return report(event)
        return _response(404, {"error": "Route not found."})
    except ValueError as exc:
        return _response(400, {"error": str(exc)})
    except Exception:
        return _response(500, {"error": "Internal server error."})
