from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    grok_api_key: str = ""
    xai_api_key: str = ""
    grok_base_url: str = "https://api.x.ai/v1"
    grok_model: str = "grok-2-latest"
    database_url: str = "postgresql+psycopg://deploymind:deploymind@localhost:5432/deploymind"
    github_token: str = ""
    ghcr_username: str = ""
    ghcr_token: str = ""
    workspace_dir: str = "/tmp/deploymind"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    kind_cluster_name: str = "deploymind"
    k8s_namespace: str = "deploymind"
    kubeconfig: str = ""
    docker_build_timeout: int = 1800


settings = Settings()

