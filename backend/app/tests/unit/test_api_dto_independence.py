from datetime import datetime

from app.api.v1.schemas.chat import ChatMessage as ApiChatMessage
from app.api.v1.schemas.dashboards import Dashboard as ApiDashboard
from app.api.v1.schemas.query_library import SavedQuery as ApiSavedQuery
from app.api.v1.schemas.settings import UserSettingsResponse as ApiUserSettingsResponse
from app.db.models.chat import ChatMessage as DomainChatMessage
from app.db.models.dashboard import Dashboard as DomainDashboard
from app.db.models.query_library import SavedQuery as DomainSavedQuery
from app.db.models.settings import UserSettings as DomainUserSettings


def test_chat_api_dto_is_independent_from_domain_model():
    domain = DomainChatMessage(role="assistant", content="done")
    api_model = ApiChatMessage.model_validate(domain.model_dump())
    assert type(api_model) is ApiChatMessage
    assert ApiChatMessage is not DomainChatMessage
    assert api_model.content == "done"


def test_dashboard_api_dto_is_independent_from_domain_model():
    domain = DomainDashboard(
        id="dash-1",
        owner_id="user-1",
        name="Revenue",
        created_at=datetime(2026, 1, 1),
    )
    api_model = ApiDashboard.model_validate(domain.model_dump())
    assert ApiDashboard is not DomainDashboard
    assert api_model.name == "Revenue"


def test_saved_query_api_dto_is_independent_from_domain_model():
    domain = DomainSavedQuery(
        id="query-1",
        owner_id="user-1",
        title="Top accounts",
        sql="select 1",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    api_model = ApiSavedQuery.model_validate(domain.model_dump())
    assert ApiSavedQuery is not DomainSavedQuery
    assert api_model.sql == "select 1"


def test_settings_api_dto_is_independent_from_domain_model():
    domain = DomainUserSettings(owner_id="user-1")
    api_model = ApiUserSettingsResponse.model_validate(domain.model_dump())
    assert ApiUserSettingsResponse is not DomainUserSettings
    assert api_model.owner_id == "user-1"
