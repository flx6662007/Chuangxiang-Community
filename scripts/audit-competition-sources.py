"""Recheck the primary sources in the three curated inventories, without database writes.

HTTP accessibility is recorded separately from editorial verification. Saved pages
are local evidence, never automatically promoted to approved knowledge.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from bs4 import BeautifulSoup
import httpx
from ingestion.http import OfficialClient, FetchError


def inventory(paths):
    targets = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        for entry in payload["entries"]:
            editions = entry.get("editions") or [{"sources": entry.get("competition_sources", [])}]
            for edition in editions:
                sources = edition.get("sources", [])
                if not sources:
                    continue
                source = sources[0]
                url = source.get("url", "")
                if urlsplit(url).scheme not in {"http", "https"}:
                    continue
                target = targets.setdefault(url, {"url": url, "catalog_codes": [], "title": source.get("title", "")})
                if entry["code"] not in target["catalog_codes"]:
                    target["catalog_codes"].append(entry["code"])
    return list(targets.values())


def fetch_host(items, cache):
    hosts = {urlsplit(x["url"]).hostname for x in items}
    client = OfficialClient(hosts)
    client.client.timeout = httpx.Timeout(8, connect=5)
    results = []
    try:
        for item in items:
            row = dict(item)
            digest = hashlib.sha256(item["url"].encode()).hexdigest()
            try:
                document = urlsplit(item["url"]).path.lower().endswith((".pdf", ".docx", ".doc"))
                page = client.get_document(item["url"]) if document else client.get(item["url"])
                if document:
                    content = page.content
                    suffix = Path(urlsplit(item["url"]).path).suffix.lower()
                else:
                    soup = BeautifulSoup(page.text, "html.parser")
                    for node in soup(["script", "style", "nav", "footer"]):
                        node.decompose()
                    content = soup.get_text("\n", strip=True).encode("utf-8")
                    suffix = ".txt"
                (cache / (digest + suffix)).write_bytes(content)
                row.update(status="retrieved", final_url=page.url, bytes=len(content),
                           sha256=hashlib.sha256(content).hexdigest(), snapshot=digest + suffix)
            except FetchError as exc:
                row.update(status="unavailable", error=exc.code, http_status=exc.status)
            except Exception as exc:
                row.update(status="unavailable", error=type(exc).__name__)
            results.append(row)
    finally:
        client.close()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventories", type=Path, nargs="+")
    parser.add_argument("--cache", type=Path, default=ROOT / ".local/source-audit")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("workers must be between 1 and 8")
    args.cache.mkdir(parents=True, exist_ok=True)
    targets = inventory(args.inventories)
    groups = {}
    for item in targets:
        groups.setdefault(urlsplit(item["url"]).hostname, []).append(item)
    rows = []
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = [pool.submit(fetch_host, items, args.cache) for items in groups.values()]
        for completed in as_completed(pending):
            rows.extend(completed.result())
            result = {"checked_on": args.as_of, "check": "source_accessibility", "total": len(targets),
                      "completed": len(rows), "retrieved": sum(r["status"] == "retrieved" for r in rows),
                      "rows": sorted(rows, key=lambda r: r["url"])}
            args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({k: result[k] for k in ("completed", "total", "retrieved")}), flush=True)


if __name__ == "__main__":
    main()
