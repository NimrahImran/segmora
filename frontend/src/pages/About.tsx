import { useEffect, useState } from 'react'
import { getModelCard, type ModelCard } from '../lib/api'

const REPO = 'https://github.com/NimrahImran/segmora'
const PIPE = [
  ['Clean', 'Remove returns and invalid lines from 541,909 invoice lines.'],
  ['Summarise', 'Build one row per customer: recency, orders, spend, tenure, variety, order value.'],
  ['Scale', 'Log transform for skew, then standardise.'],
  ['Compare', 'K-Means, Gaussian Mixture and Ward, each with 3 to 6 groups.'],
  ['Name', 'Rules assign business names from measured behaviour.'],
  ['Serve', 'FastAPI returns a segment, match strength and reasons.'],
]
const ENDPOINTS = [
  ['POST', '/api/predict', 'Segment one customer'], ['POST', '/api/analyze', 'Segment a CSV or Excel file'],
  ['GET', '/api/analysis', 'Demo store: segments, 3D points, priority list'], ['POST', '/api/personas', 'Write a persona from group averages'],
  ['POST', '/api/report.pdf', 'PDF report'], ['GET', '/api/model', 'Model card as JSON'],
]
const CURL = `curl -X POST ${location.origin}/api/predict \\
  -H "Content-Type: application/json" \\
  -d '{"recency_days":5,"orders":20,"total_spend":15000,"tenure_days":360,"product_variety":200}'`

function Technical() {
  const [m, setM] = useState<ModelCard | null>(null); const [err, setErr] = useState('')
  useEffect(() => { getModelCard().then(setM).catch(e => setErr(e.message)) }, [])
  if (err) return <p className="error">{err}</p>
  if (!m) return <p className="muted">Loading model details</p>
  const rows = m.comparison
  const best = Math.max(...rows.map(r => r.silhouette))
  return (
    <div className="tech">
      <section className="panel">
        <h2>How the model is built</h2>
        <ol className="pipe">{PIPE.map(([t, d]) => <li key={t}><strong>{t}</strong><span>{d}</span></li>)}</ol>
      </section>
      <div className="two">
        <section className="panel">
          <h2>Dataset</h2>
          <dl className="facts-list">
            <div><dt>Source</dt><dd><a href="https://archive.ics.uci.edu/dataset/352/online+retail">UCI Online Retail</a></dd></div>
            <div><dt>Period</dt><dd>December 2010 to December 2011</dd></div>
            <div><dt>Customers</dt><dd>{m.customers.toLocaleString('en-GB')}</dd></div>
            <div><dt>Features</dt><dd>{m.features.join(', ')}</dd></div>
            <div><dt>Trained</dt><dd>{m.trained_on}</dd></div>
          </dl>
        </section>
        <section className="panel">
          <h2>Final model</h2>
          <dl className="facts-list">
            <div><dt>Algorithm</dt><dd>{m.chosen.algorithm}, {m.chosen.k} groups</dd></div>
            <div><dt>Stability</dt><dd>ARI {m.stability_ari_mean} on average, {m.stability_ari_min} at worst, over 20 refits on 80% of customers</dd></div>
            <div><dt>3D view</dt><dd>PCA, showing {Math.round(m.pca_explained.reduce((a, b) => a + b, 0) * 100)}% of the variation</dd></div>
            <div><dt>Persona AI</dt><dd>{m.persona_ai ? 'Gemini, group averages only' : 'Standard profiles, no AI key set'}</dd></div>
          </dl>
        </section>
      </div>
      <section className="panel">
        <h2>Algorithm comparison</h2>
        <div className="tablebox"><table>
          <thead><tr><th>Algorithm</th><th className="n">Groups</th><th className="n">Silhouette</th><th className="n">Davies-Bouldin</th><th className="n">Calinski-Harabasz</th><th className="n">Smallest group</th></tr></thead>
          <tbody>{rows.map(r => {
            const chosen = r.algorithm === m.chosen.algorithm && r.k === m.chosen.k
            return <tr key={r.algorithm + r.k} className={chosen ? 'chosen' : ''}><td>{r.algorithm}{chosen ? ' (used)' : ''}</td><td className="n">{r.k}</td><td className="n">{r.silhouette === best ? <b>{r.silhouette}</b> : r.silhouette}</td><td className="n">{r.davies_bouldin}</td><td className="n">{r.calinski_harabasz}</td><td className="n">{Math.round(r.smallest_group * 100)}%</td></tr>
          })}</tbody>
        </table></div>
      </section>
      <section className="panel">
        <h2>Known limits</h2>
        <ul className="limits">{m.limits.map(l => <li key={l}>{l}</li>)}</ul>
      </section>
      <section className="panel">
        <div className="row-between"><h2>API</h2><div className="cta tight"><a className="ghost small" href="/api/docs">Open API docs</a><a className="ghost small" href={REPO}>View code on GitHub</a></div></div>
        <div className="tablebox"><table><tbody>{ENDPOINTS.map(([v, p, d]) => <tr key={p}><td><code>{v}</code></td><td><code>{p}</code></td><td>{d}</td></tr>)}</tbody></table></div>
        <pre><code>{CURL}</code></pre>
      </section>
    </div>
  )
}

export default function About() {
  const [tech, setTech] = useState(false)
  return (
    <main className="page">
      <header className="head"><h1>About Segmora</h1><p>A clear view of your customers, without a data team.</p></header>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={!tech} className={!tech ? 'on' : ''} onClick={() => setTech(false)}>Overview</button>
        <button role="tab" aria-selected={tech} className={tech ? 'on' : ''} onClick={() => setTech(true)}>Technical view</button>
      </div>
      {tech ? <Technical /> : (
        <section className="about">
          <p className="lede">A shopkeeper knows which customers come every week and which only come for a sale. Segmora gives any business that same knowledge, even with thousands of customers.</p>
          <p>It looks at what people really did: how recently they bought, how often, and how much. Customers who behave alike land in the same group, and each group gets a clear profile with a suggested next step.</p>
          <p>Uploaded files are read once and never saved. Only columns needed for the analysis are used, so names, emails and phone numbers are ignored.</p>
          <p className="by">Built by Nimra Imran, AI Engineer.</p>
        </section>
      )}
    </main>
  )
}
