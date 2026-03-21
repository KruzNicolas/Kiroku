import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    NOTION_TOKEN = os.getenv("NOTION_TOKEN")
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
    # Default to local for backwards compatibility, but easily overridable to https://ollama.com
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "minimax-m2.5:cloud")

    @classmethod
    def validate(cls):
        if not cls.NOTION_TOKEN:
            raise ValueError("NOTION_TOKEN environment variable is required")
        if not cls.NOTION_DATABASE_ID:
            raise ValueError("NOTION_DATABASE_ID environment variable is required")


config = Config()
