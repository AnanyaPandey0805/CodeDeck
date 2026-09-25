import { useEffect, useState, type FormEvent } from 'react'
import {
  approveProduction,
  askRepositoryQuestion,
  createProject,
  deployProduction,
  deployStaging,
  getEvaluation,
  getAnalysis,
  getFiles,
  getHealth,
  getPipeline,
  getProject,
  listDeployments,
  listProjects,
  runAiTests,
  rollbackProduction,
  startAnalysis,
  type Analysis,
  type Evaluation,
  type GeneratedTestRun,
  type Deployment,
  type GeneratedFile,
  type PipelineStep,
  type Project,
  type RepositoryAnswer,
} from './api'

const DEFAULT_STEPS = [
  'Repository Analysis',
  'Repository Intelligence',
  'Tests',
  'Security',
  'Docker',
  'Kubernetes',
  'Staging',
  'Production',
  'Completed',
]

function stepIcon(status: string) {
  if (status === 'completed') return '✓'
  if (status === 'warning') return '⚠'
  if (status === 'failed') return '✗'
  if (status === 'running') return '●'
  return '○'
}

export default function App() {
  const [url, setUrl] = useState('')
  const [projects, setProjects] = useState<Project[]>([])
  const [selected, setSelected] = useState<Project | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [pipeline, setPipeline] = useState<PipelineStep[]>([])
  const [files, setFiles] = useState<GeneratedFile[]>([])
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [deployments, setDeployments] = useState<Deployment[]>([])
  const [deploying, setDeploying] = useState(false)
  const [deployingProd, setDeployingProd] = useState(false)
  const [approvingProd, setApprovingProd] = useState(false)
  const [rollingBack, setRollingBack] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [apiOk, setApiOk] = useState<boolean | null>(null)
  const [question, setQuestion] = useState('What framework does this repository use?')
  const [qaResult, setQaResult] = useState<RepositoryAnswer | null>(null)
  const [askingQuestion, setAskingQuestion] = useState(false)
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [loadingEvaluation, setLoadingEvaluation] = useState(false)
  const [aiTests, setAiTests] = useState<GeneratedTestRun | null>(null)
  const [runningAiTests, setRunningAiTests] = useState(false)

  useEffect(() => {
    getHealth()
      .then(() => setApiOk(true))
      .catch(() => setApiOk(false))
    listProjects()
      .then(setProjects)
      .catch(() => setProjects([]))
  }, [])

  useEffect(() => {
    if (!selected) return
    const isBusy =
      selected.status === 'deploying' ||
      selected.status === 'deploying_green' ||
      selected.status === 'analyzing' ||
      pipeline.some((s) => s.status === 'running')

    if (!isBusy) return

    const interval = setInterval(() => {
      loadProject(selected).catch(() => undefined)
    }, 3000)

    return () => clearInterval(interval)
  }, [selected?.id, selected?.status, pipeline])

  useEffect(() => {
    const next = (analysis?.analysis_result ?? {}) as Record<string, unknown>
    setEvaluation((next.evaluation_result as Evaluation | undefined) ?? null)
    setAiTests((next.ai_test_result as GeneratedTestRun | undefined) ?? null)
    setQaResult(null)
  }, [selected?.id, analysis?.created_at])


  async function loadProject(project: Project, isManualSelect = false) {
    if (isManualSelect) {
      setError(null)
    }
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
    setSelectedFile((prev) => {
      if (!prev) return generated[0]?.filename ?? null
      if (!generated.some((f) => f.filename === prev)) return generated[0]?.filename ?? null
      return prev
    })
    setDeployments(deps)
    setProjects((prev) => prev.map((p) => (p.id === fresh.id ? fresh : p)))
  }

  async function onAnalyze(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const project = await createProject(url.trim())
      setSelected(project)
      setProjects((prev) => [project, ...prev.filter((p) => p.id !== project.id)])
      const result = await startAnalysis(project.id)
      setAnalysis(result)
      const [steps, fresh, generated, deps] = await Promise.all([
        getPipeline(project.id),
        getProject(project.id),
        getFiles(project.id),
        listDeployments(project.id),
      ])
      setPipeline(steps)
      setSelected(fresh)
      setFiles(generated)
      setSelectedFile(generated[0]?.filename ?? null)
      setDeployments(deps)
      setProjects((prev) => prev.map((p) => (p.id === fresh.id ? fresh : p)))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
      if (selected) {
        getPipeline(selected.id).then(setPipeline).catch(() => undefined)
      }
    } finally {
      setBusy(false)
    }
  }

  async function onDeployStaging() {
    if (!selected) return
    setDeploying(true)
    setError(null)
    try {
      const result = await deployStaging(selected.id)
      const [steps, fresh, deps] = await Promise.all([
        getPipeline(selected.id),
        getProject(selected.id),
        listDeployments(selected.id),
      ])
      setPipeline(steps)
      setSelected(fresh)
      setDeployments(deps)
      setProjects((prev) => prev.map((p) => (p.id === fresh.id ? fresh : p)))
      if (result.status === 'failed') {
        setError(result.message)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Deploy failed')
      getPipeline(selected.id).then(setPipeline).catch(() => undefined)
    } finally {
      setDeploying(false)
    }
  }

  async function onDeployProduction() {
    if (!selected) return
    setDeployingProd(true)
    setError(null)
    try {
      const result = await deployProduction(selected.id)
      const [steps, fresh, deps] = await Promise.all([
        getPipeline(selected.id),
        getProject(selected.id),
        listDeployments(selected.id),
      ])
      setPipeline(steps)
      setSelected(fresh)
      setDeployments(deps)
      setProjects((prev) => prev.map((p) => (p.id === fresh.id ? fresh : p)))
      if (result.status === 'failed') {
        setError(result.message)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Production deploy failed')
      getPipeline(selected.id).then(setPipeline).catch(() => undefined)
    } finally {
      setDeployingProd(false)
    }
  }

  async function onApproveProduction() {
    if (!selected) return
    setApprovingProd(true)
    setError(null)
    try {
      const result = await approveProduction(selected.id)
      const [steps, fresh, deps] = await Promise.all([
        getPipeline(selected.id),
        getProject(selected.id),
        listDeployments(selected.id),
      ])
      setPipeline(steps)
      setSelected(fresh)
      setDeployments(deps)
      setProjects((prev) => prev.map((p) => (p.id === fresh.id ? fresh : p)))
      if (result.status === 'failed') {
        setError(result.message)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approval failed')
      getPipeline(selected.id).then(setPipeline).catch(() => undefined)
    } finally {
      setApprovingProd(false)
    }
  }

  async function onRollback() {
    if (!selected) return
    setRollingBack(true)
    setError(null)
    try {
      const result = await rollbackProduction(selected.id)
      const [steps, fresh, deps] = await Promise.all([
        getPipeline(selected.id),
        getProject(selected.id),
        listDeployments(selected.id),
      ])
      setPipeline(steps)
      setSelected(fresh)
      setDeployments(deps)
      setProjects((prev) => prev.map((p) => (p.id === fresh.id ? fresh : p)))
      if (result.status === 'failed') {
        setError(result.message)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rollback failed')
      getPipeline(selected.id).then(setPipeline).catch(() => undefined)
    } finally {
      setRollingBack(false)
    }
  }

  async function onAskQuestion(e: FormEvent) {
    e.preventDefault()
    if (!selected || !question.trim()) return
    setAskingQuestion(true)
    setError(null)
    try {
      const result = await askRepositoryQuestion(selected.id, question.trim())
      setQaResult(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Repository Q&A failed')
    } finally {
      setAskingQuestion(false)
    }
  }

  async function onRefreshEvaluation() {
    if (!selected) return
    setLoadingEvaluation(true)
    setError(null)
    try {
      const result = await getEvaluation(selected.id)
      setEvaluation(result)
      const latest = await getAnalysis(selected.id)
      setAnalysis(latest)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Evaluation failed')
    } finally {
      setLoadingEvaluation(false)
    }
  }

  async function onRunAiTests() {
    if (!selected) return
    setRunningAiTests(true)
    setError(null)
    try {
      const result = await runAiTests(selected.id)
      setAiTests(result)
      const latest = await getAnalysis(selected.id)
      setAnalysis(latest)
      const steps = await getPipeline(selected.id)
      setPipeline(steps)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI-generated tests failed')
    } finally {
      setRunningAiTests(false)
    }
  }

  const pipelineByName = Object.fromEntries(pipeline.map((s) => [s.name, s]))
  const analysisExtra = (analysis?.analysis_result ?? {}) as Record<string, unknown>
  const testResult = analysisExtra.test_result as Record<string, unknown> | undefined
  const recommendation = analysisExtra.deployment_recommendation as
    | {
        summary?: string
        detected?: Record<string, unknown>
        potential_issues?: string[]
        recommendation?: string[]
        evidence?: string[]
      }
    | undefined
  const securityResult = analysisExtra.security_result as
    | { findings?: Array<{ severity: string; file: string; message: string }>; summary?: string }
    | undefined
  const securityFindings = securityResult?.findings ?? []
  const failedDeployment = deployments.find((d) => d.status === 'failed')
  const failureAnalysis = (failedDeployment?.details as { failure_analysis?: Record<string, unknown> } | null | undefined)
    ?.failure_analysis

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <header className="mb-10 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-1 font-mono text-xs tracking-[0.2em] text-accent uppercase">
            Software delivery assistant
          </p>
          <h1 className="text-4xl font-semibold tracking-tight text-ink sm:text-5xl">CodeDeck</h1>
          <p className="mt-2 max-w-xl text-slate">
            Analyze a GitHub repo, generate Docker and Kubernetes configs, and run a controlled
            local deployment workflow.
          </p>
        </div>
        <div
          className={`rounded-md border px-3 py-1.5 font-mono text-xs ${
            apiOk === null
              ? 'border-slate/20 text-slate'
              : apiOk
                ? 'border-ok/30 bg-ok/5 text-ok'
                : 'border-danger/30 bg-danger/5 text-danger'
          }`}
        >
          API {apiOk === null ? '…' : apiOk ? 'online' : 'offline'}
        </div>
      </header>

      <section className="rounded-xl border border-ink/10 bg-white/80 p-6 shadow-sm backdrop-blur">
        <h2 className="mb-4 text-lg font-medium">GitHub Repository</h2>
        <form onSubmit={onAnalyze} className="flex flex-col gap-3 sm:flex-row">
          <input
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://github.com/owner/repo"
            className="w-full rounded-lg border border-ink/15 bg-paper px-4 py-3 font-mono text-sm outline-none ring-accent focus:ring-2"
          />
          <button
            type="submit"
            disabled={busy}
            className="shrink-0 rounded-lg bg-accent px-5 py-3 text-sm font-medium text-white transition hover:bg-accent-dark disabled:opacity-60"
          >
            {busy ? 'Analyzing…' : 'Analyze Repository'}
          </button>
        </form>
        {error && <p className="mt-3 text-sm text-danger">{error}</p>}
      </section>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="rounded-xl border border-ink/10 bg-white/80 p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-medium">Pipeline</h2>
          <ol className="space-y-3">
            {DEFAULT_STEPS.map((name) => {
              const step = pipelineByName[name]
              const status = step?.status ?? 'pending'
              return (
                <li key={name} className="flex items-start gap-3 text-sm">
                  <span
                    className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border font-mono text-xs ${
                      status === 'warning'
                        ? 'border-warn/40 text-warn'
                        : status === 'completed'
                          ? 'border-ok/40 text-ok'
                          : status === 'failed'
                            ? 'border-danger/40 text-danger'
                            : status === 'running'
                              ? 'border-accent/40 text-accent'
                              : 'border-ink/15 text-slate'
                    }`}
                  >
                    {stepIcon(status)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-ink">{name}</span>
                      <span className="ml-auto font-mono text-xs text-slate">{status}</span>
                    </div>
                    {step?.result && <p className="mt-0.5 text-xs text-slate">{step.result}</p>}
                    {step?.error && <p className="mt-0.5 text-xs text-danger">{step.error}</p>}
                  </div>
                </li>
              )
            })}
          </ol>
        </section>

        <section className="rounded-xl border border-ink/10 bg-white/80 p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-medium">Recent Projects</h2>
          {projects.length === 0 ? (
            <p className="text-sm text-slate">No projects yet. Submit a repository to get started.</p>
          ) : (
            <ul className="space-y-2">
              {projects.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    onClick={() => loadProject(p, true).catch((err) => setError(String(err.message || err)))}
                    className={`w-full rounded-lg border px-3 py-2 text-left transition ${
                      selected?.id === p.id
                        ? 'border-accent bg-accent/5'
                        : 'border-ink/10 hover:border-ink/25'
                    }`}
                  >
                    <div className="font-medium">{p.repository_name}</div>
                    <div className="truncate font-mono text-xs text-slate">{p.repository_url}</div>
                    <div className="mt-1 font-mono text-xs text-slate">status: {p.status}</div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="mt-8 rounded-xl border border-ink/10 bg-white/80 p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-medium">Analysis</h2>
        {!analysis ? (
          <p className="text-sm text-slate">
            Stack detection will appear here after you analyze a repository.
          </p>
        ) : (
          <>
            <dl className="grid gap-3 sm:grid-cols-2">
              <div>
                <dt className="font-mono text-xs text-slate uppercase">Language</dt>
                <dd className="text-ink">{analysis.language ?? '—'}</dd>
              </div>
              <div>
                <dt className="font-mono text-xs text-slate uppercase">Framework</dt>
                <dd className="text-ink">{analysis.framework ?? '—'}</dd>
              </div>
              <div>
                <dt className="font-mono text-xs text-slate uppercase">Package manager</dt>
                <dd className="text-ink">{analysis.package_manager ?? '—'}</dd>
              </div>
              <div>
                <dt className="font-mono text-xs text-slate uppercase">Entrypoint</dt>
                <dd className="font-mono text-sm text-ink">{analysis.entrypoint ?? '—'}</dd>
              </div>
              <div>
                <dt className="font-mono text-xs text-slate uppercase">Port</dt>
                <dd className="font-mono text-sm text-ink">{String(analysisExtra.port ?? '—')}</dd>
              </div>
              <div>
                <dt className="font-mono text-xs text-slate uppercase">Test command</dt>
                <dd className="font-mono text-sm text-ink">{analysis.test_command ?? '—'}</dd>
              </div>
              <div>
                <dt className="font-mono text-xs text-slate uppercase">Security score</dt>
                <dd className="text-ink">
                  {analysis.security_score != null ? `${analysis.security_score}/100` : '—'}
                  <span className="ml-2 font-mono text-xs text-slate">(basic scan)</span>
                </dd>
              </div>
            </dl>

            {Boolean(analysisExtra.multiservice_notice) && (
              <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-3 font-mono text-xs text-blue-900">
                {String(analysisExtra.multiservice_notice)}
              </div>
            )}

            {recommendation && (
              <div className="mt-6 rounded-lg border border-ink/10 bg-paper p-4">
                <h3 className="mb-2 text-sm font-medium">Deployment recommendation</h3>
                <p className="text-sm text-ink">{recommendation.summary ?? 'No recommendation generated yet.'}</p>
                {recommendation.potential_issues && recommendation.potential_issues.length > 0 && (
                  <ul className="mt-3 space-y-1 text-sm text-slate">
                    {recommendation.potential_issues.map((item) => (
                      <li key={item}>- {item}</li>
                    ))}
                  </ul>
                )}
                {recommendation.recommendation && recommendation.recommendation.length > 0 && (
                  <ul className="mt-3 space-y-1 text-sm text-ink">
                    {recommendation.recommendation.map((item) => (
                      <li key={item}>- {item}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}


            {testResult && (
              <div className="mt-6 border-t border-ink/10 pt-4">
                <h3 className="mb-2 text-sm font-medium">Test result</h3>
                <p className="text-sm text-ink">{String(testResult.message ?? testResult.status)}</p>
                {testResult.command != null && (
                  <p className="mt-1 font-mono text-xs text-slate">{String(testResult.command)}</p>
                )}
              </div>
            )}

            {securityFindings.length > 0 && (
              <div className="mt-6 border-t border-ink/10 pt-4">
                <h3 className="mb-2 text-sm font-medium">Security findings</h3>
                <ul className="space-y-2">
                  {securityFindings.map((f, i) => (
                    <li key={`${f.file}-${i}`} className="rounded-lg border border-ink/10 px-3 py-2 text-sm">
                      <span
                        className={`font-mono text-xs ${
                          f.severity === 'HIGH' ? 'text-danger' : 'text-warn'
                        }`}
                      >
                        {f.severity}
                      </span>
                      <span className="mx-2 text-slate">{f.file}</span>
                      <span className="text-ink">{f.message}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </section>

      <section className="mt-8 rounded-xl border border-ink/10 bg-white/80 p-6 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-medium">Repository Q&A</h2>
            <p className="text-sm text-slate">
              Ask grounded questions against the indexed repository chunks and review the retrieved evidence.
            </p>
          </div>
          <button
            type="button"
            disabled={!selected || loadingEvaluation}
            onClick={() => onRefreshEvaluation()}
            className="rounded-lg border border-ink/10 px-3 py-2 text-sm text-ink transition hover:bg-paper disabled:opacity-50"
          >
            {loadingEvaluation ? 'Refreshing evaluation...' : 'Refresh evaluation'}
          </button>
        </div>

        <form onSubmit={onAskQuestion} className="flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Where is authentication implemented?"
            className="w-full rounded-lg border border-ink/15 bg-paper px-4 py-3 font-mono text-sm outline-none ring-accent focus:ring-2"
          />
          <button
            type="submit"
            disabled={!selected || askingQuestion}
            className="shrink-0 rounded-lg bg-ink px-5 py-3 text-sm font-medium text-white transition hover:bg-ink/90 disabled:opacity-60"
          >
            {askingQuestion ? 'Searching...' : 'Ask'}
          </button>
        </form>

        {qaResult && (
          <div className="mt-5 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-lg border border-ink/10 bg-paper p-4">
              <div className="font-mono text-xs uppercase text-slate">Answer</div>
              <p className="mt-2 text-sm text-ink">{qaResult.answer}</p>
            </div>
            <div className="rounded-lg border border-ink/10 bg-paper p-4">
              <div className="font-mono text-xs uppercase text-slate">Retrieved context</div>
              <div className="mt-2 space-y-3">
                {qaResult.sources.map((source) => (
                  <div key={`${source.path}-${source.line_start}`} className="text-sm">
                    <div className="font-mono text-xs text-accent">
                      {source.path}:{source.line_start}-{source.line_end} ({source.score.toFixed(2)})
                    </div>
                    <p className="mt-1 text-slate">{source.snippet}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {evaluation && (
          <div className="mt-6 border-t border-ink/10 pt-4">
            <div className="flex flex-wrap items-center gap-3">
              <h3 className="text-sm font-medium">Retrieval evaluation</h3>
              <span className="rounded bg-accent/10 px-2 py-1 font-mono text-xs text-accent">
                {evaluation.correct}/{evaluation.questions} relevant
              </span>
              <span className="font-mono text-xs text-slate">
                accuracy: {evaluation.retrieval_accuracy}%
              </span>
            </div>
            <div className="mt-3 space-y-2">
              {evaluation.results.map((item) => (
                <div key={item.question} className="rounded-lg border border-ink/10 px-3 py-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-ink">{item.question}</span>
                    <span className="ml-auto font-mono text-xs text-slate">{item.status}</span>
                  </div>
                  <p className="mt-1 text-xs text-slate">expected: {item.expected}</p>
                  <p className="mt-1 text-xs text-ink">{item.answer}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      <section className="mt-8 rounded-xl border border-ink/10 bg-white/80 p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-medium">Generated Files</h2>
        {files.length === 0 ? (
          <p className="text-sm text-slate">Dockerfile and Kubernetes manifests will appear here after generation.</p>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[12rem_1fr]">
            <ul className="space-y-1">
              {files.map((f) => (
                <li key={f.filename}>
                  <button
                    type="button"
                    onClick={() => setSelectedFile(f.filename)}
                    className={`w-full rounded-md px-3 py-2 text-left font-mono text-xs transition ${
                      selectedFile === f.filename
                        ? 'bg-accent/10 text-accent'
                        : 'text-slate hover:bg-ink/5'
                    }`}
                  >
                    {f.filename}
                  </button>
                </li>
              ))}
            </ul>
            <pre className="max-h-[28rem] overflow-auto rounded-lg border border-ink/10 bg-paper p-4 font-mono text-xs leading-relaxed text-ink">
              {files.find((f) => f.filename === selectedFile)?.content ?? ''}
            </pre>
          </div>
        )}
      </section>

      <section className="mt-8 rounded-xl border border-ink/10 bg-white/80 p-6 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-medium">AI Testing</h2>
            <p className="text-sm text-slate">
              Generate a very small route-focused test set from the detected repository entrypoint and run it safely.
            </p>
          </div>
          <button
            type="button"
            disabled={!selected || runningAiTests}
            onClick={() => onRunAiTests()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-dark disabled:opacity-60"
          >
            {runningAiTests ? 'Running AI tests...' : 'Run AI-generated tests'}
          </button>
        </div>

        {!aiTests ? (
          <p className="text-sm text-slate">No AI-generated tests have been run for this project yet.</p>
        ) : (
          <div className="space-y-4">
            <div className="rounded-lg border border-ink/10 bg-paper p-4">
              <div className="flex items-center gap-2">
                <span className="font-medium text-ink">{aiTests.message}</span>
                <span className="ml-auto font-mono text-xs text-slate">{aiTests.status}</span>
              </div>
              {aiTests.command && (
                <p className="mt-2 font-mono text-xs text-slate">{aiTests.command}</p>
              )}
            </div>

            {aiTests.generated_tests.map((testCase) => (
              <div key={testCase.path} className="rounded-lg border border-ink/10 bg-white p-4">
                <div className="font-medium text-ink">{testCase.name}</div>
                <p className="mt-1 text-sm text-slate">{testCase.rationale}</p>
                <pre className="mt-3 max-h-72 overflow-auto rounded-lg border border-ink/10 bg-paper p-3 font-mono text-xs leading-relaxed text-ink">
                  {testCase.code}
                </pre>
              </div>
            ))}

            {(aiTests.stdout || aiTests.stderr) && (
              <div className="grid gap-4 lg:grid-cols-2">
                <pre className="max-h-72 overflow-auto rounded-lg border border-ink/10 bg-paper p-3 font-mono text-xs leading-relaxed text-ink">
                  {aiTests.stdout || 'No stdout'}
                </pre>
                <pre className="max-h-72 overflow-auto rounded-lg border border-ink/10 bg-paper p-3 font-mono text-xs leading-relaxed text-ink">
                  {aiTests.stderr || 'No stderr'}
                </pre>
              </div>
            )}

            {aiTests.failure_analysis && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
                <h3 className="font-medium">AI test failure analysis</h3>
                <p className="mt-2">{String(aiTests.failure_analysis.likely_cause ?? 'No analysis')}</p>
                <p className="mt-2 text-xs">
                  Suggested fix: {String(aiTests.failure_analysis.suggested_fix ?? 'Review the logs and generated test code.')}
                </p>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="mt-8 rounded-xl border border-ink/10 bg-white/80 p-6 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-medium">Deployment Workflow</h2>
            <p className="text-sm text-slate">
              Staging &amp; Blue-Green Production deployment with human-in-the-loop approval.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={!selected || files.length === 0 || deploying || busy}
              onClick={() => onDeployStaging()}
              className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white transition hover:bg-ink/90 disabled:opacity-50"
            >
              {deploying ? 'Deploying Staging…' : 'Deploy Staging'}
            </button>
            <button
              type="button"
              disabled={!selected || files.length === 0 || deployingProd || busy}
              onClick={() => onDeployProduction()}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:opacity-50"
            >
              {deployingProd ? 'Deploying GREEN…' : 'Deploy Production (GREEN)'}
            </button>
          </div>
        </div>

        {/* Approval Alert Banner */}
        {selected?.status === 'production_awaiting_approval' && (
          <div className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="font-semibold text-amber-900">Production Approval Required</h3>
                <p className="text-sm text-amber-800">
                  GREEN version is built, deployed, and verified. Approve to switch live traffic to GREEN.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={approvingProd}
                  onClick={() => onApproveProduction()}
                  className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-semibold text-white shadow transition hover:bg-emerald-700 disabled:opacity-50"
                >
                  {approvingProd ? 'Switching Traffic…' : 'Approve Production'}
                </button>
                <button
                  type="button"
                  disabled={rollingBack}
                  onClick={() => onRollback()}
                  className="rounded-lg border border-rose-300 bg-white px-4 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                >
                  {rollingBack ? 'Rolling Back…' : 'Rollback to BLUE'}
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-ink/10 bg-paper p-4">
            <div className="font-mono text-xs text-slate uppercase">Staging Status</div>
            <div className="mt-1 flex items-center justify-between">
              <span className="font-medium text-ink">
                {deployments.find((d) => d.environment === 'staging')?.status ?? 'Not deployed'}
              </span>
              <span className="rounded bg-accent/10 px-2 py-0.5 font-mono text-xs text-accent">
                BLUE
              </span>
            </div>
          </div>
          <div className="rounded-lg border border-ink/10 bg-paper p-4">
            <div className="font-mono text-xs text-slate uppercase">Production Status</div>
            <div className="mt-1 flex items-center justify-between">
              <span className="font-medium text-ink">
                {selected?.status === 'production_healthy'
                  ? 'Active (GREEN)'
                  : selected?.status === 'production_awaiting_approval'
                    ? 'Awaiting Approval'
                    : selected?.status === 'rolled_back'
                      ? 'Rolled Back (BLUE)'
                      : 'Not deployed'}
              </span>
              <div className="flex items-center gap-2">
                {(selected?.status === 'production_healthy' || selected?.status === 'rolled_back') && (
                  <button
                    type="button"
                    disabled={rollingBack}
                    onClick={() => onRollback()}
                    className="rounded border border-rose-300 bg-rose-50 px-2 py-0.5 font-mono text-xs text-rose-700 hover:bg-rose-100 disabled:opacity-50"
                  >
                    {rollingBack ? '…' : 'Rollback'}
                  </button>
                )}
                <span
                  className={`rounded px-2 py-0.5 font-mono text-xs ${
                    selected?.status === 'production_healthy'
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-slate/10 text-slate'
                  }`}
                >
                  {selected?.status === 'production_healthy' ? 'GREEN' : 'BLUE'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {deployments.length > 0 && (
          <div className="mt-6 border-t border-ink/10 pt-4">
            <h3 className="mb-3 text-sm font-semibold text-ink">Deployment History</h3>
            <div className="space-y-2">
              {deployments.map((d) => (
                <div key={d.id} className="flex flex-col gap-1 rounded-lg border border-ink/10 bg-white p-3 text-sm sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-3">
                    <span
                      className={`inline-block rounded px-2 py-0.5 font-mono text-xs font-semibold ${
                        d.version === 'green'
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-blue-100 text-blue-800'
                      }`}
                    >
                      {d.version.toUpperCase()}
                    </span>
                    <span className="font-medium text-ink capitalize">{d.environment}</span>
                    <span className="font-mono text-xs text-slate">({d.deployment_type})</span>
                  </div>
                  <div className="flex items-center gap-4 text-xs">
                    <span
                      className={`font-semibold capitalize ${
                        d.status === 'healthy' || d.status === 'passed'
                          ? 'text-ok'
                          : d.status === 'awaiting_approval'
                            ? 'text-warn'
                            : d.status === 'rolled_back'
                              ? 'text-purple-600'
                              : 'text-danger'
                      }`}
                    >
                      {d.status.replace('_', ' ')}
                    </span>
                    <span className="font-mono text-slate">
                      {new Date(d.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  {d.details && 'message' in d.details && (
                    <div className="w-full text-xs text-slate sm:w-auto">
                      {String(d.details.message)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {failureAnalysis && (
        <section className="mt-8 rounded-xl border border-amber-200 bg-amber-50/80 p-6 shadow-sm">
          <h2 className="mb-3 text-lg font-medium text-amber-950">Deployment Failure Analysis</h2>
          <p className="text-sm text-amber-950">
            {String(failureAnalysis.likely_cause ?? failureAnalysis.failure ?? 'No failure analysis available.')}
          </p>
          <p className="mt-2 text-sm text-amber-900">
            Suggested fix: {String(failureAnalysis.suggested_fix ?? 'Review rollout status, pod logs, and smoke-test output.')}
          </p>
        </section>
      )}
    </div>
  )
}
