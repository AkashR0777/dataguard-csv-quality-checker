from backend.report_builder import build_report


def test_report_builder_adds_job_metadata():
    report = build_report(file_name="employees.csv", job_id="abc", validation={"status": "COMPLETED"})
    assert report["job_id"] == "abc"
    assert report["file_name"] == "employees.csv"
    assert report["processing_id"]
