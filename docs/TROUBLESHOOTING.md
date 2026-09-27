# CodeDeck Troubleshooting Guide

This document provides practical solutions for common issues encountered during setup, operation, or local Kubernetes deployment in CodeDeck.

---

## 1. Docker & Container Issues

### Symptom: `Docker daemon unavailable`
- **Cause**: Docker Engine / Docker Desktop is not running on the host system, or the backend container cannot access `/var/run/docker.sock`.
- **Fix**:
  1. Start Docker Desktop or run `sudo systemctl start docker` on Linux.
  2. Verify access by running `docker info` in your terminal.
  3. If running via Docker Compose, ensure the `/var/run/docker.sock` volume mount is active.

### Symptom: `Docker build timeout (1800s exceeded)`
- **Cause**: Heavy dependency installation (e.g. compiling large C extensions or downloading massive packages) exceeded the default timeout.
- **Fix**: Increase `DOCKER_BUILD_TIMEOUT` in your `.env` file or optimize the repository's `requirements.txt` / `package.json`.

---

## 2. Kubernetes (`kind`) Issues

### Symptom: `Kind cluster 'deploymind' unavailable`
- **Cause**: The local Kubernetes cluster has not been created yet.
- **Fix**: Run the following command to provision the cluster:
  ```bash
  kind create cluster --name deploymind
  ```

### Symptom: `ImagePullBackOff` or `ErrImagePull`
- **Cause**: Kubernetes is trying to pull the image from a remote registry instead of using the local image loaded into `kind`.
- **Fix**: Ensure the generated manifest has `imagePullPolicy: Never` for local `kind` deployments. CodeDeck automatically patches manifests for local cluster compatibility.

---

## 3. Backend & Database Issues

### Symptom: `PostgreSQL connection failed`
- **Cause**: The database container is starting up or port 5433/5432 is blocked.
- **Fix**:
  1. Check database container status: `docker compose ps db`.
  2. Inspect DB logs: `docker compose logs db`.
  3. Verify `DATABASE_URL` in `.env`.

### Symptom: `HTTP 504 Gateway Timeout on Analyze or Deploy`
- **Cause**: Long-running operations like cloning or building images ran synchronously on host HTTP requests.
- **Fix**: CodeDeck uses FastAPI `BackgroundTasks` for deployments. Status can be polled asynchronously via `/api/projects/{id}/pipeline` or `/api/projects/{id}`.
