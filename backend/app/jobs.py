"""Background ingest jobs, logged in app.db so progress survives page reloads."""
import json
import threading
import time

from .db import appdb, index
from . import ingest

_lock = threading.Lock()
_cancel = set()


class JobBusy(Exception):
    pass


def mark_stale():
    """Jobs left 'running' by a previous server process can never finish."""
    with appdb() as con:
        con.execute("UPDATE jobs SET status='interrupted', finished=? WHERE status='running'", (time.time(),))
        con.commit()


class JobCtx:
    def __init__(self, job_id):
        self.job_id = job_id
        self._last = 0.0

    def cancelled(self):
        return self.job_id in _cancel

    def tick(self, processed, message=None, target=None):
        now = time.time()
        if now - self._last < 0.8:
            return
        self._last = now
        with appdb() as con:
            con.execute(
                "UPDATE jobs SET processed=?, message=COALESCE(?, message), target=COALESCE(?, target) WHERE id=?",
                (processed, message, target, self.job_id),
            )
            con.commit()


def _run(job_id, fn):
    ctx = JobCtx(job_id)
    status, message = "done", ""
    try:
        with index(fast=True) as con:
            result = fn(con, ctx)
        message = result if isinstance(result, str) else json.dumps(result)
        if ctx.cancelled():
            status = "cancelled"
    except Exception as e:
        status, message = "failed", str(e) or e.__class__.__name__
    finally:
        _cancel.discard(job_id)
        with appdb() as con:
            con.execute("UPDATE jobs SET status=?, message=?, finished=? WHERE id=?",
                        (status, message, time.time(), job_id))
            con.commit()


def start(kind, params, target, fn):
    with _lock:
        with appdb() as con:
            if con.execute("SELECT 1 FROM jobs WHERE status='running'").fetchone():
                raise JobBusy()
            cur = con.execute(
                "INSERT INTO jobs(kind, params, status, target, started) VALUES (?,?,?,?,?)",
                (kind, json.dumps(params), "running", target, time.time()),
            )
            con.commit()
            job_id = cur.lastrowid
    threading.Thread(target=_run, args=(job_id, fn), daemon=True).start()
    return job_id


def cancel(job_id):
    _cancel.add(job_id)


def recent(limit=15):
    with appdb() as con:
        rows = con.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["params"] = json.loads(d["params"])
        out.append(d)
    return out


def start_arxiv_file(path, limit):
    return start("arxiv-file", {"path": path, "limit": limit}, limit,
                 lambda con, ctx: ingest.ingest_arxiv_file(con, path, limit, ctx))


def start_arxiv_search(query, limit):
    return start("arxiv-search", {"query": query, "limit": limit}, limit,
                 lambda con, ctx: ingest.ingest_arxiv_search(con, query, limit, ctx))


def start_wikipedia(limit, config):
    return start("wikipedia", {"limit": limit, "config": config}, limit,
                 lambda con, ctx: ingest.ingest_wikipedia(con, limit, config, ctx))
