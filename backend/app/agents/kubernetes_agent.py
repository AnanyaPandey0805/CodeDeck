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
    if database in {"postgresql", "postgis"}:
        image = "postgis/postgis:16-3.4" if database == "postgis" else "postgres:16-alpine"
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


def generate_dependency_manifest(app_name: str, dependency: str) -> str | None:
    """Create local-only Redis or Kafka services required by an application."""
    name = f"{app_name}-{dependency}"
    if dependency == "redis":
        image, port = "redis:7-alpine", 6379
        command = "          args: [\"redis-server\", \"--appendonly\", \"yes\"]\n"
        probe = "            exec:\n              command: [\"redis-cli\", \"ping\"]"
    elif dependency == "kafka":
        image, port = "apache/kafka:3.7.0", 9092
        command = """          env:
            - name: KAFKA_NODE_ID
              value: \"1\"
            - name: KAFKA_PROCESS_ROLES
              value: broker,controller
            - name: KAFKA_CONTROLLER_QUORUM_VOTERS
              value: 1@{name}:9093
            - name: KAFKA_LISTENERS
              value: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
            - name: KAFKA_ADVERTISED_LISTENERS
              value: PLAINTEXT://{name}:9092
            - name: KAFKA_LISTENER_SECURITY_PROTOCOL_MAP
              value: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
            - name: KAFKA_CONTROLLER_LISTENER_NAMES
              value: CONTROLLER
            - name: KAFKA_INTER_BROKER_LISTENER_NAME
              value: PLAINTEXT
            - name: KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR
              value: \"1\"
            - name: KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS
              value: \"0\"
""".format(name=name)
        probe = f"""            tcpSocket:
              port: {port}"""
    else:
        return None

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
        - name: {dependency}
          image: {image}
          ports:
            - containerPort: {port}
{command}          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 750m
              memory: 768Mi
          readinessProbe:
{probe}
            initialDelaySeconds: 10
            periodSeconds: 5
          livenessProbe:
{probe}
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
    - name: {dependency}
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
    for dependency in analysis.get("staging_dependencies") or []:
        manifest = generate_dependency_manifest(name, dependency)
        if manifest:
            files[f"dependency-{dependency}.yaml"] = manifest
    logger.info("Kubernetes manifests generated")
    return KubernetesResult(
        files=files,
        message="Deployment, Service, and RBAC generated",
        app_name=name,
        port=port,
    )
