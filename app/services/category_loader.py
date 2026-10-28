"""
Category tree loader — reads categories_default.json and seeds the database.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from app.database.db import Database
from app.database.models import Category
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

_DEFAULT_JSON = Path(__file__).parent.parent.parent / "resources" / "categories_default.json"


def _flatten(node: dict, parent_id: str | None, order: list[int]) -> list[Category]:
    """
    Recursively flatten nested category JSON into a list of Category objects.
    sort_order is assigned depth-first to preserve display order.
    """
    cats: list[Category] = []
    order[0] += 1
    cat = Category(
        id=node["id"],
        name=node["name"],
        parent_id=parent_id,
        description=node.get("description", ""),
        keywords=node.get("keywords", []),
        extensions=node.get("extensions", []),
        destination=node["destination"],
        sort_order=order[0],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    cats.append(cat)
    for child in node.get("children", []):
        cats.extend(_flatten(child, cat.id, order))
    return cats


def seed_categories(db: Database, json_path: Path = _DEFAULT_JSON) -> int:
    """
    Load categories from JSON and upsert into the database.
    Returns the number of categories loaded.
    Idempotent — safe to call on every startup.
    """
    if not json_path.exists():
        logger.error("Default categories file not found: %s", json_path)
        return 0

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read categories JSON: %s", exc)
        return 0

    all_cats: list[Category] = []
    counter = [0]
    for root_node in data.get("categories", []):
        all_cats.extend(_flatten(root_node, None, counter))

    for cat in all_cats:
        db.upsert_category(cat)

    logger.info("Seeded %d categories from %s", len(all_cats), json_path.name)
    return len(all_cats)


def get_extension_to_category_map(db: Database) -> dict[str, str]:
    """
    Build {extension: category_destination} mapping from all DB categories.
    Used by the extension classifier to look up DB-backed categories.
    """
    ext_map: dict[str, str] = {}
    for cat in db.get_all_categories():
        for ext in cat.extensions:
            ext_lower = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            ext_map[ext_lower] = cat.destination
    return ext_map
