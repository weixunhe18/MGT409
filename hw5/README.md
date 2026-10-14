# HW5 — Campus Customs agent team

A five-agent team (boss, inventory, accounting, facilities, customer service) that works the shop's tickets through a campus-customs MCP server, with a FastAPI backend and a React desk board. Details are in `output/harness.md` and `output/design.md`.

## Data

- `data/campus_customs.db`: the original database (never modified).
- `data/campus_customs_new.db`: the working copy, left in its state after the Problem 9 run (checking $1,000.00). `POST /reset` or the board's **Reset shop** button restores it from the original.

## Run

From this folder (`hw5/`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then put your Portkey key in .env
```

Start the API from `backend/`:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Start the board in a second terminal, from `frontend/`:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. To run tickets without the board: `python -m backend.run_ticket 101 102 103` from `hw5/`.
