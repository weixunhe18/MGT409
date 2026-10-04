"""SQLite access layer for the Campus Customs catalogue.

The shipped database is treated as read-only reference data for the catalogue and
inventory; only `users` and `chat_messages` are written to. `garment_type` is dirty
(22 raw values for 5 real categories, including case variants like "short-sleeve
t-shirt" vs "short-sleeve T-shirt"), so categories are normalized on read rather
than by rewriting the file — the original column stays intact for the P12 audit
trail, and re-downloading data.zip never silently undoes the cleanup.
"""

import json
import re
import sqlite3
from contextlib import contextmanager
from difflib import SequenceMatcher
from typing import Any, Iterator

from config import DB_PATH, MOTION_DIR

# Checked in priority order — the first match wins, so "short-sleeve crew-neck
# t-shirt" lands in T-shirt rather than Crewneck.
_CATEGORY_RULES: list[tuple[str, str]] = [
    ("hood", "Hoodie"),
    ("jacket", "Jacket"),
    ("quarter-zip", "Quarter-zip"),
    # Long-sleeve performance shirts are only 2 products, too thin to be their own
    # filter, so they ride along with the tees. Must be tested before "t-shirt"
    # because their raw value contains "shirt" but not "t-shirt".
    ("performance", "T-shirt"),
    ("t-shirt", "T-shirt"),
    ("tee", "T-shirt"),
    ("crewneck", "Crewneck"),
    ("crew-neck", "Crewneck"),
    # A mockneck is not strictly a crewneck, but it is a collarless pullover
    # sweatshirt and there is exactly one of them; its own category would be a
    # one-item filter. Any remaining "* sweatshirt" lands here too.
    ("mockneck", "Crewneck"),
    ("sweatshirt", "Crewneck"),
]

CATEGORIES = ["Crewneck", "Hoodie", "T-shirt", "Quarter-zip", "Jacket"]

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

#: Shoppers say "medium", not "M". Accept the spoken forms rather than making a
#: real size look like an invalid one.
_SIZE_ALIASES = {
    "xs": "XS", "extra small": "XS", "x-small": "XS", "xsmall": "XS",
    "s": "S", "small": "S", "sm": "S",
    "m": "M", "medium": "M", "med": "M",
    "l": "L", "large": "L", "lg": "L",
    "xl": "XL", "x-large": "XL", "extra large": "XL", "xlarge": "XL", "x large": "XL",
    "xxl": "XXL", "2xl": "XXL", "xx-large": "XXL", "double xl": "XXL",
    "xxlarge": "XXL", "2x": "XXL", "xx large": "XXL",
}


def normalize_size(size: str) -> str | None:
    """Map a shopper's wording to a catalogue size code, or None if unrecognized."""
    key = re.sub(r"\s+", " ", (size or "").strip().lower())
    if key.upper() in SIZE_ORDER:
        return key.upper()
    return _SIZE_ALIASES.get(key)


def normalize_category(garment_type: str) -> str:
    """Collapse a raw `garment_type` string into one of the display categories."""
    lowered = garment_type.lower()
    for needle, category in _CATEGORY_RULES:
        if needle in lowered:
            return category
    return "Other"


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    finally:
        conn.close()


def _loads(raw: str) -> list[str]:
    """`colors` and `search_tags` are stored as JSON arrays in TEXT columns."""
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _load_motion_manifest() -> dict[str, Any]:
    """Which products have a motion loop, written by scripts/make_motion_loops.py.

    Read from disk rather than stored in SQLite: the clips are build artefacts that
    live beside the images, and the shipped database is reference data we do not
    rewrite. A missing or malformed manifest simply means no product has motion,
    which is why the site still works with the directory empty.
    """
    path = MOTION_DIR / "manifest.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


MOTION = _load_motion_manifest()


def row_to_product(row: sqlite3.Row) -> dict[str, Any]:
    """Shape one catalogue row for the API, adding the normalized category."""
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "garment_type": row["garment_type"],
        "category": normalize_category(row["garment_type"]),
        "description": row["description"],
        "colors": _loads(row["colors"]),
        "search_tags": _loads(row["search_tags"]),
        # image_file_path is stored as "products/<file>.jpg"; /images serves that dir.
        "image_url": "/images/" + row["image_file_path"].split("/")[-1],
        "price": float(row["price"]),
        # None for the ~99 products with no loop; the card falls back to the still.
        "motion": MOTION.get(row["product_id"]),
    }


def fetch_products(
    category: str | None = None, search: str | None = None
) -> list[dict[str, Any]]:
    """All products, optionally filtered. Category filtering happens in Python
    because the stored column is un-normalized; search covers name, description,
    and the curated tags.

    Each product carries `sizes_available` so a caller can answer "which of these
    come in Small?" without a follow-up query per product.
    """
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM catalogue ORDER BY name").fetchall()
        stock = _stock_by_size(conn)

    products = []
    for row in rows:
        product = row_to_product(row)
        if category and product["category"].lower() != category.lower():
            continue
        if search:
            needle = search.lower()
            haystack = " ".join(
                [
                    product["name"],
                    product["description"],
                    " ".join(product["colors"]),
                    " ".join(product["search_tags"]),
                ]
            ).lower()
            if needle not in haystack:
                continue
        by_size = stock.get(product["product_id"], {})
        product["total_stock"] = sum(by_size.values())
        product["in_stock"] = product["total_stock"] > 0
        product["sizes_available"] = [s for s in SIZE_ORDER if by_size.get(s, 0) > 0]
        products.append(product)
    return products


def fetch_product(product_id: str) -> dict[str, Any] | None:
    """One product with its per-size stock, ordered XS through XXL."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM catalogue WHERE product_id = ?", (product_id,)
        ).fetchone()
        if row is None:
            return None
        sizes = conn.execute(
            "SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)
        ).fetchall()

    product = row_to_product(row)
    by_size = {s["size"]: s["quantity"] for s in sizes}
    product["sizes"] = [
        {"size": size, "quantity": by_size.get(size, 0), "in_stock": by_size.get(size, 0) > 0}
        for size in SIZE_ORDER
        if size in by_size
    ]
    product["total_stock"] = sum(by_size.values())
    product["in_stock"] = product["total_stock"] > 0
    return product


def _stock_by_size(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """{product_id: {size: quantity}} for the whole catalogue in one query."""
    rows = conn.execute("SELECT product_id, size, quantity FROM inventory").fetchall()
    out: dict[str, dict[str, int]] = {}
    for row in rows:
        out.setdefault(row["product_id"], {})[row["size"]] = row["quantity"]
    return out


# Words that would match nearly everything and so carry no signal.
_STOPWORDS = {
    "a", "an", "and", "any", "are", "do", "for", "got", "has", "have", "i", "in", "is",
    "it", "like", "looking", "me", "my", "need", "of", "on", "or", "please", "show",
    "some", "something", "the", "to", "want", "what", "with", "you", "your", "yale",
}

# Where a token can match, and how much that match is worth. Curated tags score
# highest after the name: they carry intent the product name misses, like
# "Handsome Dan" or "The Game".
_FIELD_WEIGHTS = (("name", 6), ("search_tags", 4), ("colors", 3), ("category", 3), ("description", 1))


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 1 and t not in _STOPWORDS]


def _token_forms(token: str) -> set[str]:
    """A token plus its singular forms.

    Shoppers type plurals — "hoodies", "jackets", "tees" — but the catalogue is
    written in the singular. Matching is substring-based, and "hoodies" is not a
    substring of "hoodie", so without this a request for hoodies found none of the
    27 the shop sells.
    """
    forms = {token}
    if token.endswith("ies") and len(token) > 4:
        forms.add(token[:-3] + "y")
    if token.endswith("es") and len(token) > 3:
        forms.add(token[:-2])
    if token.endswith("s") and len(token) > 2:
        forms.add(token[:-1])
    return forms


def _match_score(product: dict[str, Any], tokens: list[str]) -> tuple[int, int]:
    """Return (tokens matched, weighted score) for one product.

    An unmatched token is ignored rather than disqualifying the product. Shoppers
    ask whole questions — "whats your cheapest fleece?" — and the agent passes
    them through verbatim; requiring every word to land made "fleece" unfindable
    because "whats" and "cheapest" appear in no product. Coverage is the primary
    sort key, so a product matching two words still outranks one matching one.
    """
    haystacks = {
        "name": product["name"].lower(),
        "search_tags": " ".join(product["search_tags"]).lower(),
        "colors": " ".join(product["colors"]).lower(),
        "category": f"{product['category']} {product['garment_type']}".lower(),
        "description": product["description"].lower(),
    }
    matched = 0
    total = 0
    for token in tokens:
        forms = _token_forms(token)
        best = 0
        for field_name, weight in _FIELD_WEIGHTS:
            haystack = haystacks[field_name]
            if any(form in haystack for form in forms):
                best = max(best, weight)
        if best:
            matched += 1
            total += best
    return matched, total


def search_catalogue(
    query: str | None = None,
    category: str | None = None,
    color: str | None = None,
    size: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    in_stock_only: bool = False,
    sort_by: str = "relevance",
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Rank the catalogue against a free-text query plus optional filters.

    Scoring happens in Python rather than SQL because the searchable text lives in
    JSON columns and the category has to be normalized first.
    """
    products = fetch_products()

    if category:
        wanted = category.strip().lower()
        products = [p for p in products if p["category"].lower() == wanted]
    if color:
        wanted = color.strip().lower()
        products = [p for p in products if any(wanted in c.lower() for c in p["colors"])]
    if size:
        # Answers "which of these come in Small?" in the same call as the search,
        # instead of one stock lookup per result.
        wanted = normalize_size(size)
        if wanted:
            products = [p for p in products if wanted in p["sizes_available"]]
    if max_price is not None:
        products = [p for p in products if p["price"] <= max_price]
    if min_price is not None:
        products = [p for p in products if p["price"] >= min_price]
    if in_stock_only:
        products = [p for p in products if p["in_stock"]]

    tokens = _tokenize(query) if query else []
    if tokens:
        scored = []
        for product in products:
            matched, score = _match_score(product, tokens)
            if matched:
                scored.append((matched, score, product))
        # Relevance first; price breaks ties so equally relevant results are
        # ordered usefully rather than arbitrarily.
        scored.sort(key=lambda row: (-row[0], -row[1], row[2]["price"]))
        products = [p for _, _, p in scored]
    else:
        products.sort(key=lambda p: p["price"])

    if sort_by == "price_asc":
        products.sort(key=lambda p: p["price"])
    elif sort_by == "price_desc":
        products.sort(key=lambda p: -p["price"])

    return products[:limit]


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _normalize_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


#: Below this, two names are too different to treat as the same product.
_NAME_MATCH_THRESHOLD = 0.82


def resolve_product(identifier: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Find one product from an id *or* a name, returning (product, suggestions).

    The agent does not always have a `product_id` to hand — it may pass the name it
    just showed the shopper, or an id with a hyphen in the wrong place. Requiring an
    exact id made those lookups return nothing, which is the worst possible answer:
    the model is left with no data at the exact moment it is tempted to invent some.

    Tried in order: exact id, slugified input, exact name, then closest name above a
    similarity threshold. If nothing is confident enough, `product` is None and
    `suggestions` holds the nearest real products so the agent can ask.
    """
    ident = (identifier or "").strip()
    if not ident:
        return None, []

    with get_connection() as conn:
        rows = conn.execute("SELECT product_id, name FROM catalogue").fetchall()

    ids = {row["product_id"] for row in rows}
    if ident in ids:
        return fetch_product(ident), []

    slug = _slugify(ident)
    if slug in ids:
        return fetch_product(slug), []

    target = _normalize_name(ident)
    for row in rows:
        if _normalize_name(row["name"]) == target:
            return fetch_product(row["product_id"]), []

    best_row, best_score = None, 0.0
    for row in rows:
        score = max(
            SequenceMatcher(None, target, _normalize_name(row["name"])).ratio(),
            SequenceMatcher(None, slug, row["product_id"]).ratio(),
        )
        if score > best_score:
            best_row, best_score = row, score

    if best_row is not None and best_score >= _NAME_MATCH_THRESHOLD:
        return fetch_product(best_row["product_id"]), []

    return None, search_catalogue(query=ident, limit=4)


# --- Chat history -------------------------------------------------------------
#
# Stored in the shipped `chat_messages` table, which already has exactly the right
# columns — including `products_json`, so a restored conversation shows the same
# product cards it did the first time.


def load_chat_history(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    """The most recent messages for one shopper, oldest first.

    Scoped by `user_id`, which is what keeps one shopper's history out of another's
    — including the instructor's seeded transcripts on user 3.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content, products_json, created_at FROM chat_messages"
            " WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()

    history = []
    for row in reversed(rows):  # newest-first query, oldest-first result
        products = []
        if row["products_json"]:
            try:
                loaded = json.loads(row["products_json"])
                if isinstance(loaded, list):
                    products = loaded
            except json.JSONDecodeError:
                products = []  # a bad row should not break the whole thread
        history.append(
            {
                "role": row["role"],
                "content": row["content"],
                "products": products,
                "created_at": row["created_at"],
            }
        )
    return history


def save_chat_message(
    user_id: int, role: str, content: str, products: list[dict[str, Any]] | None = None
) -> None:
    """Append one message. Only ever called for a logged-in shopper."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json)"
            " VALUES (?, ?, ?, ?)",
            (user_id, role, content, json.dumps(products) if products else None),
        )


# --- Recently viewed products -------------------------------------------------
#
# One row per (shopper, product) rather than one per visit: the page wants "what
# have I been looking at", not a visit log, and an upsert keeps the table from
# growing without bound while someone browses.


def ensure_view_table() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS product_views (
                user_id    INTEGER NOT NULL REFERENCES users(id),
                product_id TEXT    NOT NULL REFERENCES catalogue(product_id),
                viewed_at  TEXT    NOT NULL,
                view_count INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, product_id)
            );
            CREATE INDEX IF NOT EXISTS idx_product_views_recent
                ON product_views (user_id, viewed_at DESC);
            """
        )


def record_product_view(user_id: int, product_id: str) -> bool:
    """Note that a shopper looked at a product. Returns False for unknown products.

    Checked against the catalogue first so a mistyped URL cannot put a phantom
    product into someone's history.
    """
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM catalogue WHERE product_id = ?", (product_id,)
        ).fetchone()
        if not exists:
            return False

        # Millisecond precision, not datetime('now'): a shopper can easily open two
        # products inside one second, and at second resolution the ordering of
        # "most recently viewed" became arbitrary — a re-viewed product kept its
        # old position instead of moving to the front.
        conn.execute(
            "INSERT INTO product_views (user_id, product_id, viewed_at)"
            " VALUES (?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))"
            " ON CONFLICT(user_id, product_id) DO UPDATE SET"
            " viewed_at = excluded.viewed_at, view_count = view_count + 1",
            (user_id, product_id),
        )
    return True


def recent_product_views(user_id: int, limit: int = 8) -> list[dict[str, Any]]:
    """Products this shopper looked at, most recent first, joined to the catalogue."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT c.*, v.viewed_at, v.view_count FROM product_views v"
            " JOIN catalogue c ON c.product_id = v.product_id"
            " WHERE v.user_id = ? ORDER BY v.viewed_at DESC, v.rowid DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        stock = _stock_by_size(conn)

    products = []
    for row in rows:
        product = row_to_product(row)
        by_size = stock.get(product["product_id"], {})
        product["total_stock"] = sum(by_size.values())
        product["in_stock"] = product["total_stock"] > 0
        product["sizes_available"] = [s for s in SIZE_ORDER if by_size.get(s, 0) > 0]
        product["viewed_at"] = row["viewed_at"]
        product["view_count"] = row["view_count"]
        products.append(product)
    return products


def clear_product_views(user_id: int) -> int:
    with get_connection() as conn:
        return conn.execute("DELETE FROM product_views WHERE user_id = ?", (user_id,)).rowcount


def clear_chat_history(user_id: int) -> int:
    """Forget one shopper's conversation. Returns how many messages were removed."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
        return cursor.rowcount


def category_counts() -> list[dict[str, Any]]:
    """Product count per normalized category, for filter chips."""
    with get_connection() as conn:
        rows = conn.execute("SELECT garment_type FROM catalogue").fetchall()
    counts = {name: 0 for name in CATEGORIES}
    for row in rows:
        counts[normalize_category(row["garment_type"])] += 1
    return [{"name": name, "count": counts[name]} for name in CATEGORIES]
