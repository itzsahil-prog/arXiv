import { useCallback, useEffect, useRef, useState } from 'react'
import { api, bytes, nf, sourceName, when } from '../api.js'

const KINDS = {
  'arxiv-file': 'arXiv dataset file',
  'arxiv-search': 'arXiv search',
  wikipedia: 'Wikipedia',
}

function jobLabel(j) {
  const p = j.params
  if (j.kind === 'arxiv-search') return `arXiv search for "${p.query}"`
  if (j.kind === 'arxiv-file') return `arXiv dataset file ${p.path.split(/[\\/]/).pop()}`
  return `Wikipedia, up to ${nf.format(p.limit)} articles`
}

function Jobs({ jobs, onDone }) {
  const running = jobs.some((j) => j.status === 'running')
  const was = useRef(running)
  useEffect(() => {
    if (was.current && !running) onDone()
    was.current = running
  }, [running, onDone])
  if (!jobs.length) return null
  return (
    <section>
      <h2>Imports</h2>
      <ul className="jobs">
        {jobs.map((j) => {
          const pct = j.target ? Math.min(100, (j.processed / j.target) * 100) : null
          return (
            <li key={j.id}>
              <div className="job-top">
                <span className="strong">{jobLabel(j)}</span>
                <span className={'state ' + j.status}>{j.status}</span>
              </div>
              {j.status === 'running' && (
                <div className="job-run">
                  <span className={'progress' + (pct == null ? '' : ' det')}><i style={pct == null ? undefined : { width: pct + '%' }} /></span>
                  <button className="link" onClick={() => api.cancelJob(j.id)}>Cancel</button>
                </div>
              )}
              <div className="muted">{j.message || (j.status === 'running' ? 'Starting' : '')} {when(j.started)}</div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function AddPanel({ refresh, jobs, loadJobs }) {
  const [tab, setTab] = useState('files')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [q, setQ] = useState('')
  const [limit, setLimit] = useState(200)
  const [path, setPath] = useState('')
  const [wiki, setWiki] = useState(20000)
  const files = useRef(null)
  const running = jobs.some((j) => j.status === 'running')

  async function go(fn) {
    setError(''); setMsg(''); setBusy(true)
    try { await fn() } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const upload = () => go(async () => {
    const list = Array.from(files.current.files)
    if (!list.length) throw new Error('Choose at least one file first.')
    const r = await api.upload(list)
    setMsg(`Added ${r.added}, skipped ${r.skipped} already in the library or too short` +
      (r.failed.length ? `, could not read ${r.failed.map((f) => f.name).join(', ')}.` : '.'))
    files.current.value = ''
    refresh()
  })
  const start = (fn) => go(async () => { await fn(); setMsg('Import started. Progress appears below.'); loadJobs() })

  return (
    <section>
      <h2>Add documents</h2>
      <div className="tabs" role="tablist">
        {[['files', 'Your files'], ['search', 'arXiv search'], ['dataset', 'arXiv dataset file'], ['wiki', 'Wikipedia']].map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} onClick={() => { setTab(id); setMsg(''); setError('') }}>{label}</button>
        ))}
      </div>

      {tab === 'files' && (
        <div className="panel">
          <p>Add papers you cite, open-access full texts, or your own earlier work. Full-text papers catch copying that abstracts cannot.</p>
          <input ref={files} type="file" multiple accept=".txt,.md,.docx,.pdf" />
          <div className="row"><button className="btn" onClick={upload} disabled={busy}>Add files</button></div>
        </div>
      )}
      {tab === 'search' && (
        <div className="panel">
          <p>Pull abstracts from arXiv for your topic. Use plain keywords or arXiv syntax such as cat:cs.CL. arXiv allows one request every 3 seconds, so 500 abstracts take about 20 seconds.</p>
          <div className="fields">
            <label className="field"><span>Topic or query</span>
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="blockchain digital learning" /></label>
            <label className="field small"><span>How many</span>
              <input type="number" min="1" max="5000" value={limit} onChange={(e) => setLimit(Number(e.target.value))} /></label>
          </div>
          <div className="row"><button className="btn" disabled={busy || running || q.trim().length < 2}
            onClick={() => start(() => api.startArxivSearch({ query: q, limit }))}>Import from arXiv</button></div>
        </div>
      )}
      {tab === 'dataset' && (
        <div className="panel">
          <p>For the full arXiv catalogue, download <em>arxiv-metadata-oai-snapshot.json</em> from the Kaggle dataset Cornell-University/arxiv, then enter its path on the machine running Overlap. It holds titles and abstracts only.</p>
          <div className="fields">
            <label className="field"><span>File path</span>
              <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="/data/arxiv-metadata-oai-snapshot.json" /></label>
            <label className="field small"><span>Limit (0 for all)</span>
              <input type="number" min="0" value={limit} onChange={(e) => setLimit(Number(e.target.value))} /></label>
          </div>
          <div className="row"><button className="btn" disabled={busy || running || !path.trim()}
            onClick={() => start(() => api.startArxivFile({ path: path.trim(), limit }))}>Import file</button></div>
        </div>
      )}
      {tab === 'wiki' && (
        <div className="panel">
          <p>Streams English Wikipedia articles from the Hugging Face dataset wikimedia/wikipedia. It needs the <em>datasets</em> package and an internet connection. Start with 20,000 articles; the full set is over six million.</p>
          <div className="fields">
            <label className="field small"><span>Articles</span>
              <input type="number" min="1" value={wiki} onChange={(e) => setWiki(Number(e.target.value))} /></label>
          </div>
          <div className="row"><button className="btn" disabled={busy || running}
            onClick={() => start(() => api.startWikipedia({ limit: wiki, config: '20231101.en' }))}>Import Wikipedia</button></div>
        </div>
      )}
      {msg && <p className="ok" role="status">{msg}</p>}
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  )
}

function Docs({ stats, tick }) {
  const [source, setSource] = useState('')
  const [q, setQ] = useState('')
  const [offset, setOffset] = useState(0)
  const [data, setData] = useState(null)
  const size = 20

  const load = useCallback(() => {
    api.docs({ source, q, limit: size, offset }).then(setData).catch(() => {})
  }, [source, q, offset, tick])
  useEffect(() => { load() }, [load])
  useEffect(() => { setOffset(0) }, [source, q])

  async function remove(d) {
    if (!window.confirm(`Remove "${d.title}" from the library?`)) return
    await api.deleteDoc(d.id)
    load()
  }

  return (
    <section>
      <h2>Documents</h2>
      <div className="fields">
        <label className="field small"><span>Library</span>
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">All</option>
            {stats?.sources.map((s) => <option key={s.source} value={s.source}>{sourceName(s.source)}</option>)}
          </select></label>
        <label className="field"><span>Title contains</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search titles" /></label>
      </div>
      {data && data.docs.length === 0 && <p className="muted">No documents match. Add some above.</p>}
      {data && data.docs.length > 0 && (
        <>
          <table className="table">
            <thead><tr><th>Title</th><th>Library</th><th className="num">Words</th><th>Added</th><th /></tr></thead>
            <tbody>
              {data.docs.map((d) => (
                <tr key={d.id}>
                  <td>{d.url ? <a href={d.url} target="_blank" rel="noreferrer">{d.title}</a> : d.title}</td>
                  <td>{sourceName(d.source)}</td>
                  <td className="num">{nf.format(d.words)}</td>
                  <td>{when(d.added)}</td>
                  <td className="num"><button className="link danger" onClick={() => remove(d)}>Remove</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pager">
            <span className="muted">{offset + 1} to {Math.min(offset + size, data.total)} of {nf.format(data.total)}</span>
            <button className="btn ghost sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - size))}>Previous</button>
            <button className="btn ghost sm" disabled={offset + size >= data.total} onClick={() => setOffset(offset + size)}>Next</button>
          </div>
        </>
      )}
    </section>
  )
}

export default function Library({ stats, refresh }) {
  const [jobs, setJobs] = useState([])
  const [tick, setTick] = useState(0)
  const loadJobs = useCallback(() => api.jobs().then(setJobs).catch(() => {}), [])
  useEffect(() => { loadJobs() }, [loadJobs])

  const running = jobs.some((j) => j.status === 'running')
  useEffect(() => {
    if (!running) return
    const t = setInterval(loadJobs, 1500)
    return () => clearInterval(t)
  }, [running, loadJobs])

  const done = useCallback(() => { refresh(); setTick((t) => t + 1) }, [refresh])

  return (
    <div className="narrow wide">
      <h1>Library</h1>
      <p className="lede">
        {stats
          ? `${nf.format(stats.documents)} documents, ${nf.format(stats.words)} words, ${nf.format(stats.fingerprints)} fingerprints, ${bytes(stats.bytes)} on disk.`
          : 'Loading.'}{' '}
        A check can only match what is in here, so a bigger library finds more.
      </p>
      {stats && stats.sources.length > 0 && (
        <table className="table compact">
          <thead><tr><th>Library</th><th className="num">Documents</th><th className="num">Words</th></tr></thead>
          <tbody>
            {stats.sources.map((s) => (
              <tr key={s.source}><td>{sourceName(s.source)}</td><td className="num">{nf.format(s.docs)}</td><td className="num">{nf.format(s.words)}</td></tr>
            ))}
          </tbody>
        </table>
      )}
      <AddPanel refresh={() => { refresh(); setTick((t) => t + 1) }} jobs={jobs} loadJobs={loadJobs} />
      <Jobs jobs={jobs} onDone={done} />
      <Docs stats={stats} tick={tick} />
    </div>
  )
}
