# DeployMind AI Pipeline

## 1. Repository Analysis

DeployMind starts with deterministic repository analysis:

- detect language
- detect framework
- detect package manager
- detect entrypoint
- detect test command
- detect Dockerfile / Kubernetes presence
- detect multi-service repository shape

## 2. Repository RAG

The repository intelligence layer uses a lightweight local RAG pipeline:

```text
Clone repository
  -> read code/docs
  -> split into chunks
  -> build local hashed embeddings
  -> persist repository index
  -> semantic search
  -> answer with retrieved context
```

This is intentionally simple so the project stays explainable in a course viva.

## 3. Deployment Recommendation

DeployMind combines:

- repository analysis signals
- indexed repository evidence
- route and health detection
- database hints

to generate a grounded deployment recommendation with:

- detected stack
- likely issues
- recommended next steps
- supporting evidence

## 4. AI Testing

DeployMind has two testing layers:

- run the repository's existing detected test command
- generate a very small set of route-focused tests for supported FastAPI and Flask repositories

If the generated tests fail, DeployMind returns a short explanation of the likely reason based on logs and error text.

## 5. Deployment Failure Analysis

When deployment fails, DeployMind collects:

- deployment error text
- pod and deployment status
- recent logs when possible

It then produces:

- likely cause
- evidence
- safest suggested fix

If evidence is weak, the system falls back to an explicit insufficient-information answer instead of guessing.

## 6. Evaluation

DeployMind evaluates the retrieval layer with predefined questions such as:

- What framework does this repository use?
- What language does this repository use?
- What package manager does this repository use?
- What is the deployment entrypoint?
- What port does the application use?

The output is a small report with total questions, relevant/correct answers, and retrieval accuracy.

## Prompt Organization

Prompt definitions are kept in `backend/app/core/prompts.py` for:

- repository analysis wording
- RAG Q&A
- deployment recommendation
- test generation
- deployment failure analysis
