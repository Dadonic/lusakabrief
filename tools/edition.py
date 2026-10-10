#!/usr/bin/env python3
"""Lusaka Brief — daily edition pipeline.

    python3 tools/edition.py status                  # today's date, next edition no., recent stories
    python3 tools/edition.py build  EDITION.json     # validate + publish an edition into the repo
    python3 tools/edition.py check                   # verify the site is internally consistent
    python3 tools/edition.py regen                   # rebuild archive, feed.xml and sitemap.xml only

`build` writes one page per story, draws the illustrations, then updates
assets/stories.json, index.html, news/index.html, feed.xml and sitemap.xml.
Nothing is written unless the whole edition validates. It never touches
wire.json, wire.php, api/ or assets/site.css.

See tools/EDITION.md for the edition JSON format and the editorial rules.
"""
import argparse
import datetime as dt
import email.utils
import json
import os
import re
import subprocess
import sys
import xml.dom.minidom
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

SITE = "https://lusakabrief.com"
TZ = ZoneInfo("Africa/Lusaka")
SECTIONS = ["Politics", "Economy", "Health", "Courts", "Sport", "Culture"]
ALWAYS_ON = {"Politics", "Economy", "Sport", "Culture"}   # sections the nav links to
DESKS = {
    "Politics": "Lusaka Brief Politics Desk",
    "Economy": "Lusaka Brief Business Desk",
    "Health": "Lusaka Brief Health Desk",
    "Courts": "Lusaka Brief Courts Desk",
    "Sport": "Lusaka Brief Sports Desk",
    "Culture": "Lusaka Brief Culture Desk",
}
KICKER = {
    "Politics": "var(--green)", "Economy": "var(--copper)", "Health": "#315c8a",
    "Courts": "#5b4a8a", "Sport": "#8a2f2f", "Culture": "#7a5c1e",
}
BADGE = ('\n      <span class="badge" style="display:inline-block;margin-left:10px;'
         'font:600 11px Inter,sans-serif;letter-spacing:.08em;text-transform:uppercase;'
         'color:#b4551f;border:1px solid #b4551f;border-radius:999px;padding:3px 10px;'
         'vertical-align:middle">Developing</span>')
SOURCES_STYLE = ("font-size:13.5px;color:#6b6558;border-top:1px solid #ddd;"
                 "padding-top:14px;margin-top:26px")
# Phrases that claim first-hand reporting. Editions are compiled from published
# reporting, so copy must never imply interviews or enquiries that did not happen.
BANNED = [
    "told lusaka brief", "lusaka brief has learned", "lusaka brief has learnt",
    "lusaka brief understands", "lusaka brief can reveal", "lusaka brief has seen",
    "seen by lusaka brief", "sources told this", "our reporter", "our correspondent",
    "contacted for comment", "did not respond to our", "declined to comment to",
    "in an exclusive", "this publication has",
]
FEED_ITEMS = 60
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


# ---------------------------------------------------------------- helpers
def p(*parts):
    return os.path.join(ROOT, *parts)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def attr(s):
    return esc(s).replace('"', "&quot;")


def rich(s):
    """Escape a paragraph, then allow **bold**."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(s))


def today():
    return dt.datetime.now(TZ).date()


def long_date(d):
    return f"{d.strftime('%A')}, {d.day} {MONTHS[d.month - 1]} {d.year}"


def plain_date(d):
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def short_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1][:3]}"


def load_stories():
    return json.loads(read(p("assets", "stories.json")))


def dump_stories(stories):
    return json.dumps(stories, ensure_ascii=False, indent=1)


def href(s):
    return s.get("external") or f"/news/{s['slug']}/"


def words(text):
    return len(re.findall(r"\S+", text))


def body_text(story):
    out = []
    for b in story.get("body", []):
        if isinstance(b, str):
            out.append(b)
        elif isinstance(b, dict):
            out.extend(str(v) for k, v in b.items() if k != "type" and isinstance(v, str))
            out.extend(b.get("items", []) if isinstance(b.get("items"), list) else [])
    return "\n".join(out)


def next_edition_number(stories):
    nums = [s["edition"] for s in stories if isinstance(s.get("edition"), int)]
    try:
        log = subprocess.run(["git", "-C", ROOT, "log", "-40", "--format=%s"],
                             capture_output=True, text=True, timeout=30).stdout
        nums += [int(n) for n in re.findall(r"^Edition No\. (\d+)", log, re.M)]
    except Exception:
        pass
    if not nums:
        raise SystemExit("Cannot work out the edition number (no 'Edition No. N' in "
                         "git history or stories.json). Pass --number N.")
    return max(nums) + 1


def sub_once(pattern, repl, text, what, flags=re.S):
    new, n = re.subn(pattern, lambda m: repl, text, count=0, flags=flags)
    if n != 1:
        raise SystemExit(f"index update failed: expected exactly one {what}, found {n}. "
                         "The page layout has changed — fix tools/edition.py before publishing.")
    return new


# ---------------------------------------------------------------- validation
def validate(ed, stories, day, allow_any_date=False, force=False):
    import art
    errs = []
    e = errs.append

    if not isinstance(ed, dict):
        return ["edition file must be a JSON object"]
    try:
        d = dt.date.fromisoformat(ed.get("date", ""))
    except ValueError:
        return ["'date' must be YYYY-MM-DD"]
    if d != day and not allow_any_date:
        e(f"edition date {d} is not today in Lusaka ({day})")
    if not force and any(s["iso"] == d.isoformat() and s["section"] in SECTIONS
                         for s in stories):
        e(f"an edition dated {d} is already published — nothing to do (use --force to add anyway)")
    strap = ed.get("strapline", "")
    if not 25 <= len(strap) <= 170:
        e("'strapline' must be 25–170 characters")

    items = ed.get("stories")
    if not isinstance(items, list) or not 5 <= len(items) <= 10:
        e("'stories' must hold 5–10 stories")
        return errs
    if sum(1 for s in items if s.get("lead")) != 1:
        e("exactly one story must have \"lead\": true")
    existing = {s["slug"] for s in stories}
    seen, keys = set(), set()
    for i, s in enumerate(items):
        w = f"story {i + 1} ({s.get('slug', '?')[:40]})"
        slug = s.get("slug", "")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug) or not 15 <= len(slug) <= 110:
            e(f"{w}: slug must be lowercase-kebab-case, 15–110 characters")
        if slug in existing or slug in seen or os.path.exists(p("news", slug)):
            e(f"{w}: slug already used")
        seen.add(slug)
        sec = s.get("section")
        if sec not in SECTIONS:
            e(f"{w}: section must be one of {', '.join(SECTIONS)}")
            continue
        tag = s.get("tag", "")
        if s.get("lead"):
            pass
        elif not tag.startswith(sec + " · ") or len(tag) > 60:
            e(f"{w}: tag must look like \"{sec} · Topic\" (max 60 characters)")
        if not 30 <= len(s.get("title", "")) <= 180:
            e(f"{w}: title must be 30–180 characters")
        if not 120 <= len(s.get("excerpt", "")) <= 560:
            e(f"{w}: excerpt must be 120–560 characters")
        if not re.fullmatch(r"[A-Z][A-Z .'\-]{2,30}", s.get("dateline", "")):
            e(f"{w}: dateline must be a place name in capitals, e.g. LUSAKA")
        body = s.get("body")
        if not isinstance(body, list) or sum(isinstance(b, str) for b in body) < 3:
            e(f"{w}: body needs at least 3 paragraphs")
            body = []
        for b in body:
            if isinstance(b, str):
                if not b.strip() or "<" in b:
                    e(f"{w}: paragraphs are plain text (no HTML, none empty)")
            elif not isinstance(b, dict) or b.get("type") not in (
                    "subhead", "quote", "box", "confirmed"):
                e(f"{w}: unknown body block {b!r:.60}")
            elif b["type"] == "subhead" and not b.get("text"):
                e(f"{w}: subhead needs 'text'")
            elif b["type"] == "quote" and not (b.get("text") and b.get("attribution")):
                e(f"{w}: quote needs 'text' and 'attribution'")
            elif b["type"] == "box" and not (b.get("title") and isinstance(b.get("items"), list)
                                             and b["items"]):
                e(f"{w}: box needs 'title' and a non-empty 'items' list")
            elif b["type"] == "confirmed" and not (b.get("confirmed") and b.get("unverified")):
                e(f"{w}: confirmed block needs 'confirmed' and 'unverified'")
        text = body_text(s)
        need = 420 if s.get("lead") else 260
        if words(text) < need:
            e(f"{w}: body is {words(text)} words; needs at least {need}")
        if s.get("lead") and not any(isinstance(b, dict) and b.get("type") == "confirmed"
                                     for b in body):
            e(f"{w}: the lead story needs a 'confirmed' block (confirmed vs. unverified)")
        low = (text + " " + s.get("excerpt", "") + " " + s.get("title", "")).lower()
        for phrase in BANNED:
            if phrase in low:
                e(f"{w}: remove \"{phrase}\" — editions never claim first-hand reporting")
        srcs = s.get("sources")
        if not isinstance(srcs, list) or not srcs:
            e(f"{w}: at least one source is required")
            srcs = []
        for src in srcs:
            if not (isinstance(src, dict) and src.get("outlet") and src.get("title")
                    and src.get("date")
                    and re.match(r"https://[^\s\"<>]+\.[^\s\"<>]+", src.get("url", ""))):
                e(f"{w}: each source needs outlet, title, date and an https url")
                break
        outlets = {src.get("outlet", "").strip().lower() for src in srcs if isinstance(src, dict)}
        if sec not in ("Sport", "Culture") and len(outlets) < 2:
            e(f"{w}: {sec} stories need at least two different source outlets")
        img = s.get("image")
        if not isinstance(img, dict):
            e(f"{w}: image object is required")
            continue
        key = img.get("key", "")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", key) or len(key) > 24 or key in keys:
            e(f"{w}: image.key must be a short unique kebab-case word")
        keys.add(key)
        if not 3 <= len(img.get("label", "")) <= 34:
            e(f"{w}: image.label must be 3–34 characters")
        if not 20 <= len(img.get("caption", "")) <= 220:
            e(f"{w}: image.caption must be 20–220 characters")
        if img.get("motif") and img["motif"] not in art.MOTIFS:
            e(f"{w}: image.motif must be one of {', '.join(art.MOTIFS)}")

    an = ed.get("analysis")
    if not isinstance(an, list) or not 2 <= len(an) <= 3:
        e("'analysis' must hold 2 or 3 pieces")
    else:
        for i, a in enumerate(an):
            w = f"analysis {i + 1}"
            if a.get("desk") not in SECTIONS:
                e(f"{w}: desk must be one of {', '.join(SECTIONS)}")
            if not 10 <= len(a.get("title", "")) <= 90:
                e(f"{w}: title must be 10–90 characters")
            if not 90 <= words(a.get("body", "")) <= 240:
                e(f"{w}: body must be 90–240 words (is {words(a.get('body', ''))})")
            low = a.get("body", "").lower()
            for phrase in BANNED:
                if phrase in low:
                    e(f"{w}: remove \"{phrase}\"")
    return errs


# ---------------------------------------------------------------- rendering
def render_body(story):
    out = []
    for b in story["body"]:
        if isinstance(b, str):
            out.append(f"<p>{rich(b.strip())}</p>")
        elif b["type"] == "subhead":
            out.append(f"<h2>{esc(b['text'])}</h2>")
        elif b["type"] == "quote":
            out.append(f"<blockquote>{esc(b['text'])}<br><span style=\"font-family:Inter,"
                       f"sans-serif;font-size:13.5px;font-style:normal;color:#6b6558\">"
                       f"— {esc(b['attribution'])}</span></blockquote>")
        elif b["type"] == "box":
            lis = "".join(f"<li>{rich(i)}</li>" for i in b["items"])
            out.append(f'<div class="factbox"><h3>{esc(b["title"])}</h3><ul>{lis}</ul></div>')
        elif b["type"] == "confirmed":
            out.append(
                '<div style="border:1px solid #d8d2c4;background:#f7f4ec;border-radius:10px;'
                'padding:16px 20px;margin:26px 0">\n'
                '<p style="margin:0 0 8px"><strong>Confirmed vs. alleged</strong></p>\n'
                f'<p style="margin:0 0 8px"><strong>Confirmed:</strong> {rich(b["confirmed"])}</p>\n'
                f'<p style="margin:0"><strong>Alleged or unverified:</strong> '
                f'{rich(b["unverified"])}</p>\n</div>')
    links = "; ".join(
        f'<a href="{attr(s["url"])}" rel="noopener" target="_blank" '
        f'style="color:inherit">{esc(s["outlet"])}, “{esc(s["title"])}”</a> ({esc(s["date"])})'
        for s in story["sources"])
    out.append(f'<p class="sources" style="{SOURCES_STYLE}"><strong>Sources:</strong> '
               f"{links}.</p>")
    return "\n".join(out)


def render_article(story, d):
    tpl = read(os.path.join(HERE, "article-template.html"))
    return tpl.format(
        title=esc(story["title"]), title_attr=attr(story["title"]),
        excerpt=esc(story["excerpt"]), excerpt_attr=attr(story["excerpt"]),
        slug=story["slug"], image=story["_image"], iso=d.isoformat(),
        section=story["section"], date_long=long_date(d), date=plain_date(d),
        kicker_color=KICKER[story["section"]], kicker=esc(story["_tag"]),
        badge=BADGE if story.get("developing") else "",
        author=esc(story["_author"]), dateline=esc(story["dateline"]),
        readtime=story["_readtime"], alt=attr(story["_alt"]),
        caption=esc(story["_caption"]), body=render_body(story), year=d.year)


def card_alt(s):
    """Alt text for a story card: read it back from the story's own page."""
    if s.get("_alt"):
        return attr(s["_alt"])
    try:
        page = read(p("news", s["slug"], "index.html"))
        m = re.search(r'<figure class="article-figure">\s*<img[^>]*?alt="([^"]*)"', page)
        return m.group(1) if m else ""
    except OSError:
        return ""


def home_card(s):
    h = href(s)
    return (
        '    <article class="card">\n'
        f'      <a href="{h}"><img src="/assets/{s["image"]}" alt="{card_alt(s)}" '
        'loading="lazy"></a>\n'
        '      <div class="card-body">\n'
        f'        <span class="tag">{esc(s["tag"])}</span>\n'
        f'        <h3><a href="{h}">{esc(s["title"])}</a></h3>\n'
        f'        <p>{esc(s["excerpt"])}</p>\n'
        f'        <div class="byline"><span>By <strong>{esc(s["author"])}</strong></span>'
        f'<span class="sep">•</span><span>{short_date(s["iso"])}</span></div>\n'
        '      </div>\n'
        '    </article>\n')


def home_sections(stories, iso, lead_slug, backfill=True):
    """Section grids: today's stories first, topped up to three with the most recent
    earlier stories so every grid is full and every nav anchor resolves."""
    out = []
    for sec in SECTIONS:
        pool = [s for s in stories if s["section"] == sec and s["slug"] != lead_slug
                and not s.get("external")]
        fresh = [s for s in pool if s["iso"] == iso]
        if not fresh and not (backfill and sec in ALWAYS_ON):
            continue
        cards = list(fresh)
        if backfill and len(cards) < 3:
            older = sorted((s for s in pool if s["iso"] < iso), key=lambda s: s["iso"],
                           reverse=True)
            cards += older[:3 - len(cards)]
        if not cards:
            continue
        out.append(f"  <!-- {sec} -->\n"
                   f'  <h2 class="section-label" id="{sec.lower()}">{sec}</h2>\n'
                   '  <section class="grid-3">\n' + "".join(home_card(s) for s in cards)
                   + "  </section>\n")
    return "\n".join(out)


def home_lead(lead, d):
    h = f"/news/{lead['slug']}/"
    return (
        "<!-- Lead story -->\n"
        '  <section class="lead">\n'
        '    <figure class="lead-media">\n'
        f'      <a href="{h}">\n'
        f'        <img src="/assets/{lead["_image"]}" alt="{attr(lead["_alt"])}">\n'
        "      </a>\n"
        f'      <figcaption>{esc(lead["_caption"])}</figcaption>\n'
        "    </figure>\n"
        "    <div>\n"
        f'      <a class="kicker" style="color:#b4551f" href="{h}">{esc(lead["_tag"])}</a>'
        f'{BADGE if lead.get("developing") else ""}\n'
        f'      <h1><a href="{h}">{esc(lead["title"])}</a></h1>\n'
        f'      <p class="lede">{esc(lead["excerpt"])}</p>\n'
        '      <div class="byline">\n'
        f'        <span>By <strong>{esc(lead["_author"])}</strong></span>\n'
        '        <span class="sep">•</span>\n'
        f"        <span>{plain_date(d)}</span>\n"
        '        <span class="sep">•</span>\n'
        f'        <span>{lead["_readtime"]} min read</span>\n'
        "      </div>\n"
        f'      <a class="read-story" href="{h}">Read the lead story\n'
        '        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" '
        'stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>\n'
        "      </a>\n"
        "    </div>\n"
        "  </section>")


def home_analysis(pieces):
    out = ['<!-- Opinion band -->\n<section class="opinion-band" id="opinion">\n'
           '  <div class="wrap">\n    <h2 class="section-label">Opinion &amp; Analysis</h2>\n'
           '    <div class="op-grid">\n']
    for a in pieces:
        desk = DESKS[a["desk"]].replace("Lusaka Brief ", "")
        out.append(
            '      <div class="op-piece">\n'
            '        <span class="tag">Analysis</span>\n'
            f'        <h3>{esc(a["title"])}</h3>\n'
            f'        <p>{rich(a["body"].strip())}</p>\n'
            '        <div class="op-author">\n'
            '          <div class="avatar">LB</div>\n'
            f'          <div><div class="name">Lusaka Brief</div><div class="role">{desk}'
            '</div></div>\n'
            "        </div>\n"
            "      </div>\n")
    out.append("    </div>\n  </div>\n</section>")
    return "".join(out)


def update_home(html, ed, lead, stories, d, backfill=True):
    t = attr(lead["title"]) + " — Lusaka Brief"
    ex = attr(lead["excerpt"])
    html = sub_once(r"<title>.*?</title>", f"<title>{esc(lead['title'])} — Lusaka Brief</title>",
                    html, "<title>")
    html = sub_once(r'<meta name="description" content="[^"]*">',
                    f'<meta name="description" content="{ex}">', html, "meta description")
    html = sub_once(r'<meta property="og:title" content="[^"]*">',
                    f'<meta property="og:title" content="{t}">', html, "og:title")
    html = sub_once(r'<meta property="og:description" content="[^"]*">',
                    f'<meta property="og:description" content="{ex}">', html, "og:description")
    html = sub_once(r'<meta property="og:image" content="[^"]*">',
                    f'<meta property="og:image" content="{SITE}/assets/{lead["_image"]}">',
                    html, "og:image")
    html = update_topbar(html, ed, d)
    html = sub_once(r'<!-- Lead story -->\s*<section class="lead">.*?</section>',
                    home_lead(lead, d), html, "lead section")
    block = ("<!-- edition:sections -->\n"
             + home_sections(stories, d.isoformat(), lead["slug"], backfill)
             + "<!-- /edition:sections -->")
    if "<!-- edition:sections -->" in html:
        html = sub_once(r"<!-- edition:sections -->.*?<!-- /edition:sections -->", block, html,
                        "sections block")
    else:   # first run on a page last written by the old pipeline
        names = "|".join(SECTIONS)
        html = sub_once(rf'[ \t]*<!-- (?:{names}) -->\s*<h2 class="section-label" id="[a-z]+">'
                        r".*?(?=\n</main>)", block + "\n", html, "section grids")
    html = sub_once(r'<!-- Opinion band -->\s*<section class="opinion-band" id="opinion">'
                    r".*?</section>", home_analysis(ed["analysis"]), html, "opinion band")
    return html


def update_topbar(html, ed, d):
    html = sub_once(r'<span id="live-date">[^<]*</span>',
                    f'<span id="live-date">{long_date(d)}</span>', html, "live-date span")
    return sub_once(r'<span class="edition">.*?</span>',
                    f'<span class="edition">{d.strftime("%A")}: <strong>'
                    f'{esc(ed["strapline"])}</strong></span>', html, "edition strapline")


def archive_block(stories, note):
    srt = sorted(stories, key=lambda s: s["iso"], reverse=True)   # stable: keeps edition order
    months = {}
    for s in srt:
        months.setdefault(s["iso"][:7], []).append(s)
    keys = sorted(months, reverse=True)

    def name(k):
        return f"{MONTHS[int(k[5:]) - 1]} {k[:4]}"

    tabs = "".join(
        f'<button class="month-tab{" active" if i == 0 else ""}" data-month="{k}" '
        f"onclick=\"showMonth('{k}')\">{name(k)}"
        f'<span class="month-count">{len(months[k])}</span></button>'
        for i, k in enumerate(keys))
    panels = []
    for i, k in enumerate(keys):
        cards = "\n".join(
            '<article class="card">\n'
            f'<a href="{href(s)}"><img src="/assets/{s["image"]}" alt="" loading="lazy"></a>\n'
            f'<div class="card-body"><span class="tag">{esc(s["tag"])}</span>\n'
            f'<h3><a href="{href(s)}">{esc(s["title"])}</a></h3>\n'
            f'<p>{esc(s["excerpt"])}</p>\n'
            f'<div class="byline"><span>By <strong>{esc(s["author"])}</strong></span>'
            f'<span class="sep">•</span><span>{esc(s["date"])}</span></div>\n'
            "</div></article>\n" for s in months[k])
        panels.append(f'<div class="month-panel{" active" if i == 0 else ""}" id="month-{k}">'
                      f'<section class="grid-3">\n{cards}</section></div>')
    desc = ("The complete Lusaka Brief archive — every published story, organized by month. "
            + ", ".join(name(k) for k in keys[:-1])
            + (" and " if len(keys) > 1 else "") + name(keys[-1]) + ".")
    return (f'<div class="month-tabs">\n{tabs}\n</div>\n{note}\n' + "\n".join(panels) + "\n"), desc


def update_archive(html, stories, ed=None, d=None):
    m = re.search(r'<p class="archive-note">.*?</p>', html, re.S)
    block, desc = archive_block(stories, m.group(0) if m else "")
    html = sub_once(r'<div class="month-tabs">.*?(?=</main>)', block, html, "archive body")
    html = sub_once(r'<meta name="description" content="[^"]*">',
                    f'<meta name="description" content="{attr(desc)}">', html,
                    "archive description")
    if ed:
        html = update_topbar(html, ed, d)
    return html


def build_feed(stories, now):
    srt = [s for s in sorted(stories, key=lambda s: s["iso"], reverse=True)
           if not s.get("external")][:FEED_ITEMS]
    items, per_day = [], {}
    for s in srt:
        n = per_day.get(s["iso"], 0)
        per_day[s["iso"]] = n + 1
        d = dt.date.fromisoformat(s["iso"])
        # 06:00 CAT for the first story of a day, a minute earlier for each one after it,
        # so readers that sort by time keep the edition's running order.
        when = dt.datetime(d.year, d.month, d.day, 6, 0, tzinfo=TZ) - dt.timedelta(minutes=n)
        url = f"{SITE}/news/{s['slug']}/"
        items.append(
            "    <item>\n"
            f"      <title>{esc(s['title'])}</title>\n"
            f"      <link>{url}</link>\n"
            f'      <guid isPermaLink="true">{url}</guid>\n'
            f"      <pubDate>{email.utils.format_datetime(when)}</pubDate>\n"
            f"      <description>{esc(s['excerpt'])}</description>\n"
            f"      <category>{esc(s['section'])}</category>\n"
            "    </item>\n")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
            "  <channel>\n"
            "    <title>Lusaka Brief</title>\n"
            f"    <link>{SITE}/</link>\n"
            f'    <atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>\n'
            "    <description>Public-interest journalism for Zambia</description>\n"
            "    <language>en-zm</language>\n"
            f"    <lastBuildDate>{email.utils.format_datetime(now)}</lastBuildDate>\n"
            + "".join(items) + "  </channel>\n</rss>\n")


def build_sitemap(old, stories):
    locs = re.findall(r"<loc>([^<]+)</loc>", old)
    have = set(locs)
    # stories.json is newest edition first; the sitemap lists oldest first, each
    # edition in its running order. sorted() is stable, so that order is kept.
    for s in sorted(stories, key=lambda s: s["iso"]):
        if s.get("external"):
            continue
        u = f"{SITE}/news/{s['slug']}/"
        if u not in have:
            locs.append(u)
            have.add(u)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"  <url><loc>{esc(u)}</loc></url>\n" for u in locs) + "</urlset>\n")


# ---------------------------------------------------------------- commands
def cmd_status(args):
    stories = load_stories()
    d = today()
    done = [s for s in stories if s["iso"] == d.isoformat() and s["section"] in SECTIONS]
    try:
        num = next_edition_number(stories)
    except SystemExit:
        num = None
    recent = [s for s in stories if s["section"] in SECTIONS
              and s["iso"] >= (d - dt.timedelta(days=args.days)).isoformat()]
    info = {
        "today_in_lusaka": d.isoformat(),
        "weekday": d.strftime("%A"),
        "already_published_today": bool(done),
        "stories_published_today": len(done),
        "next_edition_number": num,
        "edition_file": f"tools/editions/{d.isoformat()}.json",
        "recent_stories": [{"date": s["iso"], "section": s["section"], "title": s["title"],
                            "slug": s["slug"]} for s in recent],
    }
    print(json.dumps(info, ensure_ascii=False, indent=1))


def cmd_build(args):
    import art
    ed = json.loads(read(args.edition))
    stories = load_stories()
    day = today()
    errs = validate(ed, stories, day, args.any_date, args.force)
    if errs:
        print(f"Edition rejected — {len(errs)} problem(s):", file=sys.stderr)
        for x in errs:
            print("  - " + x, file=sys.stderr)
        sys.exit(2)
    d = dt.date.fromisoformat(ed["date"])
    num = args.number or next_edition_number(stories)

    # lead first, then the running order as written
    order = sorted(ed["stories"], key=lambda s: not s.get("lead"))
    new = []
    for s in order:
        sec = s["section"]
        s["_tag"] = f"{sec} · Lead story" if s.get("lead") else s["tag"]
        s["_author"] = DESKS[sec]
        s["_image"] = f"ed{num}-{s['image']['key']}.webp"
        s["_alt"] = f"Illustration: {s['image']['label']}"
        cap = s["image"]["caption"].strip()
        s["_caption"] = cap if cap.lower().startswith("illustration") else "Illustration: " + cap
        s["_readtime"] = max(2, round(words(body_text(s)) / 220))
        new.append({"slug": s["slug"], "section": sec, "tag": s["_tag"], "title": s["title"],
                    "excerpt": s["excerpt"], "author": s["_author"], "date": plain_date(d),
                    "iso": d.isoformat(), "image": s["_image"], "edition": num,
                    "_alt": s["_alt"]})
    lead = order[0]

    # Render everything in memory first; only write if nothing fails.
    pages = {p("news", s["slug"], "index.html"): render_article(s, d) for s in order}
    allstories = new + stories
    home = update_home(read(p("index.html")), ed, lead, allstories, d, not args.no_backfill)
    clean = [{k: v for k, v in s.items() if not k.startswith("_")} for s in allstories]
    archive = update_archive(read(p("news", "index.html")), clean, ed, d)
    feed = build_feed(clean, dt.datetime.now(TZ).replace(microsecond=0))
    sitemap = build_sitemap(read(p("sitemap.xml")), clean)
    for name, doc in (("feed.xml", feed), ("sitemap.xml", sitemap)):
        xml.dom.minidom.parseString(doc.encode("utf-8"))    # raises if malformed

    if args.dry_run:
        print(f"OK — Edition No. {num} for {long_date(d)} validates ({len(order)} stories). "
              "Dry run: nothing written.")
        return
    for s in order:
        art.make(p("assets", s["_image"]), s["section"], s["image"]["label"],
                 s["image"].get("motif"), seed=s["slug"])
    for path, doc in pages.items():
        write(path, doc)
    write(p("assets", "stories.json"), dump_stories(clean))
    write(p("index.html"), home)
    write(p("news", "index.html"), archive)
    write(p("feed.xml"), feed)
    write(p("sitemap.xml"), sitemap)

    summary = "; ".join(s["title"] + (" (lead)" if s.get("lead") else "") for s in order)
    msg = f"Edition No. {num} — {long_date(d)}\n\n{len(order)} stories: {summary}.\n"
    write(os.path.join(HERE, ".commit-message"), msg)
    print(f"Published Edition No. {num} — {long_date(d)}: {len(order)} stories.")
    print("Commit message written to tools/.commit-message (use: git commit -F tools/.commit-message)")


def cmd_regen(args):
    stories = load_stories()
    write(p("news", "index.html"), update_archive(read(p("news", "index.html")), stories))
    write(p("feed.xml"), build_feed(stories, dt.datetime.now(TZ).replace(microsecond=0)))
    write(p("sitemap.xml"), build_sitemap(read(p("sitemap.xml")), stories))
    print("Rebuilt news/index.html, feed.xml and sitemap.xml from assets/stories.json.")


def cmd_check(args):
    stories = load_stories()
    probs = []
    slugs = [s["slug"] for s in stories]
    if len(slugs) != len(set(slugs)):
        probs.append("duplicate slugs in stories.json")
    for s in stories:
        for k in ("slug", "section", "tag", "title", "excerpt", "author", "date", "iso", "image"):
            if not s.get(k):
                probs.append(f"{s.get('slug')}: missing {k}")
        if not s.get("external") and not os.path.exists(p("news", s["slug"], "index.html")):
            probs.append(f"{s['slug']}: page missing")
        if s.get("image") and not os.path.exists(p("assets", s["image"])):
            probs.append(f"{s['slug']}: image assets/{s['image']} missing")
    home = read(p("index.html"))
    archive = read(p("news", "index.html"))
    for label, doc in (("index.html", home), ("news/index.html", archive)):
        for link in set(re.findall(r'href="/news/([a-z0-9-]+)/"', doc)):
            if not os.path.exists(p("news", link, "index.html")):
                probs.append(f"{label}: links to missing story {link}")
        for img in set(re.findall(r'src="/assets/([^"]+)"', doc)):
            if not os.path.exists(p("assets", img)):
                probs.append(f"{label}: missing image {img}")
    n_arch = len(re.findall(r'<article class="card">', archive))
    if n_arch != len(stories):
        probs.append(f"archive lists {n_arch} stories; stories.json has {len(stories)}")
    feed, sm = read(p("feed.xml")), read(p("sitemap.xml"))
    for name, doc in (("feed.xml", feed), ("sitemap.xml", sm)):
        try:
            xml.dom.minidom.parseString(doc.encode("utf-8"))
        except Exception as ex:
            probs.append(f"{name}: not well-formed XML ({ex})")
    for s in stories:
        if not s.get("external") and f"/news/{s['slug']}/</loc>" not in sm:
            probs.append(f"sitemap.xml: missing {s['slug']}")
    newest = max(s["iso"] for s in stories if s["section"] in SECTIONS)
    lead = re.search(r'<section class="lead">.*?href="/news/([a-z0-9-]+)/"', home, re.S)
    if not lead or lead.group(1) not in slugs:
        probs.append("index.html: lead story link not found in stories.json")
    elif next(s for s in stories if s["slug"] == lead.group(1))["iso"] != newest:
        probs.append("index.html: lead story is not from the newest edition")
    if re.search(r"\{[a-z_]+\}", "".join(
            read(p("news", s["slug"], "index.html")) for s in stories[:12]
            if not s.get("external"))):
        probs.append("an unfilled {placeholder} is present in a recent story page")
    if probs:
        print(f"{len(probs)} problem(s):")
        for x in probs[:60]:
            print("  - " + x)
        sys.exit(1)
    print(f"Site OK — {len(stories)} stories, newest edition {newest}.")


def main():
    ap = argparse.ArgumentParser(description="Lusaka Brief daily edition pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status", help="today's date, next edition number, recent stories")
    s.add_argument("--days", type=int, default=4, help="how many days of recent stories to list")
    s.set_defaults(fn=cmd_status)
    b = sub.add_parser("build", help="validate and publish an edition JSON")
    b.add_argument("edition")
    b.add_argument("--dry-run", action="store_true", help="validate only; write nothing")
    b.add_argument("--number", type=int, help="override the edition number")
    b.add_argument("--any-date", action="store_true", help="allow a date other than today")
    b.add_argument("--force", action="store_true", help="publish even if the date already has stories")
    b.add_argument("--no-backfill", action="store_true",
                   help="homepage section grids show only this edition's stories")
    b.set_defaults(fn=cmd_build)
    sub.add_parser("regen", help="rebuild archive, feed and sitemap").set_defaults(fn=cmd_regen)
    sub.add_parser("check", help="verify site consistency").set_defaults(fn=cmd_check)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
