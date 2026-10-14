# AI Prompts Log — Homework 5: Campus Customs Multi-Agent Operations

MGT409 · Weixun He

This file logs what I typed to my vibe coder while working through HW5, one section
per problem. Each section records my first prompt in my own words, and any follow-up
prompts I needed when the first one did not get the job done.

---

## Problem 1 — Vibe coder prompts (5 points)

**First prompt:**

> set up AI_prompts.md for hw5

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 2 — Study the Campus Customs database (8 points)

**First prompt:**

> create output/harness.md
>
> For each table, list the fields and one short line on why that table matters for the agents.
> - inventory - what we have and quantities, and location
> -pricing. List price, unit cost, margins
> -vendor. Lead time
> Leases- cost rent, cash account
> Invoices - how much we owe vendors
> Tickets - open tickets linking to different tables and details

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 3 — Build the MCP server (12 points)

**First prompt:**

> Create map server in mcp_server/ using fastMCP. Talk to data/campus_customs_new.db. you do not need to connect or run it in this problem.
>
> Every agent in this hw uses tools in this map server. You will add more tools to it later; for now write 3 tools you know you need to resolve tickets in database.
>
> Tool1: fulfill customer order. Check against inventory, if we’re out of stock, reach out to vendor and place an order, return lead days
> Tool2. Pay rent on time.
> Tool3. negotiate Discount. Based on product requested, quantity, margin. come up with a reasonable discount, start at 10%. If customer pushback, progressively increase discount. Don’t offer discount greater than 50%. Also, ping tool1 if appropriate.

**Follow-up prompt:**

> In output/harness.md, list my map tools. Highlight which table it reads, which ticket it helps unlock, and one sentence on why that tool is right for that ticket. Be specific but concise. Shoot for 15 words.
>
> Add a short mcp_server/README.md to explain what map server is for, which database file it uses, and the 3 tools

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 4 — Add the MCP server to vibe coder and test each tool (8 points)

**First prompt:**

> Add map server to this project so vibe coder can call the tools. Save connection json text in .mcp.json at project root
>
> With vibe coder connected, test each tool. Save evidence in output/mcp_smoke.json. include the prompt you asked vibe coder, tool name, and tool output (must match values in data/campus_customs_new.db)

**Follow-up prompt:**

> run the problem 4 smoke test: call each campus-customs tool for tickets 101–103 and save evidence to output/mcp_smoke.json

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 5 — Build the agent team and grow the MCP tools (15 points)

**First prompt:**

> Let’s build the agent team using pedantic ai: roles include boss, inventory, accounting, facilities, and customer service. Use portkey_api_key and only gpt-6-luna for every agent.
>
> boss - you are in charge of a team. Based on the ticket, decide the most relevant agent to delegate the work to
> inventory - your job is to update inventory count, flag when we are out of stock and order more from vendors
> accounting - your job is to manage the books. When money comes in or goes out, you keep track of this using best accounting practices
> facilities - your job is to keep the lights on, literally. Make sure
>  customer service
>
> Put agent prompts in backend/prompts/, one file per agent. Put data types in backend/models.py, and agent files under backend/
>
> Ask me questions so we can elaborate on prompts to cover all aspects of agents work and scope.

**Follow-up prompt:**

> approval limit is 80% of whwat i have in checking account
>
> ask boss to sign off, track decisions so i can see when an agent made a call v boss
>
> accounting should add MCP tools in Problem 5 so it can record payments and invoices
>
> boss should chain agent, just track this in a log.
>
> customer service should take on iron man tone.

**Follow-up prompt 2:**

> for 103, since it identified we're missing 12 hoodies. it should alert the boss, who should then trigger inventory agent to order more
>
> also decision_log.jsonl seems wrong, should be decision_log.json

**Follow-up prompt 3:**

> Add any tools agents need to map server so they can work on open tickets. I’m open to suggestions. Shop facts come from map server over data/campus_customs_new_db, do not invent a second shop-tools layer that bypasses mcp.
>
> Wire agents so they append to output/audit_trail.json as they run. For each agent loop step, record enough to audit later. Append to this file, do not wipe

**What was lacking after the first prompt:**

> My first prompt left the facilities and customer service roles unfinished and didn't say when agents need approval to spend money, what tools accounting gets, or how the boss should handle tickets that need more than one agent.

---

## Problem 6 — Plan the three tickets (8 points)

**First prompt:**

> Problem 6 now.
>
> Build output/desk_tickets.html that lets me double click with one tab per ticket (101, 102, 103). Add empty cash and reflection tabs for later problems.
>
> On each ticket tab, create a section for expectation and actual. Fill in expectation now.
>
> Heres my expectation for:
> 101 - boss pings inventory, inventory checks invoices, does nothing since invoice is already out.
> 102 - boss pings facility, facility pays rent
> 103. Boss pings customer service agent, CS calculates a discount and communicates with customer, boss also pings inventory to check stock and order more from vendor

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 7 — Backend routes (7 points)

**First prompt:**

> problem 7 time. In backend/main.py, use fastAPI and add routes that:
>
> - Return the three tickets and whether each is open or resolved
> - Take a ticket id and run your agent team on that ticket
> - Return recent agent events — what each agent said and which tools they used — so the board can refresh
> - Approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash)
> - Return the current checking balance from `cash_accounts`
> - Reset the database to the original values when you want to try a fresh run
>


**Follow-up prompt:**

> this is for the frontend to talk to later. In output/harness.md, list each route in one line (what url/what it does)

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 8 — Agent dashboard (12 points)

**First prompt:**

> Problem 8. Agent dashboard. Build frontend/ with react and vice and typescript. Page should call the routes from problem 7.
>
> - List all **three** tickets
> - Let you **pick one ticket** and start the agent team on it
> - Show each agent and what they are saying / doing while the ticket runs
> - Mark a ticket **resolved** when the run finishes
> - Show a short **summary of what each agent did** on that ticket
> - Let a human **approve** a pay or purchase when asked
> - Show the checking balance (it should drop after an approved pay)
>
> Make the dashboard look good. Be creative with the layout and feel — this is a real desk people would want to sit at, so put thought into how it looks.

**Follow-up prompt:**

> emulate the robinhood trading platform theme. i like the dark and green theme

**Follow-up prompt 2:**

> Front end should talk to backend at localhost:8000. On backend, allow vote page origin so browser is allowed to call those routes, usually localhost:5173
>
> Start board with npm run dev
>
> Write output/design.md to explain decisions for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 9 — Resolve the tickets (10 points)

**First prompt:**

> Problem 9. Before testing agents on a full run over the three tickets, reset working database again so you can start clean. Note the starting checking balance. Then run all three tickets on board until each is resolved.
>
> Open output/desk_tickets.html from problem 6. On each ticket tab, fill actual section from this run: which agents worked, what they delegated, and which tools they used. Keep expected secion.

**Follow-up prompt:**

> On the cash tab of the same output/defsk_tickets.html, itemize the money:
>
> - Starting checking balance (after the reset)
> - For ticket: how cash changed when that ticket resolvefd, and why (which pay / purchase, dollar amount)
> - Ending checking balance — it muast match `cash_accounts` in the working database
>
> Wrong cash math loses poidnts even if the board shows every ticket resolved. Also save:
>
> - `output/resolved_tickets.json` — for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals
> - `output/resolved_board.html` — a page you can double-click with a scrseenshot of your React board for **each** resolved ticket (101, 102, and 103)
>
> Append real runs to `output/audit_trail.json`. Finish `output/harness.md` so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules.

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 10 — Reflection (10 points)

**First prompt:**

> _(to be filled in when I start this problem)_

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 11 — Submit to GitHub (5 points)

**First prompt:**

> _(to be filled in when I start this problem)_

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_
