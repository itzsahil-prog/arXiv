"""Overlap API and static frontend server.

Run from the backend folder:  python -m uvicorn app.main:app --port 8000
"""
import json
import os
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ingest, jobs, report
from .db import BASE, IndexEmpty, appdb, index
from .engine import analyze

DIST = os.path.join(BASE, "frontend", "dist")


@asynccontextmanager
async def lifespan(app):
    jobs.mark_stale()
    yield


app = FastAPI(title="Overlap", lifespan=lifespan)


# ------------------------------------------------------------------- library

@app.get("/api/library/stats")
def library_stats():
    with index() as con:
        return ingest.library_stats(con)


@app.get("/api/library/docs")
def library_docs(source: str = "", q: str = "", limit: int = 25, offset: int = 0):
    limit = max(1, min(limit, 100))
    where, args = [], []
    if source:
        where.append("source=?")
        args.append(source)
    if q:
        where.append("title LIKE ?")
        args.append(f"%{q}%")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    with index() as con:
        total = con.execute(f"SELECT COUNT(*) FROM docs {clause}", args).fetchone()[0]
        rows = con.execute(
            f"SELECT id, source, title, url, words, added FROM docs {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
            args + [limit, max(0, offset)],
        ).fetchall()
    keys = ["id", "source", "title", "url", "words", "added"]
    return {"total": total, "docs": [dict(zip(keys, r)) for r in rows]}


@app.delete("/api/library/docs/{doc_id}")
def library_delete(doc_id: int):
    with index() as con:
        if not ingest.delete_doc(con, doc_id):
            raise HTTPException(404, "That document is not in the library.")
    return {"ok": True}


@app.post("/api/library/upload")
def library_upload(files: List[UploadFile] = File(...)):
    payload = [(f.filename or "untitled", f.file.read()) for f in files]
    with index(fast=True) as con:
        return ingest.ingest_files(con, payload)


# ---------------------------------------------------------------------- jobs

class ArxivFile(BaseModel):
    path: str
    limit: int = Field(0, ge=0)


class ArxivSearch(BaseModel):
    query: str = Field(min_length=2)
    limit: int = Field(200, ge=1, le=5000)


class Wikipedia(BaseModel):
    limit: int = Field(20000, ge=1)
    config: str = "20231101.en"


def _start(fn, *args):
    try:
        return {"id": fn(*args)}
    except jobs.JobBusy:
        raise HTTPException(409, "Another import is still running. Wait for it to finish or cancel it.")


@app.post("/api/jobs/arxiv-file")
def job_arxiv_file(body: ArxivFile):
    if not os.path.isfile(body.path):
        raise HTTPException(400, f"No file at {body.path} on the machine running Overlap.")
    return _start(jobs.start_arxiv_file, body.path, body.limit)


@app.post("/api/jobs/arxiv-search")
def job_arxiv_search(body: ArxivSearch):
    return _start(jobs.start_arxiv_search, body.query, body.limit)


@app.post("/api/jobs/wikipedia")
def job_wikipedia(body: Wikipedia):
    try:
        import datasets  # noqa: F401
    except ImportError:
        raise HTTPException(400, "Wikipedia import needs the datasets package: pip install datasets")
    return _start(jobs.start_wikipedia, body.limit, body.config)


@app.get("/api/jobs")
def job_list():
    return jobs.recent()


@app.post("/api/jobs/{job_id}/cancel")
def job_cancel(job_id: int):
    jobs.cancel(job_id)
    return {"ok": True}


# -------------------------------------------------------------------- checks

def _check_row(row, full=True):
    d = {
        "id": row["id"], "title": row["title"], "filename": row["filename"],
        "created": row["created"], "similarity": row["similarity"],
        "total_words": row["total_words"], "matched_words": row["matched_words"],
        "source_count": row["source_count"],
    }
    if full:
        d["options"] = json.loads(row["options"])
        d["text"] = row["text"]
        d["result"] = json.loads(row["result"])
    return d


def _load_check(check_id):
    with appdb() as con:
        row = con.execute("SELECT * FROM checks WHERE id=?", (check_id,)).fetchone()
    if not row:
        raise HTTPException(404, "That check no longer exists.")
    return row


@app.post("/api/checks")
def create_check(
    title: str = Form(""),
    text: str = Form(""),
    min_words: int = Form(8),
    exclude_quotes: bool = Form(False),
    exclude_references: bool = Form(False),
    file: Optional[UploadFile] = File(None),
):
    filename = None
    if file is not None and file.filename:
        try:
            raw = ingest.read_upload(file.filename, file.file.read())
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception:
            raise HTTPException(400, f"Could not read {file.filename}. Try saving it as .docx or .txt.")
        filename = file.filename
    else:
        raw = text
    if len(raw.split()) < 20:
        raise HTTPException(400, "Add at least 20 words to check.")

    options = {"min_words": min_words, "exclude_quotes": exclude_quotes,
               "exclude_references": exclude_references}
    with index() as con:
        try:
            analysed, result = analyze(con, raw, **options)
        except IndexEmpty:
            raise HTTPException(409, "The reference library is empty. Add documents in the Library first.")
        except ValueError as e:
            raise HTTPException(400, str(e))

    title = title.strip() or filename or " ".join(raw.split()[:8]) + "…"
    with appdb() as con:
        cur = con.execute(
            "INSERT INTO checks(title, filename, created, similarity, total_words, matched_words,"
            " source_count, options, text, result) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (title, filename, time.time(), result["similarity"], result["total_words"],
             result["matched_words"], len(result["sources"]), json.dumps(options),
             analysed, json.dumps(result)),
        )
        con.commit()
        check_id = cur.lastrowid
    return _check_row(_load_check(check_id))


@app.get("/api/checks")
def list_checks():
    with appdb() as con:
        rows = con.execute(
            "SELECT id, title, filename, created, similarity, total_words, matched_words, source_count"
            " FROM checks ORDER BY id DESC LIMIT 200").fetchall()
    return [_check_row(r, full=False) for r in rows]


@app.get("/api/checks/{check_id}")
def get_check(check_id: int):
    return _check_row(_load_check(check_id))


@app.delete("/api/checks/{check_id}")
def delete_check(check_id: int):
    with appdb() as con:
        con.execute("DELETE FROM checks WHERE id=?", (check_id,))
        con.commit()
    return {"ok": True}


@app.get("/api/checks/{check_id}/report")
def check_report(check_id: int):
    check = _check_row(_load_check(check_id))
    return HTMLResponse(
        report.build(check),
        headers={"Content-Disposition": f'attachment; filename="overlap-report-{check_id}.html"'},
    )


# ------------------------------------------------------------------ frontend

if os.path.isdir(os.path.join(DIST, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")


@app.get("/{path:path}")
def frontend(path: str):
    if path.startswith("api/"):
        raise HTTPException(404)
    target = os.path.normpath(os.path.join(DIST, path))
    if path and target.startswith(DIST) and os.path.isfile(target):
        return FileResponse(target)
    page = os.path.join(DIST, "index.html")
    if os.path.isfile(page):
        return FileResponse(page)
    return HTMLResponse("The frontend is not built yet. Run npm install and npm run build in the frontend folder.", 404)
