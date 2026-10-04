"""Campus Customs API.

Serves the catalogue, the product images, and a chat endpoint that is currently a
stub. The stub keeps the same request/response shape the real agent will use, so
swapping it for the PydanticAI agent in Problem 5 touches this file only.
"""

import logging

from fastapi import Cookie, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from agent import AgentUnavailable, run_chat
from auth import current_user, ensure_auth_tables, router as auth_router
from config import CORS_ORIGINS, DB_PATH, MODEL_ID, MOTION_DIR, PRODUCT_IMAGE_DIR
from db import (
    category_counts,
    clear_chat_history,
    clear_product_views,
    ensure_view_table,
    fetch_product,
    fetch_products,
    get_connection,
    load_chat_history,
    recent_product_views,
    record_product_view,
    resolve_product,
    save_chat_message,
)
from models import ChatDeps, ChatRequest, ChatReply, ChatTurn

#: How many past messages are replayed to the agent. Enough for continuity without
#: resending a whole shopping history on every turn.
HISTORY_TURNS = 20

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Campus Customs API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Product photos ship alongside the database rather than in the frontend bundle.
app.mount("/images", StaticFiles(directory=PRODUCT_IMAGE_DIR), name="images")

# Product loops. Mounted only when the directory exists, so a checkout that has
# not run the encoder still starts.
if MOTION_DIR.is_dir():
    app.mount("/motion", StaticFiles(directory=MOTION_DIR), name="motion")

ensure_auth_tables()
ensure_view_table()
app.include_router(auth_router)


@app.get("/api/health")
def health() -> dict[str, object]:
    """Confirms the process is up and the catalogue database is readable."""
    with get_connection() as conn:
        products = conn.execute("SELECT COUNT(*) AS n FROM catalogue").fetchone()["n"]
    return {"status": "ok", "database": DB_PATH.name, "products": products}


@app.get("/api/categories")
def categories() -> list[dict[str, object]]:
    return category_counts()


@app.get("/api/products")
def products(category: str | None = None, search: str | None = None) -> dict[str, object]:
    found = fetch_products(category=category, search=search)
    return {"count": len(found), "products": found}


@app.get("/api/products/recently-viewed")
def recently_viewed(
    limit: int = 8, cc_session: str | None = Cookie(default=None)
) -> dict[str, object]:
    """Products this shopper has opened, most recent first.

    Guests get an empty list rather than an error — browsing without an account is
    fine, it simply is not remembered. Same policy as chat history.
    """
    shopper = current_user(cc_session)
    if not shopper:
        return {"logged_in": False, "products": []}
    return {
        "logged_in": True,
        "products": recent_product_views(shopper["id"], limit=max(1, min(limit, 20))),
    }


@app.delete("/api/products/recently-viewed")
def forget_recently_viewed(cc_session: str | None = Cookie(default=None)) -> dict[str, object]:
    """Clear this shopper's browsing history. Theirs to erase, like the chat log."""
    shopper = current_user(cc_session)
    if not shopper:
        raise HTTPException(status_code=401, detail="Not logged in.")
    return {"deleted": clear_product_views(shopper["id"])}


@app.post("/api/products/{product_id}/view", status_code=202)
def track_product_view(
    product_id: str, cc_session: str | None = Cookie(default=None)
) -> dict[str, object]:
    """Record that a logged-in shopper opened a product page.

    Returns 202 and `tracked: false` for guests instead of 401 — a guest opening a
    product has done nothing wrong, so this must not look like an error in their
    console.
    """
    shopper = current_user(cc_session)
    if not shopper:
        return {"tracked": False, "reason": "not logged in"}
    return {"tracked": record_product_view(shopper["id"], product_id)}


@app.get("/api/products/{product_id}")
def product_detail(product_id: str) -> dict[str, object]:
    found = fetch_product(product_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"No product '{product_id}'")
    return found


def _build_deps(shopper: dict | None, request: ChatRequest) -> ChatDeps:
    """Assemble the per-run context: who is asking, and where they are standing.

    Identity comes from the signed session; page location comes from the request.
    Neither is hardcoded in the prompt file, which stays identical for everyone.
    """
    deps = ChatDeps()

    if shopper:
        deps.user_id = shopper["id"]
        deps.first_name = shopper["first_name"]
        deps.last_name = shopper["last_name"]
        deps.full_name = shopper["name"]
        deps.email = shopper["email"]
        deps.member_since = shopper.get("created_at")

    if request.page:
        deps.page_path = request.page.path
        if request.page.product_id:
            # Resolve the id to a real product here, so the agent is never told the
            # shopper is looking at something that does not exist.
            row, _ = resolve_product(request.page.product_id)
            if row:
                deps.page_product_id = row["product_id"]
                deps.page_product_name = row["name"]

    return deps


@app.post("/api/chat", response_model=ChatReply)
async def chat(
    request: ChatRequest, cc_session: str | None = Cookie(default=None)
) -> ChatReply:
    """One turn of conversation with Handsome Dan.

    The session cookie is read here rather than trusting anything the browser sends
    in the body — otherwise a shopper could claim to be someone else simply by
    editing the request.

    History: a logged-in shopper's thread is loaded from `chat_messages`, so it
    survives a reload and cannot be rewritten by the browser. Guests may chat, and
    their thread is whatever the panel sends; nothing is stored.
    """
    shopper = current_user(cc_session)
    deps = _build_deps(shopper, request)

    if shopper:
        stored = load_chat_history(shopper["id"], limit=HISTORY_TURNS)
        history = [ChatTurn(role=m["role"], content=m["content"]) for m in stored]
    else:
        history = request.history

    try:
        reply = await run_chat(request.message, history=history, deps=deps)
    except AgentUnavailable as exc:
        # A configuration problem, not the shopper's fault — say so rather than
        # letting the panel show a bare 500.
        log.error("Agent unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=f"The shop's clerk is not available: {exc}")
    except Exception:
        log.exception("Agent run failed")
        raise HTTPException(
            status_code=502,
            detail="I couldn't reach the shop's records just now. Try again in a moment.",
        )

    # Persist only for members. Saved after a successful run so a failed turn does
    # not leave a question in the log with no answer beside it.
    if shopper:
        save_chat_message(shopper["id"], "user", request.message)
        save_chat_message(
            shopper["id"],
            "assistant",
            reply.reply,
            products=[p.model_dump() for p in reply.products] or None,
        )

    return reply


@app.get("/api/chat/history")
def chat_history(cc_session: str | None = Cookie(default=None)) -> dict[str, object]:
    """The logged-in shopper's saved conversation, for restoring the panel on load.

    Guests get an empty list rather than an error — chatting without an account is
    allowed, it simply is not remembered.
    """
    shopper = current_user(cc_session)
    if not shopper:
        return {"logged_in": False, "messages": []}
    return {
        "logged_in": True,
        "messages": load_chat_history(shopper["id"], limit=HISTORY_TURNS),
    }


@app.delete("/api/chat/history")
def delete_chat_history(cc_session: str | None = Cookie(default=None)) -> dict[str, object]:
    """Forget this shopper's conversation. Their memory should be theirs to erase."""
    shopper = current_user(cc_session)
    if not shopper:
        raise HTTPException(status_code=401, detail="Not logged in.")
    return {"deleted": clear_chat_history(shopper["id"])}


@app.get("/api/chat/health")
def chat_health() -> dict[str, object]:
    """Reports whether the agent can be built, without spending a model call."""
    from agent import get_agent, load_prompt

    try:
        prompt_chars = len(load_prompt())
        tools = sorted(t.name for t in get_agent()._function_toolset.tools.values())
        return {"status": "ok", "model": MODEL_ID, "prompt_chars": prompt_chars, "tools": tools}
    except AgentUnavailable as exc:
        return {"status": "unavailable", "reason": str(exc)}
