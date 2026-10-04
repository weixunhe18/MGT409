# Campus Customs

An officially-licensed Yale apparel shop with **Handsome Dan**, a chat assistant that
answers questions about price and stock from the shop's own database — and says so
plainly when the shop does not carry something.

Vite + React + TypeScript front end, FastAPI back end, PydanticAI agent on
`gpt-5.6-luna` via Portkey.

---

## Running it

### 1. Place the data pack

The database and product images are **not in this repository** — they are
course-supplied assets. Unzip `data.zip` into the project root so you have:

```
hw4/
└── data/
    ├── campus_customs.db
    └── products/            # 102 product images
```

Nothing else needs moving. The backend reads `data/` directly.

### 2. Add your API key

```bash
cp .env.example .env
```

Then edit `.env` and set `PORTKEY_API_KEY`. Also set `JWT_SECRET` to any long random
string, or every restart will log users out.

> Without a Portkey key the site still runs — browsing, accounts and product pages all
> work. Only the chat returns a 503 and says the clerk is unavailable.

### 3. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && cd ..
```

### 4. Run both halves

Two terminals.

**Back end** — must be started from `backend/`, since imports are flat:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Front end:**

```bash
cd frontend
npm run dev -- --port 5190
```

Open **http://localhost:5190**.

> Use the front-end URL, not the API directly. Vite proxies `/api`, `/images` and
> `/motion` to port 8000 so every request is same-origin — which is what lets the
> session cookie work. Hitting `127.0.0.1:8000` in the browser will appear to log you
> in and then not stick.

### 5. Optional — product motion loops

Three hero products show a short video loop. The clips are generated from the
catalogue photos and are not committed:

```bash
.venv/bin/python scripts/make_motion_loops.py
```

Skip it and the site is unchanged, just without motion.

---

## Signing in

The shipped database includes a test account:

| Email | Password |
|---|---|
| `test@campuscustoms.yale.edu` | `password` |

Or create a new account from the nav bar. Guests can browse and chat; only signed-in
shoppers get saved chat history and a *Recent Products Viewed* strip.

---

## Layout

```
hw4/
├── AI_prompts.md            # graded log of prompts used to build this
├── requirements.txt
├── .env.example
├── README.md
├── frontend/                # Vite React TypeScript app
├── backend/
│   ├── main.py              # FastAPI app — run with: uvicorn main:app --reload --port 8000
│   ├── agent.py             # agent wiring: prompt file + model + tools
│   ├── tools.py             # what the agent can look up
│   ├── models.py            # structured types shared by API, agent and tools
│   ├── prompts/prompt.md    # system prompt: voice, honesty rules, safety
│   ├── config.py            # settings and paths
│   ├── db.py                # SQLite access layer
│   ├── auth.py              # accounts, passwords, sessions
│   └── audit.py             # append-only agent log
├── scripts/
│   └── make_motion_loops.py # builds the product video loops
└── output/
    ├── harness.md           # how the whole system works
    ├── design.md            # styling decisions and why
    ├── usability.md         # improvements and their business case
    ├── app_check.html       # tested site walkthrough with screenshots
    ├── app_check_images/
    └── audit_trail.json     # append-only record of agent activity
```

The agent itself is four files: `prompts/prompt.md`, `agent.py`, `tools.py`,
`models.py`.

**Start with [`output/harness.md`](output/harness.md)** — it explains the database,
the agent, the tools, the safety rules, and every limit in one place.

---

## Notes

- **The agent never invents a price or a stock count.** Product cards can only be built
  from database rows, so a name the model makes up produces no card.
- **Passwords** are stored as PBKDF2-SHA256 with a per-user salt at 600,000 iterations.
  Five failed logins lock an email for 15 minutes.
- **Every agent turn is logged** to `output/audit_trail.json` — time, tools called,
  stop reason — appended, never rewritten.
