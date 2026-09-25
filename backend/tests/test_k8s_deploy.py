from app.services.kubernetes import patch_manifests_for_local


def test_patch_manifests_for_local():
    files = {
        "deployment.yaml": """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: demo
          image: ghcr.io/example/demo:latest
          imagePullPolicy: IfNotPresent
          readinessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 15
            periodSeconds: 20
""".lstrip(),
        "service.yaml": "apiVersion: v1\nkind: Service\nmetadata:\n  name: demo\n",
    }
    patched = patch_manifests_for_local(files, image="deploymind/demo:staging", app_name="demo", replicas=1)
    text = patched["deployment.yaml"]
    assert "deploymind/demo:staging" in text
    assert "imagePullPolicy: Never" in text
    assert "replicas: 1" in text
    assert "tcpSocket" in text
