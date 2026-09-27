FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI (static binary) + Docker Buildx plugin
RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz \
    | tar -xz -C /tmp \
    && mv /tmp/docker/docker /usr/local/bin/docker \
    && rm -rf /tmp/docker \
    && mkdir -p /usr/local/lib/docker/cli-plugins /root/.docker/cli-plugins \
    && curl -fsSL -o /usr/local/lib/docker/cli-plugins/docker-buildx \
       "https://github.com/docker/buildx/releases/download/v0.21.2/buildx-v0.21.2.linux-amd64" \
    && chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx \
    && ln -sf /usr/local/lib/docker/cli-plugins/docker-buildx /root/.docker/cli-plugins/docker-buildx

# kubectl (pinned stable version)
RUN KUBECTL_VERSION=$(curl -fsSL https://dl.k8s.io/release/stable.txt) \
    && curl -fsSL -o /usr/local/bin/kubectl \
    "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && chmod +x /usr/local/bin/kubectl

# kind (Kubernetes-in-Docker) — pinned to v0.27.0 (latest stable)
RUN curl -fsSL -o /usr/local/bin/kind \
    "https://kind.sigs.k8s.io/dl/v0.27.0/kind-linux-amd64" \
    && chmod +x /usr/local/bin/kind

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
