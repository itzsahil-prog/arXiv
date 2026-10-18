"""Database paths, schemas and connections.

Two SQLite files, so a long ingest never blocks a check:
  data/index.db  the reference library: documents plus winnowed fingerprints
  data/app.db    your checks and the ingest job log
"""
import json
import os
import sqlite3
from contextlib import contextmanager

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.environ.get("OVERLAP_DATA", os.path.join(BASE, "data"))
INDEX_DB = os.path.join(DATA_DIR, "index.db")
APP_DB = os.path.join(DATA_DIR, "app.db")


class IndexEmpty(Exception):
    """The reference library has no documents yet."""


INDEX_SCHEMA = """
CREATE TABLE IF NOT EXISTS docs(
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    ref TEXT NOT NULL,
    title TEXT,
    url TEXT,
    words INTEGER,
    added REAL,
    text BLOB,
    UNIQUE(source, ref));
CREATE TABLE IF NOT EXISTS fp(h INTEGER NOT NULL, doc INTEGER NOT NULL, pos INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS fp_h ON fp(h);
CREATE TABLE IF NOT EXISTS sources(
    source TEXT PRIMARY KEY,
    docs INTEGER NOT NULL DEFAULT 0,
    words INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""

APP_SCHEMA = """
CREATE TABLE IF NOT EXISTS checks(
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    filename TEXT,
    created REAL NOT NULL,
    similarity REAL NOT NULL,
    total_words INTEGER NOT NULL,
    matched_words INTEGER NOT NULL,
    source_count INTEGER NOT NULL,
    options TEXT NOT NULL,
    text TEXT NOT NULL,
    result TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    params TEXT NOT NULL,
    status TEXT NOT NULL,
    processed INTEGER NOT NULL DEFAULT 0,
    target INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    started REAL NOT NULL,
    finished REAL);
"""


@contextmanager
def index(fast=False):
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(INDEX_DB, timeout=60)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        if fast:  # bulk loading: trade crash-safety for speed
            con.execute("PRAGMA synchronous=OFF")
            con.execute("PRAGMA cache_size=-200000")
        con.executescript(INDEX_SCHEMA)
        yield con
    finally:
        con.close()


@contextmanager
def appdb():
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(APP_DB, timeout=60)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(APP_SCHEMA)
        yield con
    finally:
        con.close()


def get_params(con, k=None, w=None):
    """Shingle size k and winnowing window w are fixed when the index is first built."""
    row = con.execute("SELECT value FROM meta WHERE key='params'").fetchone()
    if row:
        return tuple(json.loads(row[0]))
    if k is None:
        raise IndexEmpty()
    con.execute("INSERT INTO meta VALUES('params', ?)", (json.dumps([k, w]),))
    con.commit()
    return k, w
