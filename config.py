from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    bot_token: str
    supabase_url: str
    supabase_anon_key: str
    bitrix_webhook_base: str
    openai_api_key: str
    openai_model: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            bot_token=os.environ["BOT_TOKEN"],
            supabase_url=os.environ["SUPABASE_URL"],
            supabase_anon_key=os.environ["SUPABASE_ANON_KEY"],
            bitrix_webhook_base=os.environ["BITRIX_WEBHOOK_BASE"],
            openai_api_key=os.environ["OPENAI_API_KEY"],
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        )


settings = Settings.from_env()
