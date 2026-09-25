REPOSITORY_ANALYSIS_PROMPT = """
Summarize a software repository from retrieved code and docs.
Return only grounded findings and name the files that support each claim.
""".strip()

RAG_QA_PROMPT = """
Answer the repository question using only the retrieved repository snippets.
If the evidence is weak, say so plainly and avoid guessing.
""".strip()

DEPLOYMENT_RECOMMENDATION_PROMPT = """
Create a short deployment recommendation from repository analysis signals.
Include detected stack, likely risks, and the next safest deployment steps.
""".strip()

TEST_GENERATION_PROMPT = """
Generate a very small set of safe repository tests from detected routes and entrypoints.
Prefer health, root, and one representative API route.
""".strip()

FAILURE_ANALYSIS_PROMPT = """
Analyze a deployment failure using only the provided error text, pod status, and logs.
State the likely cause, evidence, and the safest suggested next step.
""".strip()
