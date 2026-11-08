export const API = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

export type SegmentKey = 'vip' | 'regular' | 'deal' | 'new'
export interface Segment {
  key: SegmentKey; name: string; tagline: string; color: string; customers: number
  customer_share: number; revenue: number; revenue_share: number
  medians: Record<string, number>
}
export interface Point { id: string; s: SegmentKey; x: number; y: number; z: number; spend: number; orders: number }
export interface Priority { customer_id: string; segment: SegmentKey; score: number; total_spend: number; reason: string; action: string }
export interface Row { customer_id: string; recency_days: number; orders: number; total_spend: number; tenure_days: number; product_variety: number; segment: SegmentKey; strength: number }
export interface Analysis {
  currency: string; customers: number; total_revenue: number; segments: Segment[]; points: Point[]
  priority: Priority[]; table: Row[]
  source: { kind: string; label: string; mode?: string; note?: string; skipped?: number; shape?: string }
}
export interface Prediction {
  segment: SegmentKey; name: string; tagline: string; strength: number
  reasons: { feature: string; label: string; value: number; percentile: number; direction: string }[]
  position: { x: number; y: number; z: number }
}
export interface Persona {
  key: SegmentKey; name: string; tagline: string; observed: { label: string; value: string }[]
  story: string; day: string; likes: string[]; frustrations: string[]
  offer: { subject: string; email: string; whatsapp: string }; source: 'gemini' | 'built_in'
}
export interface CustomerInput { recency_days: number; orders: number; total_spend: number; tenure_days: number; product_variety: number }

export class ApiError extends Error {
  constructor(message: string, public status: number, public columns: string[] = [], public missing: string[] = []) { super(message) }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try { res = await fetch(API + path, init) } catch (e) { if ((e as Error).name === 'AbortError') throw e; throw new ApiError('The server could not be reached. Check your connection and try again.', 0) }
  const body = await res.json().catch(e => { if (e.name === 'AbortError') throw e; return {} })
  if (!res.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : 'Some values are not valid.'
    throw new ApiError(detail, res.status, body.columns, body.missing)
  }
  if (Object.keys(body).length === 0) throw new ApiError('The server sent an empty reply. Try again.', res.status)
  return body as T
}

export const getAnalysis = () => request<Analysis>('/api/analysis')
const json = (body: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
export const predict = (c: CustomerInput, signal?: AbortSignal) =>
  request<Prediction>('/api/predict', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(c), signal })
export const getPersona = (segment: Segment, currency: string) => request<Persona>('/api/personas', json({ segment, currency }))
export const sendContact = (body: { name: string; email: string; message: string; botcheck: boolean }) => request<{ ok: boolean }>('/api/contact', json(body))
export const getModelCard = () => request<ModelCard>('/api/model')
export function analyzeFile(file: File, mode: string, mapping: Record<string, string>) {
  const form = new FormData()
  form.append('file', file); form.append('mode', mode); form.append('mapping', JSON.stringify(mapping))
  return request<Analysis>('/api/analyze', { method: 'POST', body: form })
}
export interface ModelCard {
  trained_on: string; customers: number; features: string[]; chosen: { algorithm: string; k: number }
  comparison: { algorithm: string; k: number; silhouette: number; davies_bouldin: number; calinski_harabasz: number; smallest_group: number }[]
  stability_ari_mean: number; stability_ari_min: number; pca_explained: number[]; limits: string[]; persona_ai: boolean
}
export const IMG: Record<SegmentKey, string> = { vip: '/img/vip.jpg', regular: '/img/regular.jpg', deal: '/img/deal.jpg', new: '/img/new.jpg' }
export const IMG_ALT: Record<SegmentKey, string> = {
  vip: 'A shopping bag and a jewel', regular: 'A cup of coffee and a loyalty card', deal: 'Stacks of coins', new: 'A young plant and a small gift',
}
function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const a = document.createElement('a')
  a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 2000)
}
export function downloadCsv(a: Analysis) {
  const cols = ['customer_id', 'segment', 'strength', 'recency_days', 'orders', 'total_spend', 'tenure_days', 'product_variety'] as const
  // A leading = + - @ would run as a formula when the file is opened in Excel.
  const cell = (v: unknown) => { const s = String(v); const t = /^[=+\-@]/.test(s) ? `'${s}` : s; return /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t }
  const body = [cols.join(','), ...a.table.map(r => cols.map(c => cell(r[c])).join(','))].join('\n')
  save(new Blob([body], { type: 'text/csv' }), 'segmora_customers.csv')
}
export async function downloadPdf(a: Analysis) {
  const res = await fetch(`${API}/api/report.pdf`, json({ source_label: a.source.label.slice(0, 200), currency: a.currency, customers: a.customers, total_revenue: a.total_revenue, segments: a.segments, priority: a.priority.slice(0, 25) }))
  if (!res.ok) throw new ApiError('The PDF could not be created. Try again.', res.status)
  save(await res.blob(), 'segmora_report.pdf')
}
export const money = (v: number, cur: string) => `${cur}${Math.round(v).toLocaleString('en-GB')}`
export const pct = (v: number) => `${Math.round(v * 100)}%`
