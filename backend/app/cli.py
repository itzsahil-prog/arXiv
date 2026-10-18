"""Command line loader for big imports (no browser needed).

    python -m app.cli arxiv-file /path/arxiv-metadata-oai-snapshot.json --limit 500000
    python -m app.cli arxiv-search "blockchain education" --limit 500
    python -m app.cli wikipedia --limit 200000
    python -m app.cli folder papers/
"""
import argparse
import os
import sys

from . import ingest
from .db import index


class PrintCtx(ingest.NullCtx):
    def tick(self, processed, message=None, target=None):
        if message:
            print("  " + message, flush=True)


def main():
    p = argparse.ArgumentParser(description="Load documents into the Overlap library")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("arxiv-file"); s.add_argument("path"); s.add_argument("--limit", type=int, default=0)
    s = sub.add_parser("arxiv-search"); s.add_argument("query"); s.add_argument("--limit", type=int, default=200)
    s = sub.add_parser("wikipedia"); s.add_argument("--limit", type=int, default=20000); s.add_argument("--config", default="20231101.en")
    s = sub.add_parser("folder"); s.add_argument("path")
    a = p.parse_args()
    ctx = PrintCtx()
    with index(fast=True) as con:
        if a.cmd == "arxiv-file":
            print(ingest.ingest_arxiv_file(con, a.path, a.limit, ctx))
        elif a.cmd == "arxiv-search":
            print(ingest.ingest_arxiv_search(con, a.query, a.limit, ctx))
        elif a.cmd == "wikipedia":
            print(ingest.ingest_wikipedia(con, a.limit, a.config, ctx))
        else:
            files = []
            for root, _, names in os.walk(a.path):
                for n in names:
                    if os.path.splitext(n)[1].lower() in {".txt", ".md", ".docx", ".pdf"}:
                        with open(os.path.join(root, n), "rb") as f:
                            files.append((n, f.read()))
            print(ingest.ingest_files(con, files, ctx))


if __name__ == "__main__":
    sys.exit(main())
