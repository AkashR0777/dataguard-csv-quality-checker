"""S3-triggered Lambda that validates incoming CSV files and writes reports."""
from __future__ import annotations

import json
import logging
import os
from pathlib import PurePosixPath
from urllib.parse import unquote_plus

import boto3

from backend.config import EMPLOYEE_SCHEMA
from backend.report_builder import build_report
from backend.validator import validate_csv

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3 = boto3.client("s3")
sns = boto3.client("sns")


def _event_object(event: dict) -> tuple[str, str]:
    records = event.get("Records")
    if not isinstance(records, list) or not records:
        raise ValueError("S3 event must contain at least one record.")
    record = records[0]
    bucket = record.get("s3", {}).get("bucket", {}).get("name")
    encoded_key = record.get("s3", {}).get("object", {}).get("key")
    if not bucket or not encoded_key:
        raise ValueError("S3 event is missing bucket or object key.")
    return bucket, unquote_plus(encoded_key)


def _job_id_from_key(key: str) -> str:
    name = PurePosixPath(key).name
    if not name.startswith("job-") or "-" not in name:
        raise ValueError("Incoming object key does not contain a valid job identifier.")
    return name.split("-", 2)[1]


def lambda_handler(event: dict, _context: object) -> dict:
    bucket, key = _event_object(event)
    if not key.startswith(os.environ.get("INCOMING_PREFIX", "incoming/")):
        logger.info("Ignoring object outside incoming prefix.")
        return {"ignored": True}
    job_id = _job_id_from_key(key)
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8-sig")
        validation = validate_csv(content, EMPLOYEE_SCHEMA)
        file_name = PurePosixPath(key).name.split("-", 2)[-1]
        report = build_report(file_name=file_name, job_id=job_id, validation=validation)
    except Exception as exc:
        logger.exception("CSV processing failed for job %s", job_id)
        report = {
            "job_id": job_id,
            "file_name": PurePosixPath(key).name.split("-", 2)[-1],
            "status": "FAILED",
            "error": str(exc),
            "issues": [],
        }
    report_key = f"{os.environ.get('REPORTS_PREFIX', 'reports/')}{job_id}.json"
    s3.put_object(
        Bucket=bucket,
        Key=report_key,
        Body=json.dumps(report, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    topic_arn = os.environ.get("SNS_TOPIC_ARN")
    if topic_arn:
        summary = (
            f"DataGuard report\n\n"
            f"File: {report.get('file_name', '')}\n"
            f"Job ID: {job_id}\n"
            f"Status: {report['status']}\n"
            f"Quality score: {report.get('quality_score', 'N/A')}\n"
            f"Total rows: {report.get('total_rows', 'N/A')}\n"
            f"Valid rows: {report.get('valid_rows', 'N/A')}\n"
            f"Invalid rows: {report.get('invalid_rows', 'N/A')}\n"
            f"Missing values: {report.get('missing_values', 'N/A')}\n"
            f"Duplicate rows: {report.get('duplicate_rows', 'N/A')}\n"
            f"Invalid values: {report.get('invalid_values', 'N/A')}\n\n"
            "The detailed JSON report is stored in the configured S3 reports prefix."
        )
        sns.publish(
            TopicArn=topic_arn,
            Subject=f"DataGuard report: {report.get('status', 'UNKNOWN')}",
            Message=summary,
        )
    logger.info("Stored report for job %s", job_id)
    return {"job_id": job_id, "status": report["status"]}
