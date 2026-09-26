# DeployMind Troubleshooting Guide

This document provides practical fixes for common errors encountered when using DeployMind locally.

---

### Docker unavailable
**Symptom**: `docker: command not found` or `Cannot connect to the Docker daemon`.
**Fix**: Ensure Docker Desktop or Docker Engine is installed and running. If running DeployMind inside a container, ensure `/var/run/docker.sock` is correctly mounted in the `docker-compose.yml`.

### Docker Hub unavailable / Rate Limited
**Symptom**: Docker build fails with `toomanyrequests: You have reached your pull rate limit`.
**Fix**: Log into Docker Hub (`docker login`) to increase your pull rate limits, or use an authenticated Docker Hub proxy.

### kind missing
**Symptom**: `kind: command not found`.
**Fix**: Install `kind` from [kind.sigs.k8s.io](https://kind.sigs.k8s.io/docs/user/quick-start/#installation).

### kind cluster missing
**Symptom**: `Kubernetes cluster 'deploymind' is unavailable. Create or start the kind cluster`.
**Fix**: Create the local cluster:
```bash
kind create cluster --name deploymind
```

### Kubernetes API timeout
**Symptom**: `kubectl cluster-info` times out after 10 seconds.
**Fix**: The `kind` container may be paused, stopped, or experiencing network issues. Restart it via Docker Desktop, or recreate it:
```bash
kind delete cluster --name deploymind
kind create cluster --name deploymind
```

### kubeconfig problem
**Symptom**: `The connection to the server localhost:8080 was refused`.
**Fix**: Ensure your `~/.kube/config` exists and is mounted correctly. Run `kubectl cluster-info --context kind-deploymind` on your host to populate the kubeconfig, then restart DeployMind.

### Docker build timeout
**Symptom**: `Docker build timed out after 1800 seconds`.
**Fix**: The repository's build took longer than the configured timeout (default 30 mins). Increase `DOCKER_BUILD_TIMEOUT` in `.env` and retry. Ensure the Docker daemon has sufficient CPU/Memory allocated.

### Docker build context error
**Symptom**: `COPY failed: file not found in build context`.
**Fix**: The Dockerfile attempts to copy files that are outside of its directory. DeployMind automatically detects root-level config files (like `package.json` or `pyproject.toml`) and sets the context to the repository root. Ensure the repository's file structure is standard.

### Image not found in Kubernetes
**Symptom**: Pod status shows `ErrImagePull` or `ImagePullBackOff`.
**Fix**: Ensure the `imagePullPolicy` in the manifest is set to `Never` (DeployMind patches this automatically). Check that the image was successfully loaded into `kind` via `kind load docker-image`.

### Pod crash
**Symptom**: Pod status shows `CrashLoopBackOff`.
**Fix**: Check the pod logs for application startup errors:
```bash
kubectl logs -l app=<app-name> -n deploymind
```
Common causes include missing environment variables or failing database connections.

### Rollout failure
**Symptom**: `deployment "<app-name>" exceeded its progress deadline`.
**Fix**: The pod crashed during startup or the readiness probe failed. Inspect the pod description and logs:
```bash
kubectl describe pod -l app=<app-name> -n deploymind
```

### Smoke test failure
**Symptom**: `port-forward exited early` or HTTP endpoints return `502`/`504`.
**Fix**: The application started, but the `/health`, `/`, or `/docs` endpoints are not responding on the expected port. Verify that the application binds to `0.0.0.0` and that the correct port is exposed in the Dockerfile.

### Frontend 504 Gateway Timeout
**Symptom**: The browser network tab shows `504 Gateway Timeout` when clicking "Deploy".
**Fix**: The deployment took too long, and the proxy timed out. DeployMind has been updated to use asynchronous background tasks to fix this. Ensure you are running the latest backend code.

### Database connection failure
**Symptom**: `psycopg.OperationalError: connection to server at "db" failed`.
**Fix**: Ensure the PostgreSQL container is running: `docker compose ps`. Check if the `DATABASE_URL` in `.env` matches the docker-compose service configuration.
