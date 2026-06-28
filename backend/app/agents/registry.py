from app.agents.base import AgentDefinition
from app.agents.insights.generator import generate_widget_insight
from app.agents.nl_to_sql.graph import run_chat
from app.agents.nl_to_sql.template_recommender import generate_templates
from app.agents.visualization.generator import generate_visualization_blueprint


class AgentRegistry:
    def __init__(self) -> None:
        self._agents = {
            "sql_generator": AgentDefinition("sql_generator", run_chat, "NL-to-SQL chat graph"),
            "visualization": AgentDefinition(
                "visualization",
                generate_visualization_blueprint,
                "Visualization blueprint recommender",
            ),
            "dashboard_insight": AgentDefinition(
                "dashboard_insight",
                generate_widget_insight,
                "Dashboard insight generator",
            ),
            "template_generator": AgentDefinition(
                "template_generator",
                generate_templates,
                "Schema-aware template generator",
            ),
        }

    def get(self, name: str) -> AgentDefinition:
        return self._agents[name]

    def all(self) -> dict[str, AgentDefinition]:
        return dict(self._agents)


registry = AgentRegistry()

__all__ = ["AgentRegistry", "registry"]
