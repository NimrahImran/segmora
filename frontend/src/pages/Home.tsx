import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { IMG, IMG_ALT, pct, sendContact, type SegmentKey } from '../lib/api'
import { useData } from '../lib/store'

const CARDS: [SegmentKey, string, string, string][] = [
  ['vip', 'c1', 'VIP Shopper', 'Loves luxury, spends the most'],
  ['regular', 'c2', 'Loyal Regular', 'Comes back like a daily coffee'],
  ['deal', 'c3', 'Deal Hunter', 'Saves money, waits for sales'],
  ['new', 'c4', 'New Customer', 'Just started, ready to grow'],
]
const STEPS = [
  ['Add your customers', 'Upload a CSV or Excel file, or describe one customer.'],
  ['See the groups', 'Every customer lands in a group, with the reason in plain words.'],
  ['Know what to do', 'Get a profile, a ready message, and who to contact first.'],
]

function Hire() {
  const [state, setState] = useState<'idle' | 'busy' | 'done'>('idle'); const [err, setErr] = useState('')
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault(); const form = e.currentTarget; const d = new FormData(form)
    setState('busy'); setErr('')
    try {
      await sendContact({ name: String(d.get('name')), email: String(d.get('email')), message: String(d.get('message')), botcheck: d.get('company') !== '' })
      setState('done'); form.reset()
    } catch (x) { setErr((x as Error).message); setState('idle') }
  }
  return (
    <section className="hire" id="hire">
      <div><h2>Want this for your business?</h2><p>Tell me about your customers and what you want to learn from them. I reply by email.</p></div>
      {state === 'done' ? <p className="sent" role="status">Thank you. Your message has been sent.</p> : (
        <form onSubmit={submit}>
          <label>Your name<input name="name" required minLength={2} maxLength={100} autoComplete="name" /></label>
          <label>Your email<input name="email" type="email" required maxLength={200} autoComplete="email" /></label>
          <label className="wide">Your message<textarea name="message" required minLength={10} maxLength={5000} rows={5} /></label>
          <input className="trap" name="company" tabIndex={-1} autoComplete="off" aria-hidden="true" defaultValue="" />
          {err && <p className="error wide" role="alert">{err}</p>}
          <button className="primary wide-btn" disabled={state === 'busy'}>{state === 'busy' ? 'Sending' : 'Send message'}</button>
        </form>
      )}
    </section>
  )
}

export default function Home() {
  const { analysis } = useData()
  useEffect(() => { if (location.hash === '#hire') document.getElementById('hire')?.scrollIntoView() }, [])
  const vip = analysis?.segments.find(s => s.key === 'vip')
  return (
    <main>
      <section className="stage">
        <div className="copy">
          <h1 className="display">See who your customers really are.</h1>
          <p>Upload your customer list and Segmora sorts it into clear groups, then shows how each group lives, buys and responds.</p>
          <div className="cta"><Link className="primary" to="/personas">Explore segments</Link><Link className="ghost" to="/analytics">View analytics</Link></div>
        </div>
        <svg className="lines" viewBox="0 0 1920 1080" preserveAspectRatio="none" aria-hidden="true" fill="none" stroke="#efc69c" strokeWidth="1.4">
          <path d="M1100 215 L1160 300" /><circle cx="1160" cy="300" r="5" fill="#efc69c" />
          <path d="M1560 240 L1520 330" /><circle cx="1520" cy="330" r="5" fill="#efc69c" />
          <path d="M1085 790 L1170 720" /><circle cx="1170" cy="720" r="5" fill="#efc69c" />
          <path d="M1575 835 L1530 730" /><circle cx="1530" cy="730" r="5" fill="#efc69c" />
        </svg>
        {CARDS.map(([k, c, n, t]) => (
          <Link key={k} className={`card ${c}`} to={`/personas?segment=${k}`}><img src={IMG[k]} alt={IMG_ALT[k]} /><div><strong>{n}</strong><span>{t}</span></div></Link>
        ))}
        <div className="art" aria-hidden="true">
          <svg viewBox="0 0 100 100" fill="none" stroke="#efc69c" strokeWidth=".45">
            <path d="M25 0 L33 17" /><circle cx="33" cy="17" r="1.1" fill="#efc69c" /><path d="M75 0 L66 18" /><circle cx="66" cy="18" r="1.1" fill="#efc69c" />
            <path d="M25 100 L33 63" /><circle cx="33" cy="63" r="1.1" fill="#efc69c" /><path d="M75 100 L65 63" /><circle cx="65" cy="63" r="1.1" fill="#efc69c" />
          </svg>
        </div>
      </section>
      {vip && (
        <section className="statement">
          <p className="big">In a real store of {analysis!.customers.toLocaleString('en-GB')} customers, {pct(vip.customer_share)} of them brought in {pct(vip.revenue_share)} of the revenue.</p>
          <Link className="textlink" to="/analytics">See how the groups compare</Link>
        </section>
      )}
      <section className="steps">
        {STEPS.map(([t, d], i) => <div key={t}><span className="num">{i + 1}</span><h2>{t}</h2><p>{d}</p></div>)}
      </section>
      <Hire />
    </main>
  )
}
