import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getPersona, IMG, IMG_ALT, type Persona, type SegmentKey } from '../lib/api'
import { useData } from '../lib/store'
import { Status } from '../components/Status'

export default function Personas() {
  const { analysis: a } = useData()
  const [params, setParams] = useSearchParams()
  const key = (params.get('segment') ?? 'vip') as SegmentKey
  const [p, setP] = useState<Persona | null>(null); const [err, setErr] = useState(''); const [busy, setBusy] = useState(false)
  const [channel, setChannel] = useState<'email' | 'whatsapp'>('whatsapp'); const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!a) return
    let live = true; setBusy(true); setErr(''); setCopied(false)
    const seg = a.segments.find(s => s.key === key)
    if (!seg) { setBusy(false); setErr('This group does not exist.'); return }
    getPersona(seg, a.currency).then(x => live && setP(x)).catch(e => { if (live) { setErr(e.message); setP(null) } }).finally(() => live && setBusy(false))
    return () => { live = false }
  }, [key, a])
  if (!a) return <main className="page"><Status /></main>
  const message = !p ? '' : channel === 'email' ? `${p.offer.subject}\n\n${p.offer.email}` : p.offer.whatsapp
  const copy = async () => { await navigator.clipboard.writeText(message); setCopied(true) }
  return (
    <main className="page">
      <header className="head"><h1>AI Persona</h1><p>Meet each group as if it were one person.</p></header>
      <div className="persona-tabs" role="tablist">
        {a.segments.map(s => (
          <button key={s.key} role="tab" aria-selected={s.key === key} className={s.key === key ? 'on' : ''} onClick={() => setParams({ segment: s.key })}>
            <img src={IMG[s.key]} alt="" /><span>{s.name}</span>
          </button>
        ))}
      </div>
      {err && <p className="error" role="alert">{err}</p>}
      {p && (
        <article className={busy ? 'persona dim' : 'persona'}>
          <div className="identity">
            <img src={IMG[p.key]} alt={IMG_ALT[p.key]} />
            <h2>{p.name}</h2><p>{p.tagline}</p>
            <dl>{p.observed.map(o => <div key={o.label}><dt>{o.label}</dt><dd>{o.value}</dd></div>)}</dl>
            <p className="muted small">These numbers are measured from the data.</p>
          </div>
          <div className="story">
            <p className="lede">{p.story}</p>
            <p className="day">{p.day}</p>
            <div className="two-lists">
              <div><h3>What they like</h3><ul>{p.likes.map(x => <li key={x}>{x}</li>)}</ul></div>
              <div><h3>What puts them off</h3><ul>{p.frustrations.map(x => <li key={x}>{x}</li>)}</ul></div>
            </div>
            <div className="offer">
              <div className="row-between"><h3>Ready to send</h3>
                <div className="tabs mini" role="tablist">
                  <button role="tab" aria-selected={channel === 'whatsapp'} className={channel === 'whatsapp' ? 'on' : ''} onClick={() => { setChannel('whatsapp'); setCopied(false) }}>WhatsApp</button>
                  <button role="tab" aria-selected={channel === 'email'} className={channel === 'email' ? 'on' : ''} onClick={() => { setChannel('email'); setCopied(false) }}>Email</button>
                </div></div>
              <p className="message">{message}</p>
              <p className="muted small hint">Replace [your offer] with your real offer before sending.</p>
              <button className="primary small" onClick={copy}>{copied ? 'Copied' : 'Copy message'}</button>
            </div>
            <p className="muted small">{p.source === 'gemini' ? 'Written by AI from the group averages. Lifestyle details are an informed guess.' : 'Standard profile. Lifestyle details are an informed guess, not measured.'}</p>
          </div>
        </article>
      )}
    </main>
  )
}
