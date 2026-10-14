# Campus Customs Front Desk: Design Notes

The dashboard (`frontend/`, React + Vite + TypeScript) is the desk a shop manager sits at while the agent team works tickets. It talks to the FastAPI backend at `http://localhost:8000`, which only accepts browser calls from the board's own origin (`http://localhost:5173`, the `npm run dev` default).

The look is modeled on the Robinhood trading app: dark, quiet, and green. A trading app solves the same problem this desk does. Someone watches live activity, keeps an eye on one number that matters (there, a portfolio; here, checking), and occasionally confirms a transaction. Borrowing that visual language makes the board feel familiar and calm instead of busy.

## Layout

Three columns, read left to right in the order the work happens:

| Column | What's there | Why |
|---|---|---|
| **Left: ticket queue** | The three tickets, styled like a watchlist, with the **Start the agent team** button under the selected one. | You always start by picking work. A watchlist is the pattern people already know for "a short list of things I'm tracking". |
| **Center: agent floor** | One desk per agent, then a play-by-play feed of the run. | This is where your eyes go while a ticket runs, so it gets the widest column. The desks show *who* is working; the feed shows *what happened, in order*. |
| **Right: decisions and results** | **Needs your approval** on top, **What each agent did** below. | Things that need a human sit on the right, where you finish reading. Approvals come first because they block cash; the summary is for review after the run. |

The **checking balance** sits alone in the top bar, large, like a portfolio value. It's the one number that changes because of a human decision, so it gets the most prominent spot and is always visible.

Below about 1,150px wide, the columns stack into one so the board still works in a narrow window.

## Color

- **Black background, charcoal cards, thin dark borders.** Dark surfaces keep the screen calm during a long run and make the few colored things stand out.
- **Green (`#00c805`) means "go" or "good":** the main buttons (start a run, approve a payment), resolved tickets, and a rising balance. One action color means you never have to hunt for what to click.
- **Orange-red (`#ff5000`) means money went out:** a dropping balance and a sparkline that turns red. It's the same color Robinhood uses for a loss, so it reads instantly.
- **Amber means waiting on someone:** the "agents working" pill, the "Needs your approval" label, and boss sign-offs.

Green, red and amber are reserved for these meanings, which is why the agents use different colors.

## How the agents read differently

Each agent has a fixed identity used everywhere it appears: a desk on the floor, dots and names in the feed, and lines in the summary.

| Agent | Color | Symbol | Why |
|---|---|---|---|
| The Boss | green | ★ | The one who decides; it matches the app's "go" color. |
| Inventory | blue | ▦ | Shelves and stock: cool and orderly. |
| Customer Service | pink | ✦ | Warm and expressive, matching its Tony Stark voice. |
| Facilities | amber | ⌂ | A house for rent and the building. |
| Accounting | purple | $ | Books and money. |

On the **agent floor**:
- The agent working right now **lifts slightly, glows in its color, and its avatar pulses**, so you can tell who's working at a glance.
- Agents that aren't part of the ticket are **dimmed**. On ticket 102, for example, only the boss and facilities light up, which shows the routing without reading anything.
- Each desk has a **speech bubble** with that agent's latest action in plain English ("Checking the spend limit…", "Prepared $2,400.00. Waiting for a human to approve."). Raw tool names like `check_spend_limit` are translated, because a manager shouldn't need to know the tool API.
- A small **tool-call counter** under each desk shows how much work that agent did.

The **play-by-play feed** gives each event a timestamp, the agent's colored dot and name, a small tag for the action ("Opening the books", "reported"), and one plain-English line. It scrolls itself as events arrive and shows typing dots while the run continues. Tool calls and their results are merged into a single line, so the feed tells a story instead of a log.

## How resolved tickets show up

When a run finishes, the ticket card gets a **green RESOLVED stamp**, tilted and animated, plus a green "✓ resolved" pill. A stamp is something you notice from across the room, and it reads like a real desk marking a ticket done.

Underneath, the card still shows the **database status as a small outlined tag** (for example `awaiting restock` or `negotiating`). Two separate signals are needed because "the agents finished their work" and "the ticket is closed in the shop" aren't always the same. Ticket 101 is done for now but is waiting on a vendor delivery. Showing both keeps the board honest.

While a ticket runs, its card says **"● agents working"** in blinking amber, and the start button reads **"Agents on it…"** and is disabled, so you can't start a second run on top of the first.

Run results are saved in the browser so a refresh doesn't lose them. If the database shows a ticket as plain `open` again (the shop was reset), the saved stamp is ignored so the board never claims a ticket is resolved when it isn't.

## How cash shows up

- **The balance is the biggest text on the page**, in the top-right, like a portfolio value.
- After an approved payment, the number **counts down** to the new value instead of jumping. You see the money leave, which makes approving feel as serious as it is.
- A **sparkline** beside it tracks every balance this session. Its line and end dot turn **red after a drop** and **green after a rise** (for example after a reset).
- A change line under the balance shows the last movement in dollars and percent, e.g. **"−$2,400.00 (−70.59%)"**, in the same red or green.

## How approvals show up

Agents can only *prepare* payments, so the approval card is designed like a trading app's **order confirmation**:

- The **payment type** (e.g. "Rent payment") in amber, plus which ticket it's for.
- The **amount** in large type.
- **Who prepared it** and why ("Prepared by facilities agent · pay_rent for ticket 102").
- A **"Checking after"** row showing what the balance will be. It turns red if the payment would overdraw the account. You see the consequence before you click.
- A full-width green **Approve & pay** button and a quieter **Reject** button that asks for a reason.

A green count badge next to "Needs your approval" shows how many payments are waiting.

## Smaller choices

- **Plain language everywhere:** tool names, statuses with underscores and JSON never reach the screen.
- **Live, but cheap:** the board refreshes tickets, cash and approvals every 5 seconds, and polls the feed about every second only while a run is going.
- **Clear failure states:** if the API isn't running, a banner says so and gives the exact command to start it. Failed actions show a dismissible error.
- **Reduced motion:** all animations turn off for people who set "reduce motion" in their system settings.
- **Reset shop** asks for confirmation first, since it wipes the shop's data back to the original.
