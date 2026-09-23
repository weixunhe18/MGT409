# AI Prompt Log — HW 1

This file records prompts exchanged with the AI for review. It is separate from the runtime files in `prompts/`.

## Initial setup prompt

> I am working in HW 1 folder now. there are 9 problems total. create a AI_prompts.md file to keep track of all my prompts to you (so teacher can review prompts like this one i'm typing). this is different than the runtime files in prompts/
>
> here's how you should structure the file. there should be one section for each problem 2-9. each section must include the problem number and title, my prompts, and a placeholder section that i will edit after the problem where i summarize what was lacking after my first prompt.

> update ai_prompts.md each time i submit prompt. keep it always updated.

## Problem 2 — Read receipts

### My prompts

> problem 2 is to read receipts. create a script called read_receipts.py, call an LLM using prompt in prompts/receipts_extract.md to extract data from purchase receipt PDFs inside folder. extract data 1 row at a time. then save JSON of those rows to output/receipts.json. reference agents.md on best practice.
>
> for JSON, I want to track vendor, transaction date, description of what was purchased, amount_usd, category (cogs_part, tools_equipment, shipping), source_file (filename of PDF).
>
> if something is missing, label as fields_not_found. do not invent values.
>
> this script should run using this format: python read_receipts.py --docs-dir PATH --out-dir output
>
> docs-dir is the unzipped pack which is in HW1 now

> there are 11 pdf, you only got 4. try again

> you're right. move the receipt docs into a /receipts subfolder for better organization

> receipts should be a subfolder inside pdfs

> when parsing receipts, make sure you grab the total price including shipping, tax and fees. fix amazon receipt

### What was lacking after my first prompt

> When I checked JSON, one of the values recorded the MSRP but not the tax. I realized I was not clear which number I asked AI to record.

> there were also some receipts it missed the first time, so i asked it to check its work

## Problem 3 — Read bank statement

### My prompts

> problem 3, read bank statement. turn bank_statement_jan2026 into structured rows.
>
> create a script read_bank.py that calls an LLM using prompt in prompts/bank_extract.md to extract each line from bank_statement_jan2026, then save JSON array of those rows to output/bank_transactions.json
>
> each line must include: date, description, amount, classification as business or personal expense, credit (money in) or debut (money out), accounting_label of whether this is revenue, expense, owner_draw, transfer, expense time like rent, utilities, cogs_parts

> as a sanity check, can you add up amount in json files and give me total. do not look at the bank_statement_jan2026

> referencing `bank_transactions.json` only, what is total deposit

> referencing `bank_transactions.json` only, what is total withdrawal

> return the list of dates you used to calculate total deposit and total withdrawal, and any dates that weren't used in the calculation

> update ai_prompts.md with problem 3 prompts

### What was lacking after my first prompt

> as a sanity check, i reviewed a few lines which looked good. but when i tallied up total deposits and withdrawls, there was a discrepancy with the latter. 
> Total withdrawals from bank_transactions.json: $4,492.14. but bank statement recorded $6,892.14, which is exactly 2400 extra.

## Problem 4 — [Add problem title]

### My prompts

> problem 4. read credit card statement.
>
> create a sccript read_card.py that calls LLM using prompt in prompts/card_extract.md. extract each charge from credit_card_jan2026.pdf, save as JSON array to output/credit_card_transactions.json
>
> each charge must include charge date, merchant, amount, classification as business or personal, expense_category - use null for personal rows
>
> this script should run using this format: python read_card.py --docs-dir PATH --out-dir output
>
> once complete, add up total amounts in JSON file and return in window as a number. i'm using this as a sanity check

> Extracted 13 charges. Total amount: 1395.88. This does not match the balance on the credit card statement of $1,582.88. why do you think this happened?

> update folder name receipts to reviewed, then move bank statement and credit card statement inside too

### What was lacking after my first prompt

Extracted 13 charges. Total amount: 1395.88. This does not match the balance on the credit card statement of $1,582.88. Reconciliation will be fun.

## Problem 5 — reconciliation log

### My prompts

> create a script reconcile.py that calls an LLM using prompt in prompts/reconcile.md to reconcile amounts that appear in more than one document or need a single income-statement decision. each row in log is one reconciled amount, not every raw line from the files in output documents. pass in files from output/, plus emails and pdfs from hw1_spoke_and_wrench/. you can ignore files in pdf/ since we've reviewed those already and exported data to output/.
>
> each row must include id (a short slug for this reconciled item, sources (list of document filenames used), amounts_seen, included_in_income_statements: yes or no depending on whether we count this toward january revenue or expense, amount_used_in_income_statement (amount to book after reconciliation, use 0 if excluded), resolution, plain english explaining how you matched documents and chose final amount.)
>
> this script should run using this format: python reconcile.py --docs-dir PATH --out-dir output

> "amount_used_in_income_statement" should represent the amount to book AFTER reconciliation.

> add the following to reconciliation json. reference email_owner_voice_memo.txt for more details
>
> iou_mike_smith.pdf
> REI jacket
> New Haven Bike Parts: the 742 check on the 18th was a restock order. The 218 on the card on the 25th is a separate counter invoice — don't add them together as one expense.
> Amazon order printout for the headphones matches the 89.99 charge on the card from the 4th. That's my commute headphones, not shop equipment.

> update ai_prompts

> update reconciliation.json name to reconciliation_log.json

### What was lacking after my first prompt

> some amount_used_in_income_statement was erroreous. i repeated the prompt to get it to fix.
> first draft actually missed a few questionable transaction. i highlighted them in my follow up prompts 

## Problem 6 — Judgment call

### My prompts

> problem 6, judgement call
>
> create output/judment_calls.json as a json array.



### What was lacking after my first prompt

<!-- Summarize what was lacking after the first prompt here. -->

## Problem 7 — January income statement

### My prompts

> write a script income_statement.py that reads output/reconciliation_log.json, roll every row with "included_in_income_statement": "yes" into revenue and expense lines, save january income statement to output/income_statement_jan2026.json.
>
> json must include period (2026-01), revenue_usd, expense_lines (each with label: amount_usd, category, sources), total_expenses usd, netincome usd.
>
> don't need LLM to do roll-up math, use python. inputs must come from reconcile step, no hardcoded values.
>
> this script should run using this format: python income_statement.py --docs-dir PATH --out-dir output

> you did not show your work for total_expenses_usd. follow same structure as revenue lines

> list out expense from reconciliation_log.json to show how you got to the net number. below is an example

> no i do not want you to full reconciliation details. revert back

> according to reconciliation log, what line items make up for total expenses?

> according to reconciliation log, what line items make up for total revenues?

### What was lacking after my first prompt

> i asked a few questions due to my lack of understanding of what an income statement needs to look like. i was confused why they only showed one line for revenue, but it was actually good the first time
## Problem 8 — income statement webpage

### My prompts

> create a script report.py that reads json from output/ and builds a one page html summary. save the page to output/income_statement.html. use same numbers as JSON, do not hand-edit totals in HTML.
>
> page should include january income statement, personal and business rows you excluded, and judgement calls from problem 6.
>
> this script should run using this format: python report.py --docs-dir PATH --out-dir output

> let's spice up the html page. make it naruto shipuden theme, i want a ninja running down the page as i scroll, and a pile of cash waiting at the bottom of the page

> update ai prompt
### What was lacking after my first prompt

> wanted to make page more unique

## Problem 9 — process flow diagram

### My prompts

> show arrows from inputs to scripts to outputs
>
> You have built a chain of scripts, JSON files, and prompts. Step back and draw the full process so someone else can see how data moves through your homework. Create a one-page HTML file output/pipeline.html with a block diagram of the pipeline. Look back at Problems 2–8: one block per script, plus blocks for key inputs (document pack, PDFs, emails) and outputs (each JSON/HTML file). Show arrows from scripts to outputs. Mark where the LLM is called. Make clear each script name and what it reads/writes, which steps call the LLM, and the path from the document pack to income_statement.html.

> adjust colors so legend pops on screen


### What was lacking after my first prompt

> improving visibility

## Problem 10 - submission format

### My prompts
> reference agents.md to make this: README.md with install steps, how to set environment variables such as PORTKEY_API_KEY in a local .env file, your model name, and how to run each script. Do not include the actual API key in the README or zip.

> create a requirements.txt file, reference openai and PDF library

> verify if HW1 looks like this. if not, point out discrepancy

> fix spelling for `judgment_calls.json`, adjust project folder name to hw1 lowercase

> what's my ai spend from this project

> were my scripts using OpenAI client or sending raw HTTP request?
