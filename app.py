"""MarkItDown GUI — a minimal local Flask web app for converting files to Markdown.

Conversion runs in a background thread so large files never freeze the browser.
Job state lives in an in-memory dict keyed by a generated job_id. No database,
no sessions, no persistence beyond a transient temp file per upload.
"""

import os
import tempfile
import threading
import uuid

from flask import Flask, jsonify, render_template, request
from markitdown import MarkItDown

app = Flask(__name__)
# No upload size cap — conversion is async, so large files don't block the page.
app.config["MAX_CONTENT_LENGTH"] = None

# job_id -> {"status": "running"|"done"|"error", "markdown"?: str, "error"?: str}
_jobs = {}
_jobs_lock = threading.Lock()


def _set_job(job_id, **fields):
    with _jobs_lock:
        _jobs[job_id] = fields


def _get_job(job_id):
    with _jobs_lock:
        return _jobs.get(job_id)


def _extract_markdown(result):
    """MarkItDown's result attribute name varies across versions."""
    return getattr(result, "markdown", None) or getattr(result, "text_content", "")


def _convert_worker(job_id, source, temp_path=None):
    """Run the conversion off the request thread, then store the result."""
    try:
        result = MarkItDown().convert(source)
        _set_job(job_id, status="done", markdown=_extract_markdown(result))
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as exc:  # noqa: BLE001
        # MarkItDown's exceptions subclass BaseException (not Exception), so a
        # plain `except Exception` would let them escape this thread and leave
        # the job stuck on "running". Catch BaseException, but re-raise the
        # genuinely-fatal control-flow exceptions above.
        _set_job(job_id, status="error", error=str(exc))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def _start_job(source, temp_path=None):
    job_id = uuid.uuid4().hex
    _set_job(job_id, status="running")
    thread = threading.Thread(
        target=_convert_worker, args=(job_id, source, temp_path), daemon=True
    )
    thread.start()
    return job_id


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert():
    # File upload path
    uploaded = request.files.get("file")
    if uploaded and uploaded.filename:
        suffix = os.path.splitext(uploaded.filename)[1]
        fd, temp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        uploaded.save(temp_path)
        job_id = _start_job(temp_path, temp_path=temp_path)
        return jsonify(job_id=job_id), 202

    # URL path
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if url:
        job_id = _start_job(url)
        return jsonify(job_id=job_id), 202

    return jsonify(error="No file or URL provided."), 400


@app.route("/status/<job_id>")
def status(job_id):
    job = _get_job(job_id)
    if job is None:
        return jsonify(error="unknown job"), 404
    return jsonify(job), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
