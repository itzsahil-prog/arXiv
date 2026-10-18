import { useEffect, useRef, useState } from 'react'
import { api, nf, sourceName } from '../api.js'
import Report from '../Report.jsx'

export default function Check({ stats, goLibrary }) {
  const [mode, setMode] = useState('file')
  const [file, setFile] = useState(null)
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [opts, setOpts] = useState({ exclude_references: true, exclude_quotes: true, min_words: 8 })
  const [phase, setPhase] = useState('idle') // idle | running | done
  const [error, setError] = useState('')
  const [check, setCheck] = useState(null)
  const [secs, setSecs] = useState(0)
  const [drag, setDrag] = useState(false)
  const input = useRef(null)

  useEffect(() => {
    if (phase !== 'running') return
    setSecs(0)
    const t = setInterval(() => setSecs((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [phase])

  const empty = stats && stats.documents === 0
  const ready = mode === 'file' ? !!file : text.trim().split(/\s+/).length >= 20

  async function run() {
    setError('')
    setPhase('running')
    const f = new FormData()
    f.append('title', title)
    f.append('min_words', String(opts.min_words || 8))
    f.append('exclude_quotes', String(opts.exclude_quotes))
    f.append('exclude_references', String(opts.exclude_references))
    if (mode === 'file') f.append('file', file)
    else f.append('text', text)
    try {
      setCheck(await api.check(f))
      setPhase('done')
    } catch (e) {
      setError(e.message)
      setPhase('idle')
    }
  }

  function pick(files) {
    if (files && files[0]) setFile(files[0])
  }

  if (phase === 'done' && check) {
    return (
      <div>
        <p className="crumb">{check.title}, saved to History</p>
        <Report
          check={check}
          actions={
            <>
              <a className="btn ghost" href={`/api/checks/${check.id}/report`} download>Download report</a>
              <button className="btn ghost" onClick={() => { setPhase('idle'); setCheck(null) }}>Check another paper</button>
            </>
          }
        />
      </div>
    )
  }

  return (
    <div className="narrow">
      <h1>Check a paper</h1>
      <p className="lede">
        Find passages that match your reference library, then quote, cite, or rewrite them before you submit.
      </p>

      {stats && (
        <p className={'status' + (empty ? ' warn' : '')}>
          {empty ? (
            <>
              Your library is empty, so nothing can match yet.{' '}
              <button className="link" onClick={goLibrary}>Add reference documents</button>
            </>
          ) : (
            <>
              Checking against {nf.format(stats.documents)} documents:{' '}
              {stats.sources.map((s) => `${sourceName(s.source)} ${nf.format(s.docs)}`).join(', ')}.
            </>
          )}
        </p>
      )}

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={mode === 'file'} onClick={() => setMode('file')}>Upload a file</button>
        <button role="tab" aria-selected={mode === 'text'} onClick={() => setMode('text')}>Paste text</button>
      </div>

      {mode === 'file' ? (
        <label
          className={'drop' + (drag ? ' over' : '')}
          onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files) }}
        >
          <input ref={input} type="file" accept=".docx,.pdf,.txt,.md" onChange={(e) => pick(e.target.files)} />
          {file ? (
            <span><strong>{file.name}</strong><br />{(file.size / 1024).toFixed(0)} KB. Choose another file to replace it.</span>
          ) : (
            <span><strong>Drop your paper here</strong><br />or choose a .docx, .pdf, .txt or .md file</span>
          )}
        </label>
      ) : (
        <textarea
          className="paste"
          placeholder="Paste at least 20 words of your paper"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={12}
        />
      )}

      <div className="fields">
        <label className="field">
          <span>Title (optional)</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Name this check" />
        </label>
        <label className="field small">
          <span>Ignore matches under</span>
          <span className="inline">
            <input
              type="number" min="8" max="50" value={opts.min_words}
              onChange={(e) => setOpts({ ...opts, min_words: Number(e.target.value) })}
            /> words
          </span>
        </label>
      </div>

      <div className="checks">
        <label>
          <input type="checkbox" checked={opts.exclude_references}
            onChange={(e) => setOpts({ ...opts, exclude_references: e.target.checked })} />
          Leave out the references section
        </label>
        <label>
          <input type="checkbox" checked={opts.exclude_quotes}
            onChange={(e) => setOpts({ ...opts, exclude_quotes: e.target.checked })} />
          Leave out text in quotation marks
        </label>
      </div>

      {error && <p className="error" role="alert">{error}</p>}

      <div className="row">
        <button className="btn" onClick={run} disabled={!ready || phase === 'running' || empty}>
          {phase === 'running' ? 'Checking' : 'Check paper'}
        </button>
        {phase === 'running' && (
          <span className="running" role="status">
            <span className="progress"><i /></span>
            Comparing with your library, {secs}s
          </span>
        )}
      </div>
    </div>
  )
}
