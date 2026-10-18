# Overlap

A pre-submission similarity checker for research papers. Upload a paper, see which passages match a reference library, compare each match with its source side by side, and fix it before you submit.

## Run it

You need Python 3.10 or newer. The frontend is already built, so Node is not required.

    cd backend
    pip install -r requirements.txt
    python -m uvicorn app.main:app --port 8000

Open http://localhost:8000.

Your data lives in the `data` folder next to `backend`: `index.db` holds the reference library, `app.db` holds your checks and import log. Set `OVERLAP_DATA` to keep it somewhere else. Back up `data` to keep your work.

## Fill the library first

A check can only match what the library contains. Open the Library tab, or use the command line for big loads:

    cd backend
    python -m app.cli arxiv-search "blockchain digital learning" --limit 500
    python -m app.cli arxiv-file /path/arxiv-metadata-oai-snapshot.json --limit 500000
    python -m app.cli wikipedia --limit 200000
    python -m app.cli folder my-reference-papers/

For your topic, the quickest win is an arXiv search on your keywords, plus the full-text papers you cite added as files. The Kaggle arXiv file and the arXiv search return titles and abstracts only, so they catch copied abstracts, not copied paper bodies. Full-text papers added as files catch the rest. Open-access sets such as PubMed Central, CORE and S2ORC can be downloaded and loaded the same way.

## How it works

Each document is split into overlapping five-word shingles, hashed, and thinned by winnowing, which keeps the index small while guaranteeing that any shared run of eight or more words is found. A check looks up the paper's fingerprints, grows each hit into the full word-for-word passage, and credits every word to one source. Matches under 8 words are ignored. Quoted text and the references section can be left out.

## Honest limits

Your library is far smaller than the databases behind Turnitin or iThenticate, so a low score here does not predict their result. Use Overlap to find and fix real overlap, not to guess a number. It finds exact wording, not paraphrases; sentence embeddings with FAISS would be the next layer. The index is SQLite, which comfortably handles tens of millions of fingerprints on one machine. Beyond that, move the fingerprint table to PostgreSQL.

## Develop

    cd backend && python -m pytest -q
    cd frontend && npm install && npm run dev      # http://localhost:5173, proxies /api to :8000
    cd frontend && npm run build                   # rebuilds frontend/dist
