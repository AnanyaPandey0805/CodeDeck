# DeployMind Demo

This is a simple 5-10 minute course demo flow.

## Recommended Demo Repository

Use a small public FastAPI repository so the full flow stays quick and understandable.

## Demo Steps

1. Start DeployMind with `docker compose up --build`.
2. Open the frontend dashboard.
3. Paste a GitHub repository URL and run analysis.
4. Show detected language, framework, entrypoint, port, and package manager.
5. Show the deployment recommendation.
6. Open the Repository Q&A panel and ask a question such as:
   - What framework does this repository use?
   - What is the deployment entrypoint?
   - What database does this application use?
7. Show the retrieved repository snippets used to answer.
8. Show the retrieval evaluation summary.
9. Run AI-generated tests and review the output.
10. Show the generated Dockerfile and Kubernetes manifests.
11. Deploy staging.
12. Show rollout progress and smoke-test result.
13. Deploy GREEN production.
14. Show the approval state.
15. Approve traffic switch to GREEN.
16. If needed, demonstrate rollback to BLUE.
17. If a deployment fails, show the failure-analysis panel.

## What To Emphasize During Viva

- The deployment core is real Docker + Kubernetes automation, not mock output.
- Repository Q&A is grounded in retrieved repository chunks.
- Recommendation, testing, and failure analysis are explainable and intentionally lightweight.
- The project demonstrates coordinated tooling rather than a single prompt wrapper.
