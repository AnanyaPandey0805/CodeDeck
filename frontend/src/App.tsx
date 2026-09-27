import { useEffect, useRef, useState, type FormEvent } from 'react'
import {
  approveProduction, askRepositoryQuestion, createProject,
  deployProduction, deployStaging, getAnalysis, getEvaluation,
  getFiles, getHealth, getPipeline, getProject, getSystemStatus,
  listDeployments, listProjects, rollbackProduction, runAiTests,
  startAnalysis,
  type Analysis, type Deployment, type Evaluation, type GeneratedFile,
  type GeneratedTestRun, type PipelineStep, type Project,
  type RepositoryAnswer, type SystemStatus,
} from './api'

// ─── helpers ───────────────────────────────────────────────────────────────

type Page = 'overview' | 'repository' | 'assistant' | 'intelligence' | 'testing' | 'docker' | 'kubernetes' | 'logs' | 'settings'

const PIPELINE_STEPS = [
  'Repository Analysis', 'Repository Intelligence', 'Tests',
  'Security', 'Docker', 'Kubernetes', 'Staging',
]

function statusColor(s: string) {
  if (s === 'completed') return 'text-emerald-400'
  if (s === 'failed') return 'text-red-400'
  if (s === 'running') return 'text-yellow-400'
  if (s === 'warning') return 'text-orange-400'
  return 'text-zinc-500'
}
function statusBg(s: string) {
  if (s === 'completed') return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
  if (s === 'failed') return 'bg-red-500/10 text-red-400 border-red-500/20'
  if (s === 'running') return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
  if (s === 'warning') return 'bg-orange-500/10 text-orange-400 border-orange-500/20'
  return 'bg-zinc-800 text-zinc-500 border-zinc-700'
}
function stepIcon(s: string) {
  if (s === 'completed') return '✓'
  if (s === 'failed') return '✗'
  if (s === 'running') return '●'
  if (s === 'warning') return '⚠'
  return '○'
}

// ─── sub-components ─────────────────────────────────────────────────────────

function Pill({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="rounded border border-zinc-700 bg-zinc-800/60 px-3 py-2">
      <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-500">{label}</div>
      <div className="mt-0.5 truncate font-mono text-sm text-zinc-200">{value ?? '—'}</div>
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">
      <span className="h-px flex-1 bg-zinc-800" />
      {children}
      <span className="h-px flex-1 bg-zinc-800" />
    </h2>
  )
}

function TerminalBlock({ text, maxH = '14rem' }: { text: string; maxH?: string }) {
  const ref = useRef<HTMLPreElement>(null)
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight }, [text])
  return (
    <pre
      ref={ref}
      style={{ maxHeight: maxH }}
      className="overflow-auto rounded border border-zinc-700 bg-zinc-950 p-3 font-mono text-xs leading-relaxed text-zinc-300"
    >
      {text || <span className="text-zinc-600">No output</span>}
    </pre>
  )
}

// ─── main App ───────────────────────────────────────────────────────────────

export default function App() {
  const [page, setPage] = useState<Page>('overview')
  const [url, setUrl] = useState('')
  const [projects, setProjects] = useState<Project[]>([])
  const [selected, setSelected] = useState<Project | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [pipeline, setPipeline] = useState<PipelineStep[]>([])
  const [files, setFiles] = useState<GeneratedFile[]>([])
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [deployments, setDeployments] = useState<Deployment[]>([])
  const [qaResult, setQaResult] = useState<RepositoryAnswer | null>(null)
  const [question, setQuestion] = useState('What framework does this project use?')
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [aiTests, setAiTests] = useState<GeneratedTestRun | null>(null)
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [apiOk, setApiOk] = useState<boolean | null>(null)
  const [busy, setBusy] = useState(false)
  const [deploying, setDeploying] = useState(false)
  const [deployingProd, setDeployingProd] = useState(false)
  const [approvingProd, setApprovingProd] = useState(false)
  const [rollingBack, setRollingBack] = useState(false)
  const [askingQuestion, setAskingQuestion] = useState(false)
  const [runningAiTests, setRunningAiTests] = useState(false)
  const [loadingEval, setLoadingEval] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [logs, setLogs] = useState<Array<{ tag: string; text: string; ts: string }>>([])

  const log = (tag: string, text: string) =>
    setLogs(p => [...p.slice(-500), { tag, text, ts: new Date().toLocaleTimeString() }])

  // On mount
  useEffect(() => {
    getHealth().then(() => setApiOk(true)).catch(() => setApiOk(false))
    listProjects().then(setProjects).catch(() => setProjects([]))
    getSystemStatus().then(setSystemStatus).catch(() => setSystemStatus(null))
  }, [])

  // Poll while busy
  useEffect(() => {
    if (!selected) return
    const isBusy = selected.status === 'deploying' || selected.status === 'deploying_green' || selected.status === 'analyzing'
    if (!isBusy) return
    const iv = setInterval(() => loadProject(selected).catch(() => undefined), 3000)
    return () => clearInterval(iv)
  }, [selected?.id, selected?.status])

  // Sync sub-results from analysis_result
  useEffect(() => {
    const extra = (analysis?.analysis_result ?? {}) as Record<string, unknown>
    setEvaluation((extra.evaluation_result as Evaluation | undefined) ?? null)
    setAiTests((extra.ai_test_result as GeneratedTestRun | undefined) ?? null)
    setQaResult(null)
  }, [selected?.id, analysis?.created_at])

  async function loadProject(project: Project, isManual = false) {
    if (isManual) setError(null)
    setSelected(project)
    const [a, steps, fresh, generated, deps] = await Promise.all([
      getAnalysis(project.id),
      getPipeline(project.id),
      getProject(project.id),
      getFiles(project.id),
      listDeployments(project.id),
    ])
    setAnalysis(a)
    setPipeline(steps)
    setSelected(fresh)
    setFiles(generated)
    setSelectedFile(prev => {
      if (!prev) return generated[0]?.filename ?? null
      return generated.some(f => f.filename === prev) ? prev : generated[0]?.filename ?? null
    })
    setDeployments(deps)
    setProjects(prev => prev.map(p => p.id === fresh.id ? fresh : p))
  }

  async function onAnalyze(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    log('Analysis', `Starting analysis for ${url}`)
    try {
      const project = await createProject(url.trim())
      setSelected(project)
      setProjects(prev => [project, ...prev.filter(p => p.id !== project.id)])
      log('Analysis', 'Repository cloned — running pipeline…')
      const result = await startAnalysis(project.id)
      setAnalysis(result)
      const [steps, fresh, generated, deps] = await Promise.all([
        getPipeline(project.id), getProject(project.id),
        getFiles(project.id), listDeployments(project.id),
      ])
      setPipeline(steps)
      setSelected(fresh)
      setFiles(generated)
      setSelectedFile(generated[0]?.filename ?? null)
      setDeployments(deps)
      setProjects(prev => prev.map(p => p.id === fresh.id ? fresh : p))
      log('Analysis', `Done — ${result.language} / ${result.framework}`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Analysis failed'
      setError(msg)
      log('Analysis', `ERROR: ${msg}`)
      if (selected) getPipeline(selected.id).then(setPipeline).catch(() => undefined)
    } finally {
      setBusy(false)
    }
  }

  async function onAsk(e: FormEvent) {
    e.preventDefault()
    if (!selected || !question.trim()) return
    setAskingQuestion(true)
    setError(null)
    log('Q&A', `Question: ${question}`)
    try {
      const result = await askRepositoryQuestion(selected.id, question.trim())
      setQaResult(result)
      log('Q&A', `Answer received (${result.sources.length} sources)`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Q&A failed'
      setError(msg)
      log('Q&A', `ERROR: ${msg}`)
    } finally {
      setAskingQuestion(false)
    }
  }

  async function onRunAiTests() {
    if (!selected) return
    setRunningAiTests(true)
    setError(null)
    log('Testing', 'Running AI-generated tests…')
    try {
      const result = await runAiTests(selected.id)
      setAiTests(result)
      const [latest, steps] = await Promise.all([getAnalysis(selected.id), getPipeline(selected.id)])
      setAnalysis(latest)
      setPipeline(steps)
      log('Testing', `AI tests ${result.status}: ${result.message}`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'AI tests failed'
      setError(msg)
      log('Testing', `ERROR: ${msg}`)
    } finally {
      setRunningAiTests(false)
    }
  }

  async function onDeployStaging() {
    if (!selected) return
    setDeploying(true)
    setError(null)
    log('Docker/K8s', 'Starting staging deployment…')
    try {
      await deployStaging(selected.id)
      const [steps, fresh, deps] = await Promise.all([
        getPipeline(selected.id), getProject(selected.id), listDeployments(selected.id),
      ])
      setPipeline(steps)
      setSelected(fresh)
      setDeployments(deps)
      setProjects(prev => prev.map(p => p.id === fresh.id ? fresh : p))
      log('Docker/K8s', 'Staging deployment initiated (running in background)')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Deploy failed'
      setError(msg)
      log('Docker/K8s', `ERROR: ${msg}`)
      if (selected) getPipeline(selected.id).then(setPipeline).catch(() => undefined)
    } finally {
      setDeploying(false)
    }
  }

  async function onRefreshEval() {
    if (!selected) return
    setLoadingEval(true)
    try {
      const result = await getEvaluation(selected.id)
      setEvaluation(result)
      const latest = await getAnalysis(selected.id)
      setAnalysis(latest)
      log('Intelligence', `Evaluation: ${result.retrieval_accuracy}% accuracy`)
    } catch (err) {
      log('Intelligence', `Evaluation error: ${err instanceof Error ? err.message : err}`)
    } finally {
      setLoadingEval(false)
    }
  }

  async function onApprove() {
    if (!selected) return
    setApprovingProd(true)
    try {
      await approveProduction(selected.id)
      const [steps, fresh, deps] = await Promise.all([
        getPipeline(selected.id), getProject(selected.id), listDeployments(selected.id),
      ])
      setPipeline(steps); setSelected(fresh); setDeployments(deps)
      log('Kubernetes', 'Traffic switched to GREEN')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approval failed')
    } finally {
      setApprovingProd(false)
    }
  }

  async function onRollback() {
    if (!selected) return
    setRollingBack(true)
    try {
      await rollbackProduction(selected.id)
      const [steps, fresh, deps] = await Promise.all([
        getPipeline(selected.id), getProject(selected.id), listDeployments(selected.id),
      ])
      setPipeline(steps); setSelected(fresh); setDeployments(deps)
      log('Kubernetes', 'Rolled back to BLUE')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rollback failed')
    } finally {
      setRollingBack(false)
    }
  }

  // ── derived ─────────────────────────────────────────────────────────────
  const pipelineMap = Object.fromEntries(pipeline.map(s => [s.name, s]))
  const extra = (analysis?.analysis_result ?? {}) as Record<string, unknown>
  const recommendation = extra.deployment_recommendation as {
    summary?: string; potential_issues?: string[]; recommendation?: string[]
  } | undefined
  const testResult = extra.test_result as Record<string, unknown> | undefined
  const securityResult = extra.security_result as {
    findings?: Array<{ severity: string; file: string; message: string }>; summary?: string
  } | undefined
  const dockerResult = extra.docker_result as { message?: string; dockerfile?: string } | undefined
  const latestDeployment = deployments[0]
  const smokeResult = (latestDeployment?.details as { smoke?: Record<string, unknown> } | null)?.smoke
  const failureAnalysis = (latestDeployment?.details as { failure_analysis?: Record<string, unknown> } | null)?.failure_analysis

  // ── sidebar ─────────────────────────────────────────────────────────────
  const NAV: { id: Page; label: string; icon: string }[] = [
    { id: 'overview', label: 'Overview', icon: '⬡' },
    { id: 'repository', label: 'Repository', icon: '⎇' },
    { id: 'assistant', label: 'AI Assistant', icon: '◈' },
    { id: 'intelligence', label: 'Intelligence', icon: '◉' },
    { id: 'testing', label: 'Testing', icon: '◻' },
    { id: 'docker', label: 'Docker', icon: '▣' },
    { id: 'kubernetes', label: 'Kubernetes', icon: '⬡' },
    { id: 'logs', label: 'Logs', icon: '≡' },
    { id: 'settings', label: 'Settings', icon: '⚙' },
  ]

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950 text-zinc-200 font-mono">
      {/* ── Sidebar ── */}
      <aside className="flex w-52 shrink-0 flex-col border-r border-zinc-800 bg-zinc-900">
        {/* Brand */}
        <div className="border-b border-zinc-800 px-4 py-4">
          <div className="text-xs tracking-widest text-zinc-500 uppercase">AI DevOps</div>
          <div className="mt-0.5 text-lg font-bold tracking-tight text-white">CodeDeck</div>
        </div>

        {/* Repo selector */}
        <div className="border-b border-zinc-800 px-3 py-3">
          <div className="text-[10px] uppercase tracking-widest text-zinc-600 mb-1">Repository</div>
          {selected ? (
            <div className="text-xs text-zinc-300 truncate" title={selected.repository_url}>
              {selected.repository_name}
            </div>
          ) : (
            <div className="text-xs text-zinc-600">None loaded</div>
          )}
          <div className={`mt-1 text-[10px] font-mono ${
            selected?.status === 'ready' || selected?.status === 'staging_healthy'
              ? 'text-emerald-500' : selected?.status === 'failed' ? 'text-red-500'
              : selected?.status === 'analyzing' || selected?.status === 'deploying' ? 'text-yellow-500'
              : 'text-zinc-600'
          }`}>
            {selected?.status ?? 'idle'}
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-2">
          {NAV.map(({ id, label, icon }) => (
            <button
              key={id}
              onClick={() => setPage(id)}
              className={`flex w-full items-center gap-2.5 px-4 py-2 text-xs transition-colors ${
                page === id
                  ? 'bg-zinc-800 text-white'
                  : 'text-zinc-500 hover:bg-zinc-800/50 hover:text-zinc-300'
              }`}
            >
              <span className="text-base">{icon}</span>
              {label}
            </button>
          ))}
        </nav>

        {/* API status */}
        <div className="border-t border-zinc-800 px-4 py-3">
          <div className={`flex items-center gap-2 text-[10px] ${apiOk ? 'text-emerald-500' : apiOk === false ? 'text-red-500' : 'text-zinc-600'}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${apiOk ? 'bg-emerald-500' : apiOk === false ? 'bg-red-500' : 'bg-zinc-600'}`} />
            API {apiOk === null ? '…' : apiOk ? 'online' : 'offline'}
          </div>
        </div>
      </aside>

      {/* ── Main content ── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex shrink-0 items-center justify-between border-b border-zinc-800 bg-zinc-900 px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="text-xs uppercase tracking-widest text-zinc-500">{NAV.find(n => n.id === page)?.label}</span>
          </div>
          <div className="flex items-center gap-3">
            {selected && (
              <span className="rounded border border-zinc-700 bg-zinc-800 px-3 py-1 text-xs text-zinc-300">
                {selected.repository_name}
              </span>
            )}
            {selected && files.length > 0 && (
              <>
                <button
                  onClick={() => { setPage('kubernetes'); onDeployStaging() }}
                  disabled={deploying || busy}
                  className="rounded bg-sky-700 px-3 py-1 text-xs font-medium text-white hover:bg-sky-600 disabled:opacity-50"
                >
                  {deploying ? 'Deploying…' : 'Deploy Staging'}
                </button>
                {selected.status === 'staging_healthy' && (
                  <button
                    onClick={() => deployProduction(selected.id)}
                    disabled={deployingProd || busy}
                    className="rounded bg-emerald-700 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
                  >
                    Deploy Production
                  </button>
                )}
              </>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 rounded border border-red-700/50 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              <span className="font-semibold">Error: </span>{error}
              <button onClick={() => setError(null)} className="ml-3 text-red-500 hover:text-red-300">✕</button>
            </div>
          )}

          {/* ── OVERVIEW ── */}
          {page === 'overview' && (
            <div className="space-y-6 max-w-3xl">
              <SectionTitle>GitHub Repository</SectionTitle>
              <form onSubmit={onAnalyze} className="flex gap-2">
                <input
                  type="url"
                  required
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  placeholder="https://github.com/owner/repo"
                  className="flex-1 rounded border border-zinc-700 bg-zinc-900 px-4 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-sky-500"
                />
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded bg-sky-700 px-5 py-2.5 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-50"
                >
                  {busy ? 'Analyzing…' : 'Analyze'}
                </button>
              </form>

              {projects.length > 0 && (
                <>
                  <SectionTitle>Recent Projects</SectionTitle>
                  <div className="space-y-1.5">
                    {projects.slice(0, 8).map(p => (
                      <button
                        key={p.id}
                        onClick={() => loadProject(p, true).catch(err => setError(String(err.message || err)))}
                        className={`flex w-full items-center justify-between rounded border px-3 py-2 text-left text-xs transition ${
                          selected?.id === p.id ? 'border-sky-700 bg-sky-950/40 text-sky-300' : 'border-zinc-800 hover:border-zinc-700 text-zinc-400 hover:text-zinc-200'
                        }`}
                      >
                        <span className="font-medium">{p.repository_name}</span>
                        <span className={`ml-2 rounded px-1.5 py-0.5 text-[10px] ${
                          p.status === 'ready' || p.status === 'staging_healthy' ? 'bg-emerald-900 text-emerald-400'
                          : p.status === 'failed' ? 'bg-red-900 text-red-400'
                          : 'bg-zinc-800 text-zinc-500'
                        }`}>{p.status}</span>
                      </button>
                    ))}
                  </div>
                </>
              )}

              {selected && (
                <>
                  <SectionTitle>Pipeline Status</SectionTitle>
                  <div className="space-y-1">
                    {PIPELINE_STEPS.map(name => {
                      const step = pipelineMap[name]
                      const s = step?.status ?? 'pending'
                      return (
                        <div key={name} className="flex items-start gap-3 rounded border border-zinc-800 bg-zinc-900/50 px-3 py-2 text-xs">
                          <span className={`shrink-0 font-bold ${statusColor(s)}`}>{stepIcon(s)}</span>
                          <div className="flex-1 min-w-0">
                            <div className="flex justify-between">
                              <span className="text-zinc-300">{name}</span>
                              <span className={`ml-2 shrink-0 rounded border px-1.5 py-0.5 text-[10px] ${statusBg(s)}`}>{s}</span>
                            </div>
                            {step?.result && <div className="mt-0.5 truncate text-zinc-500">{step.result}</div>}
                            {step?.error && <div className="mt-0.5 truncate text-red-400">{step.error}</div>}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </>
              )}
            </div>
          )}

          {/* ── REPOSITORY ── */}
          {page === 'repository' && (
            <div className="space-y-6 max-w-3xl">
              <SectionTitle>Repository Details</SectionTitle>
              {!selected ? (
                <p className="text-sm text-zinc-500">No repository loaded. Use Overview to analyze one.</p>
              ) : (
                <>
                  <div className="rounded border border-zinc-800 bg-zinc-900/60 px-4 py-3">
                    <div className="text-[10px] uppercase tracking-widest text-zinc-600">URL</div>
                    <div className="mt-1 break-all text-xs text-sky-400">{selected.repository_url}</div>
                  </div>
                  {analysis ? (
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                      <Pill label="Language" value={analysis.language} />
                      <Pill label="Framework" value={analysis.framework} />
                      <Pill label="Package Manager" value={analysis.package_manager} />
                      <Pill label="Entry Point" value={analysis.entrypoint} />
                      <Pill label="Port" value={String(extra.port ?? '—')} />
                      <Pill label="Test Command" value={analysis.test_command} />
                      <Pill label="Dockerfile" value={analysis.has_dockerfile ? 'Present' : 'Not found'} />
                      <Pill label="Security Score" value={analysis.security_score != null ? `${analysis.security_score}/100` : null} />
                    </div>
                  ) : (
                    <p className="text-sm text-zinc-500">Run analysis to see repository details.</p>
                  )}

                  {(extra.multiservice_notice as string | undefined) && (
                    <div className="rounded border border-sky-700/30 bg-sky-950/30 p-3 text-xs text-sky-300">
                      {String(extra.multiservice_notice)}
                    </div>
                  )}

                  {files.length > 0 && (
                    <>
                      <SectionTitle>Generated Files</SectionTitle>
                      <div className="flex gap-3">
                        <ul className="w-36 shrink-0 space-y-1">
                          {files.map(f => (
                            <li key={f.filename}>
                              <button
                                onClick={() => setSelectedFile(f.filename)}
                                className={`w-full rounded px-2 py-1 text-left text-xs transition ${
                                  selectedFile === f.filename ? 'bg-sky-900/40 text-sky-300' : 'text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300'
                                }`}
                              >
                                {f.filename}
                              </button>
                            </li>
                          ))}
                        </ul>
                        <TerminalBlock text={files.find(f => f.filename === selectedFile)?.content ?? ''} maxH="24rem" />
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── AI ASSISTANT ── */}
          {page === 'assistant' && (
            <div className="flex h-full max-h-[calc(100vh-8rem)] flex-col gap-4 max-w-3xl">
              <SectionTitle>CodeDeck AI Assistant</SectionTitle>
              {!selected ? (
                <p className="text-sm text-zinc-500">Load a repository first.</p>
              ) : (
                <>
                  <div className="text-xs text-zinc-500">
                    Ask questions grounded in the indexed repository. Answers cite retrieved source files.
                  </div>

                  <form onSubmit={onAsk} className="flex gap-2">
                    <input
                      type="text"
                      value={question}
                      onChange={e => setQuestion(e.target.value)}
                      placeholder="Where is authentication implemented?"
                      className="flex-1 rounded border border-zinc-700 bg-zinc-900 px-4 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-sky-500"
                    />
                    <button
                      type="submit"
                      disabled={askingQuestion}
                      className="rounded bg-sky-700 px-5 py-2.5 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-50"
                    >
                      {askingQuestion ? 'Searching…' : 'Ask'}
                    </button>
                  </form>

                  {/* Quick questions */}
                  <div className="flex flex-wrap gap-2">
                    {[
                      'What framework does this project use?',
                      'What is the application entry point?',
                      'What database is being used?',
                      'What port does the application use?',
                      'How is the project structured?',
                    ].map(q => (
                      <button
                        key={q}
                        onClick={() => setQuestion(q)}
                        className="rounded border border-zinc-700 bg-zinc-900 px-2.5 py-1 text-xs text-zinc-400 hover:border-sky-700 hover:text-sky-300"
                      >
                        {q}
                      </button>
                    ))}
                  </div>

                  {qaResult && (
                    <div className="flex flex-1 gap-4 overflow-hidden">
                      <div className="flex-1 overflow-y-auto space-y-3">
                        <div className="rounded border border-zinc-700 bg-zinc-900/60 p-4">
                          <div className="text-[10px] uppercase tracking-widest text-zinc-600 mb-2">Answer</div>
                          <p className="text-sm leading-relaxed text-zinc-200">{qaResult.answer}</p>
                        </div>
                        {qaResult.sources.length > 0 && (
                          <div className="rounded border border-zinc-700 bg-zinc-900/60 p-4">
                            <div className="text-[10px] uppercase tracking-widest text-zinc-600 mb-3">Retrieved Evidence</div>
                            <div className="space-y-3">
                              {qaResult.sources.map(src => (
                                <div key={`${src.path}-${src.line_start}`} className="text-xs">
                                  <div className="font-mono text-sky-400">
                                    {src.path}:{src.line_start}–{src.line_end}
                                    <span className="ml-2 text-zinc-600">score {src.score.toFixed(2)}</span>
                                  </div>
                                  <p className="mt-1 text-zinc-400 leading-relaxed">{src.snippet}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── REPOSITORY INTELLIGENCE ── */}
          {page === 'intelligence' && (
            <div className="space-y-6 max-w-3xl">
              <SectionTitle>Repository Intelligence</SectionTitle>
              {!selected || !analysis ? (
                <p className="text-sm text-zinc-500">Analyze a repository to see intelligence data.</p>
              ) : (
                <>
                  {/* Recommendation */}
                  {recommendation && (
                    <div className="rounded border border-zinc-700 bg-zinc-900/60 p-4 space-y-3">
                      <div className="text-[10px] uppercase tracking-widest text-zinc-600">Deployment Recommendation</div>
                      <p className="text-sm text-zinc-200 leading-relaxed">{recommendation.summary}</p>
                      {(recommendation.potential_issues ?? []).length > 0 && (
                        <div>
                          <div className="text-[10px] uppercase tracking-widest text-orange-500 mb-1">Potential Issues</div>
                          <ul className="space-y-0.5">
                            {recommendation.potential_issues!.map(i => (
                              <li key={i} className="text-xs text-orange-300">⚠ {i}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {(recommendation.recommendation ?? []).length > 0 && (
                        <ul className="space-y-0.5">
                          {recommendation.recommendation!.map(i => (
                            <li key={i} className="text-xs text-zinc-400">→ {i}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}

                  {/* RAG index info */}
                  {(extra.repository_index as { file_count?: number; chunk_count?: number } | undefined) && (
                    <div className="grid grid-cols-2 gap-3">
                      <Pill label="Indexed Files" value={(extra.repository_index as { file_count?: number }).file_count} />
                      <Pill label="Index Chunks" value={(extra.repository_index as { chunk_count?: number }).chunk_count} />
                    </div>
                  )}

                  {/* Evaluation */}
                  <div className="flex items-center justify-between">
                    <div className="text-[10px] uppercase tracking-widest text-zinc-600">Retrieval Evaluation</div>
                    <button
                      onClick={onRefreshEval}
                      disabled={loadingEval}
                      className="rounded border border-zinc-700 px-3 py-1 text-xs text-zinc-400 hover:bg-zinc-800 disabled:opacity-50"
                    >
                      {loadingEval ? 'Refreshing…' : 'Refresh'}
                    </button>
                  </div>
                  {evaluation && (
                    <div className="space-y-2">
                      <div className="flex gap-4 text-xs">
                        <span className="text-zinc-400">{evaluation.correct}/{evaluation.questions} correct</span>
                        <span className="text-emerald-400 font-bold">{evaluation.retrieval_accuracy}% accuracy</span>
                      </div>
                      {evaluation.results.map(item => (
                        <div key={item.question} className="rounded border border-zinc-800 px-3 py-2 text-xs">
                          <div className="flex justify-between">
                            <span className="text-zinc-300">{item.question}</span>
                            <span className={item.status === 'correct' ? 'text-emerald-400' : 'text-orange-400'}>{item.status}</span>
                          </div>
                          <div className="mt-0.5 text-zinc-500 truncate">{item.answer}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Security */}
                  {securityResult && (
                    <>
                      <div className="text-[10px] uppercase tracking-widest text-zinc-600 mt-2">Security Scan</div>
                      <div className="text-xs text-zinc-400">{securityResult.summary}</div>
                      {(securityResult.findings ?? []).length > 0 && (
                        <div className="space-y-1">
                          {securityResult.findings!.map((f, i) => (
                            <div key={i} className="flex gap-2 rounded border border-zinc-800 px-3 py-1.5 text-xs">
                              <span className={f.severity === 'HIGH' ? 'text-red-400' : 'text-orange-400'}>{f.severity}</span>
                              <span className="text-zinc-500">{f.file}</span>
                              <span className="text-zinc-300">{f.message}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── TESTING ── */}
          {page === 'testing' && (
            <div className="space-y-6 max-w-3xl">
              <SectionTitle>Testing</SectionTitle>
              {!selected ? (
                <p className="text-sm text-zinc-500">Load a repository first.</p>
              ) : (
                <>
                  {/* Existing test result */}
                  {testResult && (
                    <div className="rounded border border-zinc-700 bg-zinc-900/60 p-4">
                      <div className="text-[10px] uppercase tracking-widest text-zinc-600 mb-2">Existing Tests (run during analysis)</div>
                      <div className="flex items-center gap-3">
                        <span className={testResult.status === 'passed' ? 'text-emerald-400' : testResult.status === 'skipped' ? 'text-zinc-500' : 'text-red-400'}>
                          {testResult.status === 'passed' ? '✓ PASSED' : testResult.status === 'skipped' ? '○ SKIPPED' : '✗ FAILED'}
                        </span>
                        <span className="text-xs text-zinc-400">{String(testResult.message ?? '')}</span>
                      </div>
                      {Boolean(testResult.command) && <div className="mt-2 font-mono text-xs text-zinc-500">{String(testResult.command)}</div>}
                    </div>
                  )}

                  {/* AI tests */}
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium text-zinc-200">AI-Generated Tests</div>
                      <div className="text-xs text-zinc-500 mt-0.5">
                        Generates route-level tests for FastAPI / Flask repositories and runs them via pytest.
                      </div>
                    </div>
                    <button
                      onClick={onRunAiTests}
                      disabled={runningAiTests}
                      className="rounded bg-sky-700 px-4 py-2 text-xs font-medium text-white hover:bg-sky-600 disabled:opacity-50"
                    >
                      {runningAiTests ? 'Running…' : 'Run AI Tests'}
                    </button>
                  </div>

                  {aiTests && (
                    <div className="space-y-4">
                      <div className="flex items-center gap-3 rounded border border-zinc-700 bg-zinc-900/60 px-4 py-3 text-xs">
                        <span className={
                          aiTests.status === 'passed' ? 'text-emerald-400 font-bold' :
                          aiTests.status === 'skipped' ? 'text-zinc-500' : 'text-red-400 font-bold'
                        }>
                          {aiTests.status === 'passed' ? '✓ PASSED' : aiTests.status === 'skipped' ? '○ SKIPPED' : '✗ FAILED'}
                        </span>
                        <span className="text-zinc-300">{aiTests.message}</span>
                        {aiTests.command && <span className="ml-auto text-zinc-600 font-mono">{aiTests.command}</span>}
                      </div>

                      {aiTests.generated_tests.map(tc => (
                        <div key={tc.path} className="space-y-2">
                          <div className="text-xs font-medium text-zinc-300">{tc.name}</div>
                          <div className="text-xs text-zinc-500">{tc.rationale}</div>
                          <TerminalBlock text={tc.code} maxH="12rem" />
                        </div>
                      ))}

                      {(aiTests.stdout || aiTests.stderr) && (
                        <div className="grid gap-3 sm:grid-cols-2">
                          <div>
                            <div className="text-[10px] uppercase tracking-widest text-zinc-600 mb-1">stdout</div>
                            <TerminalBlock text={aiTests.stdout || 'No output'} maxH="10rem" />
                          </div>
                          <div>
                            <div className="text-[10px] uppercase tracking-widest text-zinc-600 mb-1">stderr</div>
                            <TerminalBlock text={aiTests.stderr || 'No output'} maxH="10rem" />
                          </div>
                        </div>
                      )}

                      {aiTests.failure_analysis && (
                        <div className="rounded border border-orange-700/30 bg-orange-950/20 p-4 text-xs">
                          <div className="text-[10px] uppercase tracking-widest text-orange-500 mb-2">AI Failure Analysis</div>
                          <p className="text-orange-200">{String(aiTests.failure_analysis.likely_cause ?? 'No analysis')}</p>
                          {Boolean(aiTests.failure_analysis.suggested_fix) && (
                            <p className="mt-2 text-orange-300/70">
                              → {String(aiTests.failure_analysis.suggested_fix)}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── DOCKER ── */}
          {page === 'docker' && (
            <div className="space-y-6 max-w-3xl">
              <SectionTitle>Docker</SectionTitle>
              {!selected || !analysis ? (
                <p className="text-sm text-zinc-500">Analyze a repository first.</p>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <Pill label="Dockerfile" value={analysis.has_dockerfile ? 'Present in repo' : 'Generated'} />
                    <Pill label="Application Port" value={String(extra.port ?? '—')} />
                    <Pill label="Framework" value={analysis.framework} />
                    <Pill label="Entry Point" value={analysis.entrypoint} />
                  </div>

                  {dockerResult && (
                    <div className="rounded border border-zinc-700 bg-zinc-900/60 p-4">
                      <div className="text-[10px] uppercase tracking-widest text-zinc-600 mb-2">Docker Generation</div>
                      <div className="text-xs text-zinc-300">{dockerResult.message}</div>
                    </div>
                  )}

                  {files.find(f => f.filename === 'Dockerfile') && (
                    <>
                      <div className="text-[10px] uppercase tracking-widest text-zinc-600">Dockerfile</div>
                      <TerminalBlock text={files.find(f => f.filename === 'Dockerfile')!.content} maxH="18rem" />
                    </>
                  )}

                  {/* Build status from deployments */}
                  {latestDeployment && (
                    <div className="rounded border border-zinc-700 bg-zinc-900/60 px-4 py-3 text-xs">
                      <div className="text-[10px] uppercase tracking-widest text-zinc-600 mb-2">Last Build / Deploy</div>
                      <div className="flex gap-4">
                        <span className={latestDeployment.status === 'healthy' ? 'text-emerald-400' : latestDeployment.status === 'failed' ? 'text-red-400' : 'text-yellow-400'}>
                          {latestDeployment.status}
                        </span>
                        <span className="text-zinc-500">{latestDeployment.environment} / {latestDeployment.version}</span>
                        {(latestDeployment.details as { image?: string } | null)?.image && (
                          <span className="font-mono text-zinc-400">{(latestDeployment.details as { image?: string })!.image}</span>
                        )}
                      </div>
                    </div>
                  )}

                  <button
                    onClick={() => { setPage('kubernetes'); onDeployStaging() }}
                    disabled={deploying || busy || files.length === 0}
                    className="rounded bg-sky-700 px-4 py-2 text-xs font-medium text-white hover:bg-sky-600 disabled:opacity-50"
                  >
                    {deploying ? 'Building & Deploying…' : 'Build & Deploy to Staging'}
                  </button>
                </>
              )}
            </div>
          )}

          {/* ── KUBERNETES ── */}
          {page === 'kubernetes' && (
            <div className="space-y-6 max-w-3xl">
              <SectionTitle>Kubernetes / kind</SectionTitle>
              {!selected ? (
                <p className="text-sm text-zinc-500">Load a repository first.</p>
              ) : (
                <>
                  {/* Pipeline steps for K8s */}
                  {(['Docker', 'Kubernetes', 'Staging'] as const).map(name => {
                    const step = pipelineMap[name]
                    const s = step?.status ?? 'pending'
                    return (
                      <div key={name} className="flex items-center gap-3 rounded border border-zinc-800 px-4 py-3 text-xs">
                        <span className={`font-bold text-base ${statusColor(s)}`}>{stepIcon(s)}</span>
                        <div className="flex-1">
                          <div className="flex justify-between">
                            <span className="text-zinc-200">{name}</span>
                            <span className={`rounded border px-1.5 py-0.5 text-[10px] ${statusBg(s)}`}>{s}</span>
                          </div>
                          {step?.result && <div className="mt-0.5 text-zinc-500">{step.result}</div>}
                          {step?.error && <div className="mt-0.5 text-red-400">{step.error}</div>}
                        </div>
                      </div>
                    )
                  })}

                  {/* Deploy controls */}
                  <div className="flex flex-wrap gap-3 items-center">
                    <button
                      onClick={onDeployStaging}
                      disabled={deploying || busy || files.length === 0}
                      className="rounded bg-sky-700 px-4 py-2 text-xs font-medium text-white hover:bg-sky-600 disabled:opacity-50"
                    >
                      {deploying ? 'Deploying Staging…' : 'Deploy Staging'}
                    </button>
                    {selected.status === 'staging_healthy' && (
                      <button
                        onClick={() => { setDeployingProd(true); deployProduction(selected.id).finally(() => { setDeployingProd(false); loadProject(selected) }) }}
                        disabled={deployingProd}
                        className="rounded bg-emerald-700 px-4 py-2 text-xs font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
                      >
                        {deployingProd ? 'Deploying GREEN…' : 'Deploy Production (GREEN)'}
                      </button>
                    )}
                    {['staging_healthy', 'production_awaiting_approval', 'production_healthy', 'rolled_back'].includes(selected.status) && (
                      <a
                        href={`/api/projects/${selected.id}/preview/docs`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded bg-purple-700 px-4 py-2 text-xs font-medium text-white hover:bg-purple-600 flex items-center gap-1.5 shadow-lg shadow-purple-900/30"
                      >
                        <span>🌐 Open Live Preview (Docs)</span>
                        <span className="text-[10px] opacity-75">↗</span>
                      </a>
                    )}
                  </div>

                  {/* Approval banner */}
                  {selected.status === 'production_awaiting_approval' && (
                    <div className="rounded border border-yellow-700/50 bg-yellow-950/30 p-4">
                      <div className="text-sm font-medium text-yellow-300 mb-2">Production Approval Required</div>
                      <p className="text-xs text-yellow-400 mb-3">GREEN version deployed and verified. Test via Live Preview, then approve to switch live traffic.</p>
                      <div className="flex gap-3 items-center">
                        <button
                          onClick={onApprove}
                          disabled={approvingProd}
                          className="rounded bg-emerald-700 px-4 py-2 text-xs font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
                        >
                          {approvingProd ? 'Switching…' : 'Approve Production'}
                        </button>
                        <button
                          onClick={onRollback}
                          disabled={rollingBack}
                          className="rounded border border-red-700 px-4 py-2 text-xs text-red-400 hover:bg-red-950 disabled:opacity-50"
                        >
                          {rollingBack ? 'Rolling back…' : 'Rollback to BLUE'}
                        </button>
                        <a
                          href={`/api/projects/${selected.id}/preview/docs`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-yellow-300 underline hover:text-yellow-200 ml-2"
                        >
                          Test GREEN Preview ↗
                        </a>
                      </div>
                    </div>
                  )}

                  {/* Smoke test result */}
                  {smokeResult && (
                    <div className={`rounded border p-4 text-xs ${
                      smokeResult.status === 'passed'
                        ? 'border-emerald-700/30 bg-emerald-950/20'
                        : 'border-red-700/30 bg-red-950/20'
                    }`}>
                      <div className="text-[10px] uppercase tracking-widest text-zinc-600 mb-2">Smoke Test & Access</div>
                      <div className={`font-bold ${smokeResult.status === 'passed' ? 'text-emerald-400' : 'text-red-400'}`}>
                        {smokeResult.status === 'passed' ? '✓ PASSED' : '✗ FAILED'}
                      </div>
                      <div className="mt-1 text-zinc-400">{String(smokeResult.message ?? '')}</div>
                      <div className="mt-2.5 flex flex-wrap gap-2">
                        <a
                          href={`/api/projects/${selected.id}/preview/docs`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 rounded bg-emerald-600/20 px-2.5 py-1 text-xs text-emerald-300 hover:bg-emerald-600/30 border border-emerald-500/30 font-medium"
                        >
                          <span>🚀 Open Swagger API Docs</span>
                          <span>↗</span>
                        </a>
                        <a
                          href={`/api/projects/${selected.id}/preview/`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 rounded bg-zinc-800 px-2.5 py-1 text-xs text-zinc-300 hover:bg-zinc-700 border border-zinc-700"
                        >
                          <span>App Root</span>
                          <span>↗</span>
                        </a>
                      </div>
                    </div>
                  )}

                  {/* Deployment history */}
                  {deployments.length > 0 && (
                    <>
                      <div className="text-[10px] uppercase tracking-widest text-zinc-600 mt-2">Deployment History</div>
                      <div className="space-y-1.5">
                        {deployments.map(d => (
                          <div key={d.id} className="flex items-center gap-3 rounded border border-zinc-800 px-3 py-2 text-xs">
                            <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                              d.version === 'green' ? 'bg-emerald-900 text-emerald-400' : 'bg-sky-900 text-sky-400'
                            }`}>{d.version.toUpperCase()}</span>
                            <span className="text-zinc-400 capitalize">{d.environment}</span>
                            <span className={`ml-auto font-semibold ${
                              d.status === 'healthy' ? 'text-emerald-400' :
                              d.status === 'failed' ? 'text-red-400' :
                              d.status === 'awaiting_approval' ? 'text-yellow-400' : 'text-zinc-400'
                            }`}>{d.status}</span>
                            <span className="text-zinc-600">{new Date(d.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  )}

                  {/* Failure analysis */}
                  {failureAnalysis && (
                    <div className="rounded border border-orange-700/30 bg-orange-950/20 p-4 text-xs">
                      <div className="text-[10px] uppercase tracking-widest text-orange-500 mb-2">Failure Analysis</div>
                      <p className="text-orange-200">{String(failureAnalysis.likely_cause ?? 'No analysis')}</p>
                      {Boolean(failureAnalysis.suggested_fix) && (
                        <p className="mt-2 text-orange-300/70">→ {String(failureAnalysis.suggested_fix)}</p>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── LOGS ── */}
          {page === 'logs' && (
            <div className="space-y-4 max-w-4xl">
              <SectionTitle>Activity Logs</SectionTitle>
              <div className="flex justify-between items-center">
                <div className="text-xs text-zinc-500">{logs.length} entries</div>
                <button onClick={() => setLogs([])} className="text-xs text-zinc-600 hover:text-zinc-400">Clear</button>
              </div>
              <div className="overflow-y-auto rounded border border-zinc-800 bg-zinc-950" style={{ maxHeight: 'calc(100vh - 14rem)' }}>
                {logs.length === 0 ? (
                  <div className="p-6 text-center text-xs text-zinc-700">No log entries yet. Run analysis or deployment.</div>
                ) : (
                  <div className="divide-y divide-zinc-900">
                    {logs.map((entry, i) => (
                      <div key={i} className="flex gap-3 px-4 py-2 text-xs hover:bg-zinc-900/40">
                        <span className="shrink-0 text-zinc-700 tabular-nums">{entry.ts}</span>
                        <span className={`shrink-0 w-20 font-semibold ${
                          entry.tag === 'Analysis' ? 'text-sky-400' :
                          entry.tag === 'Q&A' ? 'text-purple-400' :
                          entry.tag === 'Testing' ? 'text-yellow-400' :
                          entry.tag.startsWith('Docker') ? 'text-orange-400' :
                          'text-zinc-400'
                        }`}>[{entry.tag}]</span>
                        <span className={entry.text.startsWith('ERROR') ? 'text-red-300' : 'text-zinc-300'}>{entry.text}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── SETTINGS ── */}
          {page === 'settings' && (
            <div className="space-y-6 max-w-xl">
              <SectionTitle>System Status</SectionTitle>
              {!systemStatus ? (
                <p className="text-sm text-zinc-500">Loading system status…</p>
              ) : (
                <div className="space-y-2">
                  {([
                    ['Backend API', systemStatus.backend],
                    ['Database', systemStatus.database],
                    ['Docker', systemStatus.docker],
                    ['kind', systemStatus.kind],
                    ['kubectl', systemStatus.kubectl],
                  ] as [string, { ok: boolean; message: string }][]).map(([name, stat]) => (
                    <div key={name} className="flex items-center justify-between rounded border border-zinc-800 px-4 py-3 text-xs">
                      <span className="text-zinc-400">{name}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-zinc-500 truncate max-w-xs text-right">{stat.message}</span>
                        <span className={stat.ok ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold'}>
                          {stat.ok ? '✓' : '✗'}
                        </span>
                      </div>
                    </div>
                  ))}

                  {systemStatus.kind.clusters.length > 0 && (
                    <div className="rounded border border-zinc-800 px-4 py-3 text-xs">
                      <span className="text-zinc-600">kind clusters: </span>
                      <span className="text-zinc-300">{systemStatus.kind.clusters.join(', ')}</span>
                    </div>
                  )}
                </div>
              )}

              <button
                onClick={() => getSystemStatus().then(setSystemStatus).catch(() => undefined)}
                className="rounded border border-zinc-700 px-4 py-2 text-xs text-zinc-400 hover:bg-zinc-800"
              >
                Refresh Status
              </button>

              <SectionTitle>About CodeDeck</SectionTitle>
              <div className="space-y-2 rounded border border-zinc-800 bg-zinc-900/60 p-4 text-xs text-zinc-400">
                <div><span className="text-zinc-300">Version:</span> 1.0.0</div>
                <div><span className="text-zinc-300">Stack:</span> FastAPI · PostgreSQL · React · Vite · kind</div>
                <div><span className="text-zinc-300">AI:</span> OpenAI GPT · Local embeddings · RAG pipeline</div>
                <div className="pt-2 border-t border-zinc-800 text-zinc-600">
                  Workflow: GitHub → Analysis → RAG → Q&amp;A → AI Testing → Docker → Kubernetes → Smoke Test
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
