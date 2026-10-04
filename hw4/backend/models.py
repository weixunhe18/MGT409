"""Structured types shared by the API, the agent, and its tools.

Three groups:
  * wire types   — what the browser sends and receives (ChatRequest, ChatReply)
  * card types   — how a product is shown (ProductCard, ProductDetailCard)
  * agent types  — what tools return and what the run carries (ChatDeps)

Tool return types matter more than they look: PydanticAI sends their JSON schema
to the model, so these classes are part of the prompt. Field names and docstrings
are what tell the model that `total_stock` is a count and `sizes` is per-size.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

# --- Product cards ------------------------------------------------------------


class SizeStock(BaseModel):
    """Stock for one size of one product."""

    size: str = Field(description="XS, S, M, L, XL, or XXL")
    quantity: int = Field(description="Units on the shelf. 0 means sold out in this size.")
    in_stock: bool
    status: str = Field(
        default="",
        description="Plain wording for this size: 'sold out', 'last one', '3 left'. "
        "Repeat it rather than rephrasing a count.",
    )


class ProductCard(BaseModel):
    """A product as the website shows it in a grid or a chat reply."""

    product_id: str
    name: str
    category: str = Field(description="Crewneck, Hoodie, T-shirt, Quarter-zip, or Jacket")
    price: float = Field(description="US dollars")
    image_url: str = Field(description="Relative path; the frontend prefixes its own host")
    colors: list[str] = []
    in_stock: bool = Field(description="True if any size has stock")
    total_stock: int = Field(default=0, description="Units across every size")
    sizes_available: list[str] = Field(
        default=[],
        description="Sizes with stock right now. Enough to answer a size question "
        "without calling check_stock; call that only for exact unit counts.",
    )
    url: str = Field(description="Page for this product on the website")


class ProductDetailCard(ProductCard):
    """Everything known about one product, including per-size stock."""

    description: str
    garment_type: str = Field(description="Raw catalogue wording, before normalizing")
    search_tags: list[str] = []
    sizes: list[SizeStock] = []


# --- Tool results -------------------------------------------------------------


class SearchResult(BaseModel):
    """What `search_products` hands back.

    `found` is deliberately explicit: when it is 0 the agent must say so plainly
    rather than substituting something it imagines the shopper would accept.
    """

    found: int = Field(description="How many products matched. 0 means we stock nothing like it.")
    query_echo: str = Field(description="What was actually searched for")
    products: list[ProductCard] = []
    note: str = Field(
        default="",
        description="Guidance for the agent, e.g. that nothing matched and why",
    )


class ProductLookup(BaseModel):
    """Result of looking up one product by id or name.

    Wrapped in a `found` flag rather than returning null, because a bare null tells
    the model nothing it can say out loud. When the lookup misses, `note` says what
    to tell the shopper and `suggestions` carries real nearby products.
    """

    found: bool
    product: ProductDetailCard | None = None
    note: str = ""
    suggestions: list[ProductCard] = Field(
        default=[], description="Real products to offer when the lookup missed"
    )


class StockAnswer(BaseModel):
    """Per-size availability for one product — the only honest source for sizes."""

    found: bool = True
    product_id: str = ""
    name: str = ""
    price: float = Field(default=0.0, description="US dollars, straight from the catalogue")

    #: Set only when the shopper asked about one specific size.
    requested_size: str | None = None
    requested_quantity: int | None = Field(
        default=None, description="Units of the requested size. 0 means sold out in that size."
    )
    requested_in_stock: bool | None = None

    sizes: list[SizeStock] = Field(default=[], description="Every size, ordered XS to XXL")
    sizes_available: list[str] = Field(default=[], description="Sizes with at least one unit")
    sizes_sold_out: list[str] = Field(default=[], description="Sizes with zero units")
    any_in_stock: bool = False
    total_stock: int = 0

    summary: str = Field(
        default="",
        description="One true sentence about availability, already written. Say this "
        "rather than composing your own from the numbers — it is what keeps "
        "'sold out' from becoming 'might be available'.",
    )
    note: str = Field(default="", description="Set when the lookup missed or the size was invalid")


class CategorySummary(BaseModel):
    name: str
    count: int


class CustomerProfile(BaseModel):
    """Who the agent is talking to. Returned by the `get_customer` tool.

    Only ever built from the session cookie, never from anything the browser claims,
    so the agent cannot be told it is talking to someone else.
    """

    logged_in: bool
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = Field(
        default=None,
        description="The shopper's own email. Never read it aloud unless they ask.",
    )
    member_since: str | None = Field(default=None, description="When they created the account")
    note: str = ""


# --- Chat wire types ----------------------------------------------------------

Role = Literal["user", "assistant"]


class ChatTurn(BaseModel):
    """One earlier message, replayed so the agent has the thread."""

    role: Role
    content: str


class PageContext(BaseModel):
    """Where the shopper is standing on the site when they send a message.

    This is what makes "do you have this in pink?" answerable: without it, "this"
    refers to nothing the agent can see.
    """

    path: str = Field(default="", max_length=300, description="Current route, e.g. /products/x")
    product_id: str | None = Field(
        default=None, max_length=120, description="Set when a product detail page is open"
    )


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(
        default=[],
        max_length=40,
        description="Prior turns, oldest first. Used for guests only — a logged-in "
        "shopper's history is loaded from the database instead, so the browser "
        "cannot rewrite what was said.",
    )
    page: PageContext | None = None


class ChatReply(BaseModel):
    """The API contract between the agent and the website.

    `products` is the structured half: the rows the agent really looked up this turn.
    The frontend renders them both as cards inside the chat panel and as the product
    grid on the Products page, so a conversation drives what is on screen.
    """

    reply: str = Field(description="What Handsome Dan says, in markdown")
    products: list[ProductCard] = Field(
        default=[],
        description="Products the agent actually looked up this turn, for the page to show",
    )
    query: str = Field(
        default="",
        description="What was searched for, used as the heading above the grid",
    )
    total_found: int = Field(
        default=0,
        description="How many products matched in total; may exceed len(products) when "
        "the list was capped for display",
    )
    tools_used: list[str] = []
    model: str = ""


# --- Agent run context --------------------------------------------------------


@dataclass
class ChatDeps:
    """Everything one agent run needs to know that is not in the prompt file.

    This is the *context* half of the agent. The prompt in `prompts/prompt.md` is
    static and identical for every shopper; anything that varies per request —
    who is asking, what page they are on, what the tools found — lives here and is
    injected at run time. Nothing about a particular shopper is ever written into
    the prompt file.

    `shown` is the honesty mechanism: tools append the products they really
    returned, and the API sends those to the browser. Product cards therefore
    come from the database, never from the model repeating ids back to us —
    a hallucinated id cannot reach the page.
    """

    # Who is asking. Populated from the session cookie, never from the request body.
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    member_since: str | None = None
    user_id: int | None = None

    # Where they are standing on the site, so "this" and "it" resolve to something.
    page_path: str = ""
    page_product_id: str | None = None
    page_product_name: str | None = None
    shown: dict[str, ProductCard] = field(default_factory=dict)
    tools_used: list[str] = field(default_factory=list)

    #: What the shopper was looking for, for the heading above the grid. Set by the
    #: first search of a turn — later refinements should not relabel the results.
    search_query: str = ""
    total_found: int = 0

    #: One entry per tool call, for the audit trail. Recorded as the loop runs
    #: rather than read from the result afterwards, so a turn that fails partway
    #: still shows what the agent had already done.
    events: list[dict] = field(default_factory=list)

    def record(self, cards: list[ProductCard]) -> None:
        for card in cards:
            self.shown.setdefault(card.product_id, card)

    def note_search(self, query: str, total: int) -> None:
        if not self.search_query and query.strip():
            self.search_query = query.strip()
        self.total_found = max(self.total_found, total)

    @property
    def logged_in(self) -> bool:
        return self.user_id is not None

    def note_tool(self, name: str) -> None:
        if name not in self.tools_used:
            self.tools_used.append(name)

    def log_tool(self, name: str, args: dict, result: str) -> None:
        """Record one tool call for the audit trail."""
        self.note_tool(name)
        self.events.append(
            {
                "t": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "tool": name,
                "args": {k: v for k, v in args.items() if v not in (None, "", False)},
                "result": result,
            }
        )
