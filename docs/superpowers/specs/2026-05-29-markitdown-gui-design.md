# MarkItDown GUI — Design

**Date:** 2026-05-29
**Status:** Approved

## Purpose

Microsoft's [MarkItDown](https://github.com/microsoft/markitdown) is a Python
utility that converts many file formats (PDF, DOCX, PPTX, XLSX, images, audio,
HTML, CSV, JSON, XML, EPub, ZIP, YouTube URLs, and more) into Markdown. It ships
only as a CLI and a Python library. This project wraps it in a minimal local web
GUI so a user can convert files by dragging them into a browser instead of typing
CLI commands.

## Goals

- Run entirely on the user's machine (no hosting, no external services).
- Accept input three ways: drag & drop, file picker, and pasted URL.
- Show the raw Markdown result and let the user copy it or download it as `.md`.
- Handle arbitrarily large files without freezing the browser (async conversion).
- Keep the stack toolchain-free: Python + Flask + vanilla HTML/CSS/JS.

## Non-Goals (YAGNI)

- No rendered Markdown preview (raw text only).
- No authentication, accounts, or multi-user support.
- No persistence — nothing is saved to disk beyond a transient temp file.
- No deployment / hosting configuration.
- No light/dark toggle — single clean light theme.

## Architecture

A stateless local Flask app. No database, no sessions, no auth.

```
MarkitDown/
├── app.py                 # Flask server: routes + async job management
├── requirements.txt       # flask, markitdown[all]
├── templates/
│   └── index.html         # single page
└── static/
    ├── style.css          # minimal/clean light theme
    └── app.js             # input handling, polling, copy/download
```

Conversion runs in a background thread. Job state lives in an in-memory dict
keyed by a generated `job_id`. No Redis/Celery — `threading` and a dict are
sufficient for a single local user.

## UI Layout

Single page, top-to-bottom flow:

```
┌─────────────────────────────────────┐
│  MarkItDown                          │  ← title + one-line description
├─────────────────────────────────────┤
│   [ Drag & drop files here ]         │  ← dashed-border drop zone
│   [ Browse files ]  [ paste URL … ]  │  ← file picker + URL input + Convert
├─────────────────────────────────────┤
│  [ Converting… spinner ]             │  ← hidden until a job is running
├─────────────────────────────────────┤
│  ┌───────────────────────────────┐   │
│  │ # Markdown output …           │   │  ← monospace, read-only textarea
│  └───────────────────────────────┘   │
│  [ Copy ]  [ Download .md ]          │  ← hidden until output exists
└─────────────────────────────────────┘
```

- Clicking the drop zone also opens the native file picker.
- URL field has its own "Convert" button.
- Output section and action buttons stay hidden until a conversion completes.
- Clean white background, system/Inter font, no nav, no sidebar.

## Data Flow

### File upload
1. User drops or picks a file → JS builds `FormData`.
2. `POST /convert` (`multipart/form-data`) streams the file to Flask.
3. Flask writes it to a `tempfile`, generates a `job_id`, spawns a background
   thread running `MarkItDown().convert(path)`, and returns `{ "job_id": "…" }`
   immediately.
4. The thread stores the result (or error) in the in-memory job dict and deletes
   the temp file in a `finally` block.

### URL
1. User types a URL + clicks Convert → `POST /convert` with JSON `{ "url": "…" }`.
2. Flask spawns a thread running `MarkItDown().convert(url)`; same `job_id` flow.
   No temp file is created.

### Polling
1. After receiving `job_id`, JS polls `GET /status/<job_id>` every 1 second.
2. Response is one of:
   - `{ "status": "running" }`
   - `{ "status": "done", "markdown": "…" }`
   - `{ "status": "error", "error": "…" }`
3. On `done`/`error` JS stops polling and updates the UI.

### API summary
```
POST /convert
  body: multipart file  OR  { "url": "…" }
  → { "job_id": string }            (202)
  → { "error": string }             (400)

GET /status/<job_id>
  → { "status": "running" }                       (200)
  → { "status": "done", "markdown": string }      (200)
  → { "status": "error", "error": string }        (200)
  → { "error": "unknown job" }                    (404)
```

## UI States

- **Idle** — input visible, output + spinner hidden.
- **Converting** — spinner + "Converting… (large files may take a moment)";
  inputs disabled to prevent double-submit.
- **Done** — output textarea populated, Copy / Download revealed, inputs re-enabled.
- **Error** — calm inline message below the input; inputs re-enabled.

## Output Actions

- **Copy** — `navigator.clipboard.writeText()` of the textarea contents.
- **Download** — build a `Blob`, trigger a download named after the source file
  (e.g. `report.pdf` → `report.md`; URL → `converted.md`).

## File Size

No enforced limit. `MAX_CONTENT_LENGTH` is left unset. Because conversion is
async and runs off the request thread, large uploads never freeze the page.

## Error Handling

| Scenario | Behavior |
|---|---|
| Unsupported file type | MarkItDown raises → caught in thread → `status: error` → inline message |
| Invalid / unreachable URL | MarkItDown raises → caught → `"Could not fetch or convert URL"` |
| Conversion fails mid-way | Exception caught in thread; temp file removed in `finally` |
| Unknown / expired job_id | `GET /status` returns 404 `{ "error": "unknown job" }` |
| Network error on fetch | JS `catch` → "Connection error — is the server running?" |

No stack traces or browser `alert()`s ever reach the user — all errors surface as
calm inline text beneath the input area.

## Testing

- **Backend unit tests** (`pytest`):
  - `/convert` with a small fixture file returns a `job_id`.
  - Polling that `job_id` eventually returns `status: done` with non-empty markdown.
  - `/convert` with a `url` payload returns a `job_id`.
  - `/status` with an unknown id returns 404.
  - A deliberately bad input ends in `status: error`, not a 500.
- **Manual smoke test:** drag a real PDF, a DOCX, and paste a URL; confirm
  output, Copy, and Download all work.

## Stack

- Python 3.10+ (3.14 present locally).
- `flask`, `markitdown[all]`.
- Vanilla HTML/CSS/JS — no npm, no build step.
