from typing import Optional

from pydantic import BaseModel


class UserSettingsBase(BaseModel):
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    timezone: str = "UTC"

    theme: str = "light"
    accent_color: str = "cyan"
    density: str = "comfortable"
    show_run_counts: bool = True
    animate_charts: bool = True
    syntax_highlighting: bool = True

    ai_model: str = ""
    preferred_llm_provider: Optional[str] = None
    preferred_llm_model: Optional[str] = None
    llm_preference_revision: int = 1
    allow_background_ai: bool = False
    stream_responses: bool = True
    default_row_limit: int = 500
    auto_save_queries: bool = False
    system_prompt: str = ""

    email_scheduled: bool = True
    email_failed: bool = True
    email_alerts: bool = False
    delivery_format: str = "CSV + Chart PNG"
    slack_enabled: bool = False
    slack_webhook: Optional[str] = None
    slack_channel: Optional[str] = None


class UserSubscription(BaseModel):
    owner_id: str
    plan_type: str
    queries_used: int
    queries_limit: int
    ai_used: int
    ai_limit: int
    deployment_llm_calls_used: int = 0
    deployment_llm_calls_limit: int = 10
    next_reset_date: str


class UserSettings(UserSettingsBase):
    owner_id: str


class UserSettingsUpdate(BaseModel):
    """Domain input for updating stored user settings."""

    full_name: Optional[str] = None
    job_title: Optional[str] = None
    timezone: Optional[str] = None

    theme: Optional[str] = None
    accent_color: Optional[str] = None
    density: Optional[str] = None
    show_run_counts: Optional[bool] = None
    animate_charts: Optional[bool] = None
    syntax_highlighting: Optional[bool] = None

    stream_responses: Optional[bool] = None
    default_row_limit: Optional[int] = None
    auto_save_queries: Optional[bool] = None
    system_prompt: Optional[str] = None

    email_scheduled: Optional[bool] = None
    email_failed: Optional[bool] = None
    email_alerts: Optional[bool] = None
    delivery_format: Optional[str] = None
    slack_enabled: Optional[bool] = None
    slack_webhook: Optional[str] = None
    slack_channel: Optional[str] = None
