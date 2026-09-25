from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Groq LLM
    GROQ_API_KEY: str
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    # Tavily Web Research
    TAVILY_API_KEY: str

    # LangSmith Observability
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_TRACING: bool = False
    LANGSMITH_PROJECT: str = "proposalflow-ai"

    # Database (Day 4)
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/proposalflow_db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()