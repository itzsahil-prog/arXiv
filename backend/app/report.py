"""Standalone HTML report for a saved check."""
import html
import time

HUES = [205, 28, 150, 330, 265, 48, 180, 0, 100, 300]


def build(check):
    text, result = check["text"], check["result"]
    sources = result["sources"]
    rank = {s["doc"]: i for i, s in enumerate(sources)}

    def hue(doc):
        return HUES[rank[doc] % len(HUES)]

    body, cursor = [], 0
    for m in result["matches"]:
        src = sources[rank[m["doc"]]]
        body.append(html.escape(text[cursor:m["start"]]))
        body.append(
            f'<mark style="--h:{hue(m["doc"])}" title="{html.escape(src["title"] or "")}">'
            f'{html.escape(text[m["start"]:m["end"]])}</mark>'
        )
        cursor = m["end"]
    body.append(html.escape(text[cursor:]))

    rows = []
    for s in sources:
        name = html.escape(s["title"] or "Untitled")
        if s["url"]:
            name = f'<a href="{html.escape(s["url"])}">{name}</a>'
        rows.append(
            f'<tr><td><span class="chip" style="--h:{hue(s["doc"])}"></span></td><td>{name}</td>'
            f'<td>{html.escape(s["source"])}</td><td>{s["words"]}</td><td>{s["share"]:.1f}%</td></tr>'
        )
    when = time.strftime("%d %b %Y, %H:%M", time.localtime(check["created"]))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(check["title"])} - similarity report</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ font-family: Georgia, serif; max-width: 820px; margin: 2rem auto; padding: 0 1rem; line-height: 1.7; }}
h1 {{ font-size: 1.6rem; margin-bottom: .2rem; }}
.meta {{ color: #667; font-family: system-ui, sans-serif; font-size: .9rem; }}
table {{ border-collapse: collapse; width: 100%; font-family: system-ui, sans-serif; font-size: .9rem; margin: 1.2rem 0; }}
td, th {{ border-bottom: 1px solid #8884; padding: 6px 8px; text-align: left; }}
.chip {{ display: inline-block; width: 22px; height: 12px; border-radius: 3px; background: hsl(var(--h) 90% 75%); }}
mark {{ background: hsl(var(--h) 92% 78%); color: #111; border-radius: 3px; padding: 0 2px; }}
.text {{ white-space: pre-wrap; }}
</style></head><body>
<h1>{html.escape(check["title"])}</h1>
<p class="meta">Checked {when}. {result["similarity"]:.1f}% similarity: {result["matched_words"]} of {result["total_words"]} words match {len(sources)} sources.
Matches shorter than {result["min_words"]} words are ignored. This compares against a limited library, so it will not equal a university tool's score.</p>
<table><tr><th></th><th>Source</th><th>Library</th><th>Words</th><th>Share of paper</th></tr>{"".join(rows)}</table>
<div class="text">{"".join(body)}</div>
</body></html>"""
