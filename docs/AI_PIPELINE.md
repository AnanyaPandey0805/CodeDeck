# CodeDeck — AI & RAG Pipeline

This document details the core artificial intelligence and Retrieval-Augmented Generation (RAG) pipelines powering CodeDeck's intelligent features. The pipeline transforms raw codebase data into actionable insights, automated testing, and deployment guidance.

```text
┌───────────────┐     ┌───────────────┐     ┌────────────────┐
│   User Repo   │────▶│ Deterministic │────▶│ Repository     │
│   (Source)    │     │   Analysis    │     │ Indexing (RAG) │
└───────────────┘     └───────────────┘     └────────────────┘
                                                    │
                                                    ▼
┌───────────────┐     ┌───────────────┐     ┌────────────────┐
│ AI Test       │◀────│ Deployment    │◀────│ Semantic       │
│ Generation    │     │ Generation    │     │ Retrieval      │
└───────────────┘     └───────────────┘     └────────────────┘
        │
        ▼
┌───────────────┐     ┌───────────────┐     ┌────────────────┐
│ Pipeline      │────▶│ AI Failure    │────▶│ Evaluation     │
│ Execution     │     │ Analysis      │     │ Mechanism      │
└───────────────┘     └───────────────┘     └────────────────┘
```

## 1. Deterministic Repository Analysis

Before engaging external AI models, CodeDeck performs a rapid, deterministic pass over the target repository. This step uses heuristics to extract hard truths about the codebase without incurring API latency or costs.

*   **Language Detection:** Scans for standard file extensions (e.g., `.py`, `.js`, `.go`).
*   **Framework Detection:** Inspects dependency files (`requirements.txt`, `package.json`, `go.mod`) for known framework signatures (FastAPI, Flask, Express, React).
*   **Port Detection:** Utilizes regex matching on entrypoint files to identify listening ports (e.g., `app.run(port=8080)`).
*   **Entrypoint Detection:** Identifies the primary execution script (e.g., `main.py`, `app.js`).

These signals serve as a reliable fallback and provide highly structured context for subsequent LLM prompts.

## 2. Repository Indexing

To provide the LLM with relevant context from the repository, CodeDeck builds a searchable local index.

1.  **File Selection:** The system filters out non-text files, binaries, and ignored directories (e.g., `node_modules`, `.git`, `.venv`) to ensure only relevant source code and documentation are processed.
2.  **Chunking:** Files are divided into smaller segments. CodeDeck uses a chunk size of approximately 1400 characters with an overlap of 220 characters. The overlap ensures that context isn't lost if an important function or thought spans across a chunk boundary.
3.  **Vectorization (Hashing):**
    *   *Implementation Note:* CodeDeck currently implements a lightweight, dependency-free embedding strategy. It uses term-frequency hashing based on SHA-256 mapped to a 192-dimensional vector.
    *   *Honesty Declaration:* This is a deterministic frequency hash, not a dense semantic embedding model (like those produced by transformers). It excels at exact keyword overlap but does not understand abstract semantic similarity (e.g., it won't inherently know that "create" and "build" are related).
4.  **Storage:** The chunks and their corresponding vector representations are stored locally in a `repo_index.json` file.

## 3. Semantic Retrieval

When a user asks a question or a process requires context, CodeDeck searches the generated index.

*   The user's query is vectorized using the same SHA-256 hashing mechanism.
*   The system performs a Cosine Similarity Search, comparing the query vector against all chunk vectors in the index.
*   The Top-K most similar chunks (highest cosine similarity scores) are retrieved.

## 4. AI Q&A Workflow

The RAG workflow answers user queries contextually.

1.  **Context Retrieval:** Relevant chunks are fetched via semantic search.
2.  **Prompt Assembly:** The system constructs a strict prompt (referencing strategies defined in `prompts.py`). It injects the user's question and the retrieved codebase chunks.
3.  **LLM Execution:** The prompt is sent to `gpt-4o-mini` (or similar configured model).
4.  **Grounding:** The prompt strictly instructs the LLM to base its answer *only* on the provided context and to cite its sources.
5.  **Fallback Mechanism:** If the OpenAI API key is unavailable, the system gracefully falls back to deterministic heuristic responses based on the initial analysis step, ensuring the platform remains functional offline.

## 5. Deployment Recommendation

CodeDeck leverages AI to determine the optimal deployment strategy.

*   The deterministic signals (language, framework, ports) and relevant file chunks (like `Dockerfile` if it exists, or `requirements.txt`) are passed to the LLM.
*   The LLM is prompted to output deployment guidance, specifically identifying missing infrastructure components (like generating a missing Dockerfile or standard Kubernetes manifests).

## 6. AI Test Generation

CodeDeck automates testing to validate deployment stability.

1.  **Route Detection:** Heuristics or AI identify API routes in the codebase.
2.  **Generation Prompt:** The LLM receives the route definitions and is instructed to generate testing code (specifically utilizing the `pytest` framework for Python projects).
3.  **Execution Environment:** The generated tests are saved to disk (e.g., `test_app.py`).
4.  **Subprocess Execution:** CodeDeck invokes a secure subprocess to run the `pytest` command. *The LLM does not execute the code.*
5.  **Parsing:** The standard output and standard error from the test runner are captured for analysis.

## 7. Deployment Failure Analysis

When an infrastructure task fails, AI accelerates the debugging process.

*   **Trigger:** A Docker build failure or a Kubernetes Pod crash (e.g., CrashLoopBackOff).
*   **Data Collection:** CodeDeck orchestrates the collection of raw error data, capturing Docker build logs or retrieving Pod logs via `kubectl logs`.
*   **Analysis Prompt:** The error trace, along with relevant codebase context (like the entrypoint script or Dockerfile), is sent to the LLM.
*   **Resolution:** The LLM responds with a root cause analysis and a proposed fix, significantly reducing Mean Time To Resolution (MTTR).

## 8. Evaluation Mechanism

To ensure the reliability of the RAG pipeline, CodeDeck includes a built-in evaluation protocol.

*   The system defines a standard set of 5 evaluation questions (e.g., "What are the core dependencies?", "What port does the application use?").
*   These questions are run automatically against the generated index.
*   The quality of the retrieved chunks (relevance) and the final LLM answers are evaluated to track pipeline performance and tune chunking/hashing parameters.

## Future Extension Points

*   **Dense Semantic Embeddings:** Migrating from the current SHA-256 frequency hashing to a dedicated local embedding model (e.g., via `sentence-transformers`) to enable true semantic understanding.
*   **Hybrid Search:** Implementing BM25 keyword search alongside dense vector search.
*   **Agentic Workflows:** Allowing the AI not just to recommend fixes, but to execute code edits and retry failed deployments autonomously.
