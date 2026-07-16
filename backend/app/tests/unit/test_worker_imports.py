"""Regression tests for worker startup import boundaries."""

from __future__ import annotations

import subprocess
import sys


def _run_in_fresh_interpreter(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )


def test_agents_package_does_not_eagerly_load_registry() -> None:
    result = _run_in_fresh_interpreter(
        "import sys; import app.agents; "
        "assert 'app.agents.registry' not in sys.modules"
    )
    assert result.returncode == 0, result.stderr


def test_celery_tasks_import_in_fresh_interpreter() -> None:
    result = _run_in_fresh_interpreter("import app.workers.tasks")
    assert result.returncode == 0, result.stderr
