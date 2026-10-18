import { useEffect, useState } from 'react'
import { api, nf, when } from '../api.js'
import Report from '../Report.jsx'

export default function History() {
  const [rows, setRows] = useState(null)
  const [open, setOpen] = useState(null)
  const [error, setError] = useState('')

  const load = () => api.checks().then(setRows).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  async function view(id) {
    setError('')
    try { setOpen(await api.getCheck(id)) } catch (e) { setError(e.message) }
  }
  async function remove(id) {
    if (!window.confirm('Delete this check and its report?')) return
    await api.deleteCheck(id)
    setOpen(null)
    load()
  }

  if (open) {
    return (
      <div>
        <p className="crumb">
          <button className="link" onClick={() => setOpen(null)}>History</button> / {open.title}
        </p>
        <Report
          check={open}
          actions={
            <>
              <a className="btn ghost" href={`/api/checks/${open.id}/report`} download>Download report</a>
              <button className="btn ghost danger" onClick={() => remove(open.id)}>Delete check</button>
            </>
          }
        />
      </div>
    )
  }

  return (
    <div className="narrow wide">
      <h1>History</h1>
      <p className="lede">Every check is saved with its highlights, so you can compare drafts as you revise.</p>
      {error && <p className="error" role="alert">{error}</p>}
      {rows && rows.length === 0 && <p className="muted">No checks yet. Check a paper and it will appear here.</p>}
      {rows && rows.length > 0 && (
        <table className="table">
          <thead>
            <tr><th>Paper</th><th>Checked</th><th className="num">Similarity</th><th className="num">Words</th><th className="num">Sources</th><th /></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td><button className="link strong" onClick={() => view(r.id)}>{r.title}</button></td>
                <td>{when(r.created)}</td>
                <td className="num">{r.similarity.toFixed(1)}%</td>
                <td className="num">{nf.format(r.total_words)}</td>
                <td className="num">{r.source_count}</td>
                <td className="num"><button className="link danger" onClick={() => remove(r.id)}>Delete</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
