"""Dash interface for the PydanticAI stock analyst."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from dash import Dash, Input, Output, State, dcc, html, no_update

from analyst_agent import ALLOWED_TICKERS, load_portfolio, run_analysis


APP_DIR = Path(__file__).resolve().parent
portfolio = load_portfolio()
initial_messages = [
    {
        "role": "assistant",
        "content": "I’m ready to research the approved portfolio universe. Ask about price history, news, or portfolio context.",
    }
]

app = Dash(__name__, title="Market Desk")
app.layout = html.Div(
    className="app-shell",
    children=[
        dcc.Store(id="conversation", data=initial_messages),
        dcc.Store(id="agent-history", data=[]),
        dcc.Store(id="pending-request"),
        dcc.Store(id="agent-result"),
        dcc.Store(id="in-flight", data=False),
        dcc.Interval(id="thinking-timer", interval=450, n_intervals=0),
        html.Aside(
            className="sidebar",
            children=[
                html.Div([html.Div("MARKET DESK", className="wordmark"), html.Div("PydanticAI research terminal", className="submark")]),
                html.Div(className="rule"),
                html.Div("PORTFOLIO MEMORY", className="eyebrow"),
                html.Div(f"As of {portfolio['as_of']}", className="as-of"),
                html.Div(
                    [html.Div([html.Span(item["ticker"]), html.Span(f"{item['shares']} sh")], className="holding") for item in portfolio["holdings"]],
                    className="holdings",
                ),
                html.Div(f"Cash  ${portfolio['cash']:,.0f}", className="cash"),
                html.Div(className="sidebar-bottom", children=[
                    html.Div("GUARDRAILS", className="eyebrow"),
                    html.Div("Universe: " + " · ".join(sorted(ALLOWED_TICKERS)), className="small-copy"),
                    html.Div("Research only — no trade execution", className="small-copy"),
                    html.Div("Budget: $40 / 6 weeks. Cost appears after provider usage is available.", className="budget"),
                ]),
            ],
        ),
        html.Main(
            className="main-panel",
            children=[
                html.Header(className="topbar", children=[html.Div([html.Div("RESEARCH CONSOLE", className="eyebrow"), html.H1("Stock analyst", className="title")]), html.Div("LIVE TOOLS ENABLED", className="live-pill")]),
                html.Div(id="chat", className="chat"),
                html.Div(className="composer-wrap", children=[
                    dcc.Input(id="prompt", className="composer", type="text", placeholder="Ask about AAPL, MSFT, NVDA, GOOGL, or JPM…", debounce=False, n_submit=0),
                    html.Button("Send", id="send", className="send-button", n_clicks=0),
                    html.Div("Enter to send", className="hint"),
                ]),
            ],
        ),
    ],
)


def message_card(message: dict, dots: str) -> html.Div:
    role = message["role"]
    content = dots if message.get("pending") else message["content"]
    return html.Div(className=f"message {role}", children=[html.Div("YOU" if role == "user" else "ANALYST", className="message-label"), dcc.Markdown(content, className="message-content")])


@app.callback(Output("chat", "children"), Input("conversation", "data"), Input("thinking-timer", "n_intervals"))
def render_chat(messages: list[dict], n_intervals: int):
    dots = "Researching" + "." * (n_intervals % 3 + 1)
    return [message_card(message, dots) for message in messages]


@app.callback(
    Output("prompt", "value"),
    Output("conversation", "data"),
    Output("pending-request", "data"),
    Output("in-flight", "data"),
    Input("send", "n_clicks"),
    Input("prompt", "n_submit"),
    State("prompt", "value"),
    State("conversation", "data"),
    State("in-flight", "data"),
    prevent_initial_call=True,
)
def submit_message(_clicks: int, _submits: int, prompt: str | None, messages: list[dict], busy: bool):
    if busy or not prompt or not prompt.strip():
        return no_update, no_update, no_update, no_update
    clean_prompt = prompt.strip()
    next_messages = messages + [{"role": "user", "content": clean_prompt}, {"role": "assistant", "content": "", "pending": True}]
    return "", next_messages, {"id": str(uuid4()), "prompt": clean_prompt}, True


@app.callback(
    Output("agent-result", "data"),
    Input("pending-request", "data"),
    State("agent-history", "data"),
    prevent_initial_call=True,
)
def ask_agent(request: dict | None, history: list[dict]):
    if not request:
        return no_update
    try:
        answer, updated_history = run_analysis(request["prompt"], history, portfolio)
        return {"answer": answer, "history": updated_history}
    except Exception as exc:
        return {"answer": f"I couldn’t complete that research request: {exc}", "history": history}


@app.callback(
    Output("conversation", "data", allow_duplicate=True),
    Output("agent-history", "data"),
    Output("in-flight", "data", allow_duplicate=True),
    Input("agent-result", "data"),
    State("conversation", "data"),
    prevent_initial_call=True,
)
def finish_response(result: dict | None, messages: list[dict]):
    if not result:
        return no_update, no_update, no_update
    completed = messages[:-1] + [{"role": "assistant", "content": result["answer"]}]
    return completed, result["history"], False


@app.callback(Output("prompt", "disabled"), Output("send", "disabled"), Input("in-flight", "data"))
def lock_composer(busy: bool):
    return busy, busy


if __name__ == "__main__":
    app.run(debug=False, use_reloader=False, port=8050)
