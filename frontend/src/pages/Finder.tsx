import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { analyzeFile, API, ApiError, downloadCsv, downloadPdf, IMG, IMG_ALT, money, predict, type Analysis, type CustomerInput, type Prediction, type Row, type SegmentKey } from '../lib/api'
import { useData } from '../lib/store'
import { Status } from '../components/Status'

const Scene = lazy(() => import('../components/Scene'))
const FIELD_LABEL: Record<string, string> = {
  customer_id: 'Customer ID', recency_days: 'Days since last purchase', orders: 'Number of orders', total_spend: 'Total spend',
  invoice: 'Invoice or order number', invoice_date: 'Order date', quantity: 'Quantity', unit_price: 'Unit price',
}
const SLIDERS: { key: keyof CustomerInput; label: string; min: number; max: number; step: number; unit?: string; log?: boolean }[] = [
  { key: 'recency_days', label: 'Days since last purchase', min: 0, max: 370, step: 1 },
  { key: 'orders', label: 'Number of orders', min: 1, max: 60, step: 1 },
  { key: 'total_spend', label: 'Total spend', min: 20, max: 30000, step: 10, unit: '£', log: true },
  { key: 'tenure_days', label: 'Days as a customer', min: 0, max: 370, step: 1 },
  { key: 'product_variety', label: 'Different products bought', min: 1, max: 300, step: 1 },
]
const toPos = (v: number, min: number, max: number) => Math.log(v / min) / Math.log(max / min)
const fromPos = (p: number, min: number, max: number) => Math.round(min * Math.pow(max / min, p) / 10) * 10

function One() {
  const { baseline: analysis } = useData()
  const [c, setC] = useState<CustomerInput>({ recency_days: 12, orders: 9, total_spend: 4200, tenure_days: 320, product_variety: 90 })
  const [r, setR] = useState<Prediction | null>(null); const [err, setErr] = useState('')
  useEffect(() => {
    const ctl = new AbortController()
    const t = setTimeout(() => predict({ ...c, tenure_days: Math.max(c.tenure_days, c.recency_days) }, ctl.signal)
      .then(x => { setR(x); setErr('') }).catch(e => { if (e instanceof ApiError) setErr(e.message) }), 160)
    return () => { clearTimeout(t); ctl.abort() }
  }, [c])
  const names = useMemo(() => Object.fromEntries((analysis?.segments ?? []).map(s => [s.key, s.name])), [analysis])
  return (
    <div className="split">
      <div className="panel">
        <h2>Describe one customer</h2>
        <p className="muted">Move a slider and watch the group change.</p>
        {SLIDERS.map(s => {
          const v = c[s.key]
          return (
            <label className="slider" key={s.key}>
              <span>{s.label}<b>{s.unit}{v.toLocaleString('en-GB')}</b></span>
              {s.log
                ? <input type="range" min={0} max={1000} value={Math.round(toPos(v, s.min, s.max) * 1000)} onChange={e => setC({ ...c, [s.key]: fromPos(+e.target.value / 1000, s.min, s.max) })} />
                : <input type="range" min={s.min} max={s.max} step={s.step} value={v} onChange={e => setC({ ...c, [s.key]: +e.target.value })} />}
            </label>
          )
        })}
      </div>
      <div className="panel flush">
        {analysis && <Suspense fallback={<div className="scene" />}><Scene points={analysis.points} marker={r?.position} currency={analysis.currency} names={names} /></Suspense>}
        {err && <p className="error" role="alert">{err}</p>}
        {r && (
          <div className="result" aria-live="polite">
            <img className="round" src={IMG[r.segment]} alt={IMG_ALT[r.segment]} />
            <div className="result-main">
              <p className="muted">This customer is a</p>
              <h3>{r.name}</h3>
              <p>{r.tagline}</p>
              <div className="strength"><span>Match strength</span><i><em style={{ width: `${r.strength * 100}%` }} /></i><b>{Math.round(r.strength * 100)}%</b></div>
              <ul className="reasons">{r.reasons.map(x => <li key={x.feature}>{reason(x)}</li>)}</ul>
              <Link className="textlink" to={`/personas?segment=${r.segment}`}>Open this group's profile</Link>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
function reason(x: Prediction['reasons'][number]) {
  const value = x.feature.includes('spend') || x.feature.includes('value') ? `£${Math.round(x.value).toLocaleString('en-GB')}` : Math.round(x.value).toLocaleString('en-GB')
  const side = x.percentile >= 50 ? `Higher than ${x.percentile}% of customers` : `Lower than ${100 - x.percentile}% of customers`
  return <><b>{x.label[0].toUpperCase() + x.label.slice(1)}: {value}.</b> {side}.</>
}

function Bulk() {
  const { setAnalysis } = useData(); const nav = useNavigate()
  const [file, setFile] = useState<File | null>(null); const [mode, setMode] = useState('standard')
  const [busy, setBusy] = useState(false); const [err, setErr] = useState('')
  const [columns, setColumns] = useState<string[]>([]); const [missing, setMissing] = useState<string[]>([]); const [map, setMap] = useState<Record<string, string>>({})
  const [res, setRes] = useState<Analysis | null>(null)
  const run = async (f: File, m: Record<string, string>) => {
    setBusy(true); setErr(''); setRes(null)
    try { const a = await analyzeFile(f, mode, m); setRes(a); setAnalysis(a); setMissing([]); setColumns([]) }
    catch (e) { const x = e as ApiError; setErr(x.message); setColumns(x.columns ?? []); setMissing(x.missing ?? []) }
    finally { setBusy(false) }
  }
  const pick = (f?: File | null) => {
    if (!f) return
    if (f.size > 4 * 1024 * 1024) { setFile(null); setErr('This file is larger than 4 MB. Split it or keep one row per customer.'); return }
    setFile(f); setMap({}); run(f, {})
  }
  const sample = async () => {
    setBusy(true); setErr('')
    try { const blob = await (await fetch(`${API}/api/sample.csv`)).blob(); pick(new File([blob], 'segmora_sample.csv', { type: 'text/csv' })) }
    catch { setErr('The sample file could not be loaded. Try again.'); setBusy(false) }
  }
  return (
    <div>
      <div className="panel">
        <label className="drop" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); pick(e.dataTransfer.files[0]) }}>
          <input type="file" accept=".csv,.xlsx,.xlsm,.txt" onChange={e => pick(e.target.files?.[0])} />
          <strong>{busy ? 'Sorting your customers' : file ? file.name : 'Drop your CSV or Excel file here'}</strong>
          <span>{busy ? 'This takes a few seconds.' : 'Or click to choose a file, up to 4 MB. Your file is not saved.'}</span>
        </label>
        <div className="row-between">
          <fieldset className="choice"><legend className="sr">How to sort</legend>
            <label><input type="radio" checked={mode === 'standard'} onChange={() => setMode('standard')} />Use the ready-made model</label>
            <label><input type="radio" checked={mode === 'own'} onChange={() => setMode('own')} />Find groups inside my data</label>
          </fieldset>
          <button className="ghost small" onClick={sample} disabled={busy}>Try sample data</button>
        </div>
        {err && <p className="error" role="alert">{err}</p>}
        {missing.length > 0 && file && (
          <div className="map">
            {missing.map(k => (
              <label key={k}>{FIELD_LABEL[k] ?? k}
                <select value={map[k] ?? ''} onChange={e => setMap({ ...map, [k]: e.target.value })}>
                  <option value="">Choose a column</option>{columns.map(c => <option key={c}>{c}</option>)}
                </select>
              </label>
            ))}
            <button className="primary small" disabled={missing.some(k => !map[k]) || busy} onClick={() => run(file, map)}>Sort customers</button>
          </div>
        )}
      </div>
      {res && <Results a={res} onOpen={() => nav('/analytics')} />}
    </div>
  )
}

function Results({ a, onOpen }: { a: Analysis; onOpen: () => void }) {
  const [pdfErr, setPdfErr] = useState(''); const [q, setQ] = useState(''); const [seg, setSeg] = useState<SegmentKey | ''>(''); const [page, setPage] = useState(0)
  const names = Object.fromEntries(a.segments.map(s => [s.key, s.name]))
  const rows = useMemo(() => a.table.filter((r: Row) => (!seg || r.segment === seg) && r.customer_id.toLowerCase().includes(q.toLowerCase())), [a, q, seg])
  const size = 12; const pages = Math.max(1, Math.ceil(rows.length / size))
  useEffect(() => setPage(0), [q, seg])
  return (
    <div className="panel results">
      <div className="row-between">
        <div><h2>{a.customers.toLocaleString('en-GB')} customers sorted</h2>
          <p className="muted">{a.source.shape === 'transactions' ? 'Order lines were combined into one row per customer.' : 'Read as one row per customer.'}{a.source.skipped ? ` ${a.source.skipped} rows skipped because values were missing.` : ''}{a.source.note ? ` ${a.source.note}` : ''}</p></div>
        <div className="cta tight"><button className="primary small" onClick={onOpen}>Open in Analytics</button>
          <button className="ghost small" onClick={() => downloadCsv(a)}>Download CSV</button><button className="ghost small" onClick={() => { setPdfErr(''); downloadPdf(a).catch(e => setPdfErr(e.message)) }}>Download PDF</button></div>
      </div>
      {pdfErr && <p className="error" role="alert">{pdfErr}</p>}
      <div className="seg-row">{a.segments.map(s => (
        <button key={s.key} className={seg === s.key ? 'seg on' : 'seg'} aria-pressed={seg === s.key} onClick={() => setSeg(seg === s.key ? '' : s.key)}>
          <img src={IMG[s.key]} alt="" /><span>{s.name}<b>{s.customers.toLocaleString('en-GB')}</b></span></button>))}
      </div>
      <input className="search" placeholder="Search customer ID" aria-label="Search customer ID" value={q} onChange={e => setQ(e.target.value)} />
      <div className="tablebox"><table>
        <thead><tr><th>Customer</th><th>Group</th><th className="n">Match</th><th className="n">Last purchase</th><th className="n">Orders</th><th className="n">Spend</th></tr></thead>
        <tbody>{rows.slice(page * size, page * size + size).map(r => (
          <tr key={r.customer_id}><td>{r.customer_id}</td><td>{names[r.segment]}</td><td className="n">{Math.round(r.strength * 100)}%</td><td className="n">{Math.round(r.recency_days)} days</td><td className="n">{r.orders}</td><td className="n">{money(r.total_spend, a.currency)}</td></tr>
        ))}{rows.length === 0 && <tr><td colSpan={6}>No customers match this search.</td></tr>}</tbody>
      </table></div>
      <div className="pager"><button className="ghost small" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button><span>Page {page + 1} of {pages}</span><button className="ghost small" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>Next</button></div>
    </div>
  )
}

export default function Finder() {
  const [tab, setTab] = useState<'one' | 'file'>('one')
  return (
    <main className="page">
      <header className="head"><h1>Segment Finder</h1><p>Find out which group a customer belongs to.</p></header>
      <Status />
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'one'} className={tab === 'one' ? 'on' : ''} onClick={() => setTab('one')}>One customer</button>
        <button role="tab" aria-selected={tab === 'file'} className={tab === 'file' ? 'on' : ''} onClick={() => setTab('file')}>Customer file</button>
      </div>
      {tab === 'one' ? <One /> : <Bulk />}
    </main>
  )
}
