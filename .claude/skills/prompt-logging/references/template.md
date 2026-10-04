# AI_prompts.md template

Plain markdown only. No inline HTML, no colored `<span>` tags — markdown has no color
primitive, most renderers strip the `style` attribute anyway, and the markup shows up as
noise if a grader opens the raw file. Blockquotes and bold carry the structure fine.

## Header

```markdown
# AI Prompts Log — <Homework title from the course page>

MGT409 · <Student name>

This file logs what I typed to my vibe coder while working through <HWN>, one section
per problem. Each section records my first prompt in my own words, and any follow-up
prompts I needed when the first one did not get the job done.

---
```

## One section per problem

Repeat for every problem, separated by `---`:

```markdown
## Problem <N> — <Title> (<P> points)

**First prompt:**

> _(to be filled in when I start this problem)_

**Follow-up prompt:**

> _(to be filled in if needed)_

**What was lacking after the first prompt:**

> _(one sentence)_
```

## A filled-in section

The user's words are quoted exactly as typed — lowercase, terse, unedited:

```markdown
## Problem 1 — Vibe coder prompts (6 points)

**First prompt:**

> let's start by setting up AI_prompts.md. keep this as a log for vibe coder.
>
> create 10 sections. for each section, include placeholder for problem number, title,
> prompts i entered first, and leave space for me to add follow prompts i added if my
> first prompt did not get the job done.

**Follow-up prompt:**

> can you add colors to text that i wrote so it pops out more in md file

> revert, remove html stuff. no visual effect and adds fluff.

**What was lacking after the first prompt:**

> Nothing was wrong with the first result — I tried adding color to make my own words
> stand out, but markdown has no native color syntax and the inline HTML it required
> rendered inconsistently, so I reverted to plain text.
```

Note what this example does: it keeps both follow-ups including the one that got reverted,
and the reflection describes the student's own reasoning rather than grading the assistant.

## Formatting details

- Multi-paragraph prompts: separate paragraphs with a bare `>` line so the blockquote holds.
- Multiple distinct follow-ups: separate blockquotes with a blank line between, in the order
  they were sent. Don't merge them into one — the sequence is part of the record.
- First prompt worked: put `> _(none needed)_` under follow-up and `> _(n/a — first prompt
  was sufficient)_` under what was lacking.
- Leave untouched problems as placeholders. Empty scaffolding is honest; pre-filled
  speculation is not.
