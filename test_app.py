"""Tests for the MarkItDown GUI Flask backend."""

import io
import time

import pytest

import app as app_module


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def _wait_for_job(client, job_id, timeout=15):
    """Poll /status until the async job leaves the 'running' state."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/status/{job_id}")
        data = resp.get_json()
        if data.get("status") != "running":
            return data
        time.sleep(0.1)
    raise AssertionError("job did not finish in time")


def test_convert_file_returns_job_and_completes(client):
    data = {"file": (io.BytesIO(b"col1,col2\n1,2\n3,4\n"), "sample.csv")}
    resp = client.post("/convert", data=data, content_type="multipart/form-data")
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]

    result = _wait_for_job(client, job_id)
    assert result["status"] == "done"
    assert result["markdown"].strip() != ""


def test_convert_url_returns_job_id(client):
    resp = client.post("/convert", json={"url": "https://example.com"})
    assert resp.status_code == 202
    assert "job_id" in resp.get_json()


def test_convert_no_input_returns_400(client):
    resp = client.post("/convert", data={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_status_unknown_job_returns_404(client):
    resp = client.get("/status/does-not-exist")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "unknown job"


def test_bad_file_ends_in_error_not_500(client):
    # A bogus extension with unmatchable garbage bytes should fail conversion
    # gracefully (status="error", never a crash). These bytes match no converter,
    # so MarkItDown raises UnsupportedFormatException almost instantly — which,
    # crucially, subclasses BaseException, so this also guards the worker's
    # BaseException handling.
    data = {"file": (io.BytesIO(b"\x00\x01garbage notreal"), "broken.xyzzy")}
    resp = client.post("/convert", data=data, content_type="multipart/form-data")
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]

    result = _wait_for_job(client, job_id)
    assert result["status"] == "error"
    assert "error" in result
