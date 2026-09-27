# CodeDeck — Comprehensive Project Explanation

CodeDeck is an AI-assisted software delivery and DevOps platform designed to simplify and automate the lifecycle of software repositories — from source code ingestion to production deployment on local Kubernetes (`kind`) clusters.

## Core Purpose

Modern software development requires developers to handle complex tasks across code analysis, dependency management, unit testing, containerization, Kubernetes manifest generation, deployment orchestration, and failure diagnosis. 

CodeDeck unifies these operational steps into an automated, observable workflow:

1. **Repository Ingestion & Analysis**: Clones public GitHub repositories and performs deterministic detection of technology stack, dependencies, framework, entrypoints, and ports.
2. **Repository Intelligence (RAG)**: Indexing repository contents via term-frequency hash embeddings and storing vector representation for grounded Q&A and architecture discovery.
3. **Automated Testing & Security Audit**: Runs native test suites (e.g. pytest/npm), generates route-focused AI tests for FastAPI/Flask, and performs static security scanning for hardcoded secrets and container privilege risks.
4. **Containerization**: Generates optimized Dockerfiles tailored to the detected stack and builds container images.
5. **Kubernetes Deployment**: Provisions and applies Kubernetes Deployment, Service, and RBAC manifests to a local `kind` cluster with real rollout tracking and HTTP smoke tests.
6. **Failure Diagnosis**: Extracts Pod logs and events when deployments encounter errors and uses LLMs to synthesize actionable root-cause analysis.

## System Architecture Overview

```
                      +-------------------+
                      |   React Frontend  |
                      |   (Vite / Tailwind) |
                      +---------+---------+
                                |
                                v REST API
                      +---------+---------+
                      |  FastAPI Backend  |
                      +----+----+----+----+
                           |    |    |
        +------------------+    |    +------------------+
        |                       v                       |
        v               +-------+-------+               v
+-------+-------+       |   LangGraph   |       +-------+-------+
|  PostgreSQL   |       | Orchestrator  |       | Docker & kind |
|  Database     |       +-------+-------+       | Kubernetes    |
+---------------+               |               +---------------+
                                v
                        +-------+-------+
                        | AI / RAG Engine|
                        | (OpenAI / RAG)|
                        +---------------+
```
