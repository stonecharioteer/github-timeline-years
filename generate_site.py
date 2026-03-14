# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Generate a self-contained HTML visualization of GitHub contribution data."""

import json
import statistics
from pathlib import Path
from datetime import datetime, date
from collections import Counter

DATA_DIR = Path(__file__).parent / "data"
OUTPUT = Path(__file__).parent / "index.html"


def load_all_data() -> tuple[dict, dict]:
    all_data = {}
    # date_str -> {repo_name: {commits: N, issues: N, prs: N, reviews: N}}
    raw_by_date: dict[str, dict[str, dict[str, int]]] = {}
    for f in sorted(DATA_DIR.glob("*.json")):
        year = f.stem
        with open(f) as fh:
            raw = json.load(fh)
        collection = raw["data"]["user"]["contributionsCollection"]
        all_data[year] = collection["contributionCalendar"]

        # Commits (each node has commitCount)
        for repo_entry in collection.get("commitContributionsByRepository", []):
            repo_name = repo_entry["repository"]["nameWithOwner"]
            for node in repo_entry["contributions"]["nodes"]:
                day = node["occurredAt"][:10]
                entry = raw_by_date.setdefault(day, {}).setdefault(repo_name, {})
                entry["commits"] = entry.get("commits", 0) + node["commitCount"]

        # Issues, PRs, Reviews (each node = 1 contribution)
        for kind, key in [
            ("issueContributionsByRepository", "issues"),
            ("pullRequestContributionsByRepository", "prs"),
            ("pullRequestReviewContributionsByRepository", "reviews"),
        ]:
            for repo_entry in collection.get(kind, []):
                repo_name = repo_entry["repository"]["nameWithOwner"]
                for node in repo_entry["contributions"]["nodes"]:
                    day = node["occurredAt"][:10]
                    entry = raw_by_date.setdefault(day, {}).setdefault(repo_name, {})
                    entry[key] = entry.get(key, 0) + 1

    # Flatten to: date -> [(repo_name, summary_str, total_count), ...]
    repo_by_date = {}
    for day, repos in raw_by_date.items():
        day_list = []
        for repo_name, counts in repos.items():
            parts = []
            total = 0
            for key, label in [("commits", "commit"), ("issues", "issue"), ("prs", "PR"), ("reviews", "review")]:
                n = counts.get(key, 0)
                if n > 0:
                    total += n
                    parts.append(f"{n} {label}{'s' if n != 1 else ''}")
            day_list.append((repo_name, ", ".join(parts), total))
        day_list.sort(key=lambda x: x[2], reverse=True)
        repo_by_date[day] = [(name, summary) for name, summary, _ in day_list]

    return all_data, repo_by_date


def compute_stats(data: dict) -> dict:
    grand_total = sum(y["totalContributions"] for y in data.values())
    best_year = max(data.keys(), key=lambda k: data[k]["totalContributions"])
    best_year_total = data[best_year]["totalContributions"]

    max_daily = 0
    longest_streak = 0
    current_streak = 0
    active_days = 0
    all_daily_counts = []
    nonzero_counts = []
    weekday_totals = Counter()  # 0=Mon ... 6=Sun
    last_active_date = None

    for cal in data.values():
        for week in cal["weeks"]:
            for day in week["contributionDays"]:
                c = day["contributionCount"]
                all_daily_counts.append(c)
                dt = datetime.strptime(day["date"], "%Y-%m-%d")
                weekday_totals[dt.weekday()] += c
                max_daily = max(max_daily, c)
                if c > 0:
                    active_days += 1
                    nonzero_counts.append(c)
                    current_streak += 1
                    longest_streak = max(longest_streak, current_streak)
                    d = dt.date()
                    if last_active_date is None or d > last_active_date:
                        last_active_date = d
                else:
                    current_streak = 0

    total_days = len(all_daily_counts)
    median_on_active = statistics.median(nonzero_counts) if nonzero_counts else 0

    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    busiest_dow_idx = max(weekday_totals, key=weekday_totals.get)
    busiest_dow = weekday_names[busiest_dow_idx]

    # Recent activity windows
    today = date.today()

    # Last 365 days
    cutoff_year = today.replace(year=today.year - 1)
    year_counts = []

    # Last 3 months
    cutoff_3m = today.replace(month=today.month - 3) if today.month > 3 else today.replace(
        year=today.year - 1, month=today.month + 9)
    recent_counts = []

    for cal in data.values():
        for week in cal["weeks"]:
            for day in week["contributionDays"]:
                dt = datetime.strptime(day["date"], "%Y-%m-%d").date()
                if cutoff_year <= dt <= today:
                    year_counts.append(day["contributionCount"])
                if cutoff_3m <= dt <= today:
                    recent_counts.append(day["contributionCount"])

    year_total = len(year_counts)
    year_active = sum(1 for c in year_counts if c > 0)
    year_active_pct = round(year_active / year_total * 100, 1) if year_total else 0

    recent_total = len(recent_counts)
    recent_active = sum(1 for c in recent_counts if c > 0)
    recent_active_pct = round(recent_active / recent_total * 100, 1) if recent_total else 0

    return {
        "grand_total": grand_total,
        "best_year": best_year,
        "best_year_total": best_year_total,
        "max_daily": max_daily,
        "longest_streak": longest_streak,
        "active_days": active_days,
        "total_days": total_days,
        "median_on_active": round(median_on_active, 1),
        "year_active_pct": year_active_pct,
        "busiest_dow": busiest_dow,
        "recent_active_pct": recent_active_pct,
        "last_active": last_active_date.isoformat() if last_active_date else "N/A",
    }


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def get_level(count: int) -> int:
    if count == 0: return 0
    if count <= 3: return 1
    if count <= 6: return 2
    if count <= 9: return 3
    return 4


def build_year_html(year: str, cal: dict, max_total: int) -> str:
    total = cal["totalContributions"]
    weeks = cal["weeks"]

    seen_months = set()
    week_month_map = {}
    for wi, week in enumerate(weeks):
        for day in week["contributionDays"]:
            dt = datetime.strptime(day["date"], "%Y-%m-%d")
            if dt.month not in seen_months:
                seen_months.add(dt.month)
                week_month_map[wi] = MONTH_NAMES[dt.month - 1]
                break

    n_weeks = len(weeks)
    month_labels = []
    for wi in range(n_weeks):
        label = week_month_map.get(wi, "")
        month_labels.append(f'<span class="month-label">{label}</span>')
    month_row = "".join(month_labels)

    day_labels = ["Sun", "", "Tue", "", "Thu", "", "Sat"]
    day_labels_html = "".join(f'<div class="day-label">{d}</div>' for d in day_labels)

    cols_html = []
    for week in weeks:
        days_html = []
        for day in week["contributionDays"]:
            count = day["contributionCount"]
            level = get_level(count)
            days_html.append(
                f'<div class="cell" data-level="{level}" data-date="{day["date"]}" data-count="{count}"></div>'
            )
        cols_html.append(f'<div class="grid-col">{"".join(days_html)}</div>')

    bar_pct = (total / max_total * 100) if max_total > 0 else 0

    return f"""
    <section class="year-section" id="y{year}">
      <div class="year-header">
        <h2>{year}</h2>
        <span class="year-total"><strong>{total:,}</strong> contributions</span>
        <div class="year-bar" style="width:200px"><div class="year-bar-inner" style="width:{bar_pct:.1f}%"></div></div>
      </div>
      <div class="grid-scroll">
        <div class="month-labels">{month_row}</div>
        <div class="grid-wrapper">
          <div class="day-labels">{day_labels_html}</div>
          <div class="grid">{"".join(cols_html)}</div>
        </div>
      </div>
    </section>"""


def generate_html(data: dict, stats: dict, repo_by_date: dict | None = None) -> str:
    years = sorted(data.keys(), reverse=True)
    max_total = max(data[y]["totalContributions"] for y in years)
    nav_links = " ".join(f'<a href="#y{y}">{y}</a>' for y in years)
    year_sections = "\n".join(build_year_html(y, data[y], max_total) for y in years)
    from_year = years[-1]
    to_year = years[0]
    num_years = len(years)
    repo_json = json.dumps(repo_by_date or {}, separators=(",", ":"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GitHub Contributions \u2014 {from_year}\u2013{to_year}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;1,6..72,400;1,6..72,600&family=Martian+Mono:wght@300;400;600&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}

:root {{
  --bg-canvas: #0a0c10;
  --bg-default: #0d1117;
  --bg-subtle: #161b22;
  --bg-muted: #1c2128;
  --border-default: #30363d;
  --border-muted: #21262d;
  --text-primary: #e6edf3;
  --text-secondary: #8b949e;
  --text-muted: #484f58;
  --green-0: #161b22;
  --green-1: #0e4429;
  --green-2: #006d32;
  --green-3: #26a641;
  --green-4: #39d353;
  --glow-1: rgba(14, 68, 41, 0.3);
  --glow-2: rgba(0, 109, 50, 0.4);
  --glow-3: rgba(38, 166, 65, 0.4);
  --glow-4: rgba(57, 211, 83, 0.5);
  --cell-size: 11px;
  --cell-gap: 2px;
  --day-label-width: 24px;
}}

html {{
  scroll-behavior: smooth;
  scrollbar-width: thin;
  scrollbar-color: var(--border-default) var(--bg-canvas);
}}

body {{
  background: var(--bg-canvas);
  color: var(--text-primary);
  font-family: 'Martian Mono', monospace;
  min-height: 100vh;
  overflow-x: hidden;
}}

body::before {{
  content: '';
  position: fixed;
  inset: 0;
  background:
    radial-gradient(ellipse 80% 50% at 50% 0%, rgba(14, 68, 41, 0.15), transparent),
    radial-gradient(ellipse 60% 40% at 80% 100%, rgba(0, 109, 50, 0.08), transparent);
  pointer-events: none;
  z-index: 0;
}}

.noise {{
  position: fixed;
  inset: 0;
  opacity: 0.025;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
  pointer-events: none;
  z-index: 1;
}}

.container {{
  position: relative;
  z-index: 2;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 2rem;
}}

/* Hero */
.hero {{
  padding: 4rem 0 2.5rem;
  border-bottom: 1px solid var(--border-muted);
}}

.hero-profile {{
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.5rem;
  opacity: 0;
  animation: fadeUp 0.8s ease forwards 0.2s;
}}

.hero-avatar {{
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 2px solid var(--border-default);
}}

.hero-user {{
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}}

.hero-username {{
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}}

.hero-handle {{
  font-size: 0.6rem;
  font-weight: 300;
  color: var(--text-muted);
}}

.hero h1 {{
  font-family: 'Newsreader', serif;
  font-style: italic;
  font-weight: 600;
  font-size: clamp(2.2rem, 5vw, 3.8rem);
  line-height: 1.1;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
  opacity: 0;
  animation: fadeUp 0.8s ease forwards 0.4s;
}}

.hero h1 span {{
  background: linear-gradient(135deg, var(--green-3), var(--green-4));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}}

.hero-subtitle {{
  font-size: 0.7rem;
  font-weight: 300;
  color: var(--text-muted);
  letter-spacing: 0.05em;
  opacity: 0;
  animation: fadeUp 0.8s ease forwards 0.6s;
}}

/* Stats */
.stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1px;
  margin: 2.5rem 0;
  background: var(--border-muted);
  border-radius: 12px;
  overflow: hidden;
  opacity: 0;
  animation: fadeUp 0.8s ease forwards 0.8s;
}}

.stat {{
  background: var(--bg-default);
  padding: 1.25rem 1rem;
  text-align: center;
  transition: background 0.2s ease;
}}

.stat:hover {{ background: var(--bg-subtle); }}

.stat-value {{
  font-size: 1.4rem;
  font-weight: 600;
  color: var(--green-4);
  line-height: 1;
  margin-bottom: 0.4rem;
}}

.stat-value.text {{ font-size: 1rem; }}

.stat-label {{
  font-size: 0.5rem;
  font-weight: 300;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.12em;
}}

/* Year nav */
.year-nav {{
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(10, 12, 16, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-muted);
  padding: 0.75rem 0;
  margin: 0 -2rem;
  padding-left: 2rem;
  padding-right: 2rem;
  overflow-x: auto;
  scrollbar-width: none;
  display: flex;
  gap: 0.25rem;
  opacity: 0;
  animation: fadeUp 0.6s ease forwards 1s;
}}

.year-nav::-webkit-scrollbar {{ display: none; }}

.year-nav a {{
  font-size: 0.65rem;
  font-weight: 400;
  color: var(--text-muted);
  text-decoration: none;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  white-space: nowrap;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}}

.year-nav a:hover {{
  color: var(--text-secondary);
  background: var(--bg-subtle);
}}

.year-nav a.active {{
  color: var(--green-4);
  background: var(--bg-subtle);
  border-color: var(--border-default);
}}

/* Year sections */
.years {{ padding: 2rem 0 4rem; }}

.year-section {{
  margin-bottom: 3rem;
  opacity: 0;
  transform: translateY(24px);
  transition: opacity 0.6s ease, transform 0.6s ease;
  scroll-margin-top: 4rem;
}}

.year-section.visible {{
  opacity: 1;
  transform: translateY(0);
}}

.year-header {{
  display: flex;
  align-items: baseline;
  gap: 1rem;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-muted);
}}

.year-header h2 {{
  font-family: 'Newsreader', serif;
  font-style: italic;
  font-weight: 400;
  font-size: 1.8rem;
  color: var(--text-primary);
}}

.year-total {{
  font-size: 0.7rem;
  font-weight: 300;
  color: var(--text-secondary);
}}

.year-total strong {{ color: var(--green-3); font-weight: 600; }}

.year-bar {{
  height: 2px;
  background: var(--green-1);
  border-radius: 1px;
  margin-left: auto;
}}

.year-bar-inner {{
  height: 100%;
  background: linear-gradient(90deg, var(--green-2), var(--green-4));
  border-radius: 1px;
  transition: width 1.2s cubic-bezier(0.22, 1, 0.36, 1);
}}

/* Month labels */
.month-labels {{
  display: flex;
  gap: var(--cell-gap);
  padding-left: calc(var(--day-label-width) + 4px);
  margin-bottom: 4px;
}}

.month-label {{
  width: var(--cell-size);
  flex-shrink: 0;
  font-size: 0.5rem;
  font-weight: 300;
  color: var(--text-muted);
  text-align: left;
  white-space: nowrap;
  overflow: visible;
}}

/* Scrollable grid area on mobile */
.grid-scroll {{
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  scrollbar-color: var(--border-default) transparent;
  -webkit-overflow-scrolling: touch;
}}

.grid-scroll::-webkit-scrollbar {{ height: 4px; }}
.grid-scroll::-webkit-scrollbar-track {{ background: transparent; }}
.grid-scroll::-webkit-scrollbar-thumb {{ background: var(--border-default); border-radius: 2px; }}

/* Grid */
.grid-wrapper {{ display: flex; gap: 4px; }}

.day-labels {{
  display: flex;
  flex-direction: column;
  gap: var(--cell-gap);
  flex-shrink: 0;
  width: var(--day-label-width);
}}

.day-label {{
  height: var(--cell-size);
  font-size: 0.45rem;
  font-weight: 300;
  color: var(--text-muted);
  display: flex;
  align-items: center;
}}

.grid {{ display: flex; gap: var(--cell-gap); flex-grow: 1; }}
.grid-col {{ display: flex; flex-direction: column; gap: var(--cell-gap); }}

.cell {{
  width: var(--cell-size);
  height: var(--cell-size);
  border-radius: 2px;
  position: relative;
  cursor: crosshair;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  font-size: 0;
  line-height: 0;
  overflow: hidden;
  color: transparent;
}}

.cell:hover {{ transform: scale(1.8); z-index: 10; }}

.cell[data-level="0"] {{ background: var(--green-0); }}
.cell[data-level="1"] {{ background: var(--green-1); box-shadow: 0 0 3px var(--glow-1); }}
.cell[data-level="2"] {{ background: var(--green-2); box-shadow: 0 0 4px var(--glow-2); }}
.cell[data-level="3"] {{ background: var(--green-3); box-shadow: 0 0 6px var(--glow-3); }}
.cell[data-level="4"] {{ background: var(--green-4); box-shadow: 0 0 8px var(--glow-4); }}

.cell:hover[data-level="1"] {{ box-shadow: 0 0 12px var(--glow-1); }}
.cell:hover[data-level="2"] {{ box-shadow: 0 0 14px var(--glow-2); }}
.cell:hover[data-level="3"] {{ box-shadow: 0 0 16px var(--glow-3); }}
.cell:hover[data-level="4"] {{ box-shadow: 0 0 20px var(--glow-4); }}

/* Tooltip */
.tooltip {{
  position: fixed;
  pointer-events: none;
  background: var(--bg-subtle);
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 0.5rem 0.7rem;
  font-size: 0.6rem;
  color: var(--text-primary);
  z-index: 1000;
  opacity: 0;
  transition: opacity 0.12s ease;
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  max-width: 320px;
}}

.tooltip.show {{ opacity: 1; }}
.tt-header {{ display: flex; gap: 0.3rem; white-space: nowrap; }}
.tt-header .tt-count {{ color: var(--green-4); font-weight: 600; }}
.tt-header .tt-text {{ color: var(--text-secondary); }}
.tt-repos {{
  margin-top: 0.35rem;
  padding-top: 0.35rem;
  border-top: 1px solid var(--border-muted);
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}}
.tt-repo {{
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  white-space: nowrap;
}}
.tt-repo-name {{ color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; }}
.tt-repo-count {{ color: var(--green-3); font-weight: 600; flex-shrink: 0; }}

/* Legend */
.legend {{
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 2rem;
  justify-content: center;
  opacity: 0;
  animation: fadeUp 0.8s ease forwards 1.2s;
}}

.legend-label {{ font-size: 0.5rem; font-weight: 300; color: var(--text-muted); }}

.legend-cell {{ width: 11px; height: 11px; border-radius: 2px; }}

footer {{
  border-top: 1px solid var(--border-muted);
  padding: 2rem 0;
  text-align: center;
  font-size: 0.55rem;
  color: var(--text-muted);
  font-weight: 300;
}}

footer a {{
  transition: color 0.2s ease, border-color 0.2s ease;
}}

footer a:hover {{
  color: var(--green-3);
  border-color: var(--green-2);
}}

@keyframes fadeUp {{
  from {{ opacity: 0; transform: translateY(16px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}

@media (max-width: 768px) {{
  :root {{
    --cell-size: 8px;
    --cell-gap: 2px;
    --day-label-width: 20px;
  }}
  .container {{ padding: 0 1rem; }}
  .hero {{ padding: 3rem 0 2rem; }}
  .hero h1 {{ font-size: 1.6rem; }}
  .stats {{ grid-template-columns: repeat(2, 1fr); }}
  .day-label {{ font-size: 0.4rem; }}
  .month-label {{ font-size: 0.4rem; }}
  .year-nav {{ margin: 0 -1rem; padding-left: 1rem; padding-right: 1rem; }}
  .year-header {{ flex-wrap: wrap; gap: 0.5rem; }}
  .year-bar {{ width: 100% !important; margin-left: 0; }}
}}
</style>
</head>
<body>

<div class="noise"></div>

<div class="tooltip" id="tooltip">
  <div class="tt-header">
    <span class="tt-count" id="ttCount"></span>
    <span class="tt-text" id="ttText"></span>
  </div>
  <div class="tt-repos" id="ttRepos"></div>
</div>

<div class="container">
  <header class="hero">
    <div class="hero-profile">
      <img class="hero-avatar" src="https://avatars.githubusercontent.com/u/11478411?v=4" alt="stonecharioteer" width="48" height="48">
      <div class="hero-user">
        <span class="hero-username">Vinay Keerthi</span>
        <span class="hero-handle">@stonecharioteer &middot; member since 2015</span>
      </div>
    </div>
    <h1>{stats['grand_total']:,} contributions across <span>{num_years} years</span></h1>
    <p class="hero-subtitle">{from_year} \u2013 {to_year}</p>
  </header>

  <div class="stats">
    <div class="stat">
      <div class="stat-value" data-count="{stats['grand_total']}">0</div>
      <div class="stat-label">Total Contributions</div>
    </div>
    <div class="stat">
      <div class="stat-value text">{stats['best_year']}</div>
      <div class="stat-label">Best Year ({stats['best_year_total']:,})</div>
    </div>
    <div class="stat">
      <div class="stat-value" data-count="{stats['longest_streak']}">0</div>
      <div class="stat-label">Longest Streak (days)</div>
    </div>
    <div class="stat">
      <div class="stat-value" data-count="{stats['max_daily']}">0</div>
      <div class="stat-label">Peak Day</div>
    </div>
    <div class="stat">
      <div class="stat-value" data-count="{stats['active_days']}">0</div>
      <div class="stat-label">Active Days</div>
    </div>
    <div class="stat">
      <div class="stat-value">{stats['median_on_active']}</div>
      <div class="stat-label">Median on Active Days</div>
    </div>
    <div class="stat">
      <div class="stat-value">{stats['year_active_pct']}%</div>
      <div class="stat-label">Active (last 365 days)</div>
    </div>
    <div class="stat">
      <div class="stat-value text">{stats['busiest_dow']}</div>
      <div class="stat-label">Busiest Day of Week</div>
    </div>
    <div class="stat">
      <div class="stat-value">{stats['recent_active_pct']}%</div>
      <div class="stat-label">Active (last 3 months)</div>
    </div>
    <div class="stat">
      <div class="stat-value text">{stats['last_active']}</div>
      <div class="stat-label">Last Active (UTC)</div>
    </div>
  </div>

  <nav class="year-nav" id="yearNav">
    {nav_links}
  </nav>

  <div class="years" id="years">
    {year_sections}
  </div>

  <div class="legend">
    <span class="legend-label">Less</span>
    <div class="legend-cell" style="background: var(--green-0)"></div>
    <div class="legend-cell" style="background: var(--green-1)"></div>
    <div class="legend-cell" style="background: var(--green-2)"></div>
    <div class="legend-cell" style="background: var(--green-3)"></div>
    <div class="legend-cell" style="background: var(--green-4)"></div>
    <span class="legend-label">More</span>
  </div>

  <footer>
    <p><a href="contribution_timeline.png" download style="color:var(--green-3);text-decoration:none;border-bottom:1px solid var(--green-1);">Download Infographic</a></p>
    <p style="margin-top:0.5rem;">Data fetched via GitHub GraphQL API &middot; Includes private contributions</p>
    <p style="margin-top:0.5rem;"><a href="https://github.com/stonecharioteer/github-timeline-years" style="color:var(--text-secondary);text-decoration:none;border-bottom:1px solid var(--border-default);">View source on GitHub</a></p>
  </footer>
</div>

<script>
const repoData = {repo_json};

// Scroll-triggered visibility
const observer = new IntersectionObserver((entries) => {{
  entries.forEach(entry => {{
    if (entry.isIntersecting) entry.target.classList.add('visible');
  }});
}}, {{ threshold: 0.1 }});
document.querySelectorAll('.year-section').forEach(el => observer.observe(el));

// Active nav tracking — always highlight the topmost visible section
const navLinks = document.querySelectorAll('.year-nav a');
const visibleSections = new Set();
const allSections = [...document.querySelectorAll('.year-section')];

function updateActiveNav() {{
  for (const section of allSections) {{
    if (visibleSections.has(section.id)) {{
      navLinks.forEach(link => {{
        link.classList.toggle('active', link.getAttribute('href') === '#' + section.id);
      }});
      return;
    }}
  }}
}}

const navObserver = new IntersectionObserver((entries) => {{
  entries.forEach(entry => {{
    if (entry.isIntersecting) {{
      visibleSections.add(entry.target.id);
    }} else {{
      visibleSections.delete(entry.target.id);
    }}
  }});
  updateActiveNav();
}}, {{ threshold: 0.3 }});
document.querySelectorAll('.year-section').forEach(el => navObserver.observe(el));

// Tooltip
const tooltip = document.getElementById('tooltip');
const ttCount = document.getElementById('ttCount');
const ttText = document.getElementById('ttText');
const ttRepos = document.getElementById('ttRepos');

document.addEventListener('mouseover', (e) => {{
  const cell = e.target.closest('.cell');
  if (!cell) {{ tooltip.classList.remove('show'); return; }}
  const count = cell.dataset.count;
  const dateStr = cell.dataset.date;
  const plural = count === '1' ? 'contribution' : 'contributions';
  ttCount.textContent = count;
  ttText.textContent = plural + ' on ' + dateStr;

  // Show per-repo breakdown
  ttRepos.textContent = '';
  const repos = repoData[dateStr];
  if (repos && repos.length > 0) {{
    ttRepos.style.display = '';
    repos.forEach(([name, summary]) => {{
      const row = document.createElement('div');
      row.className = 'tt-repo';
      const nameEl = document.createElement('span');
      nameEl.className = 'tt-repo-name';
      nameEl.textContent = name;
      const countEl = document.createElement('span');
      countEl.className = 'tt-repo-count';
      countEl.textContent = summary;
      row.appendChild(nameEl);
      row.appendChild(countEl);
      ttRepos.appendChild(row);
    }});
  }} else {{
    ttRepos.style.display = 'none';
  }}

  tooltip.classList.add('show');
}});

document.addEventListener('mousemove', (e) => {{
  if (tooltip.classList.contains('show')) {{
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top = (e.clientY - 36) + 'px';
  }}
}});

document.addEventListener('mouseout', (e) => {{
  if (e.target.closest('.cell')) tooltip.classList.remove('show');
}});

// Animated counters
function animateCounters() {{
  document.querySelectorAll('[data-count]').forEach(el => {{
    const target = parseInt(el.dataset.count);
    const duration = 1200;
    const start = performance.now();
    function update(now) {{
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = Math.floor(eased * target).toLocaleString();
      if (progress < 1) requestAnimationFrame(update);
      else el.textContent = target.toLocaleString();
    }}
    requestAnimationFrame(update);
  }});
}}

const statsObserver = new IntersectionObserver((entries) => {{
  if (entries[0].isIntersecting) {{
    animateCounters();
    statsObserver.disconnect();
  }}
}}, {{ threshold: 0.5 }});
statsObserver.observe(document.querySelector('.stats'));
</script>
</body>
</html>"""


def main():
    data, repo_by_date = load_all_data()
    stats = compute_stats(data)

    html = generate_html(data, stats, repo_by_date)
    OUTPUT.write_text(html)
    print(f"Generated {OUTPUT} ({OUTPUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
