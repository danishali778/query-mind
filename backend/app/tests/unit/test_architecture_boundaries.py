from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]


def _python_files(root: Path):
    return [path for path in root.rglob("*.py") if path.name != "__init__.py"]


def test_api_schemas_do_not_import_db_models():
    offenders = []
    for path in _python_files(APP_ROOT / "api" / "v1" / "schemas"):
        text = path.read_text(encoding="utf-8")
        if "app.db.models" in text:
            offenders.append(path.relative_to(APP_ROOT).as_posix())

    assert offenders == []


def test_services_and_db_do_not_import_api_schemas():
    offenders = []
    for root in (APP_ROOT / "services", APP_ROOT / "db"):
        for path in _python_files(root):
            text = path.read_text(encoding="utf-8")
            if "app.api.v1.schemas" in text:
                offenders.append(path.relative_to(APP_ROOT).as_posix())

    assert offenders == []


def test_removed_compatibility_packages_do_not_exist():
    assert not (APP_ROOT / "db" / "schema_inspector.py").exists()
    assert not (APP_ROOT / "common").exists()
