#!/usr/bin/env python3
"""Generates self-hosted profile SVGs (stdlib only, no pip install needed):
   assets/contrib-eraser.svg  - contribution heatmap with an animated eraser rubbing out the commits
   assets/stats.svg           - total repos, stars, contributions, current + longest streak
   assets/commit-graph.svg    - 30-day commit graph
Usage: python scripts/generate_profile_art.py SpoidyMon [--demo]
Real data needs GITHUB_TOKEN in the environment (the Action provides it)."""
import os, sys, json, random, html, datetime as dt, urllib.request

args = [a for a in sys.argv[1:] if not a.startswith("--")]
USER = args[0] if args else "SpoidyMon"
TOKEN = os.environ.get("GITHUB_TOKEN")
DEMO = "--demo" in sys.argv or not TOKEN
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
os.makedirs(OUT, exist_ok=True)

W = 860
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
GREENS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
LV = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

# ------------------------------------------------------------------ data
def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": "bearer " + TOKEN, "Content-Type": "application/json", "User-Agent": "profile-art"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if "errors" in d:
        raise SystemExit(f"GraphQL error: {d['errors']}")
    return d["data"]

Q = """query($login:String!,$after:String){ user(login:$login){
  contributionsCollection{ contributionCalendar{ totalContributions
    weeks{ contributionDays{ date contributionCount weekday contributionLevel } } } }
  repositories(ownerAffiliations:OWNER, privacy:PUBLIC, first:100, after:$after){
    totalCount pageInfo{ hasNextPage endCursor } nodes{ stargazerCount isFork } } } }"""

def level(n):
    return 0 if n == 0 else 1 if n <= 2 else 2 if n <= 5 else 3 if n <= 9 else 4

def demo_data():
    random.seed(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=364)
    start -= dt.timedelta(days=start.isoweekday() % 7)
    weeks, d, total = [], start, 0
    while d <= today:
        wk = []
        for _ in range(7):
            if d > today: break
            r = random.random()
            n = 0 if r < .42 else random.randint(1, 4) if r < .8 else random.randint(5, 14)
            total += n
            wk.append({"date": d.isoformat(), "count": n, "weekday": d.isoweekday() % 7, "level": level(n)})
            d += dt.timedelta(days=1)
        weeks.append(wk)
    return weeks, total, 18, 42

def real_data():
    after, stars, repos, weeks, total = None, 0, 0, None, 0
    while True:
        u = gql(Q, {"login": USER, "after": after})["user"]
        if weeks is None:
            cal = u["contributionsCollection"]["contributionCalendar"]
            total = cal["totalContributions"]
            weeks = [[{"date": x["date"], "count": x["contributionCount"], "weekday": x["weekday"],
                       "level": LV[x["contributionLevel"]]} for x in w["contributionDays"]] for w in cal["weeks"]]
        r = u["repositories"]; repos = r["totalCount"]
        stars += sum(n["stargazerCount"] for n in r["nodes"] if not n["isFork"])
        if not r["pageInfo"]["hasNextPage"]: break
        after = r["pageInfo"]["endCursor"]
    return weeks, total, repos, stars

weeks, total, repos, stars = demo_data() if DEMO else real_data()
days = [d for w in weeks for d in w]
if DEMO: print("DEMO MODE: sample data (no GITHUB_TOKEN or --demo)")

def streaks(days):
    cur = 0
    i = len(days) - 1
    if i >= 0 and days[i]["count"] == 0: i -= 1   # today may not have commits yet
    while i >= 0 and days[i]["count"] > 0: cur += 1; i -= 1
    best = run = 0
    for d in days:
        run = run + 1 if d["count"] > 0 else 0
        best = max(best, run)
    return cur, best
cur_streak, best_streak = streaks(days)

# ------------------------------------------------------------------ svg helpers
def window(title, h, body, style=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" font-family="{FONT}">'
            f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#111722"/><stop offset="1" stop-color="#0d1117"/></linearGradient></defs>'
            f'<style>{style}</style>'
            f'<rect width="{W}" height="{h}" rx="12" fill="url(#bg)"/><rect x=".5" y=".5" width="{W-1}" height="{h-1}" rx="12" fill="none" stroke="#30363d"/>'
            f'<line x1="0" y1="30" x2="{W}" y2="30" stroke="#30363d"/>'
            f'<circle cx="20" cy="15" r="5" fill="#ff5f56"/><circle cx="36" cy="15" r="5" fill="#ffbd2e"/><circle cx="52" cy="15" r="5" fill="#27c93f"/>'
            f'<text x="{W/2}" y="19" fill="#7d8590" font-size="12" text-anchor="middle">{html.escape(title)}</text>{body}</svg>')

def save(name, s):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f: f.write(s)

# ------------------------------------------------------------------ 1. eraser heatmap
def heatmap():
    T = 16.0                                   # loop length (s)
    x0, y0, cols = 46, 88, len(weeks)
    pitch = (W - x0 - 26) / cols; cell = pitch - 3
    H = int(y0 + 7 * pitch + 52)
    step = 0.325 * T / (cols - 1)              # per-column delay == eraser speed
    b = [f'<text x="26" y="54" fill="#e6edf3" font-size="14" font-weight="700">{total:,} contributions in the last year</text>']
    last_m, last_i = None, -9
    for i, wk in enumerate(weeks):
        m = dt.date.fromisoformat(wk[0]["date"]).strftime("%b")
        if m != last_m and i - last_i >= 3:
            b.append(f'<text x="{x0+i*pitch:.1f}" y="{y0-8}" fill="#7d8590" font-size="11">{m}</text>'); last_m, last_i = m, i
    for r, lab in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        b.append(f'<text x="14" y="{y0+r*pitch+cell-1:.1f}" fill="#7d8590" font-size="10">{lab}</text>')
    for i, wk in enumerate(weeks):
        for d in wk:
            b.append(f'<rect class="c" x="{x0+i*pitch:.1f}" y="{y0+d["weekday"]*pitch:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="2.5" '
                     f'fill="{GREENS[d["level"]]}" style="animation-delay:{i*step:.2f}s"><title>{d["date"]}: {d["count"]}</title></rect>')
    ex0, ex1, ey = x0 + cell / 2, x0 + (cols - 1) * pitch + cell / 2, y0 + 3.5 * pitch
    amp = 3.5 * pitch - 8
    b.append('<g class="er"><g class="scrub"><g transform="rotate(-18)">'
             '<rect x="-20" y="-11" width="40" height="22" rx="5" fill="#58a6ff" stroke="#0d1117" stroke-width="1.5"/>'
             '<path d="M3,-11 h12 a5,5 0 0 1 5,5 v12 a5,5 0 0 1 -5,5 h-12 z" fill="#ff7b9c" stroke="#0d1117" stroke-width="1.5"/>'
             '<line x1="-14" y1="-6" x2="-2" y2="-6" stroke="#cfe4ff" stroke-width="2" stroke-linecap="round" opacity=".7"/></g></g></g>')
    lx = W - 190
    b.append(f'<text x="{lx}" y="{H-16}" fill="#7d8590" font-size="10">Less</text>')
    for k in range(5):
        b.append(f'<rect x="{lx+30+k*15}" y="{H-25}" width="11" height="11" rx="2.5" fill="{GREENS[k]}"/>')
    b.append(f'<text x="{lx+110}" y="{H-16}" fill="#7d8590" font-size="10">More</text>')
    b.append(f'<text x="26" y="{H-16}" fill="#484f58" font-size="10">$ git filter-branch --erase-history  # they always come back</text>')
    css = (f'.c{{transform-box:fill-box;transform-origin:center;animation:cyc {T}s linear infinite}}'
           '@keyframes cyc{0%,24%{opacity:1;transform:scale(1)}27%{opacity:0;transform:scale(.2)}60%{opacity:0;transform:scale(.2)}'
           '63%{opacity:1;transform:scale(1.18)}66%,100%{opacity:1;transform:scale(1)}}'
           f'.er{{opacity:0;animation:sweep {T}s linear infinite}}'
           f'@keyframes sweep{{0%,24%{{transform:translate({ex0:.1f}px,{ey:.1f}px);opacity:0}}'
           f'25.5%{{transform:translate({ex0:.1f}px,{ey:.1f}px);opacity:1}}'
           f'58%{{transform:translate({ex1:.1f}px,{ey:.1f}px);opacity:1}}'
           f'60%,100%{{transform:translate({ex1:.1f}px,{ey:.1f}px);opacity:0}}}}'
           f'.scrub{{animation:scrub .42s ease-in-out infinite alternate}}'
           f'@keyframes scrub{{from{{transform:translateY({-amp:.0f}px)}}to{{transform:translateY({amp:.0f}px)}}}}'
           '@media (prefers-reduced-motion:reduce){.c,.scrub{animation:none}.er{display:none}}')
    save("contrib-eraser.svg", window(f"{USER}@github: ~$ ./contributions.sh --erase", H, "".join(b), css))

# ------------------------------------------------------------------ 2. stats cards
def stats():
    items = [("Total Repos", f"{repos:,}", "public", "#58a6ff"),
             ("Stars Earned", f"{stars:,}", "across your repos", "#e3b341"),
             ("Contributions", f"{total:,}", "last 12 months", "#39d353"),
             ("Current Streak", f"{cur_streak}", "days in a row", "#ff7b72"),
             ("Longest Streak", f"{best_streak}", "days", "#d2a8ff")]
    gap, pad = 12, 22
    cw = (W - 2 * pad - gap * 4) / 5; H = 176
    b = [f'<text x="{pad}" y="56" fill="#7d8590" font-size="12">$ ./stats.sh --user {html.escape(USER)}</text>']
    for i, (lab, val, sub, col) in enumerate(items):
        x = pad + i * (cw + gap)
        b.append(f'<g class="card" style="animation-delay:{i*0.12:.2f}s"><rect x="{x:.1f}" y="70" width="{cw:.1f}" height="88" rx="8" fill="#161b22" stroke="#30363d"/>'
                 f'<rect x="{x:.1f}" y="70" width="{cw:.1f}" height="3" rx="1.5" fill="{col}"/>'
                 f'<text x="{x+cw/2:.1f}" y="109" fill="#e6edf3" font-size="28" font-weight="700" text-anchor="middle">{val}</text>'
                 f'<text x="{x+cw/2:.1f}" y="130" fill="{col}" font-size="12" font-weight="700" text-anchor="middle">{lab}</text>'
                 f'<text x="{x+cw/2:.1f}" y="147" fill="#7d8590" font-size="10" text-anchor="middle">{sub}</text></g>')
    css = ('.card{opacity:0;transform:translateY(8px);animation:up .6s ease-out forwards}'
           '@keyframes up{to{opacity:1;transform:none}}@media (prefers-reduced-motion:reduce){.card{animation:none;opacity:1;transform:none}}')
    save("stats.svg", window(f"{USER}@github: ~$ ./stats.sh", H, "".join(b), css))

# ------------------------------------------------------------------ 3. commit graph (30 days)
def commit_graph():
    last = days[-30:]; n = len(last)
    H, L, R, Tp, B = 270, 56, 30, 70, 44
    ph = H - Tp - B; pw = W - L - R
    mx = max(5, max(d["count"] for d in last)); mx = ((mx + 3) // 4) * 4
    pts = [(L + i * pw / (n - 1), Tp + ph - d["count"] / mx * ph) for i, d in enumerate(last)]
    path = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        m = (xb - xa) / 2; path += f" C{xa+m:.1f},{ya:.1f} {xb-m:.1f},{yb:.1f} {xb:.1f},{yb:.1f}"
    area = path + f" L{pts[-1][0]:.1f},{Tp+ph} L{pts[0][0]:.1f},{Tp+ph} Z"
    b = [f'<defs><linearGradient id="ar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#39d353" stop-opacity=".35"/><stop offset="1" stop-color="#39d353" stop-opacity="0"/></linearGradient></defs>',
         f'<text x="26" y="54" fill="#e6edf3" font-size="14" font-weight="700">Commit graph · last 30 days</text>',
         f'<text x="{W-26}" y="54" fill="#7d8590" font-size="12" text-anchor="end">{sum(d["count"] for d in last)} contributions</text>']
    for k in range(5):
        y = Tp + ph - k * ph / 4
        b.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W-R}" y2="{y:.1f}" stroke="#21262d"/><text x="{L-10}" y="{y+4:.1f}" fill="#7d8590" font-size="10" text-anchor="end">{k*mx//4}</text>')
    for i in range(0, n, 5):
        dd = dt.date.fromisoformat(last[i]["date"]).strftime("%b %d")
        b.append(f'<text x="{pts[i][0]:.1f}" y="{H-18}" fill="#7d8590" font-size="10" text-anchor="middle">{dd}</text>')
    b.append(f'<path class="area" d="{area}" fill="url(#ar)"/>')
    b.append(f'<path class="line" d="{path}" pathLength="1" fill="none" stroke="#39d353" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>')
    for i, ((x, y), d) in enumerate(zip(pts, last)):
        if d["count"] > 0:
            b.append(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="#0d1117" stroke="#39d353" stroke-width="2" style="animation-delay:{0.6+i*0.07:.2f}s"><title>{d["date"]}: {d["count"]}</title></circle>')
    css = ('.line{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 2.6s ease-out .2s forwards}@keyframes draw{to{stroke-dashoffset:0}}'
           '.area{opacity:0;animation:fade 1.2s ease-out 1.4s forwards}@keyframes fade{to{opacity:1}}'
           '.dot{opacity:0;animation:fade .4s ease-out forwards}'
           '@media (prefers-reduced-motion:reduce){.line,.area,.dot{animation:none;stroke-dashoffset:0;opacity:1}}')
    save("commit-graph.svg", window(f"{USER}@github: ~$ git log --graph --since=30.days", H, "".join(b), css))

heatmap(); stats(); commit_graph()
print(f"ok: {len(days)} days, repos={repos}, stars={stars}, streak={cur_streak}/{best_streak}, total={total}")
