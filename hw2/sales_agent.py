"""Research one potential Nexa customer with PydanticAI and Playwright.

Usage:
    python sales-agent.py "Profile https://example.com as a potential Nexa customer"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urljoin, urlparse

from dotenv import load_dotenv
from openai import AsyncOpenAI
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider


PROJECT_ROOT = Path(__file__).resolve().parent
ROOT_ENV = PROJECT_ROOT.parent / ".env"
SYSTEM_PROMPT_PATH = PROJECT_ROOT / "prompts" / "sales_agent.md"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
MODEL_NAME = "gpt-5.6-terra"
MAX_PAGES = 20
MAX_PDFS = 8
PAGE_KEYWORDS = (
    "about", "company", "operation", "facility", "facilities", "sustain",
    "water", "infrastructure", "project", "news", "leadership", "team",
    "investor", "report", "annual", "contact", "location", "locations",
    "property", "properties", "portfolio", "hotel", "room", "rooms",
    "building", "square", "foot", "career", "esg", "fact",
)
APPROVED_EXTERNAL_HOSTS = ("gcs-web.com",)


class Evidence(BaseModel):
    evidence: str
    sources: list[str] = Field(default_factory=list)
    source_quote: str | None = None


class NeedEvidence(BaseModel):
    type: str
    evidence: str
    sources: list[str] = Field(default_factory=list)


class DecisionMaker(BaseModel):
    role_or_person: str
    context: str = ""
    sources: list[str] = Field(default_factory=list)


class TriggerEvent(BaseModel):
    event: str
    sources: list[str] = Field(default_factory=list)


class FitEvidence(BaseModel):
    claim: str
    sources: list[str] = Field(default_factory=list)


class Estimate(BaseModel):
    value: str | None = None
    basis: str
    confidence: Literal["high", "medium", "low", "unknown"] = "unknown"
    sources: list[str] = Field(default_factory=list)


class NexaFit(BaseModel):
    assessment: str
    evidence: list[FitEvidence] = Field(default_factory=list)


class CompanyProfile(BaseModel):
    company_name: str | None = None
    website: str
    headquarters: Evidence | None = None
    operating_locations: list[Evidence] = Field(default_factory=list)
    property_footprint: list[Evidence] = Field(default_factory=list)
    estimated_building_size: Estimate | None = None
    estimated_room_count: Estimate | None = None
    industry: list[Evidence] = Field(default_factory=list)
    water_infrastructure: list[Evidence] = Field(default_factory=list)
    water_intensive_or_complex_assets: list[Evidence] = Field(default_factory=list)
    needs_and_risks: list[NeedEvidence] = Field(default_factory=list)
    current_monitoring_and_asset_tools: list[Evidence] = Field(default_factory=list)
    decision_makers_and_departments: list[DecisionMaker] = Field(default_factory=list)
    trigger_events: list[TriggerEvent] = Field(default_factory=list)
    nexa_fit: NexaFit
    sales_hypotheses: list[FitEvidence] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    research_quality: dict[str, Any] = Field(default_factory=dict)


class Contact(BaseModel):
    email: str | None = None
    contact_type: Literal["role", "general", "named", "unknown"] = "unknown"
    source: str | None = None


class TargetCompany(BaseModel):
    index: int = 0
    company_name: str
    website: str
    headquarters: str | None = None
    operating_locations: list[str] = Field(default_factory=list)
    industry: str | None = None
    business_context: list[FitEvidence] = Field(default_factory=list)
    water_or_facility_signals: list[dict[str, Any]] = Field(default_factory=list)
    why_seller_fit: str
    contact: Contact
    unknowns: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class DraftEmail(BaseModel):
    target_company: str
    to: str | None = None
    subject: str
    body: str
    personalization_evidence: list[FitEvidence] = Field(default_factory=list)
    call_to_action: str
    status: Literal["draft_only"] = "draft_only"


class CustomerFindingResult(BaseModel):
    targets: list[TargetCompany] = Field(default_factory=list)
    emails: list[DraftEmail] = Field(default_factory=list)


class AuditRun:
    """Collect operational audit data without recording hidden chain-of-thought."""

    def __init__(self, query: str, output_dir: Path) -> None:
        self.started_at = utc_now()
        self.query = query
        self.output_dir = output_dir
        self.events: list[dict[str, Any]] = []
        self.thoughts: list[str] = []

    def note(self, text: str) -> None:
        self.thoughts.append(f"{utc_now()}: {text}")

    def tool_call(self, name: str, arguments: dict[str, Any], summary: str) -> None:
        self.events.append(
            {
                "name": name,
                "arguments": arguments,
                "results_summary": summary,
                "when_run": utc_now(),
            }
        )

    def finish(self, status: str, error: str | None = None) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / "audit_log.json"
        existing: list[dict[str, Any]] = []
        if path.exists():
            try:
                existing = json.loads(path.read_text())
            except json.JSONDecodeError:
                existing = []
        existing.append(
            {
                "run_started_at": self.started_at,
                "run_stopped_at": utc_now(),
                "status": status,
                "query": self.query,
                "thoughts": self.thoughts,
                "tool_calls": self.events,
                "error": error,
            }
        )
        path.write_text(json.dumps(existing, indent=2) + "\n")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_url(query: str) -> str:
    match = re.search(r"https?://[^\s)]+", query)
    if not match:
        raise ValueError("Include the target company's public website URL in the query.")
    return match.group(0).rstrip(".,;:]")


def url_score(url: str) -> int:
    lowered = url.lower()
    return sum(3 if keyword in lowered else 0 for keyword in PAGE_KEYWORDS)


def is_allowed_host(hostname: str, starting_host: str) -> bool:
    """Allow the target host plus explicitly approved investor/filing hosts."""
    host = hostname.lower().split(":", 1)[0]
    start = starting_host.lower().split(":", 1)[0]
    return (
        host == start
        or host.endswith("." + start)
        or any(host == approved or host.endswith("." + approved) for approved in APPROVED_EXTERNAL_HOSTS)
    )


async def crawl_website(url: str, audit: AuditRun, max_pages: int = MAX_PAGES) -> dict[str, Any]:
    """Discover and crawl high-value first-party pages with Playwright."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid website URL: {url}")

    pages: list[dict[str, str]] = []
    documents: list[dict[str, str]] = []
    visited: set[str] = set()
    queue = [url]
    audit.note("Playwright is discovering the homepage, sitemap, prioritized links, and first-party documents.")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            # Sitemap discovery is useful when important pages are not linked in the homepage navigation.
            for sitemap_url in (urljoin(url, "/sitemap.xml"), urljoin(url, "/sitemap_index.xml")):
                try:
                    response = await page.goto(sitemap_url, wait_until="domcontentloaded", timeout=15_000)
                    body = await page.locator("body").inner_text(timeout=5_000)
                    sitemap_links = re.findall(r"<loc>\s*(https?://[^<\s]+)", body, flags=re.IGNORECASE)
                    if not sitemap_links:
                        sitemap_links = re.findall(r"https?://[^\s<>]+", body)
                    for sitemap_link in sitemap_links:
                        if is_allowed_host(urlparse(sitemap_link).netloc, parsed.netloc):
                            queue.append(sitemap_link)
                    audit.tool_call("discover_sitemap", {"url": sitemap_url}, f"Found {len(sitemap_links)} URL candidate(s).")
                    if response and response.status < 400 and sitemap_links:
                        break
                except Exception:
                    continue

            while queue and len(pages) < max_pages:
                queue.sort(key=url_score, reverse=True)
                current = queue.pop(0)
                normalized = current.split("#", 1)[0]
                if normalized in visited:
                    continue
                visited.add(normalized)
                try:
                    response = await page.goto(normalized, wait_until="domcontentloaded", timeout=30_000)
                    await page.wait_for_timeout(500)
                    content_type = (response.headers.get("content-type", "") if response else "").lower()
                    is_pdf = "application/pdf" in content_type or normalized.lower().split("?", 1)[0].endswith(".pdf")
                    if is_pdf:
                        if response and len(documents) < MAX_PDFS:
                            try:
                                from pypdf import PdfReader
                                reader = PdfReader(BytesIO(await response.body()))
                                pdf_text = "\n".join((p.extract_text() or "") for p in reader.pages)
                                documents.append({"url": page.url, "text": pdf_text[:30_000]})
                                audit.tool_call("extract_pdf", {"url": normalized, "content_type": content_type}, f"Extracted text from {len(reader.pages)} PDF page(s).")
                            except Exception as exc:
                                audit.note(f"A first-party PDF was found but could not be extracted: {type(exc).__name__}.")
                        continue
                    text = await page.locator("body").inner_text(timeout=10_000)
                    links = await page.locator("a[href]").evaluate_all(
                        "els => els.map(el => el.href)"
                    )
                    page_status = response.status if response else None
                    pages.append(
                        {
                            "url": page.url,
                            "status": str(page_status if page_status is not None else "unknown"),
                            "text": text[:30_000],
                        }
                    )
                    if page_status and page_status >= 400:
                        audit.note(f"Access denied or HTTP error on {normalized}: HTTP {page_status}.")
                        audit.tool_call("crawl_page", {"url": normalized, "status": page_status}, f"Page returned HTTP {page_status}; retained the error text and did not treat it as company evidence.")
                    else:
                        audit.tool_call("crawl_page", {"url": normalized, "status": page_status}, f"Collected visible text from {page.url} ({len(text)} characters).")
                    for link in links:
                        link_url = urljoin(page.url, link).split("#", 1)[0]
                        if is_allowed_host(urlparse(link_url).netloc, parsed.netloc) and link_url not in visited:
                            queue.append(link_url)
                except Exception as exc:  # keep other public pages crawlable
                    audit.note(f"A page could not be read ({normalized}): {type(exc).__name__}.")
        finally:
            await browser.close()

    summary = f"Collected {len(pages)} HTML page(s), {len(documents)} PDF(s); {len(visited)} URL(s) attempted."
    audit.tool_call("crawl_website", {"url": url, "max_pages": max_pages, "keywords": PAGE_KEYWORDS}, summary)
    if not pages:
        raise RuntimeError("Playwright could not retrieve any page from the supplied website.")
    return {"start_url": url, "pages": pages, "documents": documents, "research_quality": {"pages_crawled": len(pages), "pdfs_extracted": len(documents), "urls_attempted": len(visited)}}


def make_agent(crawl_data: dict[str, Any], audit: AuditRun) -> Agent[None, CompanyProfile]:
    load_dotenv(ROOT_ENV)
    import os

    api_key = os.environ.get("PORTKEY_API_KEY") or os.environ.get("portkey_api_key")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is missing from the root .env file.")

    instructions = SYSTEM_PROMPT_PATH.read_text()
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-provider": "openai"},
    )
    provider = OpenAIProvider(openai_client=client)
    model = OpenAIResponsesModel(MODEL_NAME, provider=provider)

    agent = Agent(
        model,
        system_prompt=instructions,
        output_type=CompanyProfile,
        retries=2,
        name="nexa-sales-analyst",
    )

    @agent.tool
    async def website_research(ctx: RunContext[None]) -> str:
        """Return the Playwright research collected for the requested company website."""
        audit.note("The model requested the required website research tool.")
        return json.dumps(crawl_data, ensure_ascii=False)

    return agent


async def search_public_web(search_query: str, audit: AuditRun, max_results: int = 10) -> list[dict[str, str]]:
    """Search public results; candidate facts must still be verified on each official site."""
    results: list[dict[str, str]] = []
    search_url = "https://www.bing.com/search?q=" + quote(search_query)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            response = await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
            links = await page.locator("li.b_algo h2 a").evaluate_all(
                "els => els.map(el => ({title: el.innerText, url: el.href}))"
            )
            for item in links[:max_results]:
                if item.get("url", "").startswith(("http://", "https://")):
                    results.append({"title": item.get("title", ""), "url": item["url"]})
        except Exception as exc:
            audit.note(f"Public search failed: {type(exc).__name__}.")
        finally:
            await browser.close()
    audit.tool_call("search_public_web", {"query": search_query, "max_results": max_results}, f"Found {len(results)} public result(s).")
    return results


def make_customer_agent(seller_brief: str, company_profile: str, audit: AuditRun) -> Agent[None, CustomerFindingResult]:
    load_dotenv(ROOT_ENV)
    import os

    api_key = os.environ.get("PORTKEY_API_KEY") or os.environ.get("portkey_api_key")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is missing from the root .env file.")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-provider": "openai"},
    )
    model = OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
    extra_instructions = f"""
You are now running the customer-finding workflow from the system prompt.

SELLER BRIEF:
{seller_brief}

COMPANY PROFILE:
{company_profile}

You must call search_public_web to discover candidates, then call research_company_website for the official website of each serious candidate. Do not qualify a candidate from search-result snippets alone. Keep only good fits for the seller. Draft emails only; never send anything.
"""
    agent = Agent(
        model,
        system_prompt=SYSTEM_PROMPT_PATH.read_text() + "\n" + extra_instructions,
        output_type=CustomerFindingResult,
        retries=2,
        name="nexa-customer-finder",
    )

    @agent.tool
    async def search_public_web_tool(ctx: RunContext[None], search_query: str) -> str:
        """Search public web results for possible customer companies."""
        audit.note(f"Searching publicly for customer candidates: {search_query}")
        return json.dumps(await search_public_web(search_query, audit), ensure_ascii=False)

    @agent.tool
    async def research_company_website(ctx: RunContext[None], url: str) -> str:
        """Crawl and return evidence from a candidate's official website."""
        audit.note(f"Researching an official candidate website: {url}")
        try:
            data = await crawl_website(url, audit, max_pages=8)
            return json.dumps(data, ensure_ascii=False)
        except Exception as exc:
            audit.note(f"Candidate website research failed for {url}: {type(exc).__name__}.")
            return json.dumps({"url": url, "access_status": "failed", "error": str(exc)})

    return agent


def print_table(profile: CompanyProfile) -> None:
    rows = [
        ("Company", profile.company_name or "Unknown"),
        ("Website", profile.website),
        ("Headquarters", profile.headquarters.evidence if profile.headquarters else "Unknown"),
        ("Property footprint", "; ".join(item.evidence for item in profile.property_footprint) or "Unknown"),
        ("Building size", profile.estimated_building_size.value if profile.estimated_building_size and profile.estimated_building_size.value else "Unknown"),
        ("Room count", profile.estimated_room_count.value if profile.estimated_room_count and profile.estimated_room_count.value else "Unknown"),
        ("Industry", "; ".join(item.evidence for item in profile.industry) or "Unknown"),
        ("Water infrastructure", "; ".join(item.evidence for item in profile.water_infrastructure) or "Unknown"),
        ("Needs / risks", "; ".join(item.evidence for item in profile.needs_and_risks) or "Unknown"),
        ("Nexa fit", profile.nexa_fit.assessment),
        ("Unknowns", "; ".join(profile.unknowns) or "None recorded"),
    ]
    width = max(len(label) for label, _ in rows)
    print("\nCompany profile\n")
    for label, value in rows:
        print(f"| {label:<{width}} | {value} |")


def write_targets_review(targets: list[TargetCompany], path: Path) -> None:
    """Write a compact human-review table alongside the machine-readable JSON."""
    def clean(value: str) -> str:
        return " ".join(value.replace("|", "\\|").split())

    lines = [
        "# Target Review",
        "",
        "| # | Company | Industry | Website | Contact email | Why it may fit |",
        "|---:|---|---|---|---|---|",
    ]
    for target in targets:
        lines.append(
            f"| {target.index} | {clean(target.company_name)} | {clean(target.industry or 'Unknown')} | "
            f"[{clean(target.website)}]({target.website}) | {clean(target.contact.email or 'None found')} | "
            f"{clean(target.why_seller_fit)} |"
        )
    path.write_text("\n".join(lines) + "\n")


async def run(query: str, output_dir: Path) -> CompanyProfile:
    audit = AuditRun(query, output_dir)
    try:
        url = extract_url(query)
        audit.note(f"Parsed target website from the input query: {url}")
        crawl_data = await crawl_website(url, audit)
        agent = make_agent(crawl_data, audit)
        audit.note("Running the PydanticAI sales analyst against the crawler evidence.")
        result = await agent.run(query)
        profile = result.output
        profile_json = profile.model_dump_json(indent=2) + "\n"
        (output_dir / "company_profile.json").write_text(profile_json)
        requested_profile_path = PROJECT_ROOT / "assets" / "company_profile.json"
        requested_profile_path.parent.mkdir(parents=True, exist_ok=True)
        requested_profile_path.write_text(profile_json)
        audit.note("Saved the validated company profile JSON.")
        audit.finish("success")
        return profile
    except Exception as exc:
        audit.finish("error", f"{type(exc).__name__}: {exc}")
        raise


async def run_customer_finding(query: str, profile_path: Path, output_dir: Path) -> CustomerFindingResult:
    audit = AuditRun(query, output_dir)
    try:
        seller_path = PROJECT_ROOT / "assets" / "seller_brief.md"
        if not seller_path.exists():
            raise FileNotFoundError(f"Seller brief not found: {seller_path}")
        if not profile_path.is_absolute():
            profile_path = PROJECT_ROOT / profile_path
        if not profile_path.exists():
            fallback_path = PROJECT_ROOT / "output" / profile_path.name
            if fallback_path.exists():
                audit.note(f"Requested profile path was missing; using existing profile at {fallback_path}.")
                profile_path = fallback_path
            else:
                raise FileNotFoundError(f"Company profile not found: {profile_path}")
        seller_brief = seller_path.read_text()
        company_profile = profile_path.read_text()
        audit.note(f"Read seller brief from {seller_path} and company profile from {profile_path}.")
        agent = make_customer_agent(seller_brief, company_profile, audit)
        result = await agent.run(query)
        output_dir.mkdir(parents=True, exist_ok=True)
        for index, target in enumerate(result.output.targets, start=1):
            target.index = index
        (output_dir / "targets.json").write_text(json.dumps([item.model_dump() for item in result.output.targets], indent=2) + "\n")
        write_targets_review(result.output.targets, output_dir / "targets_review.md")
        (output_dir / "emails.json").write_text(json.dumps([item.model_dump() for item in result.output.emails], indent=2) + "\n")
        audit.note(f"Saved {len(result.output.targets)} numbered target(s), a review table, and {len(result.output.emails)} draft email(s); no messages were sent.")
        audit.finish("success")
        return result.output
    except Exception as exc:
        audit.finish("error", f"{type(exc).__name__}: {exc}")
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a company profile or find qualified Nexa customers.")
    parser.add_argument("query", nargs="+", help="Free-form request")
    parser.add_argument("--profile", help="Run customer-finding mode using this company profile JSON")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()
    query = " ".join(args.query)
    if args.profile:
        result = asyncio.run(run_customer_finding(query, Path(args.profile), Path(args.out_dir)))
        print(f"\nSaved {len(result.targets)} targets to {Path(args.out_dir) / 'targets.json'}")
        print(f"Review table saved to {Path(args.out_dir) / 'targets_review.md'}")
        print(f"Saved {len(result.emails)} draft emails to {Path(args.out_dir) / 'emails.json'}")
    else:
        profile = asyncio.run(run(query, Path(args.out_dir)))
        print_table(profile)


if __name__ == "__main__":
    main()
