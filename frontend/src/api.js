async function req(path, opts) {
  const r = await fetch('/api' + path, opts)
  if (!r.ok) {
    let msg = r.statusText
    try {
      const j = await r.json()
      msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch { /* keep status text */ }
    throw new Error(msg)
  }
  return r.json()
}

const post = (path, body) =>
  req(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  stats: () => req('/library/stats'),
  docs: (p) => req('/library/docs?' + new URLSearchParams(p)),
  deleteDoc: (id) => req('/library/docs/' + id, { method: 'DELETE' }),
  upload: (files) => {
    const f = new FormData()
    files.forEach((x) => f.append('files', x))
    return req('/library/upload', { method: 'POST', body: f })
  },
  startArxivFile: (b) => post('/jobs/arxiv-file', b),
  startArxivSearch: (b) => post('/jobs/arxiv-search', b),
  startWikipedia: (b) => post('/jobs/wikipedia', b),
  jobs: () => req('/jobs'),
  cancelJob: (id) => req(`/jobs/${id}/cancel`, { method: 'POST' }),
  check: (form) => req('/checks', { method: 'POST', body: form }),
  checks: () => req('/checks'),
  getCheck: (id) => req('/checks/' + id),
  deleteCheck: (id) => req('/checks/' + id, { method: 'DELETE' }),
}

export const nf = new Intl.NumberFormat()
export const when = (t) =>
  new Date(t * 1000).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
export function bytes(n) {
  if (n < 1024 * 1024) return Math.max(1, Math.round(n / 1024)) + ' KB'
  if (n < 1024 ** 3) return (n / 1024 ** 2).toFixed(1) + ' MB'
  return (n / 1024 ** 3).toFixed(2) + ' GB'
}
export const sourceName = (s) => ({ arxiv: 'arXiv', wikipedia: 'Wikipedia', files: 'Your files' }[s] || s)
export const HUES = [205, 28, 150, 330, 265, 48, 180, 0, 100, 300]
