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
    openai_proxy: str | None
    supabase_support_url: str
    supabase_support_anon_key: str
    openai_model_support: str
    openai_model_coordinator: str
    # Electronic case Supabase
    supabase_cases_url: str
    supabase_cases_anon_key: str
    # ImConnector / Open Lines
    bitrix_url: str
    bitrix_openline_id: str
    bitrix_connector_id: str
    bitrix_oauth_client_id: str
    bitrix_oauth_client_secret: str
    bitrix_oauth_access_token: str
    bitrix_oauth_refresh_token: str
    webhook_port: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            bot_token=os.environ["BOT_TOKEN"],
            supabase_url=os.environ["SUPABASE_URL"],
            supabase_anon_key=os.environ["SUPABASE_ANON_KEY"],
            bitrix_webhook_base=os.environ["BITRIX_WEBHOOK_BASE"],
            openai_api_key=os.environ["OPENAI_API_KEY"],
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            openai_proxy=os.getenv("OPENAI_PROXY"),
            supabase_support_url=os.environ["SUPABASE_SUPPORT_URL"],
            supabase_support_anon_key=os.environ["SUPABASE_SUPPORT_ANON_KEY"],
            supabase_cases_url=os.environ["SUPABASE_CASES_URL"],
            supabase_cases_anon_key=os.environ["SUPABASE_CASES_ANON_KEY"],
            openai_model_support=os.getenv("OPENAI_MODEL_SUPPORT", "gpt-4o-mini"),
            openai_model_coordinator=os.getenv("OPENAI_MODEL_COORDINATOR", "gpt-4o"),
            bitrix_url=os.environ["BITRIX_URL"],
            bitrix_openline_id=os.getenv("BITRIX_OPENLINE_ID", "56"),
            bitrix_connector_id=os.getenv("BITRIX_CONNECTOR_ID", "tg_alina_support"),
            bitrix_oauth_client_id=os.environ["BITRIX_OAUTH_CLIENT_ID"],
            bitrix_oauth_client_secret=os.environ["BITRIX_OAUTH_CLIENT_SECRET"],
            bitrix_oauth_access_token=os.environ["BITRIX_OAUTH_ACCESS_TOKEN"],
            bitrix_oauth_refresh_token=os.environ["BITRIX_OAUTH_REFRESH_TOKEN"],
            webhook_port=int(os.getenv("WEBHOOK_PORT", "8080")),
        )


settings = Settings.from_env()
