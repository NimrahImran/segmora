import { money, pct } from './api'

test('money rounds and groups', () => { expect(money(1234.6, '£')).toBe('£1,235') })
test('pct rounds', () => { expect(pct(0.712)).toBe('71%') })
