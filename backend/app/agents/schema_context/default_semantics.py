"""Built-in semantic synonym groups (generic defaults)."""

DEFAULT_ENTITIES: list[dict] = [
    {
        "name": "customer",
        "synonyms": ["client", "buyer", "account"],
    },
    {
        "name": "order",
        "synonyms": ["purchase", "transaction", "sale"],
    },
    {
        "name": "product",
        "synonyms": ["item", "sku", "goods"],
    },
    {
        "name": "user",
        "synonyms": ["member", "profile"],
    },
]

DEFAULT_METRIC_SYNONYMS: dict[str, list[str]] = {
    "revenue": ["sales", "income", "gross", "paid amount"],
    "churn": ["cancellation", "inactive", "lost", "stopped"],
    "subscription": ["plan", "membership"],
}

__all__ = ["DEFAULT_ENTITIES", "DEFAULT_METRIC_SYNONYMS"]
