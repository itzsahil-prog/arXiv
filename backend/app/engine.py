"""Similarity engine.

Word 5-gram shingles, winnowing (Schleimer et al.) to keep the index small, then
exact-match extension around each seed to recover the full matching passage.
Any shared run of at least k + w - 1 words is guaranteed to be found.
"""
import hashlib
import re
import zlib
from collections import Counter, defaultdict
from functools import lru_cache

from .db import get_params

MASK = (1 << 63) - 1
TOKEN_RE = re.compile(r"\w+(?:'\w+)?")
REF_RE = re.compile(
    r"^\s*(?:\d+[.)]?\s*)?(references|bibliography|works cited|literature cited)\s*:?\s*$",
    re.I | re.M,
)
QUOTE_RE = re.compile(r'"[^"\n]{10,800}"|\u201c[^\u201d\n]{10,800}\u201d')
CONTEXT = 140  # characters of surrounding text shown with each match


@lru_cache(maxsize=1_000_000)
def tok_hash(tok):
    digest = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") & MASK


def tokenize(text):
    """Lowercased word tokens plus (start, end) character offsets."""
    text = text.replace("\u2019", "'")  # same length, so offsets stay valid
    toks, spans = [], []
    for m in TOKEN_RE.finditer(text):
        toks.append(m.group().lower())
        spans.append((m.start(), m.end()))
    return toks, spans


def kgram_hashes(tokens, k):
    hs = [tok_hash(t) for t in tokens]
    out = []
    for i in range(len(hs) - k + 1):
        h = 0
        for j in range(i, i + k):
            h = (h * 1000003 + hs[j]) & MASK
        out.append(h)
    return out


def winnow(hashes, w):
    """Minimum hash in every window of w (rightmost on ties) as sorted (pos, hash)."""
    n = len(hashes)
    if n == 0:
        return []
    if n <= w:
        i = min(range(n), key=lambda x: (hashes[x], -x))
        return [(i, hashes[i])]
    picked, last = {}, -1
    for s in range(n - w + 1):
        window = hashes[s:s + w]
        m = min(window)
        idx = s + w - 1 - window[::-1].index(m)
        if idx != last:
            picked[idx] = m
            last = idx
    return sorted(picked.items())


def strip_references(text):
    for m in reversed(list(REF_RE.finditer(text))):
        if m.start() > 0.5 * len(text):
            return text[:m.start()]
    return text


def quote_mask(spans, text):
    quotes = [(m.start(), m.end()) for m in QUOTE_RE.finditer(text)]
    mask, qi = [False] * len(spans), 0
    for i, (s, _) in enumerate(spans):
        while qi < len(quotes) and quotes[qi][1] <= s:
            qi += 1
        if qi < len(quotes) and quotes[qi][0] <= s < quotes[qi][1]:
            mask[i] = True
    return mask


def find_seeds(con, tokens, k, w, max_docs_per_hash, top_docs):
    """Look up the paper's fingerprints; return {doc_id: [(paper_pos, doc_pos)]}."""
    fps = winnow(kgram_hashes(tokens, k), w)
    by_hash = defaultdict(list)
    for pos, h in fps:
        by_hash[h].append(pos)
    keys = list(by_hash)
    rows = []
    for i in range(0, len(keys), 500):
        batch = keys[i:i + 500]
        q = "SELECT h, doc, pos FROM fp WHERE h IN (%s)" % ",".join("?" * len(batch))
        rows.extend(con.execute(q, batch))
    docs_per_hash = defaultdict(set)
    for h, d, _ in rows:
        docs_per_hash[h].add(d)
    # Fingerprints present in very many documents are boilerplate; they only add noise.
    rows = [r for r in rows if len(docs_per_hash[r[0]]) <= max_docs_per_hash]
    shared = defaultdict(set)
    for h, d, _ in rows:
        shared[d].add(h)
    top = set(sorted(shared, key=lambda d: len(shared[d]), reverse=True)[:top_docs])
    seeds = defaultdict(list)
    for h, d, dpos in rows:
        if d in top:
            for ppos in by_hash[h]:
                seeds[d].append((ppos, dpos))
    return seeds


def extend_segments(tokens, doc_tokens, seeds, k):
    """Grow each seed into the longest exact word-for-word match: (a, e, doc_start)."""
    segs, seen = [], {}
    for ppos, dpos in sorted(seeds):
        diag = ppos - dpos
        if seen.get(diag, -1) > ppos:
            continue
        if tokens[ppos:ppos + k] != doc_tokens[dpos:dpos + k]:
            continue  # hash collision
        a, b = ppos, dpos
        while a > 0 and b > 0 and tokens[a - 1] == doc_tokens[b - 1]:
            a -= 1
            b -= 1
        e, f = ppos + k, dpos + k
        while e < len(tokens) and f < len(doc_tokens) and tokens[e] == doc_tokens[f]:
            e += 1
            f += 1
        segs.append((a, e, b))
        seen[diag] = e
    return segs


def runs(cov):
    """Yield (start, end, value) for each run of equal values in cov."""
    start = 0
    for i in range(1, len(cov) + 1):
        if i == len(cov) or cov[i] != cov[start]:
            yield start, i, cov[start]
            start = i


def analyze(con, text, min_words=8, exclude_quotes=False, exclude_references=False,
            top_docs=100, max_docs_per_hash=200):
    """Check text against the index. Returns (analysed_text, result_dict)."""
    k, w = get_params(con)
    if exclude_references:
        text = strip_references(text)
    min_words = max(int(min_words), k + w - 1)
    tokens, spans = tokenize(text)
    n = len(tokens)
    if n < k + w:
        raise ValueError(f"The text is too short to check. Add at least {k + w} words.")

    seeds = find_seeds(con, tokens, k, w, max_docs_per_hash, top_docs)
    segments, docs = [], {}  # segments: (a, e, doc, doc_start)
    for d, sd in seeds.items():
        row = con.execute("SELECT source, title, url, text FROM docs WHERE id=?", (d,)).fetchone()
        if not row:
            continue
        dtext = zlib.decompress(row[3]).decode("utf-8")
        dtoks, dspans = tokenize(dtext)
        docs[d] = {"source": row[0], "title": row[1], "url": row[2], "text": dtext, "spans": dspans}
        for a, e, b in extend_segments(tokens, dtoks, sd, k):
            if e - a >= min_words:
                segments.append((a, e, d, b))

    # Longest matches claim words first, so each word is credited to exactly one source.
    cov = [-1] * n  # index of the segment that owns each word
    for si in sorted(range(len(segments)), key=lambda i: segments[i][0] - segments[i][1]):
        a, e = segments[si][0], segments[si][1]
        for i in range(a, e):
            if cov[i] == -1:
                cov[i] = si

    if exclude_quotes:
        for i, quoted in enumerate(quote_mask(spans, text)):
            if quoted:
                cov[i] = -1
    for s, e, v in list(runs(cov)):
        if v != -1 and e - s < min_words:
            for i in range(s, e):
                cov[i] = -1

    matches, per_doc, per_doc_count = [], Counter(), Counter()
    for s, e, si in runs(cov):
        if si == -1:
            continue
        a, _, d, b = segments[si]
        ds = b + (s - a)
        de = min(ds + (e - s), len(docs[d]["spans"]))
        dsp, dtext = docs[d]["spans"], docs[d]["text"]
        cs, ce = dsp[ds][0], dsp[de - 1][1]
        excerpt = dtext[cs:ce]
        if len(excerpt) > 700:
            excerpt = excerpt[:350].rstrip() + " … " + excerpt[-300:].lstrip()
        matches.append({
            "id": len(matches),
            "start": spans[s][0],
            "end": spans[e - 1][1],
            "words": e - s,
            "doc": d,
            "source_before": dtext[max(0, cs - CONTEXT):cs],
            "source_match": excerpt,
            "source_after": dtext[ce:ce + CONTEXT],
        })
        per_doc[d] += e - s
        per_doc_count[d] += 1

    matched = sum(per_doc.values())
    sources = [{
        "doc": d,
        "source": docs[d]["source"],
        "title": docs[d]["title"],
        "url": docs[d]["url"],
        "words": c,
        "share": round(100 * c / n, 2),
        "passages": per_doc_count[d],
    } for d, c in per_doc.most_common()]

    return text, {
        "total_words": n,
        "matched_words": matched,
        "similarity": round(100 * matched / n, 2),
        "min_words": min_words,
        "index_params": [k, w],
        "sources": sources,
        "matches": matches,
    }
