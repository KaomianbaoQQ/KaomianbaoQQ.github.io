#!/usr/bin/env python3
"""Fetch GitHub's official contributions endpoint and emit a compact JSON.

This script is designed to run inside GitHub Actions (or locally). It calls the
same endpoint that powers the contribution heatmap on github.com, which requires
no token but does not allow browser CORS. By running it server-side on a schedule
we can ship a same-origin data.json to the static GitHub Pages site.

Output: contributions.json in the current directory with shape:
  {"total": 60, "days": [{"date":"2025-11-16","count":0,"level":0}, ...],
   "fetchedAt":"2026-11-19T08:00:00Z","source":"github.com official"}
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

USERNAME = "KaomianbaoQQ"
URL = f"https://github.com/users/{USERNAME}/contributions"


def fetch() -> str:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def parse(html: str) -> dict:
    # Total contributions in the last year
    m = re.search(r"([\d,]+)\s+contributions?\s+in the last year", html)
    total = int(m.group(1).replace(",", "")) if m else 0

    # GitHub renders each day as a self-closing <td id="contribution-day-component-R-C" ...>
    # followed by an external <tool-tip for="contribution-day-component-R-C">N contributions...</tool-tip>.
    # Map tooltip text by the `for` id, then join to each cell.
    tip_count = {}
    for tid, text in re.findall(r'<tool-tip\b[^>]*\bfor="([^"]+)"[^>]*>(.*?)</tool-tip>', html, re.S):
        cm = re.search(r"(\d+)\s+contributions?\s+on", text)
        if cm:
            tip_count[tid] = int(cm.group(1))

    cells = re.findall(
        r'<td\b[^>]*\bid="(contribution-day-component-[^"]+)"[^>]*data-date="([\d-]+)"[^>]*data-level="(\d+)"[^>]*>',
        html,
    )
    if not cells:
        # tolerate different attribute order: capture whole td tag then parse inside
        days = []
        for tag in re.findall(r'<td\b[^>]*data-date="[\d-]+"[^>]*>', html):
            dm = re.search(r'data-date="([\d-]+)"', tag)
            lm = re.search(r'data-level="(\d+)"', tag)
            im = re.search(r'id="([^"]+)"', tag)
            if not (dm and lm):
                continue
            cnt = tip_count.get(im.group(1), 0) if im else 0
            days.append({"date": dm.group(1), "count": cnt, "level": int(lm.group(1))})
    else:
        days = []
        for cell_id, date, level in cells:
            days.append({"date": date, "count": tip_count.get(cell_id, 0), "level": int(level)})

    return {
        "total": total,
        "days": days,
        "fetchedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "github.com official contributions endpoint",
    }


def main():
    try:
        data = parse(fetch())
    except Exception as e:  # noqa: BLE001
        print(f"Fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not data["days"]:
        print("Parsed 0 days - endpoint structure may have changed", file=sys.stderr)
        sys.exit(1)

    with open("contributions.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: total={data['total']} days={len(data['days'])} "
          f"active={sum(1 for d in data['days'] if d['count']>0)}")


if __name__ == "__main__":
    main()
