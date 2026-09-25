const API_BASE = import.meta.env.VITE_API_URL ?? '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const headers = isFormData
    ? { ...(options?.headers ?? {}) }
    : { 'Content-Type': 'application/json', ...(options?.headers ?? {}) };

  const res = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.message || body.detail;
    const msg = typeof detail === 'string' ? detail : `Request failed (${res.status})`;
    throw new Error(msg);
  }

  if (res.status === 204 || res.headers.get('content-length') === '0') {
    return {} as T;
  }
  return res.json().catch(() => ({} as T));
}

export type Project = {
  id: number;
  repository_url: string;
  repository_name: string;
  status: string;
  created_at: string;
};

export type Analysis = {
  project_id: number;
  language: string | null;
  framework: string | null;
  package_manager: string | null;
  entrypoint: string | null;
  test_command: string | null;
  has_dockerfile: boolean;
  security_score: number | null;
  analysis_result: Record<string, unknown> | null;
  created_at: string;
};

export type PipelineStep = {
  name: string;
  status: string;
  result: string | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export function getHealth() {
  return request<{ status: string; service: string }>('/health');
}

export function listProjects() {
  return request<Project[]>('/api/projects');
}

export function createProject(repository_url: string) {
  return request<Project>('/api/projects', {
    method: 'POST',
    body: JSON.stringify({ repository_url }),
  });
}

export function startAnalysis(projectId: number) {
  return request<Analysis>(`/api/projects/${projectId}/analyze`, {
    method: 'POST',
  });
}

export function getAnalysis(projectId: number) {
  return request<Analysis | null>(`/api/projects/${projectId}/analysis`);
}

export function getPipeline(projectId: number) {
  return request<PipelineStep[]>(`/api/projects/${projectId}/pipeline`);
}

export function getProject(projectId: number) {
  return request<Project>(`/api/projects/${projectId}`);
}

export type GeneratedFile = {
  filename: string;
  content: string;
};

export function getFiles(projectId: number) {
  return request<GeneratedFile[]>(`/api/projects/${projectId}/files`);
}

export type SearchSource = {
  path: string;
  snippet: string;
  score: number;
  line_start: number;
  line_end: number;
};

export type RepositoryAnswer = {
  question: string;
  answer: string;
  sources: SearchSource[];
};

export function askRepositoryQuestion(projectId: number, question: string) {
  return request<RepositoryAnswer>(`/api/projects/${projectId}/qa`, {
    method: 'POST',
    body: JSON.stringify({ question }),
  });
}

export type EvaluationItem = {
  question: string;
  expected: string;
  answer: string;
  matched_source: string | null;
  status: string;
};

export type Evaluation = {
  questions: number;
  correct: number;
  retrieval_accuracy: number;
  results: EvaluationItem[];
};

export function getEvaluation(projectId: number) {
  return request<Evaluation>(`/api/projects/${projectId}/evaluation`);
}

export type GeneratedTestCase = {
  name: string;
  rationale: string;
  path: string;
  code: string;
};

export type GeneratedTestRun = {
  status: string;
  message: string;
  command: string | null;
  generated_tests: GeneratedTestCase[];
  stdout: string;
  stderr: string;
  failure_analysis: Record<string, unknown> | null;
};

export function runAiTests(projectId: number) {
  return request<GeneratedTestRun>(`/api/projects/${projectId}/ai-tests`, {
    method: 'POST',
  });
}

export type Deployment = {
  id: number;
  environment: string;
  version: string;
  status: string;
  deployment_type: string;
  details: Record<string, unknown> | null;
  created_at: string;
};

export function deployStaging(projectId: number) {
  return request<{
    status: string;
    message: string;
    deployment?: Deployment;
    details?: Record<string, unknown>;
  }>(`/api/projects/${projectId}/deploy/staging`, { method: 'POST' });
}

export function deployProduction(projectId: number) {
  return request<{
    status: string;
    message: string;
    deployment?: Deployment;
    details?: Record<string, unknown>;
  }>(`/api/projects/${projectId}/deploy/production`, { method: 'POST' });
}

export function approveProduction(projectId: number) {
  return request<{
    status: string;
    message: string;
    deployment?: Deployment;
  }>(`/api/projects/${projectId}/deploy/production/approve`, { method: 'POST' });
}

export function rollbackProduction(projectId: number) {
  return request<{
    status: string;
    message: string;
    deployment?: Deployment;
  }>(`/api/projects/${projectId}/rollback`, { method: 'POST' });
}

export function listDeployments(projectId: number) {
  return request<Deployment[]>(`/api/projects/${projectId}/deployments`);
}

