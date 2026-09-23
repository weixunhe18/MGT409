# AI Prompt Log — HW 2

This file records prompts exchanged with the AI for review. It is separate from the runtime files in `prompts/`.

## Initial setup prompt

> i am working in hw2 folder today. start by copying AI_prompts.md from hw1. clear all the content but keep the structure. update this file every time i enter a prompt into codex.

> the titles after the - is wrong. update it with titles here [https://zlisto.github.io/mgt_409_fa26/hw2/p2.html](https://zlisto.github.io/mgt_409_fa26/hw2/p2.html)

## Problem 1 — Vibe coder prompts

### My prompts

> build one pydanticai agent in sales-agent.py that loads prompts/sales_agent.md into system prompt.
>
> use playwright web crawler to help with research.
>
> be prepared to work with input query text, you should be able to figure out what user wants. build a profile for the given company.
>
> use openai gpt-5.6-terra, you are a sales analyst agent, always call tools to scrape website for info, never invent data. provide output data in the form of a digestable table.
>
> each time the agent is run, track date and time, thoughts, tool calls (name, arguments, results summary, when run stops) to output/audit_log.json.

> i dont see the output folder

> update ai prompts.md




### What was lacking after my first prompt

<!-- Summarize what was lacking after the first prompt here. -->

## Problem 2 — Seller brief

### My prompts

> i want to help nexa find sales target. i want to help this company because i care about water yet it is often invisible. this company is helping customers gain visibility into how water is moving inside their infrastructure and monitor/protect their asset.
>
> here's website https://www.nexaplatform.com/
>
> collect info about the product it sells, its functionality, its price, constraints, what it can and cannot do, case studies, markets.
>
> save this into assets/seller_brief.md

> we will use portkey_api_key for ai model calls. API key is at the root. use chatgpt-5.6-terra.

### What was lacking after my first prompt

<!-- Summarize what was lacking after the first prompt here. -->

## Problem 3 — Agent system prompt

### My prompts

> let's build an agent using pydanticai. store agent system file in prompts/sales_agent.md.
>
> step 1 is to build a company profile. when you're crawling potential customer sites, collect the following:
>
> 1. Company name, website, headquarters, and operating locations.
> 2. Industry and type of water infrastructure owned or operated.
> 3. Evidence of water-intensive operations or distributed/complex assets.
> 4. Evidence of leakage, aging infrastructure, water scarcity, resilience, compliance, maintenance, or visibility needs.
> 5. Current monitoring, metering, controls, or asset-management tools, if public.
> 6. Relevant decision-makers and departments.
> 7. Trigger event, such as a capital project, sustainability goal, incident, expansion, regulation, or public water-risk commitment.
> 8. Why Nexa may fit, stated cautiously and tied to evidence.
> 9. Unknowns that require discovery before outreach.
>
> do not invent facts, only use verified info form the website.
>
> save finished profiles to assets/company_profile.json

> create virtual env for testing


### What was lacking after my first prompt

<!-- Summarize what was lacking after the first prompt here. -->

## Problem 4 — Build agent + profile run

### My prompts
build one pydanticai agent in sales-agent.py that loads prompts/sales\_agent.md into system prompt.&#x20;

use playwright web crawler to help with research.

be prepared to work with input query text, you should be able to figure out what user wants. build a profile for the given company.&#x20;

use openai gpt-5.6-terra, you are a sales analyst agent, always call tools to scrape website for info, never invent data. provide output data in the form of a digestable table.&#x20;

each time the agent is run, track date and time, thoughts, tool calls (name, arguments, results summary, when run stops) to output/audit\_log.json.>

### What was lacking after my first prompt

<!-- Summarize what was lacking after the first prompt here. -->

## Problem 5 — Expand prompt + find customers

### My prompts
> i tried running "python sales_agent.py \"Build a profile of this company.\" --url https://www.marriot.com" but python command not found

> zsh: command not found: python

> my results are really bad. i think the info i want to search is difficult to find from the website. give me recommendation on how to adjust

> make these adjustments. im on problem 5 btw.

> rerun seller brief since there was cloudflare outage yesterday. update data

> try again https://www.nexaplatform.com/hardware

> make sales agent better. search website for location, estimate building size, room number

> | Nexa fit             | Unable to assess fit from the supplied public-site crawl because Marriott’s website returned an access-denied response and no company, operations, water, or facilities content was available for verification. |
> | Unknowns             | Headquarters and operating locations are not verifiable from the available crawl evidence.; The website crawl did not provide verified information on Marriott’s industry, property portfolio, rooms, sinks/faucets, or other water-intensive or distributed assets.; Water infrastructure, metering, monitoring, controls, asset-management tools, leakage history, water-risk commitments, maintenance needs, and resilience/compliance requirements are not publicly verifiable from the available crawl evidence.; Relevant decision-makers, departments, and current trigger events require discovery.; Discovery questions: Which properties and water systems are in scope? How are water use, flow, leaks, and water-related assets currently monitored? Which teams own facilities engineering, utilities, sustainability, and maintenance? Are there active renovation, conservation, resilience, or compliance projects? |

> i got the same results when i tried the prompt again. Unable to assess fit from the target website because the only crawled page returned Access Denied; no company operations, properties, water assets, or stated needs could be verified. what should we do when page says access denied?

> i tried annual report page, bu Playwright is having issue. help root cause
>
> https://marriott.gcs-web.com/static-files/9cf0e9b0-bbfa-48a6-9e21-ffbdbc4b2d78

> make these improvement

> i tried https://www.navyfederal.org/ just now and results are better. i want to push agent to get creative and use context clue. i am looking for customers that handle water infrastructure, that should be anybody who runs faucet. in this case, banks have toilets and water fountains. they may not explicitly call it out since their main business is banking, but you should use common sense. update sales agent prompt

### What was lacking after my first prompt

the crawler had a hard time with my company sites. either cloudflare outage, or access denied. 
the info i want also is not clearly laidout in the customer site, so i needed to make adjustment to estimate number of faucets/leak risk


## Problem 6 — Agent harness summary

### My prompts

> i'm on problem 6 now
>
> add instructions to the same prompts/sales_agent.md file on how to find customer companies and draft outreach emails when asked. you should read the company profile file, search web for potential customer companies, only keep company if it would be a good customer for the seller specified in seller_brief.md, look through candidate website for useful business context and contact email, draft a targeted outreach email for each target, never send. save results to output/targets.json (company info and contact emails) and output/emails.json (drafted emails). keep the audit tracker file updated output/audit_log.json

> create the terminal prompt like python sales_agent.py "Find 3 good customer targets for this company and draft outreach emails." --profile assets/company_profile.json

> sales-agent.py: error: unrecognized arguments: --profile assets/company_profile.json

> build customer finding mode

> FileNotFoundError: Company profile not found: /Users/bossman/Documents/Yale/MGT409/hw2/assets/company_profile.json

> working on problem 6 now
>
> create harness.md at project root. this is a short summary of how you keep the agent under control - harness around model, not a dump of the code. create first draft and i will edit as needed
>
> every tools the agent can use (name, what it does, inputs/outputs), stopping rules when agent is done/must stop (max steps, enough targets, failures), guardrails - what it must not do (invent facts, send email, runaway cost, unsafe actions)


### What was lacking after my first prompt

fixed a few mismatch paths

## Problem 7 — Rank targets and email

### My prompts

> crearte output/reflection.md

> show info in targets.json as a table that i can review. add an index to count each company


### What was lacking after my first prompt

<!-- Summarize what was lacking after the first prompt here. -->

## Problem 8 — Sales dashboard webpage

### My prompts

> build a webpage, dashboard.html, that shows your company profile, target customers, and drafted email. make the info easy to skim, human should be able to open the page and see who the seller is, targets, contact info, and emails. since there are 3 customers, rather than make 1 long page, show only 1 customer info at a time and add a toggle button to switch between customers.

> last prompt and this one is for problem 8 btw. can you check that profile, targets and emails are all in HTML itself. do not make page read json. hard code the content inside

> company profile data is wordy. don't use full sentences. make concise

> next, i want to update UX. since seller is in the space of water conservation, make the website water theme. i want waves dynamicaly moving as i scroll down the page. when i click on any buttons, i want a splash effect

> when i click buton, i want the water droplet logo to pop up, not just circles

> i want something like this. make the effect bigger

> turn my mouse into nemo, the fish


### What was lacking after my first prompt

<!-- Summarize what was lacking after the first prompt here. -->

## Problem 9 — Submit zip

### My prompts

> Put everything in a folder named hw2, zip it as hw2.zip, and upload to Canvas. Make sure you don't put your .env file in the zip. Include .env.example with PORTKEY_API_KEY / model settings shown as placeholders only (no real secrets). Expected layout includes AI_prompts.md, HARNESS.md, requirements.txt, .env.example, sales_agent.py, dashboard.html, assets, prompts, and output.


### What was lacking after my first prompt

<!-- Summarize what was lacking after the first prompt here. -->
### Follow-up prompt

> Continue the packaging work: rebuild the submission ZIP cleanly, exclude secrets and cache files, and verify the archive.

### Follow-up prompt

> There are two dashboard.html files inside hw2. Compare their code and tell me the difference.

### Follow-up prompt

> What is the difference between sales_agent.py and sales-agent.py?

### Follow-up prompt

> Zip up hw2 again.
