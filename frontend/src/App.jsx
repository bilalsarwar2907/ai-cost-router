import { useState, useEffect } from 'react'
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'

// ── Config ────────────────────────────────────────────────────────────────────

const API_URL = 'http://localhost:8000'

const DEMO_CONTENT = `Apple Inc. reported Q4 2024 revenue of $94.9 billion, a 6% increase year-over-year. Services revenue reached an all-time high of $24.2 billion. iPhone revenue was $46.2B, slightly below estimates of $47.5B amid softening demand in Greater China. Management guided Q1 2025 revenue of $124B. CEO Tim Cook highlighted momentum in India where revenue grew 33% YoY. CFO Luca Maestri noted gross margins expanded to 46.2%, up 150 basis points. EPS of $1.64 beat consensus of $1.60. The board approved a $110B share buyback. Key risks include China regulatory environment and FX headwinds. AAPL shares rose 2.3% in after-hours trading on October 31, 2024.`

const TASK_OPTIONS = [
  { id: 'extract_dates',      label: 'Extract Dates',      tier: 'local'   },
  { id: 'extract_tickers',    label: 'Extract Tickers',    tier: 'local'   },
  { id: 'extract_numbers',    label: 'Extract Numbers',    tier: 'local'   },
  { id: 'count_words',        label: 'Count Words',        tier: 'local'   },
  { id: 'classification',     label: 'Classification',     tier: 'small'   },
  { id: 'sentiment_analysis', label: 'Sentiment Analysis', tier: 'small'   },
  { id: 'short_summary',      label: 'Short Summary',      tier: 'small'   },
  { id: 'executive_summary',  label: 'Executive Summary',  tier: 'premium' },
  { id: 'risk_analysis',      label: 'Risk Analysis',      tier: 'premium' },
  { id: 'investment_thesis',  label: 'Investment Thesis',  tier: 'premium' },
]

const TIER = {
  local:   { color: '#10b981', dimColor: '#064e3b', label: 'LOCAL',   badge: 'bg-emerald-950 text-emerald-300 border border-emerald-800' },
  small:   { color: '#f59e0b', dimColor: '#451a03', label: 'SMALL',   badge: 'bg-amber-950  text-amber-300  border border-amber-800'   },
  premium: { color: '#f43f5e', dimColor: '#4c0519', label: 'PREMIUM', badge: 'bg-rose-950   text-rose-300   border border-rose-800'    },
}

// ── Small components ──────────────────────────────────────────────────────────

function RouteBadge({ route }) {
  const t = TIER[route] ?? TIER.premium
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-semibold tracking-wide ${t.badge}`}>
      {t.label}
    </span>
  )
}

function StatCard({ label, value, sub, highlight }) {
  return (
    <div className={`rounded-xl p-5 border ${
      highlight
        ? 'bg-gradient-to-br from-emerald-950 to-slate-900 border-emerald-800'
        : 'bg-slate-900 border-slate-800'
    }`}>
      <p className={`text-xs uppercase tracking-widest mb-1 ${highlight ? 'text-emerald-400' : 'text-slate-500'}`}>
        {label}
      </p>
      <p className={`font-black ${highlight ? 'text-5xl text-emerald-400' : 'text-3xl text-white'}`}>
        {value}
      </p>
      {sub && <p className="text-xs text-slate-600 mt-2">{sub}</p>}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function App() {
  // Analyze tab state
  const [content, setContent]             = useState(DEMO_CONTENT)
  const [selectedTasks, setSelectedTasks] = useState([
    'extract_dates', 'extract_tickers', 'classification', 'executive_summary',
  ])
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  // Tab state
  const [activeTab, setActiveTab] = useState('analyze')

  // History tab state
  const [analytics, setAnalytics]   = useState(null)
  const [history, setHistory]       = useState([])
  const [histLoading, setHistLoading] = useState(false)
  const [histError, setHistError]   = useState(null)

  // Fetch analytics + history whenever History tab is opened
  useEffect(() => {
    if (activeTab !== 'history') return
    const load = async () => {
      setHistLoading(true)
      setHistError(null)
      try {
        const [analyticsRes, historyRes] = await Promise.all([
          fetch(`${API_URL}/analytics`),
          fetch(`${API_URL}/history?limit=50`),
        ])
        if (!analyticsRes.ok || !historyRes.ok) throw new Error('API error')
        const [analyticsData, historyData] = await Promise.all([
          analyticsRes.json(),
          historyRes.json(),
        ])
        setAnalytics(analyticsData)
        setHistory(historyData.executions ?? [])
      } catch (e) {
        setHistError('Cannot load history. Is the backend running?')
      } finally {
        setHistLoading(false)
      }
    }
    load()
  }, [activeTab])

  const toggleTask = (id) =>
    setSelectedTasks(prev =>
      prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
    )

  const handleAnalyze = async () => {
    if (!content.trim() || selectedTasks.length === 0) return
    setLoading(true)
    setError(null)
    setResults(null)
    try {
      const res = await fetch(`${API_URL}/batch`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(selectedTasks.map(t => ({ task_type: t, content }))),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail ?? `API error ${res.status}`)
      }
      setResults(await res.json())
    } catch (err) {
      setError(
        err.message.includes('fetch')
          ? 'Cannot reach backend. Is it running on port 8000?'
          : err.message
      )
    } finally {
      setLoading(false)
    }
  }

  // Chart data helpers
  const toMicro = v => parseFloat((v * 1e6).toFixed(3))

  const costData    = results?.tasks.map(t => ({ name: t.task_type.replace(/_/g, ' '), v: toMicro(t.estimated_cost_usd), route: t.route }))
  const latencyData = results?.tasks.map(t => ({ name: t.task_type.replace(/_/g, ' '), v: t.estimated_latency_ms, route: t.route }))

  const tooltipStyle = {
    contentStyle: { background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, fontSize: 11 },
    labelStyle:   { color: '#94a3b8' },
  }

  // Format ISO timestamp to short date/time
  const fmtDate = iso => {
    if (!iso) return '—'
    const d = new Date(iso)
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) +
           ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100" style={{ fontFamily: 'ui-monospace, monospace' }}>

      {/* ── Header ── */}
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <div>
            <h1 className="text-lg font-bold text-white tracking-tight">AI Cost Router</h1>
            <p className="text-xs text-slate-500">Intelligent task routing · Local → Small Model → Premium Model</p>
          </div>
        </div>
        <div className="flex gap-2 text-xs text-slate-600">
          <span className="border border-slate-800 rounded px-2 py-1">FastAPI :8000</span>
          <span className="border border-slate-800 rounded px-2 py-1">React :5173</span>
        </div>
      </header>

      <div className="flex" style={{ height: 'calc(100vh - 65px)' }}>

        {/* ── Left panel: Input ── */}
        <aside className="w-72 flex-shrink-0 border-r border-slate-800 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 space-y-5">

            {/* Content textarea */}
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-widest block mb-2">
                Document Content
              </label>
              <textarea
                value={content}
                onChange={e => setContent(e.target.value)}
                rows={8}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs text-slate-300
                           resize-none focus:outline-none focus:border-blue-600 leading-relaxed"
                placeholder="Paste document content here..."
              />
              <p className="text-xs text-slate-700 mt-1">{content.split(/\s+/).filter(Boolean).length} words</p>
            </div>

            {/* Task checkboxes grouped by tier */}
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-widest block mb-3">
                Select Tasks
              </label>
              {(['local', 'small', 'premium']).map(tier => (
                <div key={tier} className="mb-4">
                  <div className="flex items-center gap-1.5 mb-2">
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: TIER[tier].color }} />
                    <span className="text-xs font-semibold uppercase" style={{ color: TIER[tier].color }}>
                      {tier === 'local' ? 'Local Python · $0.00' : tier === 'small' ? 'Small Model · cheap' : 'Premium Model · deep reasoning'}
                    </span>
                  </div>
                  {TASK_OPTIONS.filter(t => t.tier === tier).map(task => (
                    <label key={task.id} className="flex items-center gap-2 py-1 cursor-pointer group">
                      <input
                        type="checkbox"
                        checked={selectedTasks.includes(task.id)}
                        onChange={() => toggleTask(task.id)}
                      />
                      <span className="text-xs text-slate-400 group-hover:text-slate-200 transition-colors">
                        {task.label}
                      </span>
                    </label>
                  ))}
                </div>
              ))}
            </div>
          </div>

          {/* Sticky CTA */}
          <div className="flex-shrink-0 p-4 border-t border-slate-800">
            <button
              onClick={handleAnalyze}
              disabled={loading || selectedTasks.length === 0 || !content.trim()}
              className="w-full py-2.5 rounded-lg text-sm font-semibold transition-all
                         bg-blue-600 hover:bg-blue-500
                         disabled:bg-slate-800 disabled:text-slate-600 disabled:cursor-not-allowed
                         active:scale-95"
            >
              {loading
                ? <span className="flex items-center justify-center gap-2">
                    <span className="w-3 h-3 border border-slate-400 border-t-transparent rounded-full animate-spin" />
                    Routing...
                  </span>
                : `Analyze ${selectedTasks.length} task${selectedTasks.length !== 1 ? 's' : ''} →`
              }
            </button>
            {error && <p className="text-xs text-rose-400 mt-2">{error}</p>}
          </div>
        </aside>

        {/* ── Right panel ── */}
        <main className="flex-1 overflow-y-auto flex flex-col">

          {/* Tab bar */}
          <div className="flex-shrink-0 border-b border-slate-800 flex px-6 gap-1 pt-3">
            {[
              { id: 'analyze', label: 'Analyze' },
              { id: 'history', label: 'History' },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 text-xs font-semibold rounded-t border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-slate-500 hover:text-slate-300'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* ── Analyze tab ── */}
          {activeTab === 'analyze' && (
            <div className="flex-1 overflow-y-auto p-6">

              {/* Empty state */}
              {!results && !loading && (
                <div className="h-full flex flex-col items-center justify-center text-slate-700 gap-2">
                  <span className="text-5xl">⚡</span>
                  <p className="text-sm">Select tasks and click Analyze</p>
                  <p className="text-xs">The router picks the cheapest path for each task</p>
                </div>
              )}

              {/* Loading state */}
              {loading && (
                <div className="h-full flex items-center justify-center">
                  <div className="text-center text-slate-500">
                    <div className="w-8 h-8 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin mx-auto mb-3" />
                    <p className="text-sm">Routing tasks to optimal execution tier...</p>
                  </div>
                </div>
              )}

              {/* Results */}
              {results && (
                <div className="space-y-5 max-w-4xl">

                  {/* Savings cards */}
                  <div className="grid grid-cols-3 gap-4">
                    <StatCard
                      highlight
                      label="Cost Saved"
                      value={`${results.summary.savings_percent}%`}
                      sub={`$${toMicro(results.summary.total_savings_usd)} μ$ saved vs all-premium`}
                    />
                    <StatCard
                      label="With Routing"
                      value={`$${toMicro(results.summary.total_cost_usd)} μ$`}
                      sub={`${results.summary.total_tasks} tasks`}
                    />
                    <StatCard
                      label="Without Routing"
                      value={`$${toMicro(results.summary.cost_if_all_premium_usd)} μ$`}
                      sub="all routed to premium"
                    />
                  </div>

                  {/* Routing decisions table */}
                  <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
                    <div className="px-4 py-3 border-b border-slate-800">
                      <h2 className="text-sm font-semibold text-white">Routing Decisions</h2>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-slate-800 text-slate-500">
                            <th className="text-left px-4 py-2 font-normal">Task</th>
                            <th className="text-left px-4 py-2 font-normal">Route</th>
                            <th className="text-left px-4 py-2 font-normal">Reason</th>
                            <th className="text-right px-4 py-2 font-normal">Cost (μ$)</th>
                            <th className="text-right px-4 py-2 font-normal">Latency</th>
                          </tr>
                        </thead>
                        <tbody>
                          {results.tasks.map((task, i) => (
                            <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                              <td className="px-4 py-3 text-slate-300 font-medium">{task.task_type}</td>
                              <td className="px-4 py-3"><RouteBadge route={task.route} /></td>
                              <td className="px-4 py-3 text-slate-500 max-w-xs">
                                <span className="block truncate" title={task.routing_reason}>
                                  {task.routing_reason}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-right">
                                {task.estimated_cost_usd === 0
                                  ? <span className="text-emerald-400">$0.00</span>
                                  : <span className="text-slate-400">${toMicro(task.estimated_cost_usd)}</span>
                                }
                              </td>
                              <td className="px-4 py-3 text-right text-slate-400">{task.estimated_latency_ms}ms</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Charts */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-4">
                        Cost per Task (μ$)
                      </h3>
                      <ResponsiveContainer width="100%" height={160}>
                        <BarChart data={costData} margin={{ left: -20, right: 8 }}>
                          <XAxis dataKey="name" tick={{ fill: '#475569', fontSize: 9 }} />
                          <YAxis tick={{ fill: '#475569', fontSize: 9 }} />
                          <Tooltip {...tooltipStyle} formatter={v => [`${v} μ$`, 'cost']} />
                          <Bar dataKey="v" radius={[4, 4, 0, 0]}>
                            {costData.map((entry, i) => (
                              <Cell key={i} fill={TIER[entry.route]?.color ?? '#6366f1'} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>

                    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-4">
                        Latency per Task (ms)
                      </h3>
                      <ResponsiveContainer width="100%" height={160}>
                        <BarChart data={latencyData} margin={{ left: -20, right: 8 }}>
                          <XAxis dataKey="name" tick={{ fill: '#475569', fontSize: 9 }} />
                          <YAxis tick={{ fill: '#475569', fontSize: 9 }} />
                          <Tooltip {...tooltipStyle} formatter={v => [`${v}ms`, 'latency']} />
                          <Bar dataKey="v" radius={[4, 4, 0, 0]}>
                            {latencyData.map((entry, i) => (
                              <Cell key={i} fill={TIER[entry.route]?.color ?? '#6366f1'} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  {/* Execution results */}
                  <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
                    <div className="px-4 py-3 border-b border-slate-800">
                      <h2 className="text-sm font-semibold text-white">Execution Results</h2>
                    </div>
                    <div className="divide-y divide-slate-800">
                      {results.tasks.map((task, i) => (
                        <div key={i} className="px-4 py-3">
                          <div className="flex items-center gap-2 mb-2">
                            <RouteBadge route={task.route} />
                            <span className="text-xs font-medium text-slate-300">{task.task_type}</span>
                            <span className="text-xs text-slate-700 ml-auto">{task.execution_method}</span>
                          </div>
                          <pre className="text-xs text-slate-400 whitespace-pre-wrap break-words leading-relaxed">
                            {typeof task.result === 'string'
                              ? task.result
                              : JSON.stringify(task.result, null, 2)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  </div>

                </div>
              )}
            </div>
          )}

          {/* ── History tab ── */}
          {activeTab === 'history' && (
            <div className="flex-1 overflow-y-auto p-6">

              {histLoading && (
                <div className="h-64 flex items-center justify-center text-slate-500">
                  <div className="text-center">
                    <div className="w-8 h-8 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin mx-auto mb-3" />
                    <p className="text-sm">Loading history...</p>
                  </div>
                </div>
              )}

              {histError && (
                <div className="h-64 flex items-center justify-center">
                  <p className="text-sm text-rose-400">{histError}</p>
                </div>
              )}

              {!histLoading && !histError && analytics && (
                <div className="space-y-5 max-w-4xl">

                  {/* All-time stats */}
                  <div className="grid grid-cols-3 gap-4">
                    <StatCard
                      highlight
                      label="All-Time Savings"
                      value={`${analytics.savings_percent}%`}
                      sub={`$${toMicro(analytics.total_savings_usd)} μ$ saved total`}
                    />
                    <StatCard
                      label="Tasks Processed"
                      value={analytics.total_tasks.toLocaleString()}
                      sub="across all sessions"
                    />
                    <StatCard
                      label="Total Spend"
                      value={`$${toMicro(analytics.total_cost_usd)} μ$`}
                      sub="with intelligent routing"
                    />
                  </div>

                  {/* Tier breakdown */}
                  {Object.keys(analytics.by_route).length > 0 && (
                    <div className="grid grid-cols-3 gap-4">
                      {['local', 'small', 'premium'].map(route => {
                        const d = analytics.by_route[route]
                        if (!d) return null
                        return (
                          <div key={route} className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                            <RouteBadge route={route} />
                            <p className="text-2xl font-black text-white mt-2">{d.count}</p>
                            <p className="text-xs text-slate-600 mt-1">
                              tasks · ${toMicro(d.savings)} μ$ saved
                            </p>
                          </div>
                        )
                      })}
                    </div>
                  )}

                  {/* Savings over time */}
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                    <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-4">
                      Savings Over Time (μ$ / day · last 30 days)
                    </h3>
                    {analytics.daily_savings.length === 0 ? (
                      <div className="h-40 flex items-center justify-center text-slate-700 text-xs">
                        No data yet — run some tasks to see the chart
                      </div>
                    ) : (
                      <ResponsiveContainer width="100%" height={180}>
                        <LineChart
                          data={analytics.daily_savings.map(d => ({
                            day:     d.day.slice(5),   // MM-DD
                            savings: toMicro(d.daily_savings),
                            tasks:   d.task_count,
                          }))}
                          margin={{ left: -20, right: 8 }}
                        >
                          <XAxis dataKey="day" tick={{ fill: '#475569', fontSize: 9 }} />
                          <YAxis tick={{ fill: '#475569', fontSize: 9 }} />
                          <Tooltip
                            {...tooltipStyle}
                            formatter={(v, name) => name === 'savings' ? [`${v} μ$`, 'saved'] : [v, 'tasks']}
                          />
                          <Line
                            type="monotone"
                            dataKey="savings"
                            stroke="#10b981"
                            strokeWidth={2}
                            dot={{ fill: '#10b981', r: 3 }}
                            activeDot={{ r: 5 }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    )}
                  </div>

                  {/* Recent executions table */}
                  <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
                    <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
                      <h2 className="text-sm font-semibold text-white">Recent Executions</h2>
                      <span className="text-xs text-slate-600">{history.length} shown</span>
                    </div>
                    {history.length === 0 ? (
                      <div className="px-4 py-8 text-center text-slate-700 text-xs">
                        No executions logged yet — run your first analysis
                      </div>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b border-slate-800 text-slate-500">
                              <th className="text-left px-4 py-2 font-normal">Task</th>
                              <th className="text-left px-4 py-2 font-normal">Route</th>
                              <th className="text-left px-4 py-2 font-normal">Method</th>
                              <th className="text-right px-4 py-2 font-normal">Cost (μ$)</th>
                              <th className="text-right px-4 py-2 font-normal">Saved (μ$)</th>
                              <th className="text-right px-4 py-2 font-normal">When</th>
                            </tr>
                          </thead>
                          <tbody>
                            {history.map((row, i) => (
                              <tr key={row.id ?? i} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                                <td className="px-4 py-2.5 text-slate-300">{row.task_type}</td>
                                <td className="px-4 py-2.5"><RouteBadge route={row.route} /></td>
                                <td className="px-4 py-2.5 text-slate-600">{row.execution_method ?? '—'}</td>
                                <td className="px-4 py-2.5 text-right">
                                  {row.estimated_cost_usd === 0
                                    ? <span className="text-emerald-400">$0.00</span>
                                    : <span className="text-slate-400">${toMicro(row.estimated_cost_usd)}</span>
                                  }
                                </td>
                                <td className="px-4 py-2.5 text-right text-emerald-400">
                                  ${toMicro(row.savings_vs_premium_usd)}
                                </td>
                                <td className="px-4 py-2.5 text-right text-slate-600">
                                  {fmtDate(row.created_at)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                </div>
              )}

              {/* Empty analytics state */}
              {!histLoading && !histError && !analytics && (
                <div className="h-64 flex flex-col items-center justify-center text-slate-700 gap-2">
                  <span className="text-4xl">📊</span>
                  <p className="text-sm">Run an analysis first to see history</p>
                </div>
              )}

            </div>
          )}

        </main>
      </div>
    </div>
  )
}
