"""
Swarm Hunter v1.0 — Localized Vulnerability Intelligence Aggregator
Queries public APIs only. No authentication required for basic NVD/GitHub advisory feeds.

Outputs: D:\Trishula-Infra\Swarm\intelligence_feed.json
"""

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx  # pip install httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path(r"D:\Trishula-Infra\Swarm\intelligence_feed.json")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# Stack keywords for NVD CPE/keyword search
TRISHULA_STACK_KEYWORDS = [
    "python",
    "flask",
    "powershell",
    "windows server",
    "linux kernel",
]

NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
GITHUB_ADVISORIES_API = "https://api.github.com/advisories"
CVSS_THRESHOLD = 8.0
LOOKBACK_DAYS = 7


def fetch_nvd_cves(keyword: str, client: httpx.Client) -> list[dict]:
    """Query NVD for recent high-severity CVEs matching a stack keyword."""
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime(
        "%Y-%m-%dT%H:%M:%S.000"
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000")

    params = {
        "keywordSearch": keyword,
        "pubStartDate": since,
        "pubEndDate": now,
        "cvssV3Severity": "HIGH",  # HIGH = 7.0-8.9, CRITICAL = 9.0-10.0
        "resultsPerPage": 20,
    }

    try:
        # NVD rate limit: ~5 req/30s without API key. We sleep between calls.
        resp = client.get(NVD_API_BASE, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        vulns = []
        for item in data.get("vulnerabilities", []):
            cve = item.get("cve", {})
            cve_id = cve.get("id", "N/A")
            description = next(
                (d["value"] for d in cve.get("descriptions", []) if d["lang"] == "en"),
                "No description available."
            )
            # Extract CVSS v3.1 base score
            metrics = cve.get("metrics", {})
            score = None
            vector = None
            for entry in metrics.get("cvssMetricV31", []):
                score = entry.get("cvssData", {}).get("baseScore")
                vector = entry.get("cvssData", {}).get("vectorString")
                break

            if score and float(score) >= CVSS_THRESHOLD:
                vulns.append({
                    "cve_id": cve_id,
                    "score": score,
                    "vector": vector,
                    "description": description[:300],
                    "published": cve.get("published", ""),
                    "source": "NVD",
                    "keyword": keyword,
                })
        logger.info(f"NVD [{keyword}]: {len(vulns)} hits above CVSS {CVSS_THRESHOLD}")
        return vulns
    except httpx.HTTPStatusError as e:
        logger.error(f"NVD HTTP error for '{keyword}': {e.response.status_code}")
        return []
    except Exception as e:
        logger.error(f"NVD fetch failed for '{keyword}': {e}")
        return []


def fetch_github_advisories(client: httpx.Client) -> list[dict]:
    """
    Query GitHub's public Security Advisory database.
    No auth needed for public advisories (rate limit: 60 req/hr unauthenticated).
    """
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    params = {
        "type": "reviewed",
        "severity": "high,critical",
        "per_page": 30,
    }
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        resp = client.get(
            GITHUB_ADVISORIES_API,
            params=params,
            headers=headers,
            timeout=30
        )
        resp.raise_for_status()
        advisories = []
        for adv in resp.json():
            published = adv.get("published_at", "")
            # Filter by lookback window
            if published and published < since:
                continue
            ecosystems = [
                v.get("package", {}).get("ecosystem", "")
                for v in adv.get("vulnerabilities", [])
            ]
            advisories.append({
                "ghsa_id": adv.get("ghsa_id"),
                "cve_id": adv.get("cve_id"),
                "severity": adv.get("severity"),
                "summary": adv.get("summary", "")[:300],
                "ecosystems": list(set(ecosystems)),
                "published": published,
                "url": adv.get("html_url"),
                "source": "GitHub Advisories",
            })
        logger.info(f"GitHub Advisories: {len(advisories)} high/critical hits")
        return advisories
    except httpx.HTTPStatusError as e:
        logger.error(f"GitHub Advisory HTTP error: {e.response.status_code}")
        return []
    except Exception as e:
        logger.error(f"GitHub Advisory fetch failed: {e}")
        return []


def run_hunter() -> dict:
    """Execute a full intelligence sweep and return the feed payload."""
    logger.info("=== Swarm Hunter: Intelligence Sweep Started ===")
    feed = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": LOOKBACK_DAYS,
        "cvss_threshold": CVSS_THRESHOLD,
        "nvd_findings": [],
        "github_advisories": [],
        "summary": {},
    }

    with httpx.Client() as client:
        # NVD: one keyword at a time to stay under rate limits
        all_nvd = []
        for keyword in TRISHULA_STACK_KEYWORDS:
            results = fetch_nvd_cves(keyword, client)
            all_nvd.extend(results)
            time.sleep(6)  # NVD rate limit: ~5 req/30s without API key

        # Deduplicate by CVE ID
        seen = set()
        for finding in all_nvd:
            if finding["cve_id"] not in seen:
                feed["nvd_findings"].append(finding)
                seen.add(finding["cve_id"])

        # GitHub Advisories
        feed["github_advisories"] = fetch_github_advisories(client)

    feed["summary"] = {
        "total_nvd": len(feed["nvd_findings"]),
        "total_github": len(feed["github_advisories"]),
        "critical_count": sum(
            1 for a in feed["github_advisories"] if a.get("severity") == "critical"
        ),
        "highest_cvss": max(
            (float(f["score"]) for f in feed["nvd_findings"] if f.get("score")),
            default=0.0
        ),
    }

    logger.info(
        f"Sweep complete — NVD: {feed['summary']['total_nvd']}, "
        f"GitHub: {feed['summary']['total_github']}, "
        f"Critical: {feed['summary']['critical_count']}"
    )
    return feed


def save_feed(feed: dict) -> None:
    OUTPUT_PATH.write_text(
        json.dumps(feed, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    logger.info(f"Intelligence feed saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    feed = run_hunter()
    save_feed(feed)
    print(f"\n[Swarm] Feed written to {OUTPUT_PATH}")
    print(f"[Swarm] Summary: {json.dumps(feed['summary'], indent=2)}")
