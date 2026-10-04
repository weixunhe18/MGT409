# AI Prompts Log — Homework 4: Campus Customs Shop + Chatbot

MGT409 · Weixun He

This file logs what I typed to my vibe coder while working through HW4, one section
per problem. Each section records my first prompt in my own words, and any follow-up
prompts I needed when the first one did not get the job done.

---

## Problem 1 — Vibe coder prompts (4 points)

**First prompt:**

> /prompt-logging
>
> /prompt-logging https://zlisto.github.io/mgt_409_fa26/hw4/p1.html

**Follow-up prompt:**

> please update ai prompt md as we progress along. you're slacking now

**What was lacking after the first prompt:**

> I set the file up but never said to keep filling it in while we worked, so it went
> stale — I had scaffolded the sections and then built most of Problem 2 before noticing
> nothing was being logged (the very first try also had no URL attached, so it couldn't
> get the real problem titles until I resent it with the link).

---

## Problem 2 — Analyze the database (6 points)

**First prompt:**

> download the data.zip, and unzip

**Follow-up prompt:**

> let's fix the data problem. i like consolidating the types into 6 categories. show me
> the current state, proposed state,

> let's fold performance shirt into t shirt since it's such a small category on its own

> open up campus_customs.db so i can look at the raw file

> why are there chat messages with tauhid at the bottom of the sql db?

> create output/harness.md
>
> document each table and its field, and 1 short line on why each field matters for the
> shop/chatbot. start with the catalogue, inventory, and users

**What was lacking after the first prompt:**

> I never said where data.zip lives, and the hw4 page doesn't link it anywhere, so it had
> to guess URLs until one worked; I also asked for 6 categories before looking at how the
> 102 products actually spread across them, which left a category holding only 2 items
> that I had to fold in on a second pass.

---

## Problem 3 — Build the Campus Customs website (10 points)

**First prompt:**

> goal of today is to build a customer website with chatbot. i'm using react and vite
> typescript front end and pythong fast api backend, brain is pydantic ai agent. shoppers
> should be able to browse products, create an account, chat about merch, see matching
> items appear on page, and get honest answers about price and stock from local database.
>
> use portkey_api_key for making agent calls. we'll use luna today.

**Follow-up prompt:**

> let's test the current front end

> let's work on the frontend. put a navigation bar at top that links to main pages: home,
> products, about us, log in, create account.
>
> pull campus customs-style wording from https://yalebulldogblue.com/ for home and about
> us. but write these pages in a unique voice (as benjamin franklin would, the greatest
> founding father).

> on products page, show product images from catalogue (use image paths in db) with basic
> product info.
>
> make each product open a single item page (large image on one side, full product text on
> the other) clicking on a card on products should take shopper there.
>
> add a chat interface in bottom right of the site as a floating chat panel. it should look
> like handsome dan, then expand when click on. it does not need to talk to an agent yet, a
> stub that will call the backend is enough for now.
>
> we'll need a small api soon to read database. start a simple fastapi app in backend/main.py
> so we can serve products and images, then grow it into the agent backend later

> do not scale the images when expanding. now they look stretched
>
> also this is not what dan looks like. he;s a chubby bulldog. use websearch to verify his
> face.

**What was lacking after the first prompt:**

> images were stretched and handsome dan didn't look real. i asked AI to maintain scale and do websearch to verify dan's face

---

## Problem 4 — Create account and login (8 points)

**First prompt:**

> problem 4 now. lets setup create-account/login flow.
>
> * create account: ask for first name, last, email, password, confirm password
> * login: email and password
>
> new accounts are saved into users table. make sure to store psaswords securely so hackers
> (human or ai) cannot access them (briefly explain how you will achieve this). update
> harness.md to explain how auth work (what we store for user and how passwords are
> protected
>
> i am attaching image of a test

**Follow-up prompt:**

> * add a limit on repeated login attempt to 5 , start showing the count down when someone
> misses the password. also allow for password reset.

**What was lacking after the first prompt:**

> I asked for secure password storage but not for protection against someone guessing
> passwords over and over, or for a way back in when a password is forgotten — both were
> listed as gaps once the first version was built.

---

## Problem 5 — PydanticAI agent backend (12 points)

**First prompt:**

> P5. Build the chatbot as pydanticAI agent behind fastapi, plugged into the front end chat
> widget. Put api app in backend/main.py. that is the file you run with uvicorn. Keep agent
> as these four files next to it.
> - backend/prompts/prompt.md - system prompt (grow this file later)
> - backend/agent.py - agent entry/wiring
> - backend/tools.py - tools agent can call
> - backend/models.py - pydantic/pydantic ai structured types
>
> In main.py, expose a chat route so message from website returns a reply from agent (and
> whatever else you need for product/auth) . Use the ai model api key for agent.
>
> Put campus customs voice and safety basics into prompts/prompt.md. start to track types in
> models/py for chat replies and product cards as needed.
> In harness.md, note how front nd talks to fast api and how agent is loaded (prompt file +
> model)
>
> i am attaching image of how to run the backend

**Follow-up prompt:**

> when i asked for sport ts, it showed Tri Blend Sports Baseball T-Shirt only, when there
> are more than 1 options. also, it showed 6 counts of Tri Blend Sports Baseball T-Shirt,
> which is excessive. it should only show one count of a product max and leave room for
> other options display.
>
> also, when i asked "do you sell any sport ts in small", it returned "I cannot reach the
> shop just now (I couldn't reach the shop's records just now. Try again in a moment.). Is
> the backend running on port 8020?" why is it tripped up by a 2 part query

**What was lacking after the first prompt:**

> My first prompt said to build the agent and plug it into the chat widget but never said
> anything about what the results should look like or how many tool calls a question is
> allowed to make — so long product names got clipped until six different shirts looked
> like one, and a two-part question ("sport ts" + "in small") made it check stock on every
> result until it blew the tool-call limit and crashed.

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 6 — Tools: product info and stock (8 points)

**First prompt:**

> p6 now, lets make the product/stock tools solid
>
> Arm agent with tools that look up real info from campus_customs.db: product description,
> price, how many are in stock by size when customer asks
>
> Agent must use database. It should not invent price or quantities. If a size is out of
> stock, say so clearly.
> Expand prompts/prompt.md so agent knows to call these tools for price and stock questions.
> Add/update return types in models.py
> In output.harness.md, list each tool and explain which model fields you chose for lookup
> results and why.

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 7 — Chat search that updates the page (10 points)

**First prompt:**

> p7 now, chat search should update the product grid on the page
>
> New feature alert. When customer asks about a type of item, ie, what hoodies do you have.
> The agent should search catalogue and website should dynamically show those matching items
> as product cards (image, name, price, short info). this is an api contract. The agent
> returns structured product matches and then front end renders them on website
> Test/verification. After dynamic product cards are loaded by new feature, make sure the
> same single-item page behavior you built in problem 3 still works. Each product card -
> including the ones the chat just put on page, should still open that detail view (large
> image + full info) when clicked.
> Update prompts/prompt.md and harnes.md so its clear how search results reach the page.

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 8 — Customer memory (8 points)

**First prompt:**

> p8 now, let's add customer memory
>
> When a shopper logs in, save their chat history in the database in an appropriate table
> and reload it when they return. Greet them by name. The agent should know who is chatting
> (name, email) - put that in agent deps and tools the agent can call. Also pass enough page
> context that if someone is on a product page and asks "do you have this in pink", agent
> know which item they mean. You could put code into agent context (what's benefit of this).
> I think this means we can put a variable into agent context, rather than hardcoding, is
> that right??
> Guests can chat, but history only needs to persist for logged in users. Document in
> harness.md how user chat history is stored, what customer fields agent sees, how page
> context is passed.

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 9 — Usability improvements (12 points)

**First prompt:**

> p9 now, usability improvements
>
> Let's add improvements. I feel like I already added a few front and back end improvements
> earlier in addition to the prompt, ie Adjusting images to keep scale. Can you help me make
> a list of improvements we've made already that were separate from my main prompt

**Follow-up prompt:**

> If user is signed in, Track product clicks. Next time they login, show them a new section
> called "recent products viewed"

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 10 — Style the website (6 points)

**First prompt:**

> p10 now, let's style the website
>
> Instead of static colors, let the UI react dynamically to school pride and identity:
>
> * Spirit-Adaptive Themes: Allow users to toggle between different school eras or moods
> (e.g., 1900s Vintage Heritage, Game Day Energy, or Gameday Night Mode). The accent colors,
> typography weight, and background textures change dynamically.

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 11 — Site testing (app check) (8 points)

**First prompt:**

> p11 now, site testing
>
> Test the live site and document it in output/app_check.html. include clear screenshots and
> short captions for:
> 1. Chat checking inventory level of an item (honest stock/price from db)
> 2. Dynamic search-result cards appearing after category question (ie hoodies)
> 3. 1 usability features we added in p9
>
> To simplify grading, include heading for each check, screenshot, one or 2 sentence on what
> screenshot proves.
> Store screenshots in output/app_check_images/ and link them from app_check.html with
> relative paths (ie app_check_images/inventory.png)

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 12 — Audit trail, safety, finish harness (4 points)

**First prompt:**

> p12 now, audit trail and safety
>
> Keep an append-only output/audit_trail.json of agent-loop activity (time, tool name, short
> args/result, stop reason). Do not wipe between runs. Also, think of safety rules to give
> agent and put them in prompts/prompt.md
> - customers are mostly students, stay on topic.
> - protecting our brand is critical. if you're unsure about question, do not overpromise and
> make up info.
>
> Finish harness.md so it's clear how system works. Use 1-2 line, short explanation
> - explain model fields in models.py and why we chose them
> - tools and abilities
> - safety rules
> - specs (loop limits, result caps, models, how to run front and back)

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 13 — Push to GitHub and submit the URL (4 points)

**First prompt:**

> Double check to ensure my hw4 format looks like this. If not, adjust as needed.
> [attached the expected file layout and the local-only data pack rules]

**Follow-up prompt:**

> yes delete both, then commit everything

> changed my mind. put it in MGT409 repo. that's fine

> p13 now, push to github and submit url

**What was lacking after the first prompt:**

> Checking the layout turned up more than formatting — data/ was not gitignored, so the
> database and all 102 product images would have been committed, and .env.example and
> README.md were missing entirely; I also had to decide separately whether to sweep hw3's
> data pack into the same commit.

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_
