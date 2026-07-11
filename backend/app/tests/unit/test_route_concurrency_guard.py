"""Guard against `async def` route handlers that never `await` anything.

Context: the app database is remote (~180ms/round-trip). FastAPI runs plain
`def` route handlers in its AnyIO worker threadpool, so a blocking (sync)
call only stalls that one worker thread. `async def` handlers, by contrast,
run directly on the single asyncio event loop -- if one of them performs
blocking I/O without ever `await`-ing, it freezes the loop and every other
concurrent request queues behind it (head-of-line blocking).

The rule this test enforces: any router-decorated `async def` handler must
contain at least one `await` in its body. If it doesn't, it is doing sync
work on the event loop for no benefit and should be declared `def` instead
so FastAPI dispatches it to the threadpool.

`ROUTE_ASYNC_NO_AWAIT_ALLOWLIST` is the escape hatch for handlers that are
justified exceptions to this rule. It should be empty or near-empty --
every entry needs a comment explaining why it's there.
"""

import ast
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
ROUTES_DIR = APP_ROOT / "api" / "v1" / "routes"

_ROUTER_METHODS = {"get", "post", "put", "patch", "delete"}

# (filename, function_name) pairs explicitly allowed to be `async def` with
# no `await` in their body. Keep this empty unless there is a concrete,
# documented reason a handler must stay async without awaiting anything.
ROUTE_ASYNC_NO_AWAIT_ALLOWLIST: set[tuple[str, str]] = set()


def _is_router_decorator(decorator: ast.expr) -> bool:
    """True if `decorator` looks like `@router.<get|post|put|patch|delete>(...)`."""
    if not isinstance(decorator, ast.Call):
        return False
    func = decorator.func
    if not isinstance(func, ast.Attribute):
        return False
    if not isinstance(func.value, ast.Name):
        return False
    return func.value.id == "router" and func.attr in _ROUTER_METHODS


def _route_handlers(tree: ast.Module):
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        if any(_is_router_decorator(dec) for dec in node.decorator_list):
            yield node


def _has_await(func: ast.AST) -> bool:
    return any(isinstance(n, ast.Await) for n in ast.walk(func))


def _route_files():
    return sorted(p for p in ROUTES_DIR.glob("*.py") if p.name != "__init__.py")


def test_async_route_handlers_await_something():
    """Every `async def` route handler must await at least once in its body.

    An `async def` handler that never awaits does purely synchronous work
    directly on the event loop, blocking every other concurrent request for
    the duration of that work. Such a handler should be declared `def` so
    FastAPI runs it in the threadpool instead.
    """
    offenders = []

    for path in _route_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in _route_handlers(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue  # plain `def` handlers are exactly what we want
            if _has_await(node):
                continue

            key = (path.name, node.name)
            if key in ROUTE_ASYNC_NO_AWAIT_ALLOWLIST:
                continue

            offenders.append(f"{path.relative_to(APP_ROOT).as_posix()}::{node.name}")

    assert offenders == [], (
        "async def route handler(s) with no await found (blocks the event "
        f"loop on sync work): {offenders}. Either add a genuine await, "
        "convert the handler to plain `def`, or add a justified, commented "
        "entry to ROUTE_ASYNC_NO_AWAIT_ALLOWLIST."
    )


def test_allowlist_entries_still_exist_and_are_justified():
    """Keep the allowlist honest: no stale entries for functions that no longer exist."""
    all_handlers = set()
    for path in _route_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in _route_handlers(tree):
            all_handlers.add((path.name, node.name))

    stale = ROUTE_ASYNC_NO_AWAIT_ALLOWLIST - all_handlers
    assert stale == [] if isinstance(stale, list) else stale == set(), (
        f"ROUTE_ASYNC_NO_AWAIT_ALLOWLIST has stale entries no longer present "
        f"as route handlers: {stale}. Remove them."
    )
