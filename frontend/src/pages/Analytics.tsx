import { lazy, Suspense, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { downloadCsv, downloadPdf, money, pct, type Segment, type SegmentKey } from '../lib/api'
import { useData } from '../lib/store'
import { Status } from '../components/Status'

const Scene = lazy(() => import('../components/Scene'))
const COMPARE: [string, string, (v: number, c: string) => string][] = [
  ['Typical total spend', 'total_spend', money], ['Typical order value', 'avg_order_value', money],
  ['Typical orders', 'orders', v => `${Math.round(v)}`], ['Last purchase', 'recency_days', v => `${Math.round(v)} days ago`],
  ['Time as a customer', 'tenure_days', v => `${Math.round(v)} days`], ['Different products', 'product_variety', v => `${Math.round(v)}`],
]

function Share({ segments }: { segments: Segment[] }) {
  const [tip, setTip] = useState<string>('')
  const max = Math.max(...segments.flatMap(s => [s.customer_share, s.revenue_share]))
  return (
    <div className="panel">
      <h2>Who brings in the money</h2>
      <div className="legend"><span><i style={{ background: '#6f5546' }} />Share of customers</span><span><i className="grad" />Share of revenue</span></div>
      <div className="bars">
        {segments.map(s => (
          <div className="bar-row" key={s.key}>
            <span className="bar-name">{s.name}</span>
            <div className="bar-track" onMouseEnter={() => setTip(`${s.name}: ${pct(s.customer_share)} of customers, ${pct(s.revenue_share)} of revenue`)} onMouseLeave={() => setTip('')}>
              <div className="bar b1" style={{ width: `${s.customer_share / max * 88}%` }}><b>{pct(s.customer_share)}</b></div>
              <div className="bar" style={{ width: `${s.revenue_share / max * 88}%`, background: s.color }}><b>{pct(s.revenue_share)}</b></div>
            </div>
          </div>
        ))}
      </div>
      <p className="muted tipline" aria-live="polite">{tip || 'Point at a group for the full numbers.'}</p>
    </div>
  )
}

export default function Analytics() {
  const { analysis: a, reset } = useData()
  const [focus, setFocus] = useState<SegmentKey | null>(null); const [pdfErr, setPdfErr] = useState('')
  const [left, setLeft] = useState<SegmentKey>('vip'); const [right, setRight] = useState<SegmentKey>('deal')
  const names = useMemo(() => Object.fromEntries((a?.segments ?? []).map(s => [s.key, s.name])), [a])
  if (!a) return <main className="page"><Status /></main>
  const L = a.segments.find(s => s.key === left)!; const R = a.segments.find(s => s.key === right)!
  const seg = a.segments.filter(s => s.customers > 0)
  return (
    <main className="page">
      <header className="head row-between">
        <div><h1>Analytics</h1><p>{a.customers.toLocaleString('en-GB')} customers, {money(a.total_revenue, a.currency)} revenue. {a.source.label}.</p></div>
        <div className="cta tight">
          {a.source.kind !== 'baseline' && <button className="ghost small" onClick={reset}>Back to the demo store</button>}
          <button className="ghost small" onClick={() => downloadCsv(a)}>Download CSV</button>
          <button className="primary small" onClick={() => { setPdfErr(''); downloadPdf(a).catch(e => setPdfErr(e.message)) }}>Download PDF</button>
        </div>
      </header>
      {pdfErr && <p className="error" role="alert">{pdfErr}</p>}
      <section className="panel flush">
        <Suspense fallback={<div className="scene big" />}><div className="big-wrap"><Scene points={a.points} focus={focus} currency={a.currency} names={names} /></div></Suspense>
        <div className="scene-bar">
          <p className="muted">Each bead is one real customer. Drag to turn it. Beads close together behave alike.</p>
          <div className="chips">
            {seg.map(s => <button key={s.key} aria-pressed={focus === s.key} className={focus === s.key ? 'chip on' : 'chip'} onClick={() => setFocus(focus === s.key ? null : s.key)}><i style={{ background: s.color }} />{s.name}</button>)}
          </div>
        </div>
      </section>
      <div className="two">
        <Share segments={a.segments} />
        <div className="panel">
          <h2>Compare two groups</h2>
          <div className="pick">
            <select aria-label="First group" value={left} onChange={e => setLeft(e.target.value as SegmentKey)}>{a.segments.map(s => <option key={s.key} value={s.key}>{s.name}</option>)}</select>
            <select aria-label="Second group" value={right} onChange={e => setRight(e.target.value as SegmentKey)}>{a.segments.map(s => <option key={s.key} value={s.key}>{s.name}</option>)}</select>
          </div>
          <table className="plain"><tbody>{COMPARE.map(([label, key, f]) => (
            <tr key={key}><th scope="row">{label}</th><td className="n">{L.medians[key] === undefined ? 'None' : f(L.medians[key], a.currency)}</td><td className="n">{R.medians[key] === undefined ? 'None' : f(R.medians[key], a.currency)}</td></tr>
          ))}</tbody></table>
        </div>
      </div>
      <section className="panel">
        <h2>Contact these customers first</h2>
        <p className="muted">Valuable customers who have gone quiet, and new customers worth a second order.</p>
        {a.priority.length === 0 ? <p>No urgent follow-ups were found in this data.</p> : (
          <div className="tablebox"><table>
            <thead><tr><th>Customer</th><th>Group</th><th className="n">Spend</th><th>Why now</th><th>Next step</th></tr></thead>
            <tbody>{a.priority.slice(0, 10).map(p => <tr key={p.customer_id}><td>{p.customer_id}</td><td>{names[p.segment]}</td><td className="n">{money(p.total_spend, a.currency)}</td><td>{p.reason}</td><td>{p.action}</td></tr>)}</tbody>
          </table></div>
        )}
        <Link className="textlink" to="/personas">See what to say to each group</Link>
      </section>
    </main>
  )
}
