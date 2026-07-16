"""AI agent implementations.

Package initialization must remain side-effect free. Importing a lightweight
module such as ``app.agents.schema_context.types`` is also an import of this
package, so eagerly constructing the complete agent registry here creates
cycles through query execution, connection services, and repositories.

Callers that need the registry should import it explicitly from
``app.agents.registry``.
"""

__all__: list[str] = []
