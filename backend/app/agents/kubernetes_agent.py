import logging
import re

from pydantic import BaseModel, Field

logger = logging.getLogger("deploymind")


class KubernetesResult(BaseModel):
    files: dict[str, str] = Field(default_factory=dict)
    message: str = ""
    app_name: str = "app"
    port: int = 8000


def sanitize_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9-]", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return (name or "app")[:63]


def generate_database_manifest(app_name: str, database: str | None) -> str | None:
    """Create an isolated, ephemeral database for local staging only."""
    if database == "postgresql":
        image = "postgres:16-alpine"
        env = """            - name: POSTGRES_DB
              value: app
            - name: POSTGRES_USER
              value: deploymind
            - name: POSTGRES_PASSWORD
              value: deploymind"""
        port = 5432
    elif database == "mysql":
        image = "mysql:8.4"
        env = """            - name: MYSQL_DATABASE
              value: app
            - name: MYSQL_USER
              value: deploymind
            - name: MYSQL_PASSWORD
              value: deploymind
            - name: MYSQL_ROOT_PASSWORD
              value: deploymind-root"""
        port = 3306
    else:
        return None

    name = f"{app_name}-db"
    return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  labels:
    app: {name}
    managed-by: deploymind
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
        - name: database
          image: {image}
          ports:
            - containerPort: {port}
          env:
{env}
          securityContext:
            allowPrivilegeEscalation: false
            runAsNonRoot: true
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
          readinessProbe:
            tcpSocket:
              port: {port}
            initialDelaySeconds: 10
            periodSeconds: 5
          livenessProbe:
            tcpSocket:
              port: {port}
            initialDelaySeconds: 30
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: {name}
  labels:
    app: {name}
spec:
  selector:
    app: {name}
  ports:
    - name: database
      port: {port}
      targetPort: {port}
"""


def generate_kubernetes(analysis: dict, app_name: str | None = None) -> KubernetesResult:
    name = sanitize_name(app_name or analysis.get("repository_name") or "app")
    port = int(analysis.get("port") or 8000)
    image = f"ghcr.io/example/{name}:latest"

    logger.info("Kubernetes generation for %s", name)

    deployment = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  labels:
    app: {name}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      serviceAccountName: {name}
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: {name}
          image: {image}
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: {port}
              name: http
          securityContext:
            allowPrivilegeEscalation: false
            runAsNonRoot: true
            runAsUser: 1000
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
          readinessProbe:
            tcpSocket:
              port: {port}
            initialDelaySeconds: 10
            periodSeconds: 5
            failureThreshold: 6
          livenessProbe:
            tcpSocket:
              port: {port}
            initialDelaySeconds: 30
            periodSeconds: 20
            failureThreshold: 3
"""

    service = f"""apiVersion: v1
kind: Service
metadata:
  name: {name}
  labels:
    app: {name}
spec:
  type: ClusterIP
  selector:
    app: {name}
  ports:
    - name: http
      port: 80
      targetPort: {port}
"""

    rbac = f"""apiVersion: v1
kind: ServiceAccount
metadata:
  name: {name}
  labels:
    app: {name}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: {name}
  labels:
    app: {name}
rules:
  - apiGroups: [""]
    resources: ["pods", "services", "configmaps"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: {name}
  labels:
    app: {name}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: {name}
subjects:
  - kind: ServiceAccount
    name: {name}
"""

    files = {
        "deployment.yaml": deployment.strip() + "\n",
        "service.yaml": service.strip() + "\n",
        "rbac.yaml": rbac.strip() + "\n",
    }
    database = generate_database_manifest(name, analysis.get("database"))
    if database:
        files["database.yaml"] = database
    logger.info("Kubernetes manifests generated")
    return KubernetesResult(
        files=files,
        message="Deployment, Service, and RBAC generated",
        app_name=name,
        port=port,
    )
