# AI Prompts Log — Homework 3: Campus Customs Agent

MGT409 · Weixun He

This file logs what I typed to my vibe coder while working through HW3, one section
per problem. Each section records my first prompt in my own words, and any follow-up
prompts I needed when the first one did not get the job done.

---

## Problem 1 — Vibe coder prompts (6 points)

**First prompt:**

> let's start by setting up AI_prompts.md. keep this as a log for vibe coder.
>
> create 10 sections. for each section, include placeholder for problem number, title,
> prompts i entered first, and leave space for me to add follow prompts i added if my
> first prompt did not get the job done. as i work through the assignment, i will tell
> you when i move to a new problem, that's when you should update this doc with my prompt.

**Follow-up prompt:**

> can you add colors to text that i wrote so it pops out more in md file

> revert, remove html stuff. no visual effect and adds fluff.

**What was lacking after the first prompt:**

> Nothing was wrong with the first result — I tried adding color to make my own words
> stand out, but markdown has no native color syntax and the inline HTML it required
> rendered inconsistently, so I reverted to plain text.

---

## Problem 2 — Build the product catalogue (18 points)

**First prompt:**

> let's move to problem 2. don't do any work yet. i want help brainstorming strategies.
>
> i want to turn 102 product photos in data/products/ into a structured catalogue entry.
> fields i want to track are school (ex: yale, benjamin franklin), clothing type (hoodie,
> crewneck, t-shirt).
>
> 102 images is a lot. what are ways we can speed up the code so we're not grinding
> through 1 image at a time? give me 3 options. i want to achieve something faster than
> a plain sequential loop

**Follow-up prompt:**

> let's go with option 1, add caching and downscaling
>
> create build_catalogue.py that turns every product photo in data/products into a
> structured catalogue entry. fields i want to track are clothing type (hoodie, crewneck,
> t-shirt), color (primary color of the shirt), special note (sport, school, dad). save
> catalogue to output/catalogue.json
>
> store catalogue entry type in models.py as a pydanticAI model, this is where structured
> data lives.

**What was lacking after the first prompt:**

> Nothing was missing — I deliberately split this into two prompts, asking for speedup
> strategies first so I could pick an approach myself before any code was written, then
> giving the build instructions once I had decided on concurrency plus caching.

---

## Problem 3 — Product-identify agent (18 points)

**First prompt:**

> let's move to problem 3. let's build a product-idenify agent. do this in 4 files:
>
> prompts/prompt.md - system prompt (load it into agent, will add later)
> agent.py - pydantic agent entry point
> tools.py - put the agents tools helper functions here
> models.py - pydantic pydanticai structured types - this already exist
>
> first feature, when i give you an image, you should decide whether a campus customs
> product appears in it (and which one, if you can tell). implement that tool logic in
> tools.py and wire it from agent.py.
>
> do not check every catalogue image one at a time against query photo, and without
> sending more than 10 product images in a single call to the ai. my proposal is to run
> a feature check on the photo, describe it based on identifiers in models.py (clothing
> type, color, description, text on garment), then compare that description against
> catalogue.json to find a match.
>
> add the structured return type for this ability to models.py as a pydantic/pydanticai
> model .
>
> agent should be able to take image path from terminal, like this "python agent.py
> --image "data/test_images/example.jpg"
>
> use portkey_api_key for ai model calls in the agent. we'll use gpt-5.6-terra today

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 4 — Test identify on four images (12 points)

**First prompt:**

> let's move to problem 4, run agent on all 4 test images. test images are in data/. save
> agent output to output/identify_product.json - each entry should match the identify
> pydantic/pydantic ai model in models.py

**Follow-up prompt:**

> create output/agent_evaluation.md. in it, write the following: "
> my model performed 4/4, 100%. it was able to accurately describe the garment, match it
> to catalogue.json. what we could improve is giving it tougher images where logos are
> stretched or blurry.
> "

**What was lacking after the first prompt:**

> My first prompt only covered running the agent and saving the JSON, so it missed the
> second half of the problem — the written evaluation of how the agent actually did.

---

## Problem 5 — Ad video + profile ability (12 points)

**First prompt:**

> let's move to problem 5, add ad video + profile ability
>
> add ability for agent to take video and customer profile json file, then judge how
> effective video would be at convincing that customer to shop at campus customs. put new
> tool code in tools.py. update prompts/prompt.md so agent knows how to use new ability.
>
> reuse same files, do not create duplicates.
>
> add structured result type for this ability in models.py
>
> wire terminal the same way: python agent.py --video "data/videos/ad_humble.mp4"
> --profile "profiles/profile_student.json"

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 6 — Student and parent profiles (8 points)

**First prompt:**

> let's move to problem 6, create student and parent profiles
>
> create profiles/profile_student.json and profiles/profile_parent.json. these describe
> typical yale student and parent.
>
> student - 16-21. smart, thoughtful, inquisitive, social
> parent - 40-60, caring, wealthy, college educated
>
> what would matter for whether an ad resonates. add this to models.py
>
> * production quality
> * thoughtful voice
> * clear call to action
> * sound logic

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 7 — Run ad for both profiles (10 points)

**First prompt:**

> let's move to problem 7, run ad for both profiles
>
> python agent.py --video "data/videos/ad_humble.mp4" --profile "profiles/profile_student.json"
> python agent.py --video "data/videos/ad_humble.mp4" --profile "profiles/profile_parent.json"

**Follow-up prompt:**

> save structured results for both runs to output/ad

**What was lacking after the first prompt:**

> My first prompt was just the two commands and did not say where the results had to end
> up, so I followed up to pin the output file — though the agent was already writing both
> runs into output/ad_effectiveness.json.

---

## Problem 8 — Safety rules + audit trail (8 points)

**First prompt:**

> let's do problem 8. add safety rules for processing images ( what agent must and must
> not do with customer photos) to prompt/prompt.md, do not make nudes, keep it PG. nothing
> that would make me embarassed in a professional environment.
>
> add clear safety section that agent will load as system prompt.
>
> agent should append to output/audit_trail.json on every run: for every agent loop
> iteration, record enough to aduit lataer (time, thoughts, tool names + args + short
> result, stop reason). apend as agent runs, do not wipe file each time.
>
> put audit entry type in models.py as pydantic model so each appended record is structured
> same way.

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 9 — Finish the harness (4 points)

**First prompt:**

> let's move to problem 9, finish the harness
>
> don't be verbose. keep this document under 300 words. keep the earlier sections. this
> problem is about making whole document coherent and complete
>
> write in my normal style. incomplete sentence, typos, no proper caps.

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_

---

## Problem 10 — Submit zip (4 points)

**First prompt:**

> let's move to problem 10, review against these checks
>
> (pasted the Problem 10 expected layout and submission rules: hw3/ folder zipped as
> hw3.zip, no real .env, .env.example with placeholder PORTKEY_API_KEY and model settings,
> agent is four files, models.py holds all structured types, course data/ pack not required
> inside the zip)

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_
