import re


BLOCKED_KEYWORDS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bUPDATE\b",
    r"\bINSERT\b",
    r"\bALTER\b",
    r"\bTRUNCATE\b",
    r"\bCREATE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\blo_import\b",
    r"\blo_export\b",
    r"\bdblink\b",
    r"\bdblink_exec\b",
    r"\bpg_read_file\b",
    r"\bpg_write_file\b",
    r"\bpg_execute_server_program\b",
    r"\bCOPY\b",
]

_BLOCKED_PATTERN = re.compile("|".join(BLOCKED_KEYWORDS), re.IGNORECASE)
_STRING_LITERAL_PATTERN = re.compile(r"'[^']*'|\"[^\"]*\"", re.DOTALL)


def _strip_literals(sql: str) -> str:
    return _STRING_LITERAL_PATTERN.sub("''", sql)


def _contains_multiple_statements(sql: str) -> bool:
    stripped = sql.strip().rstrip(";")
    return ";" in stripped


def validate_query(sql: str) -> tuple[bool, str]:
    cleaned = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()

    if not cleaned:
        return False, "Empty query"

    cleaned_for_scan = _strip_literals(cleaned)
    if _contains_multiple_statements(cleaned_for_scan):
        return False, "Multiple SQL statements are not allowed."

    match = _BLOCKED_PATTERN.search(cleaned_for_scan)
    if match:
        keyword = match.group().upper()
        return False, f"Blocked: {keyword} statements are not allowed. Only SELECT queries are permitted."

    first_word = cleaned_for_scan.split()[0].upper()
    if first_word not in ("SELECT", "WITH", "EXPLAIN", "SHOW", "DESCRIBE"):
        return False, f"Only SELECT queries are allowed. Got: {first_word}"

    return True, ""


def get_readonly_wrapped_query(sql: str) -> str:
    sql = sql.rstrip(";").strip()
    return f"SET TRANSACTION READ ONLY; {sql};"


def sanitize_row_limit(sql: str, max_rows: int) -> str:
    if re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        return sql

    sql = sql.rstrip(";").strip()
    return f"{sql} LIMIT {max_rows}"


__all__ = [
    "validate_query",
    "get_readonly_wrapped_query",
    "sanitize_row_limit",
]
