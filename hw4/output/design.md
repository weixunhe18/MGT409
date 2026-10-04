# Design Changes

Two changes to how the store looks and moves, and what each is meant to earn.

---

## 1. Spirit-adaptive themes

**What I changed.** The whole site reads from CSS variables, so a theme is a swap of
values rather than a second stylesheet. Three moods in the nav bar — **1900s Heritage**
(parchment, light serif), **Game Day** (bright, heavy uppercase, bunting stripes), and
**Gameday Night** (dark, floodlight glow). Accent colours, typography weight and
background texture all change. The choice is remembered.

**Why it helps.** Picking a mood is a small act of affiliation — the shop becomes *the
visitor's*, not a catalogue they happen to be on. Night mode matters more than it
sounds: a lot of browsing happens in the evening, and a dark page is simply easier to
stay on, which buys longer sessions. Game Day aligns the store with the weekend a
shopper is actually buying for. And because the choice persists, a returning customer
lands in the store they already set up, which is the cheapest kind of familiarity.

**What it cost.** About 0.2 KB of extra gzipped CSS. No component knows a theme exists,
so adding a fourth is one block of variables.

---

## 2. Motion loops on hero products

**What I changed.** Three hero products now have a 2.4-second seamless loop — a slow
camera push-in on the crest or graphic — alongside the still. Grid cards play on hover;
the product page waits for a deliberate *See in Motion*.

**Why it helps.** The hardest thing about selling clothing online is that nobody can
feel it. A flat photo flattens exactly the things that justify $68 for a hoodie:
texture, weight, the depth of an embroidered crest. Motion restores some of that, and
the less a shopper has to guess, the less they abandon — and the fewer garments come
back as returns, which is where apparel margin dies. Hovering also keeps someone on a
tile a few seconds longer, which is usually the difference between scrolling past and
clicking in.

**What it cost.** Nothing, unless asked for. No video element exists in the page until
a shopper wants one — verified at **zero video elements across 102 cards**. All six
files together are 644 KB, and the largest clip is 11% of the 1.5 MB budget. That
restraint is the point: page speed is itself a conversion factor, so a gallery feature
that slowed the grid down would cost more than it earned.

---

**Worth being straight about:** the loops are camera parallax generated from the
existing flat photos, not footage of models on campus. They add depth and draw the eye,
but they do not show drape or how a garment moves on a body — which is the part that
would actually move the returns number. Real footage drops into the same slots with no
code change.
