# HW5 — Campus Customs agent team

A five-agent team (boss, inventory, accounting, facilities, customer service) that works the shop's tickets through a campus-customs MCP server, with a FastAPI backend and a React desk board. Details are in `output/harness.md` and `output/design.md`.

All commands below run from this folder (`hw5/`) unless a step says otherwise.

## 1. Set up

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then put your Portkey key in .env
```

## 2. Databases (and a clean run)

- `data/campus_customs.db`: the original database. Never modified.
- `data/campus_customs_new.db`: the working copy the agents change. It's committed in its state after the Problem 9 run (checking $1,000.00).

When you need a clean run, copy the original over the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

The board's **Reset shop** button and `POST /reset` do the same thing.

## 3. Start the MCP server

```bash
python mcp_server/server.py
```

This runs the campus-customs server over stdio, which is how `.mcp.json` connects it to a coding assistant. The agents don't need it running separately: each agent starts its own copy of `mcp_server/server.py` when it runs, all pointed at `data/campus_customs_new.db`.

## 4. Start the FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API is at http://localhost:8000 (interactive docs at `/docs`). It only accepts browser calls from the board at http://localhost:5173.

## 5. Start the React board

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## 6. Full three-ticket run

1. **Reset the database first**: click **Reset shop** on the board, or run the `cp` command from step 2. Checking should read $3,400.00.
2. Pick ticket 101 and click **Start the agent team**. Repeat for 102 and 103.
3. Ticket 102 prepares the $2,400 rent payment. Click **Approve & pay** under **Needs your approval**; checking drops to $1,000.00.

Every run is appended to `output/audit_trail.json` and `output/decision_log.json`.

To run tickets without the board: `python -m backend.run_ticket 101 102 103` (or `--open` for every open ticket).
