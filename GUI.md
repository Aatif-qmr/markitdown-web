# MarkItDown GUI

A minimal **local web GUI** for [MarkItDown](https://github.com/microsoft/markitdown).
Convert PDF, DOCX, PPTX, XLSX, images, audio, HTML, CSV, JSON, EPub, ZIP, YouTube
URLs and more to Markdown — by dragging a file into your browser instead of using
the CLI. Everything runs on your machine; nothing is uploaded anywhere.

## Features

- Drag & drop, file picker, or paste a URL
- Async conversion — large files never freeze the page (no size limit)
- Copy to clipboard or download as `.md`
- Clean, single-page light UI; no build step, no npm

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> **Python 3.14 note:** install MarkItDown from PyPI — `pip install 'markitdown[all]'`,
> which is exactly what [requirements.txt](requirements.txt) does, and it pulls in all
> the converters (PDF, DOCX, PPTX, XLSX, …). Do **not** use the editable install of the
> bundled source (`pip install -e 'packages/markitdown[all]'`): on Python 3.14 it fails
> because some optional deps (e.g. `youtube-transcript-api`) pin to versions that
> require Python < 3.14.

## Run

```bash
python app.py
```

Open <http://127.0.0.1:5000> in your browser.

## How it works

| Piece | Responsibility |
|---|---|
| [app.py](app.py) | Flask server. `POST /convert` accepts a file or `{url}`, spawns a background thread, returns a `job_id`. `GET /status/<job_id>` reports `running` / `done` / `error`. |
| [templates/index.html](templates/index.html) | Single page. |
| [static/style.css](static/style.css) | Minimal light theme. |
| [static/app.js](static/app.js) | Input handling, 1s status polling, copy/download. |

Files are written to a temp path, converted in memory off the request thread, and
the temp file is deleted in a `finally` block. No database, no persistence.

## Tests

```bash
pip install pytest
pytest test_app.py
```

(Run `pytest test_app.py` specifically — a bare `pytest` would also collect the
upstream package tests under `packages/`, which need their own `hatch` setup.)

## Design

See [docs/superpowers/specs/2026-05-29-markitdown-gui-design.md](docs/superpowers/specs/2026-05-29-markitdown-gui-design.md).
