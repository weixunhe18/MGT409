"""Tools the agent can call.

Each one reads the shipped SQLite database and returns a typed result. Two habits
run through all of them:

* **Everything returned is also recorded on `ctx.deps`.** The API sends that record
  to the browser, so the product cards on screen are the rows the tool actually
  read. The model never gets to name a product into existence.

* **An empty result is an answer, not a failure.** `found: 0` with a `note` saying
  what is missing gives the model something true to say, which is the difference
  between "we don't carry shorts" and an invented pair of shorts.
"""

from pydantic_ai import RunContext

from db import CATEGORIES, SIZE_ORDER, normalize_size, resolve_product, search_catalogue
from models import (
    CategorySummary,
    ChatDeps,
    CustomerProfile,
    ProductCard,
    ProductDetailCard,
    ProductLookup,
    SearchResult,
    SizeStock,
    StockAnswer,
)


def _size_status(quantity: int) -> str:
    """Plain wording for one size, written once here so every reply says it the
    same way — and so 'sold out' is never softened into 'may be available'."""
    if quantity <= 0:
        return "sold out"
    if quantity == 1:
        return "last one"
    return f"{quantity} left"


def _join(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _card(row: dict) -> ProductCard:
    return ProductCard(
        product_id=row["product_id"],
        name=row["name"],
        category=row["category"],
        price=row["price"],
        image_url=row["image_url"],
        colors=row["colors"],
        in_stock=row.get("in_stock", False),
        total_stock=row.get("total_stock", 0),
        sizes_available=row.get("sizes_available") or [
            s["size"] for s in row.get("sizes", []) if s["quantity"] > 0
        ],
        url=f"/products/{row['product_id']}",
    )


def search_products(
    ctx: RunContext[ChatDeps],
    query: str,
    category: str | None = None,
    color: str | None = None,
    size: str | None = None,
    max_price: float | None = None,
    in_stock_only: bool = False,
    sort_by: str = "relevance",
    limit: int = 8,
) -> SearchResult:
    """Search the catalogue for products matching a shopper's description.

    Searches names, curated tags, colors, category and description. Use this for any
    browsing question, including vague ones. Returns `found: 0` only when the shop
    genuinely stocks nothing like it.

    Every result already lists its `sizes_available`, so a question like "any sports
    tees in small?" is ONE call with size="S" — never a search followed by a stock
    check per product.

    Args:
        query: The descriptive words only — "fleece", "navy hoodie", "bulldog".
            Strip question words: for "what's your cheapest fleece?" pass
            query="fleece" with sort_by="price_asc", not the whole sentence.
            Pass "" to list everything.
        category: Optional exact filter. One of Crewneck, Hoodie, T-shirt,
            Quarter-zip, Jacket.
        color: Optional color filter, e.g. "navy".
        size: Optional size filter (XS, S, M, L, XL, XXL). Returns only products
            that have that size in stock. Use this for "in a small" questions.
        max_price: Optional ceiling in dollars.
        in_stock_only: True to hide products with nothing left in any size.
        sort_by: "relevance" (default), "price_asc" for cheapest-first — use this
            for "cheapest" questions — or "price_desc".
        limit: Most products to return (1-12).
    """
    limit = max(1, min(limit, 12))

    if category and category.strip().lower() not in {c.lower() for c in CATEGORIES}:
        ctx.deps.log_tool("search_products", {"query": query, "category": category},
                          "rejected: unknown category")
        return SearchResult(
            found=0,
            query_echo=query,
            note=(
                f"'{category}' is not a category this shop has. The only categories are: "
                f"{', '.join(CATEGORIES)}. Tell the shopper what the shop actually sells."
            ),
        )

    rows = search_catalogue(
        query=query or None,
        category=category,
        color=color,
        size=size,
        max_price=max_price,
        in_stock_only=in_stock_only,
        sort_by=sort_by if sort_by in {"relevance", "price_asc", "price_desc"} else "relevance",
        limit=limit,
    )
    cards = [_card(row) for row in rows]
    ctx.deps.record(cards)
    # Label the grid with what the shopper asked for, not the raw filter values.
    ctx.deps.note_search(query or category or color or "", len(cards))

    if not cards:
        bits = [f"nothing matches '{query}'" if query else "no products match"]
        if category:
            bits.append(f"in {category}")
        if color:
            bits.append(f"in {color}")
        if size:
            bits.append(f"in size {size.upper()}")
        if max_price is not None:
            bits.append(f"under ${max_price:g}")
        ctx.deps.log_tool("search_products",
                          {"query": query, "category": category, "color": color, "size": size},
                          "0 products")
        return SearchResult(
            found=0,
            query_echo=query,
            note=(
                f"The shop stocks {' '.join(bits)}. Say so plainly — do not invent a "
                f"product. The shop only sells: {', '.join(CATEGORIES)}. You may offer "
                "the closest real alternative, clearly labelled as a suggestion."
            ),
        )

    ctx.deps.log_tool(
        "search_products",
        {"query": query, "category": category, "color": color, "size": size,
         "max_price": max_price, "sort_by": sort_by},
        f"{len(cards)} products",
    )
    return SearchResult(found=len(cards), query_echo=query, products=cards)


def _detail_card(row: dict) -> ProductDetailCard:
    return ProductDetailCard(
        **_card(row).model_dump(),
        description=row["description"],
        garment_type=row["garment_type"],
        search_tags=row["search_tags"],
        sizes=[
            SizeStock(**s, status=_size_status(s["quantity"])) for s in row["sizes"]
        ],
    )


def get_product(ctx: RunContext[ChatDeps], product: str) -> ProductLookup:
    """Everything about one product: description, price, colors, tags, per-size stock.

    This is the tool for "how much is X?", "what colors does X come in?" and "tell me
    about X". The price it returns is the catalogue price — never quote a figure that
    did not come from here or from a search result.

    Accepts an id *or* a product name, so you can pass the name you just showed the
    shopper. If the lookup misses, `found` is false and `suggestions` holds real
    products to offer instead.

    Args:
        product: Product id ("boola-boola-t-shirt") or name ("Boola Boola T Shirt").
    """
    row, suggestions = resolve_product(product)

    if row is None:
        cards = [_card(s) for s in suggestions]
        ctx.deps.record(cards)
        ctx.deps.log_tool("get_product", {"product": product},
                          f"not found; {len(cards)} suggestions")
        return ProductLookup(
            found=False,
            note=(
                f"No product matches '{product}'. Do not invent one or guess its price. "
                + (
                    "Offer one of the suggestions instead."
                    if cards
                    else "Tell the shopper the shop has nothing by that name."
                )
            ),
            suggestions=cards,
        )

    detail = _detail_card(row)
    ctx.deps.record([detail])
    ctx.deps.note_search(row["name"], 1)
    ctx.deps.log_tool("get_product", {"product": product},
                      f"{row['name']} @ ${row['price']:.2f}")
    return ProductLookup(found=True, product=detail)


def check_stock(ctx: RunContext[ChatDeps], product: str, size: str | None = None) -> StockAnswer:
    """How many of one product are in stock, by size. The only honest source for sizes.

    Use for "do you have it in a Large?" and any question about quantities. A size with
    `quantity: 0` is sold out — report that plainly, using the `status` and `summary`
    text provided rather than composing your own.

    For "which of several products come in size X", use `search_products(size=...)`
    instead — one call rather than one per product.

    Args:
        product: Product id or name.
        size: Optional single size (XS, S, M, L, XL, XXL). Omit for every size.
    """
    row, suggestions = resolve_product(product)

    if row is None:
        cards = [_card(s) for s in suggestions]
        ctx.deps.record(cards)
        names = ", ".join(c.name for c in cards)
        ctx.deps.log_tool("check_stock", {"product": product, "size": size}, "not found")
        return StockAnswer(
            found=False,
            note=(
                f"No product matches '{product}', so there is no stock to report. Do not "
                "invent quantities."
                + (f" Nearest real products: {names}." if names else "")
            ),
            summary=f"I couldn't find a product called '{product}'.",
        )

    ctx.deps.record([_card(row)])
    ctx.deps.note_search(row["name"], 1)
    sizes = [SizeStock(**s, status=_size_status(s["quantity"])) for s in row["sizes"]]
    available = [s.size for s in sizes if s.in_stock]
    sold_out = [s.size for s in sizes if not s.in_stock]

    answer = StockAnswer(
        product_id=row["product_id"],
        name=row["name"],
        price=row["price"],
        sizes=sizes,
        sizes_available=available,
        sizes_sold_out=sold_out,
        any_in_stock=bool(available),
        total_stock=row["total_stock"],
    )

    if size:
        wanted = normalize_size(size)
        match = next((s for s in sizes if s.size == wanted), None) if wanted else None
        if match is None:
            # Previously an unrecognised size was ignored and every size came back,
            # which invited an answer about the wrong one.
            answer.note = (
                f"'{size}' is not a size this shop uses. Sizes are "
                f"{', '.join(SIZE_ORDER)}. Ask the shopper which they meant."
            )
            answer.summary = (
                f"{row['name']} comes in {', '.join(SIZE_ORDER)} — I don't have a "
                f"size called '{size}'."
            )
            ctx.deps.log_tool("check_stock", {"product": product, "size": size},
                              f"invalid size for {row['name']}")
            return answer

        answer.requested_size = match.size
        answer.requested_quantity = match.quantity
        answer.requested_in_stock = match.in_stock
        if match.in_stock:
            answer.summary = (
                f"{row['name']} is in stock in {match.size} ({match.status}), "
                f"at ${row['price']:.2f}."
            )
        else:
            others = _join(available)
            answer.summary = (
                f"{row['name']} is sold out in {match.size}."
                + (f" Still available in {others}." if others else " Sold out in every size.")
            )
        ctx.deps.log_tool("check_stock", {"product": product, "size": size}, answer.summary)
        return answer

    if not available:
        answer.summary = f"{row['name']} is sold out in every size."
    elif not sold_out:
        answer.summary = (
            f"{row['name']} is in stock in every size ({', '.join(SIZE_ORDER)}), "
            f"at ${row['price']:.2f}."
        )
    else:
        answer.summary = (
            f"{row['name']} is available in {_join(available)}, and sold out in "
            f"{_join(sold_out)}. It is ${row['price']:.2f}."
        )
    ctx.deps.log_tool("check_stock", {"product": product}, answer.summary)
    return answer


def list_categories(ctx: RunContext[ChatDeps]) -> list[CategorySummary]:
    """The kinds of apparel the shop sells, with how many products are in each.

    Use when a shopper asks what the shop carries, or to show them that something
    they asked for is not a kind of thing sold here.
    """
    from db import category_counts

    counts = [CategorySummary(**c) for c in category_counts()]
    ctx.deps.log_tool("list_categories", {}, f"{len(counts)} categories")
    return counts


def get_customer(ctx: RunContext[ChatDeps]) -> CustomerProfile:
    """Who you are talking to: name, email, and when they joined.

    Read from the signed session, so it is trustworthy. Use it when the shopper asks
    something about themselves ("what's my name?", "what email am I under?"). You
    already know their first name without calling this — it is in your instructions.

    Returns `logged_in: false` for a guest, in which case you know nothing about them
    and must not guess.
    """
    deps = ctx.deps

    if not deps.logged_in:
        ctx.deps.log_tool("get_customer", {}, "guest")
        return CustomerProfile(
            logged_in=False,
            note=(
                "This shopper is browsing as a guest, so you know nothing about them. "
                "Do not guess a name. They can log in from the navigation bar."
            ),
        )

    ctx.deps.log_tool("get_customer", {}, f"user_id={deps.user_id}")
    return CustomerProfile(
        logged_in=True,
        first_name=deps.first_name,
        last_name=deps.last_name,
        full_name=deps.full_name,
        email=deps.email,
        member_since=deps.member_since,
    )


def get_current_product(ctx: RunContext[ChatDeps]) -> ProductLookup:
    """The product the shopper is looking at right now, if they are on a product page.

    Call this the moment they say "this", "it", or "that one" without naming a
    product — for example "do you have this in pink?". Returns `found: false` when
    they are not on a product page, in which case ask which item they mean rather
    than guessing.
    """
    product_id = ctx.deps.page_product_id

    if not product_id:
        ctx.deps.log_tool("get_current_product", {}, "no product on page")
        return ProductLookup(
            found=False,
            note=(
                "The shopper is not on a product page, so there is no 'this' to resolve. "
                "Ask which product they mean."
            ),
        )

    row, _ = resolve_product(product_id)
    if row is None:
        ctx.deps.log_tool("get_current_product", {"page_product_id": product_id},
                          "id not in catalogue")
        return ProductLookup(
            found=False,
            note=f"The page refers to '{product_id}', which is not in the catalogue.",
        )

    detail = _detail_card(row)
    ctx.deps.record([detail])
    ctx.deps.note_search(row["name"], 1)
    ctx.deps.log_tool("get_current_product", {"page_product_id": product_id}, row["name"])
    return ProductLookup(found=True, product=detail)


#: Registered with the agent in agent.py.
ALL_TOOLS = [
    search_products,
    get_product,
    check_stock,
    list_categories,
    get_customer,
    get_current_product,
]
