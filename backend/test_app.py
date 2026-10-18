"""Run with: python -m pytest -q   (from the backend folder)"""
import io
import os
import tempfile
import time

os.environ["OVERLAP_DATA"] = tempfile.mkdtemp()

from fastapi.testclient import TestClient  # noqa: E402

from app import ingest, jobs  # noqa: E402
from app.main import app  # noqa: E402

A = ("Blockchain technology provides a decentralized ledger that records academic credentials in a "
     "tamper resistant way, allowing universities to issue certificates that employers can verify "
     "instantly without contacting the issuing institution directly.")
B = ("The convolutional neural network architecture uses learned filters that slide across an input "
     "image, producing feature maps that capture edges, textures, and eventually complex object parts.")
PAPER = ("Introduction\n\nThis paper studies digital learning in universities across several regions. "
         + A + " We then describe our own method in entirely original wording about student engagement "
         "and retention over several semesters of observation.\n\nAs noted earlier, \""
         + B[:120] + "\" which we quote here.\n\nReferences\nSmith (2020). Something else entirely.\n")

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><id>http://arxiv.org/abs/2301.00001v2</id><title>Trusted learning
 with ledgers</title><summary>""" + A.encode() + b"""</summary></entry></feed>"""


def test_end_to_end():
    c = TestClient(app)
    assert c.get("/api/library/stats").json()["documents"] == 0
    r = c.post("/api/checks", data={"text": PAPER})
    assert r.status_code == 409  # empty library

    up = c.post("/api/library/upload", files=[
        ("files", ("a.txt", A.encode(), "text/plain")),
        ("files", ("b.txt", B.encode(), "text/plain")),
        ("files", ("bad.xyz", b"x", "text/plain")),
    ]).json()
    assert up["added"] == 2 and len(up["failed"]) == 1

    r = c.post("/api/checks", data={"text": PAPER, "exclude_references": "true", "exclude_quotes": "true"})
    assert r.status_code == 200
    d = r.json()
    assert [s["title"] for s in d["result"]["sources"]] == ["a.txt"]
    m = d["result"]["matches"][0]
    assert d["text"][m["start"]:m["end"]].lower().startswith("blockchain technology")
    assert "decentralized ledger" in m["source_match"]

    d2 = c.post("/api/checks", data={"text": PAPER, "exclude_references": "true"}).json()
    assert {s["title"] for s in d2["result"]["sources"]} == {"a.txt", "b.txt"}

    assert len(c.get("/api/checks").json()) == 2
    assert c.get(f"/api/checks/{d['id']}").json()["text"] == d["text"]
    assert "<mark" in c.get(f"/api/checks/{d['id']}/report").text

    docs = c.get("/api/library/docs?q=a.txt").json()
    assert docs["total"] == 1
    assert c.delete(f"/api/library/docs/{docs['docs'][0]['id']}").status_code == 200
    d3 = c.post("/api/checks", data={"text": PAPER, "exclude_references": "true"}).json()
    assert {s["title"] for s in d3["result"]["sources"]} == {"b.txt"}
    assert c.get("/api/library/stats").json()["documents"] == 1
    assert c.delete(f"/api/checks/{d['id']}").status_code == 200


def test_arxiv_search_job(monkeypatch):
    monkeypatch.setattr(ingest, "_fetch", lambda url: ATOM)
    monkeypatch.setattr(ingest.time, "sleep", lambda s: None)
    c = TestClient(app)
    job = c.post("/api/jobs/arxiv-search", json={"query": "ledger learning", "limit": 5}).json()
    for _ in range(50):
        j = [x for x in c.get("/api/jobs").json() if x["id"] == job["id"]][0]
        if j["status"] != "running":
            break
        time.sleep(0.1)
    assert j["status"] == "done", j
    stats = c.get("/api/library/stats").json()
    assert any(s["source"] == "arxiv" for s in stats["sources"])
    recs = ingest.parse_arxiv_atom(ATOM)
    assert recs[0]["id"] == "2301.00001" and recs[0]["title"] == "Trusted learning with ledgers"
