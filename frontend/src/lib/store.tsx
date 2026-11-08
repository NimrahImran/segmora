import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { getAnalysis, type Analysis } from './api'

interface Ctx { analysis: Analysis | null; baseline: Analysis | null; error: string; slow: boolean; setAnalysis: (a: Analysis) => void; reset: () => void; retry: () => void }
const C = createContext<Ctx>(null as unknown as Ctx)
export const useData = () => useContext(C)

export function DataProvider({ children }: { children: ReactNode }) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [baseline, setBaseline] = useState<Analysis | null>(null)
  const [error, setError] = useState(''); const [slow, setSlow] = useState(false); const [tick, setTick] = useState(0)
  useEffect(() => {
    let live = true
    setError(''); const t = setTimeout(() => live && setSlow(true), 4000)
    getAnalysis().then(a => { if (live) { setBaseline(a); setAnalysis(c => c ?? a) } })
      .catch(e => live && setError(e.message)).finally(() => { clearTimeout(t); if (live) setSlow(false) })
    return () => { live = false; clearTimeout(t) }
  }, [tick])
  const reset = useCallback(() => baseline && setAnalysis(baseline), [baseline])
  const retry = useCallback(() => setTick(t => t + 1), [])
  return <C.Provider value={{ analysis, baseline, error, slow, setAnalysis, reset, retry }}>{children}</C.Provider>
}
