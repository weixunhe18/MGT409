# Market Desk

A Dash chat interface for a PydanticAI stock-research agent.

## Start

```bash
source .venv/bin/activate
python app.py
```

Open `http://127.0.0.1:8050`.

The app loads `PORTKEY_API_KEY` from `../.env`, calls `gpt-5.6-luna` through Portkey, and uses the OpenAI Responses native `web_search` tool plus an audited yfinance `get_stock_price(ticker, start, stop)` tool.

## Safety and operations

- The ticker universe is limited to the five holdings in `portfolio.json`.
- Price claims require yfinance output; no estimate or invented price is returned.
- Each turn is capped at 8 model requests and 5 tool calls; native web search is capped at 2 uses.
- `audit.jsonl` records prompts, observable tool activity, data observations, errors, and token counts. It deliberately does not retain private chain-of-thought.
- This is research/education software, not trading or personalized financial advice.

Provider cost is not exposed by the app yet. The course budget is $40 over six weeks; check Portkey usage to calculate cumulative spend and remaining budget before extended use.

Official OpenAI native web-search reference: https://developers.openai.com/api/docs/guides/tools-web-search
