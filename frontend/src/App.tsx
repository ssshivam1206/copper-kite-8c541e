import { useEffect, useMemo, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

type Metrics = {
  matched: number
  forecastAvailable: number
  actualAvailable: number
  maeMw: number | null
  biasMw: number | null
  overforecastRate: number | null
}
type Metadata = {
  retrievedAt: string
  forecastRecords: number
  actualRecords: number
  warnings: string[]
  method: string
}
type Row = {
  startTime: string
  localTime: string
  forecastMw: number | null
  actualMw: number | null
  publishTime: string | null
  errorMw: number | null
}
type Replay = {
  asOf: string
  decisionDate: string
  deliveryDate: string
  timezone: string
  unit: string
  rows: Row[]
  metrics: Metrics
  metadata: Metadata
}
type Day = Metrics & { decisionDate: string; deliveryDate: string }
type Summary = {
  decisionTime: string
  timezone: string
  unit: string
  days: Day[]
  metrics: Metrics
  metadata: Metadata
}
type View = 'replay' | 'accuracy'

const DATE_MIN = '2026-01-01'
const DATE_MAX = '2026-01-31'
const DEFAULT_DATE = '2026-01-15'
const DEFAULT_TIME = '12:00'
const nf = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 })

function readUrl() {
  const params = new URLSearchParams(window.location.search)
  const candidateDate = params.get('date') ?? DEFAULT_DATE
  const candidateTime = params.get('time') ?? DEFAULT_TIME
  return {
    date: /^2026-01-(?:0[1-9]|[12]\d|3[01])$/.test(candidateDate) ? candidateDate : DEFAULT_DATE,
    time: /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(candidateTime) ? candidateTime : DEFAULT_TIME,
    view: params.get('view') === 'accuracy' ? 'accuracy' as View : 'replay' as View,
  }
}

function asOfIso(date: string, time: string) {
  // Every supported decision falls in January, when Europe/London is UTC.
  return `${date}T${time}:00Z`
}

async function apiGet<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`)
  }
  return body as T
}

function dateLabel(date: string, includeYear = false) {
  const parsed = new Date(`${date}T12:00:00Z`)
  return parsed.toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', ...(includeYear ? { year: 'numeric' } : {}), timeZone: 'UTC',
  })
}

function nextDate(date: string) {
  return new Date(Date.parse(`${date}T00:00:00Z`) + 86400000).toISOString().slice(0, 10)
}

function mw(value: number | null) {
  return value === null ? '—' : `${nf.format(value)} MW`
}

function signedMw(value: number | null) {
  return value === null ? '—' : `${value > 0 ? '+' : ''}${nf.format(value)} MW`
}

function percent(value: number | null) {
  return value === null ? '—' : `${Math.round(value * 100)}%`
}

function timestamp(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString('en-GB', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Europe/London',
  })
}

function Metric({ label, value, detail, tone }: { label: string; value: string; detail: string; tone?: string }) {
  return <div className={`metric ${tone ?? ''}`}>
    <span className="metric-label">{label}</span>
    <strong>{value}</strong>
    <span className="metric-detail">{detail}</span>
  </div>
}

function HelpText() {
  return <div className="method-note">
    <span className="method-mark">i</span>
    <p><strong>How to read this:</strong> WINDFOR targets in the inspected data are hourly; FUELHH outturn is a 30-minute average. We compare only identical start times and never fill missing forecast values. Positive bias means the forecast overstated wind. This is a historical difference, not a buying recommendation.</p>
  </div>
}

export default function App() {
  const initial = useMemo(readUrl, [])
  const [date, setDate] = useState(initial.date)
  const [time, setTime] = useState(initial.time)
  const [view, setView] = useState<View>(initial.view)
  const [replay, setReplay] = useState<Replay | null>(null)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [replayError, setReplayError] = useState('')
  const [summaryError, setSummaryError] = useState('')
  const [loadingReplay, setLoadingReplay] = useState(true)
  const [loadingSummary, setLoadingSummary] = useState(true)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams({ date, time, view })
    window.history.replaceState({}, '', `?${params}`)
    document.title = `Windline | ${view === 'replay' ? 'Decision replay' : 'January accuracy'}`
  }, [date, time, view])

  useEffect(() => {
    const controller = new AbortController()
    setLoadingReplay(true)
    setReplayError('')
    apiGet<Replay>(`/api/replay?as_of=${encodeURIComponent(asOfIso(date, time))}`, controller.signal)
      .then(setReplay)
      .catch(error => { if (error.name !== 'AbortError') setReplayError(error.message) })
      .finally(() => { if (!controller.signal.aborted) setLoadingReplay(false) })
    return () => controller.abort()
  }, [date, time])

  useEffect(() => {
    const controller = new AbortController()
    setLoadingSummary(true)
    setSummaryError('')
    apiGet<Summary>(`/api/summary?decision_time=${encodeURIComponent(time)}`, controller.signal)
      .then(setSummary)
      .catch(error => { if (error.name !== 'AbortError') setSummaryError(error.message) })
      .finally(() => { if (!controller.signal.aborted) setLoadingSummary(false) })
    return () => controller.abort()
  }, [time])

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  const activeError = view === 'replay' ? replayError : summaryError
  const activeLoading = view === 'replay' ? loadingReplay : loadingSummary
  const metadata = replay?.metadata ?? summary?.metadata

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-symbol" aria-hidden="true"><span /><span /><span /></span><div><strong>WINDLINE</strong><small>ENERGY INTELLIGENCE</small></div></div>
      <div className="sidebar-section-label">WORKSPACE</div>
      <nav aria-label="Main navigation" className="side-nav">
        <button className={view === 'replay' ? 'active' : ''} onClick={() => setView('replay')} aria-current={view === 'replay' ? 'page' : undefined}><span className="nav-glyph">◫</span> Decision replay</button>
        <button className={view === 'accuracy' ? 'active' : ''} onClick={() => setView('accuracy')} aria-current={view === 'accuracy' ? 'page' : undefined}><span className="nav-glyph">▥</span> January accuracy</button>
      </nav>
      <div className="sidebar-bottom"><span className="status-dot" /> HISTORICAL PILOT <small>January 2026 · Great Britain</small></div>
    </aside>

    <main className="main">
      <header className="topbar"><div className="breadcrumbs">MARKET OPERATIONS <span>/</span> WIND INTELLIGENCE</div><div className="topbar-right"><span className="top-status"><span className="status-dot" /> ELEXON DATA</span><button className="text-button" onClick={copyLink}>{copied ? 'Link copied' : 'Share view ↗'}</button></div></header>
      <div className="content">
        <div className="page-intro"><div><div className="eyebrow">JANUARY 2026 PILOT</div><h1>{view === 'replay' ? 'Decision replay' : 'January accuracy'}</h1><p>{view === 'replay' ? 'See the wind outlook available at the moment a day ahead decision was made.' : 'Understand how wind forecasts compared with the generation that followed.'}</p></div><div className="intro-aside"><span className="intro-aside-kicker">DATA SCOPE</span><strong>Great Britain wind</strong><span>Forecast & outturn only</span></div></div>

        <section className="controls" aria-label="Decision controls"><div className="control-heading"><span className="section-index">01</span><div><strong>Set the decision moment</strong><span>The delivery day follows the selected date.</span></div></div><div className="control-fields"><label><span className="field-label">Decision date</span><input type="date" value={date} min={DATE_MIN} max={DATE_MAX} onChange={event => { if (event.target.value >= DATE_MIN && event.target.value <= DATE_MAX) setDate(event.target.value) }} /></label><label><span className="field-label">Decision time <span className="label-hint">UK local</span></span><input type="time" value={time} step="60" onChange={event => { if (/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(event.target.value)) setTime(event.target.value) }} /></label><span className="control-arrow" aria-hidden="true">→</span><div className="delivery-value"><span>DELIVERY DAY</span><strong>{dateLabel(nextDate(date), true)}</strong></div></div></section>

        <div className="view-tabs" aria-label="Analysis view"><button aria-pressed={view === 'replay'} className={view === 'replay' ? 'selected' : ''} onClick={() => setView('replay')}>Decision replay</button><button aria-pressed={view === 'accuracy'} className={view === 'accuracy' ? 'selected' : ''} onClick={() => setView('accuracy')}>January accuracy</button></div>

        {activeError && <div className="error-panel" role="alert"><strong>Unable to load this analysis.</strong><span>{activeError}</span></div>}
        {activeLoading && !activeError && <div className="loading-panel" role="status">Loading historical wind data…</div>}

        {!activeLoading && !activeError && view === 'replay' && replay && <>
          <div className="section-heading"><div><span className="section-index">02</span><div><h2>What the buyer could see</h2><p>As of {timestamp(replay.asOf)} · For delivery on {dateLabel(replay.deliveryDate, true)}</p></div></div><span className="section-tag">HISTORICAL REPLAY</span></div>
          <div className="metrics-grid"><Metric label="Matched forecast points" value={`${replay.metrics.matched} / 48`} detail="Only exact timestamp pairs" /><Metric label="Mean absolute difference" value={mw(replay.metrics.maeMw)} detail="Average absolute forecast gap" /><Metric label="Signed bias" value={signedMw(replay.metrics.biasMw)} detail="Positive = wind overforecast" tone={(replay.metrics.biasMw ?? 0) > 0 ? 'warn' : ''} /><Metric label="Overforecast frequency" value={percent(replay.metrics.overforecastRate)} detail="Share of matched points" /></div>
          {replay.metrics.forecastAvailable === 0 && <div className="loading-panel" role="status">No forecast was available for this delivery day at the selected decision time.</div>}
          <section className="panel chart-panel"><div className="panel-head"><div><h3>Next day wind profile</h3><p>Forecast known at the decision time; outturn was published afterward.</p></div><div className="legend"><span><i className="forecast-key" /> Forecast</span><span><i className="actual-key" /> Outturn · known afterward</span></div></div><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><LineChart data={replay.rows} margin={{ top: 15, right: 16, left: 4, bottom: 4 }}><CartesianGrid stroke="#e7ecea" vertical={false} /><XAxis dataKey="localTime" interval={5} tickLine={false} axisLine={false} tick={{ fill: '#789095', fontSize: 11 }} /><YAxis tickFormatter={value => `${Math.round(value / 1000)}k`} tickLine={false} axisLine={false} tick={{ fill: '#789095', fontSize: 11 }} width={39} /><Tooltip content={<ReplayTooltip />} /><Line type="linear" dataKey="actualMw" name="Outturn" stroke="#6b7d86" strokeWidth={2} dot={false} activeDot={{ r: 4 }} /><Line type="linear" dataKey="forecastMw" name="Forecast" stroke="#0aa884" strokeWidth={2.8} dot={{ r: 2.5, fill: '#0aa884', strokeWidth: 0 }} activeDot={{ r: 5 }} /></LineChart></ResponsiveContainer></div><div className="chart-foot"><span>00:00</span><span>Forecast dots mark reported hourly points. Missing half-hours remain gaps.</span><span>23:30</span></div></section>
          <HelpText />
          <details className="details-panel"><summary>Explore all 48 delivery periods <span>↗</span></summary><div className="table-scroll"><table><thead><tr><th>UK time</th><th>Forecast</th><th>Published</th><th>Outturn</th><th>Difference</th></tr></thead><tbody>{replay.rows.map(row => <tr key={row.startTime}><td>{row.localTime}</td><td>{mw(row.forecastMw)}</td><td>{timestamp(row.publishTime)}</td><td>{mw(row.actualMw)}</td><td className={row.errorMw !== null && row.errorMw > 0 ? 'positive-error' : ''}>{signedMw(row.errorMw)}</td></tr>)}</tbody></table></div></details>
        </>}

        {!activeLoading && !activeError && view === 'accuracy' && summary && <>
          <div className="section-heading"><div><span className="section-index">02</span><div><h2>A month of comparable decisions</h2><p>Each day evaluated at {time} UK local time; delivery follows the next day.</p></div></div><span className="section-tag">31 DECISIONS</span></div>
          <div className="metrics-grid"><Metric label="Matched forecast points" value={nf.format(summary.metrics.matched)} detail="Across 31 delivery days" /><Metric label="Mean absolute difference" value={mw(summary.metrics.maeMw)} detail="Weighted by matched timestamps" /><Metric label="Signed bias" value={signedMw(summary.metrics.biasMw)} detail="Positive = wind overforecast" tone={(summary.metrics.biasMw ?? 0) > 0 ? 'warn' : ''} /><Metric label="Overforecast frequency" value={percent(summary.metrics.overforecastRate)} detail="Share of matched points" /></div>
          <section className="panel chart-panel"><div className="panel-head"><div><h3>Daily absolute difference</h3><p>Average MW gap between forecast and outturn on matched timestamps.</p></div><span className="mini-unit">MW</span></div><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={summary.days} margin={{ top: 15, right: 15, left: 4, bottom: 4 }}><CartesianGrid stroke="#e7ecea" vertical={false} /><XAxis dataKey="decisionDate" tickFormatter={value => value.slice(8)} interval={2} tickLine={false} axisLine={false} tick={{ fill: '#789095', fontSize: 11 }} /><YAxis tickFormatter={value => `${Math.round(value / 1000)}k`} tickLine={false} axisLine={false} tick={{ fill: '#789095', fontSize: 11 }} width={39} /><Tooltip content={<DailyTooltip />} /><ReferenceLine y={summary.metrics.maeMw ?? undefined} stroke="#789095" strokeDasharray="4 4" /><Bar dataKey="maeMw" radius={[3, 3, 0, 0]} maxBarSize={26}>{summary.days.map(day => <Cell key={day.decisionDate} fill={day.decisionDate === date ? '#0aa884' : '#a9dcd0'} />)}</Bar></BarChart></ResponsiveContainer></div><div className="chart-foot"><span>1 JAN</span><span>Dashed line: month-wide mean absolute difference</span><span>31 JAN</span></div></section>
          <HelpText />
          <section className="panel daily-panel"><div className="panel-head"><div><h3>Day by day</h3><p>Select a date to inspect the original forecast and outturn. Scroll for all 31 days.</p></div><span className="scroll-hint">Swipe table sideways →</span></div><div className="table-scroll"><table><thead><tr><th>Decision</th><th>Delivery</th><th>Matched</th><th>Abs. difference</th><th>Signed bias</th><th>Overforecast</th><th></th></tr></thead><tbody>{summary.days.map(day => <tr key={day.decisionDate} className={day.decisionDate === date ? 'highlight-row' : ''}><td>{dateLabel(day.decisionDate)}</td><td>{dateLabel(day.deliveryDate)}</td><td>{day.matched}</td><td>{mw(day.maeMw)}</td><td className={day.biasMw !== null && day.biasMw > 0 ? 'positive-error' : ''}>{signedMw(day.biasMw)}</td><td>{percent(day.overforecastRate)}</td><td><button className="table-link" onClick={() => { setDate(day.decisionDate); setView('replay') }}>Replay →</button></td></tr>)}</tbody></table></div></section>
        </>}

        <footer className="footer"><span>WINDLINE / HISTORICAL PILOT</span><span>Source: Elexon WINDFOR + FUELHH · Snapshot {metadata ? timestamp(metadata.retrievedAt) : 'unavailable'}</span></footer>
      </div>
    </main>
  </div>
}

function ReplayTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ payload: Row }>; label?: string }) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return <div className="chart-tooltip"><strong>{label} UK time</strong><span>Forecast: {mw(row.forecastMw)}</span><span>Outturn: {mw(row.actualMw)}</span><small>Forecast published {timestamp(row.publishTime)}</small></div>
}

function DailyTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: Day }> }) {
  if (!active || !payload?.length) return null
  const day = payload[0].payload
  return <div className="chart-tooltip"><strong>{dateLabel(day.decisionDate, true)} decision</strong><span>Mean absolute difference: {mw(day.maeMw)}</span><span>Matched points: {day.matched}</span></div>
}
