import { useData } from '../lib/store'

export function Status() {
  const { error, slow, retry, analysis } = useData()
  if (analysis) return null
  if (error) return <div className="notice"><p>{error}</p><button className="ghost" onClick={retry}>Try again</button></div>
  return <div className="notice"><p>{slow ? 'Waking up the server. On the free plan this can take about a minute.' : 'Loading customer data'}</p></div>
}
