#!/usr/bin/env python3
"""One-off, re-runnable site repairs (October 2026).

  1. Withdraw the Veteran Refinery "developing report": the page becomes a short
     withdrawal notice (noindex) and every link to it is removed.
  2. Replace invented reporter names with desk bylines everywhere.
  3. Replace the footer claim that parties are "contacted for comment" with an
     accurate description of how stories are produced.
  4. Remove placeholder social links that point at x.com / facebook.com / instagram.com.

Idempotent: safe to run again.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import edition as ed  # noqa: E402

NAMES = {
    "Chanda Mwape": "Politics", "Natasha Banda": "Economy", "Mwelwa Phiri": "Sport",
}
FOOTER_OLD = [
    "Claims are attributed to named sources, and parties mentioned in our reporting are contacted for comment.",
    "Claims are attributed, and parties named are contacted for comment.",
    "Claims are attributed, and parties named in our reporting are contacted for comment.",
    "Claims are attributed to their sources, and parties named in our reporting are contacted for comment. Photographs are credited and illustrative material is labelled as such.",
]
FOOTER_NEW = ("Stories are compiled from published reporting and official sources, which are listed and "
              "linked at the foot of each article; we do not conduct interviews. Illustrations are "
              "labelled as such.")
WITHDRAWN = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Report withdrawn — Lusaka Brief</title>
<meta name="description" content="This developing report has been withdrawn.">
<meta name="robots" content="noindex,nofollow">
<link rel="canonical" href="https://lusakabrief.com/veteran-refinery/">
<link rel="icon" type="image/svg+xml" href="/assets/lusaka-brief-mark.svg">
<link rel="stylesheet" href="/assets/site.css">
</head>
<body>
<header class="masthead"><div class="masthead-inner">
<img class="brand-mark" src="/assets/lusaka-brief-mark.svg" alt="Lusaka Brief eagle mark">
<div><a class="brand-word" href="/">LUSAKA <span>BRIEF</span></a><div class="brand-tag">Public-interest journalism for Zambia</div></div>
</div></header>
<main class="wrap"><div class="article-head" style="padding:48px 0 80px">
<span class="kicker" style="color:var(--copper)">Notice</span>
<h1>This report has been withdrawn</h1>
<p class="standfirst">The developing report that appeared at this address, published on 3 September 2026, has been withdrawn by the editors because its claims could not be substantiated to our standards. We apologise to anyone affected.</p>
<p><a class="back-link" href="/">← Back to the front page</a></p>
</div></main>
<footer class="footer"><div class="copyright">© 2026 Lusaka Brief · Lusaka, Zambia</div></footer>
</body>
</html>
"""


def html_files():
    for dp, dn, fn in os.walk(ROOT):
        if any(x in dp for x in ("/.git", "/tools")):
            continue
        for f in fn:
            if f.endswith(".html"):
                yield os.path.join(dp, f)


def main():
    changed = 0
    # 1. withdraw the page
    ed.write(ed.p("veteran-refinery", "index.html"), WITHDRAWN)
    stories = ed.load_stories()
    stories = [s for s in stories if s.get("external") != "/veteran-refinery/"]
    # 2. desk bylines in the record
    by_slug = {}
    for s in stories:
        if s["author"] in NAMES:
            s["author"] = ed.DESKS.get(s["section"], "Lusaka Brief Newsroom")
        by_slug[s["slug"]] = s
    ed.write(ed.p("assets", "stories.json"), ed.dump_stories(stories))

    for path in html_files():
        rel = os.path.relpath(path, ROOT)
        if rel == "veteran-refinery/index.html":
            continue
        html = orig = ed.read(path)
        # nav links and archive card
        html = re.sub(r'\s*<a href="/veteran-refinery/">Developing Report</a>', "", html)
        html = re.sub(r'<article class="card">\s*<a href="/veteran-refinery/">.*?</article>\s*', "", html, flags=re.S)
        # bylines: use the story's section desk where we know it, else by name
        slug = rel.split("/")[1] if rel.startswith("news/") and rel.count("/") == 2 else None
        for name, sec in NAMES.items():
            desk = ed.DESKS.get(by_slug[slug]["section"], "Lusaka Brief Newsroom") if slug in by_slug else ed.DESKS[sec]
            html = html.replace(f"By <strong>{name}</strong>", f"By <strong>{desk}</strong>")
            html = html.replace(f'"name": "{name}"', f'"name": "{desk}"')
        # home page opinion-band authors and avatars from the old pipeline
        html = re.sub(r'<div class="avatar">(CM|NB|MP)</div>\s*<div><div class="name">(Chanda Mwape|Natasha Banda|Mwelwa Phiri)</div><div class="role">([^<]*)</div></div>',
                      lambda m: '<div class="avatar">LB</div>\n          <div><div class="name">Lusaka Brief</div><div class="role">'
                      + {"Chanda Mwape": "Politics Desk", "Natasha Banda": "Business Desk", "Mwelwa Phiri": "Investigations Desk"}[m.group(2)]
                      + "</div></div>", html)
        for old in FOOTER_OLD:
            html = html.replace(old, FOOTER_NEW)
        # placeholder social links
        html = re.sub(r'\s*<a href="https://(x|facebook|instagram)\.com" aria-label="[^"]*" rel="noopener">\s*<svg.*?</svg>\s*</a>',
                      "", html, flags=re.S)
        if html != orig:
            ed.write(path, html)
            changed += 1
    # archive month counts and feed/sitemap follow stories.json
    ed.write(ed.p("news", "index.html"), ed.update_archive(ed.read(ed.p("news", "index.html")), stories))
    sm = ed.read(ed.p("sitemap.xml")).replace("  <url><loc>https://lusakabrief.com/veteran-refinery/</loc></url>\n", "")
    ed.write(ed.p("sitemap.xml"), ed.build_sitemap(sm, stories))
    ed.write(ed.p("feed.xml"), ed.build_feed(stories, ed.dt.datetime.now(ed.TZ).replace(microsecond=0)))
    print(f"{changed} pages changed; {len(stories)} stories on record.")


if __name__ == "__main__":
    main()
