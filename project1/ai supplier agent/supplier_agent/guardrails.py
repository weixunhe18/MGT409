"""Deterministic guardrails. No LLM in this file.

These checks are plain code on purpose: a language model can be talked out of a
rule, a regex cannot. LLM reviewers elsewhere may only make outcomes STRICTER.

- Sender check: allowlist, blocklist, lookalike-domain / display-name impersonation
- Prompt-injection scan: hidden HTML text, instruction phrases, invisible unicode, exfil asks
- Topic detection: price / quantity / date / PO / payment / drawing (hard), engineering change (soft)
- Question extraction from supplier email bodies
- Outbound compliance: recipients locked, no attachments/links, no money/qty/date commitments,
  no confidential terms, no echoed injection text
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from .knowledge import MONEY_RE, tokenize

HARD_TOPICS = ("price", "quantity", "date", "po", "payment", "drawing", "identity")
TOPIC_LABELS = {
    "price": "pricing",
    "quantity": "quantities",
    "date": "timing",
    "po": "purchase orders",
    "payment": "payment",
    "drawing": "drawings",
    "identity": "who you are talking to",
    "engineering_change": "a proposed spec or part change",
}

_ADDR_RE = re.compile(r"^\s*(?:\"?(?P<name>[^\"<]*?)\"?\s*)?<\s*(?P<addr>[^<>\s]+@[^<>\s]+)\s*>\s*$")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


# --------------------------------------------------------------------- senders
def parse_address(value: str) -> tuple[str, str]:
    """'Kevin Zhang <kevin@x.com>' -> ('Kevin Zhang', 'kevin@x.com')."""
    value = (value or "").strip()
    m = _ADDR_RE.match(value)
    if m:
        return (m.group("name") or "").strip(), m.group("addr").strip().lower()
    m2 = EMAIL_RE.search(value)
    return "", (m2.group(0).lower() if m2 else value.lower())


def domain_of(address: str) -> str:
    return address.rsplit("@", 1)[-1].lower() if "@" in address else ""


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


_HOMOGLYPHS = (("rn", "m"), ("vv", "w"), ("cl", "d"), ("0", "o"), ("1", "l"), ("|", "l"), ("5", "s"))


def _skeleton(domain: str) -> str:
    s = domain.lower()
    for fake, real in _HOMOGLYPHS:
        s = s.replace(fake, real)
    return s


def _list_match(address: str, entries: list[str]) -> str | None:
    dom = domain_of(address)
    for entry in entries:
        e = str(entry).strip().lower()
        if not e:
            continue
        if e.startswith("@") and dom == e[1:]:
            return entry
        if "@" not in e and dom == e:
            return entry
        if e == address:
            return entry
    return None


def check_sender(from_header: str, policy: dict, extra_allow: list | None = None,
                 extra_block: list | None = None) -> dict:
    """Return {status, reason, address, name, contact}.

    status: allowed | blocked | impersonation | unknown
    """
    name, address = parse_address(from_header)
    contacts = list(policy.get("allowlist", [])) + [
        {"address": a, "name": "", "company": "added by Wei", "role": ""} for a in (extra_allow or [])
    ]
    blocklist = list(policy.get("blocklist", [])) + list(extra_block or [])
    base = {"address": address, "name": name, "contact": None}

    hit = _list_match(address, blocklist)
    if hit:
        return {**base, "status": "blocked", "reason": f"Sender matches blocklist entry '{hit}'."}

    allow_entries = [c.get("address", "") if isinstance(c, dict) else str(c) for c in contacts]
    hit = _list_match(address, allow_entries)
    if hit:
        contact = next((c for c in contacts if isinstance(c, dict) and c.get("address") == hit), None)
        return {**base, "status": "allowed", "reason": "Sender is on the allowlist.", "contact": contact}

    # Impersonation: lookalike domain of a trusted supplier, or a trusted name on a strange address.
    dom = domain_of(address)
    trusted_domains = sorted({domain_of(a) if "@" in a.strip("@") else a.lstrip("@").lower()
                              for a in allow_entries if a})
    for trusted in trusted_domains:
        if not trusted or dom == trusted:
            continue
        if _skeleton(dom) == _skeleton(trusted) or levenshtein(dom, trusted) <= 2:
            return {**base, "status": "impersonation",
                    "reason": f"Lookalike domain: '{dom}' imitates trusted supplier domain '{trusted}'."}
    if name:
        for c in contacts:
            if isinstance(c, dict) and c.get("name") and c["name"].strip().lower() == name.lower():
                return {**base, "status": "impersonation",
                        "reason": f"Display name '{name}' belongs to a trusted contact, but the address "
                                  f"'{address}' is not theirs."}
    return {**base, "status": "unknown", "reason": "Sender is not on the allowlist."}


# ------------------------------------------------------------------- HTML scan
_HIDDEN_STYLE_RES = [
    re.compile(r"display:none"),
    re.compile(r"visibility:hidden"),
    re.compile(r"opacity:0(?:\.0+)?(?:;|$)"),
    re.compile(r"font-size:0(?:\.\d+)?(?:px|pt|em|rem|%)?(?:;|$)"),
    re.compile(r"font-size:[01](?:\.\d+)?(?:px|pt)(?:;|$)"),
    re.compile(r"(?:^|;)color:(?:#fff(?:fff)?|white|rgba?\(255,255,255)(?:;|$|,|\))"),
    re.compile(r"(?:max-)?height:0(?:px)?(?:;|$)"),
    re.compile(r"text-indent:-\d{3,}"),
    re.compile(r"(?:left|top):-\d{3,}"),
]
_VOID_TAGS = {"br", "img", "hr", "meta", "link", "input", "area", "base", "col", "embed", "param",
              "source", "track", "wbr"}


def _is_hidden(tag: str, attrs: dict) -> bool:
    if "hidden" in attrs or str(attrs.get("aria-hidden", "")).lower() == "true":
        return True
    style = str(attrs.get("style") or "").lower().replace(" ", "")
    return any(r.search(style) for r in _HIDDEN_STYLE_RES)


class _HTMLScanner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, str]] = []  # (tag, mode) mode: visible | hidden | ignore
        self.visible: list[str] = []
        self.hidden: list[str] = []
        self.comments: list[str] = []
        self.scripts = 0

    def _mode(self) -> str:
        return self.stack[-1][1] if self.stack else "visible"

    def handle_starttag(self, tag, attrs):
        if tag in _VOID_TAGS:
            if tag == "br" and self._mode() == "visible":
                self.visible.append("\n")
            return
        parent = self._mode()
        if tag == "style":
            mode = "ignore"
        elif tag == "script":
            self.scripts += 1
            mode = "hidden"
        elif parent == "hidden" or _is_hidden(tag, dict(attrs)):
            mode = "hidden"
        elif parent == "ignore":
            mode = "ignore"
        else:
            mode = "visible"
        self.stack.append((tag, mode))
        if tag in ("p", "div", "tr", "li") and mode == "visible":
            self.visible.append("\n")

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if not data.strip():
            return
        mode = self._mode()
        if mode == "visible":
            self.visible.append(data)
        elif mode == "hidden":
            self.hidden.append(data.strip())

    def handle_comment(self, data):
        if data.strip():
            self.comments.append(data.strip())


def scan_html(html: str) -> dict:
    scanner = _HTMLScanner()
    try:
        scanner.feed(html or "")
        scanner.close()
    except Exception:  # malformed HTML must never crash the pipeline
        pass
    visible = re.sub(r"[ \t]+", " ", "".join(scanner.visible))
    visible = re.sub(r"\n\s*\n+", "\n\n", visible).strip()
    return {
        "visible_text": visible,
        "hidden_text": " ".join(scanner.hidden).strip(),
        "comments": " ".join(scanner.comments).strip(),
        "scripts": scanner.scripts,
    }


# ------------------------------------------------------------ injection scan
_STRONG = [
    ("override_instructions", re.compile(
        r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|any|your|the)\b"
        r"[^.\n]{0,20}\b(instructions?|rules|polic(y|ies)|prompts?|guardrails|guidelines)", re.I)),
    ("system_prompt_language", re.compile(r"\b(system|developer)\s+(prompt|message|notice|instructions?)\b", re.I)),
    ("addresses_the_ai", re.compile(
        r"\b(for|to|attention)\s+(the\s+)?(ai|llm|gpt|automated)\s+(assistant|agent|model|system)s?\b"
        r"|\byou\s+are\s+(now\s+)?(an?\s+|the\s+)?(ai|assistant|agent|language\s+model|llm|chatbot)\b", re.I)),
    ("chat_template_tokens", re.compile(r"<\|?(im_start|im_end|system|endoftext)\|?>|\[/?(inst|sys)\]", re.I)),
    ("jailbreak_terms", re.compile(r"\b(jailbreak|dan\s+mode|developer\s+mode)\b", re.I)),
]
_MEDIUM = [
    ("fake_authorization", re.compile(
        r"\bpre-?authori[sz]ed\b|\b(has|have)\s+(already\s+)?authori[sz]ed\s+you\b", re.I)),
    ("secrecy_request", re.compile(
        r"\bdo\s+not\s+(mention|reveal|tell|disclose|inform)\b[^.\n]{0,40}\b(this|wei|anyone|user|human|note|notice|instructions?)",
        re.I)),
    ("prompt_extraction", re.compile(
        r"\b(reveal|print|show|output|repeat)\b[^.\n]{0,30}\b(your|the)\s+(instructions|prompt|rules|policy|configuration)",
        re.I)),
    ("new_instructions", re.compile(r"\bnew\s+instructions?\b", re.I)),
]
_EXFIL = [
    ("asks_for_confidential", re.compile(r"\b(target|internal)\s+(cost|price|pricing|margin|budget)\b", re.I)),
    ("asks_for_everything", re.compile(
        r"\b(full|complete|entire|whole)\s+(?:\S+\s+){0,2}(spec|specification|documentation|bom|drawing\s+package|design\s+files?)\b",
        re.I)),
]
_INVISIBLE_RE = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩\U000e0000-\U000e007f]")
_BASE64_RE = re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")


def _find(patterns, text):
    hits = []
    for name, regex in patterns:
        m = regex.search(text)
        if m:
            hits.append((name, m.group(0)))
    return hits


def scan_injection(text: str, html: str | None, sender_domain: str, own_domain: str = "",
                   suspicious_threshold: float = 0.4, injection_threshold: float = 1.0) -> dict:
    """Score how likely an email is trying to instruct the AI. Higher = worse."""
    html_info = scan_html(html) if html else {"visible_text": "", "hidden_text": "", "comments": "", "scripts": 0}
    hidden = " ".join(x for x in (html_info["hidden_text"], html_info["comments"]) if x)
    combined = "\n".join(x for x in (text or "", html_info["visible_text"], hidden) if x)
    signals: list[dict] = []

    def add(signal, weight, evidence):
        signals.append({"signal": signal, "weight": weight, "evidence": str(evidence)[:200]})

    if len(hidden.split()) >= 6:
        add("hidden_text", 0.5, hidden)
    if html_info["scripts"]:
        add("script_tag", 0.3, f"{html_info['scripts']} <script> element(s)")
    for name, ev in _find(_STRONG, combined):
        add(name, 1.0, ev)
    for name, ev in _find(_MEDIUM, combined):
        add(name, 0.6, ev)
    for name, ev in _find(_EXFIL, combined):
        add(name, 0.4, ev)
    if hidden and (_find(_STRONG, hidden) or _find(_MEDIUM, hidden)):
        add("instructions_inside_hidden_text", 1.0, hidden)
    invisible = [c for c in _INVISIBLE_RE.findall(combined)]
    if invisible:
        add("invisible_unicode", 0.6, f"{len(invisible)} zero-width/bidi/tag character(s)")
    if _BASE64_RE.search(combined):
        add("encoded_blob", 0.3, "long base64-like string")
    trusted = {d for d in (sender_domain, own_domain) if d}
    outside = sorted({a for a in EMAIL_RE.findall(combined) if domain_of(a.lower()) not in trusted})
    if outside:
        add("third_party_address", 0.4, ", ".join(outside[:3]))

    score = round(sum(s["weight"] for s in signals), 2)
    verdict = "injection" if score >= injection_threshold else "suspicious" if score >= suspicious_threshold else "clean"
    return {
        "score": score,
        "verdict": verdict,
        "signals": signals,
        "hidden_text": hidden[:1000],
        "visible_html_text": html_info["visible_text"],
    }


# ----------------------------------------------------------------- topics
_MONTHS = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_WEEKDAYS = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
DATE_RE = re.compile(
    rf"\b{_MONTHS}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?\b"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTHS}\b"
    r"|\b20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\b"
    r"|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"
    rf"|\b(?:by|before|until|on)\s+(?:this\s+|next\s+)?(?:{_WEEKDAYS}|today|tonight|tomorrow|end\s+of\s+(?:the\s+)?(?:day|week|month))\b"
    r"|\b(?:today|tonight|tomorrow|next\s+week|next\s+month|this\s+week|asap)\b",
    re.I,
)
QTY_RE = re.compile(r"\b\d[\d,.]*\s?k?\s?(?:pcs|pc|pieces|units|sets|kpcs)\b|\b\d+k\b", re.I)

TOPIC_PATTERNS: dict[str, re.Pattern] = {
    "price": re.compile(
        r"\b(price|prices|pricing|cost|costs|quote|quotes|quoted|quotation|quotations|discount|unit\s+price|fob|exw|ddp|cif)\b",
        re.I),
    "quantity": re.compile(r"\b(moq|quantity|quantities|qty|forecast|volume|volumes)\b", re.I),
    "date": re.compile(
        r"\b(deadline|due\s+date|delivery\s+date|ship(?:ping)?\s+date|etd|eta|build\s+date|launch\s+date|schedule|timeline|dvt|pvt|evt)\b",
        re.I),
    "po": re.compile(
        r"\bpo\b|\bp\.o\.|\bpurchase\s+orders?\b|\border\s+confirmation\b|\bplace\s+(?:an?\s+|the\s+)?orders?\b",
        re.I),
    "payment": re.compile(
        r"\b(payment|deposit|invoice|bank|account\s+number|swift|iban|wire|t/t|remit|remittance|pay)\b", re.I),
    "drawing": re.compile(
        r"\b(drawings?|step\s+files?|stp|igs|iges|dwg|dxf|gerbers?|cad|3d\s+(?:data|files?|model)|2d|schematics?|firmware|source\s+code)\b",
        re.I),
    # "Are you a bot?" The persona never answers this itself (never claims to be human): Wei decides.
    "identity": re.compile(
        r"\b(?:are|r)\s+(?:you|u)\s+(?:an?\s+)?(?:real\s+)?(?:bot|robot|ai|a\.i\.|machine|human|person|chatbot|automated)\b"
        r"|\b(?:am\s+i|are\s+we)\s+(?:talking|speaking|chatting|writing)\s+(?:to|with)\s+(?:an?\s+)?(?:real\s+)?"
        r"(?:bot|robot|ai|machine|human|person)\b"
        r"|\bis\s+this\s+(?:an?\s+)?(?:bot|robot|ai|automated|auto-?generated)\b|\bchatgpt\b",
        re.I),
    "engineering_change": re.compile(
        r"\b(alternative|alternate|substitut\w*|equivalent|replacement|deviation|waiver|"
        r"change\s+(?:the\s+)?(?:material|spec|design|supplier|process)|"
        # Proposals phrased as questions ("can we use P20 steel?", "welding instead of adhesive"), matching the live manager.
        r"(?:can|could|may)\s+we\s+use|instead\s+of)\b",
        re.I),
}


def detect_topics(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}

    def note(topic, evidence):
        bucket = found.setdefault(topic, [])
        if evidence not in bucket and len(bucket) < 4:
            bucket.append(evidence)

    for topic, regex in TOPIC_PATTERNS.items():
        for m in regex.finditer(text or ""):
            note(topic, m.group(0))
    for m in MONEY_RE.finditer(text or ""):
        note("price", m.group(0))
    for m in QTY_RE.finditer(text or ""):
        note("quantity", m.group(0))
    for m in DATE_RE.finditer(text or ""):
        note("date", m.group(0))
    return found


def hard_topics_in(text: str) -> list[str]:
    topics = detect_topics(text)
    return [t for t in HARD_TOPICS if t in topics]


# --------------------------------------------------------------- questions
_QUOTE_MARKERS = [
    re.compile(r"^On .{0,200}wrote:\s*$", re.I),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}", re.I),
    re.compile(r"^From:\s", re.I),
    re.compile(r"^_{10,}$"),
    re.compile(r"^(发件人|寄件者)[:：]"),
]
_NUMBERED_RE = re.compile(r"^\s*(?:\(?\d{1,2}[.)]|[-*•])\s+(?P<item>.+)$")
_REQUEST_RE = re.compile(
    r"\b(please|pls|kindly)\b.*\b(confirm|share|send|advise|provide|check|let\s+(?:us|me)\s+know|tell)\b", re.I)
_SENT_SPLIT = re.compile(r"(?<=[.?!])\s+")
_GREETING_RE = re.compile(r"^(hi|hello|dear|good\s+(morning|afternoon|evening))\b", re.I)
_SIGNOFF_RE = re.compile(
    r"^(best\s+regards|kind\s+regards|regards|thanks|thank\s+you|many\s+thanks|br|best|cheers|sincerely)\b[\s,!.]*$",
    re.I)


def strip_quoted(body: str) -> str:
    out = []
    for line in (body or "").splitlines():
        s = line.strip()
        if any(p.match(s) for p in _QUOTE_MARKERS):
            break
        if s.startswith(">"):
            continue
        out.append(line)
    return "\n".join(out)


def strip_signature(body: str) -> str:
    out = []
    for line in body.splitlines():
        if _SIGNOFF_RE.match(line.strip()):
            break
        out.append(line)
    return "\n".join(out)


def extract_questions(body: str, limit: int = 10) -> list[str]:
    """Numbered items, plus sentences with '?', plus 'please confirm/share/send' requests
    (the last only when the email has no numbered list)."""
    content = strip_signature(strip_quoted(body))
    numbered: list[str] = []
    other: list[str] = []
    for line in content.splitlines():
        s = line.strip()
        if not s:
            continue
        m = _NUMBERED_RE.match(s)
        if m:
            numbered.append(m.group("item").strip())
        else:
            other.append(s)
    questions = list(numbered)
    for line in other:
        if _GREETING_RE.match(line) and len(line) < 40:
            continue
        for sentence in _SENT_SPLIT.split(line):
            s = sentence.strip()
            if not s or s.endswith(":"):
                continue
            if "?" in s or (not numbered and _REQUEST_RE.search(s)):
                if len(tokenize(s)) >= 2:
                    questions.append(s)
    return questions[:limit]


def is_auto_reply(subject: str, headers: dict | None) -> bool:
    headers = {str(k).lower(): str(v).lower() for k, v in (headers or {}).items()}
    if headers.get("auto-submitted", "no") not in ("", "no"):
        return True
    if "x-autoreply" in headers or "x-autorespond" in headers:
        return True
    return bool(re.match(r"^(automatic reply|auto(-|\s)?reply|out of (the )?office|自动回复)", (subject or "").strip(), re.I))


# ---------------------------------------------------------------- outbound
_LINK_RE = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+\.(?:com|cn|net|org|io|ly|co|me|info|biz|example)/\S*", re.I)
_ATTACH_CLAIM_RE = re.compile(r"\b(attached|attachments?|enclosed)\b", re.I)
_COMMIT_VERB_RE = re.compile(
    r"\b(accept(?:s|ed|ing)?|agree(?:s|d|ing)?|approve(?:s|d)?|approving|confirm(?:s|ed|ing)?|commit(?:s|ted|ting)?|"
    r"place(?:s|d)?|issue(?:s|d)?|guarantee(?:s|d)?|promise(?:s|d)?|authori[sz]e(?:s|d)?|book(?:s|ed)?|"
    r"reserve(?:s|d)?|go\s+ahead|proceed)\b", re.I)
_COMMIT_OBJECT_RE = re.compile(
    r"\b(price|prices|pricing|quote|quotation|offer|order|orders|po|purchase|quantity|quantities|moq|volume|forecast|"
    r"deposit|payment|invoice|date|dates|deadline|schedule|delivery|lead\s+time|build|capacity|contract|terms)\b", re.I)
_SENTENCE_RE = re.compile(r"(?:[^.!?\n]|\.(?=\d))+[.!?]?")  # don't split "3.85" into two sentences


def check_outbound(body: str, *, to: list[str], cc: list[str], attachments: list, original_sender: str,
                   sensitive_terms: list[str], shareable_text: str, signature: str = "") -> dict:
    """Deterministic compliance check on a draft reply. Any failed check blocks autonomous sending."""
    checks: list[dict] = []
    body = body or ""
    low = body.lower()
    shareable_low = (shareable_text or "").lower()

    def add(cid, label, ok, detail=""):
        checks.append({"id": cid, "label": label, "ok": bool(ok), "detail": detail})

    ok = [a.lower() for a in to] == [original_sender.lower()] and not cc
    add("recipients_locked", "Reply goes only to the original allowlisted sender", ok,
        "" if ok else f"to={to} cc={cc}")

    claim = _ATTACH_CLAIM_RE.search(body)
    add("no_attachments", "No attachments or file sharing", not attachments and not claim,
        f"draft mentions '{claim.group(0)}'" if claim else ("draft has attachments" if attachments else ""))

    link = _LINK_RE.search(body) or EMAIL_RE.search(body)
    add("no_links_or_addresses", "No links or email addresses in the body", not link,
        f"found '{link.group(0)}'" if link else "")

    money = MONEY_RE.search(body)
    add("no_prices", "No prices or money amounts", not money, f"found '{money.group(0)}'" if money else "")

    bad_qty = [m.group(0) for m in QTY_RE.finditer(body) if m.group(0).lower() not in shareable_low]
    add("no_quantities", "No order quantities (spec values excepted)", not bad_qty,
        f"found '{bad_qty[0]}'" if bad_qty else "")

    bad_dates = [m.group(0) for m in DATE_RE.finditer(body) if m.group(0).lower() not in shareable_low]
    add("no_dates", "No dates or deadlines", not bad_dates, f"found '{bad_dates[0]}'" if bad_dates else "")

    commitment = ""
    for sentence in _SENTENCE_RE.findall(body):
        if _COMMIT_VERB_RE.search(sentence) and _COMMIT_OBJECT_RE.search(sentence):
            commitment = sentence.strip()
            break
    add("no_commitment_language", "No commitment language (accept/confirm/approve + order/price/date…)",
        not commitment, f"'{commitment[:140]}'" if commitment else "")

    leaked = [t for t in sensitive_terms if t and t.lower() in low]
    add("no_confidential_terms", "No confidential terms (target cost, codename, internal dates…)", not leaked,
        f"found '{leaked[0]}'" if leaked else "")

    echoed = _find(_STRONG, body) + _find(_MEDIUM, body)
    add("no_injection_echo", "No instruction-like text copied from the supplier", not echoed,
        f"'{echoed[0][1]}'" if echoed else "")

    add("length_ok", "Reasonable length", 20 <= len(body) <= 4000, f"{len(body)} characters")

    if signature.strip():
        signed = " ".join(signature.lower().split()) in " ".join(low.split())
        add("signature", "Signed with the configured persona signature", signed,
            "" if signed else "signature missing")

    blocking = [c for c in checks if not c["ok"]]
    return {"passed": not blocking, "checks": checks, "blocking": blocking}
