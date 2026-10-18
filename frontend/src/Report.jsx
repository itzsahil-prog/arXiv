import { useMemo, useRef, useState } from 'react'
import { HUES, nf, sourceName } from './api.js'

function verdict(r) {
  const n = r.sources.length
  if (r.matched_words === 0) return 'No passages in this paper match your library.'
  const pct = `${r.similarity.toFixed(r.similarity < 10 ? 1 : 0)}%`
  return `${pct} of this paper matches ${n} ${n === 1 ? 'source' : 'sources'}.`
}

function guidance(r) {
  const flagged = r.sources.filter((s) => s.share > 5).length
  const parts = []
  if (flagged) parts.push(`${flagged} ${flagged === 1 ? 'source makes' : 'sources make'} up more than 5% of the paper on their own, so start there.`)
  parts.push('Journals and universities often look for under 10 to 15% overall, but each sets its own limit.')
  return parts.join(' ')
}

const reduced = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

export default function Report({ check, actions }) {
  const { text, result } = check
  const { sources, matches } = result
  const rank = useMemo(() => Object.fromEntries(sources.map((s, i) => [s.doc, i])), [sources])
  const hue = (doc) => HUES[rank[doc] % HUES.length]
  const [focus, setFocus] = useState(null)
  const [sel, setSel] = useState(null)
  const panel = useRef(null)

  const visible = useMemo(
    () => matches.filter((m) => focus == null || m.doc === focus),
    [matches, focus],
  )

  const scrollTo = (id) => {
    document.getElementById('m' + id)?.scrollIntoView({ block: 'center', behavior: reduced() ? 'auto' : 'smooth' })
  }
  const select = (id) => {
    setSel(id)
    scrollTo(id)
    panel.current?.scrollTo({ top: 0 })
  }
  const step = (d) => {
    if (!visible.length) return
    const at = visible.findIndex((m) => m.id === sel)
    const next = at === -1 ? (d > 0 ? 0 : visible.length - 1) : Math.min(visible.length - 1, Math.max(0, at + d))
    select(visible[next].id)
  }
  const pickSource = (doc) => {
    if (focus === doc) { setFocus(null); return }
    setFocus(doc)
    const first = matches.find((m) => m.doc === doc)
    if (first) select(first.id)
  }

  const nodes = useMemo(() => {
    const out = []
    let cur = 0
    matches.forEach((m) => {
      if (m.start > cur) out.push(text.slice(cur, m.start))
      const dim = focus != null && m.doc !== focus
      out.push(
        <mark
          key={m.id}
          id={'m' + m.id}
          className={'hl' + (dim ? ' dim' : '') + (sel === m.id ? ' on' : '')}
          style={{ '--h': hue(m.doc) }}
          tabIndex={dim ? -1 : 0}
          onClick={() => setSel(m.id)}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSel(m.id) } }}
        >
          {text.slice(m.start, m.end)}
        </mark>,
      )
      cur = m.end
    })
    out.push(text.slice(cur))
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, matches, focus, sel, rank])

  const m = sel != null ? matches[sel] : null
  const src = m ? sources[rank[m.doc]] : null
  const at = visible.findIndex((x) => x.id === sel)

  return (
    <div className="report">
      <header className="report-head">
        <h1>{verdict(result)}</h1>
        <p className="lede">
          {nf.format(result.matched_words)} of {nf.format(result.total_words)} words matched. Matches shorter
          than {result.min_words} words are ignored. {result.matched_words > 0 && guidance(result)}
        </p>
        {actions && <div className="row">{actions}</div>}
      </header>

      <div className="report-body">
        <article className="sheet" aria-label="Your paper with matches highlighted">
          <div className="minimap" aria-hidden="true">
            {matches.map((x) => (
              <span
                key={x.id}
                style={{
                  top: `${(x.start / text.length) * 100}%`,
                  height: `max(3px, ${((x.end - x.start) / text.length) * 100}%)`,
                  '--h': hue(x.doc),
                  opacity: focus != null && x.doc !== focus ? 0.2 : 1,
                }}
                onClick={() => select(x.id)}
              />
            ))}
          </div>
          <div className="doc">{nodes}</div>
        </article>

        <aside className="side" ref={panel}>
          {m && (
            <section className="compare" aria-live="polite">
              <div className="compare-head">
                <h2>Passage {at >= 0 ? at + 1 : m.id + 1}</h2>
                <button className="link" onClick={() => setSel(null)}>Close</button>
              </div>
              <p className="label">Your paper</p>
              <p className="quote">
                {text.slice(Math.max(0, m.start - 140), m.start)}
                <mark className="hl on" style={{ '--h': hue(m.doc) }}>{text.slice(m.start, m.end)}</mark>
                {text.slice(m.end, m.end + 140)}
              </p>
              <p className="label">
                {src.url ? <a href={src.url} target="_blank" rel="noreferrer">{src.title}</a> : src.title}
                {' '}({sourceName(src.source)})
              </p>
              <p className="quote">
                {m.source_before}
                <mark className="hl on" style={{ '--h': hue(m.doc) }}>{m.source_match}</mark>
                {m.source_after}
              </p>
              <p className="hint">{m.words} words match word for word. Quote it, cite it, or rewrite it in your own words.</p>
            </section>
          )}

          <section>
            <div className="side-head">
              <h2>Sources</h2>
              <div className="stepper">
                <button className="btn ghost sm" onClick={() => step(-1)} disabled={!visible.length}>Previous</button>
                <button className="btn ghost sm" onClick={() => step(1)} disabled={!visible.length}>Next</button>
              </div>
            </div>
            {sources.length === 0 && <p className="muted">Nothing to list.</p>}
            <ol className="sources">
              {sources.map((s, i) => (
                <li key={s.doc} className={focus === s.doc ? 'active' : ''}>
                  <button onClick={() => pickSource(s.doc)} aria-pressed={focus === s.doc}>
                    <span className="chip" style={{ '--h': HUES[i % HUES.length] }} />
                    <span className="s-title">{s.title || 'Untitled'}</span>
                    <span className="s-meta">
                      {sourceName(s.source)}, {s.passages} {s.passages === 1 ? 'passage' : 'passages'},{' '}
                      {nf.format(s.words)} words
                    </span>
                    <span className="bar"><i style={{ width: `${Math.min(100, s.share * 4)}%`, '--h': HUES[i % HUES.length] }} /></span>
                    <span className={'s-share' + (s.share > 5 ? ' warn' : '')}>
                      {s.share.toFixed(1)}%{s.share > 5 ? ' of paper, review' : ''}
                    </span>
                  </button>
                  {s.url && <a className="s-link" href={s.url} target="_blank" rel="noreferrer">Open source</a>}
                </li>
              ))}
            </ol>
            {focus != null && <button className="link" onClick={() => setFocus(null)}>Show all sources</button>}
          </section>
        </aside>
      </div>
    </div>
  )
}
