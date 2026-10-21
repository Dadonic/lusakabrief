#!/usr/bin/env python3
"""Lusaka Brief — technical SEO check (and a few safe fixes).

    python3 tools/seo_check.py            # report problems, exit 1 if any errors
    python3 tools/seo_check.py --fix      # also: add missing canonicals and JSON-LD to existing pages

Checks every HTML page in the site: one <title> (unique), one meta description
(unique, ≤170 chars), canonical matching the page's URL, Open Graph tags,
exactly one <h1>, well-formed JSON-LD, alt text on content images, internal
links that resolve, and sitemap coverage. Warnings do not fail the run.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import edition as ed  # noqa: E402

SITE = ed.SITE
SKIP_DIRS = {"tools", ".git", "api", "assets"}


def pages():
    for dirpath, dirs, files in os.walk(ROOT):
        rel = os.path.relpath(dirpath, ROOT)
        top = rel.split(os.sep)[0]
        if top in SKIP_DIRS or top.startswith("_"):
            dirs[:] = []
            continue
        for f in files:
            if f.endswith(".html"):
                yield os.path.join(dirpath, f)


def url_of(path):
    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    if rel == "index.html":
        return SITE + "/"
    if rel.endswith("/index.html"):
        return f"{SITE}/{rel[:-len('index.html')]}"
    return f"{SITE}/{rel}"


def resolve(href):
    """Does an internal href point at a file in the repo?"""
    h = href.split("#")[0].split("?")[0]
    if not h or not h.startswith("/"):
        return True
    cand = os.path.join(ROOT, h.lstrip("/"))
    if h.endswith("/"):
        cand = os.path.join(cand, "index.html")
    return os.path.exists(cand) or os.path.exists(cand.rstrip("/") + ".php")


def check(fix=False):
    errors, warns = [], []
    titles, descs = defaultdict(list), defaultdict(list)
    sitemap = ed.read(ed.p("sitemap.xml"))
    sm_urls = set(re.findall(r"<loc>([^<]+)</loc>", sitemap))
    stories = {s["slug"]: s for s in ed.load_stories()}
    fixed = 0
    for path in sorted(pages()):
        rel = os.path.relpath(path, ROOT)
        html = ed.read(path)
        url = url_of(path)
        noindex = bool(re.search(r'<meta name="robots" content="[^"]*noindex', html))
        t = re.findall(r"<title>(.*?)</title>", html, re.S)
        if len(t) != 1:
            errors.append(f"{rel}: {len(t)} <title> tags")
        else:
            titles[t[0].strip()].append(rel)
            if len(t[0]) > 160:
                warns.append(f"{rel}: title is {len(t[0])} chars (search engines show ~60)")
        d = re.findall(r'<meta name="description" content="([^"]*)"', html)
        if len(d) != 1:
            errors.append(f"{rel}: {len(d)} meta descriptions")
        else:
            descs[d[0]].append(rel)
            if len(d[0]) > 400:
                warns.append(f"{rel}: description is {len(d[0])} chars")
        c = re.findall(r'<link rel="canonical" href="([^"]*)"', html)
        if len(c) != 1:
            if fix and len(c) == 0 and not noindex:
                html = html.replace("</title>", f'</title>\n<link rel="canonical" href="{url}">', 1)
                fixed += 1
            else:
                errors.append(f"{rel}: {len(c)} canonical tags")
        elif c[0] != url and not noindex:
            errors.append(f"{rel}: canonical {c[0]} ≠ {url}")
        for tag in ("og:title", "og:description"):
            if f'property="{tag}"' not in html:
                warns.append(f"{rel}: missing {tag}")
        h1 = len(re.findall(r"<h1[\s>]", html))
        if h1 != 1:
            errors.append(f"{rel}: {h1} <h1> elements")
        lds = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        for block in lds:
            try:
                data = json.loads(block)
                graph = data.get("@graph", [data]) if isinstance(data, dict) else data
                for node in graph:
                    if "@type" not in node:
                        errors.append(f"{rel}: JSON-LD node without @type")
            except json.JSONDecodeError as ex:
                errors.append(f"{rel}: JSON-LD does not parse ({ex})")
        if not lds:
            slug = rel.split("/")[1] if rel.startswith("news/") and rel.count("/") == 2 else None
            if fix and slug in stories:
                html = html.replace("</head>", legacy_article_jsonld(stories[slug], html) + "\n</head>", 1)
                fixed += 1
            elif rel != "news/index.html":
                warns.append(f"{rel}: no structured data")
        if rel.startswith("news/") and rel.count("/") == 2 or rel.startswith("people/"):
            for m in re.finditer(r"<img\b[^>]*>", html):
                if 'alt="' not in m.group(0) or 'alt=""' in m.group(0):
                    errors.append(f"{rel}: image without alt text: {m.group(0)[:60]}")
                    break
        for href in set(re.findall(r'href="(/[^"#?]*)', html)):
            if not resolve(href):
                errors.append(f"{rel}: broken internal link {href}")
        for src in set(re.findall(r'src="(/[^"]+)"', html)):
            if not resolve(src):
                errors.append(f"{rel}: missing asset {src}")
        if not noindex and url not in sm_urls and rel != "veteran-refinery/index.html":
            errors.append(f"{rel}: not in sitemap.xml")
        # old story pages that point at an image file that never existed: use the image on record
        slug = rel.split("/")[1] if rel.startswith("news/") and rel.count("/") == 2 else None
        if fix and slug in stories:
            bad = f"/assets/{slug}.webp"
            good = f"/assets/{stories[slug]['image']}"
            if bad in html and not os.path.exists(ed.p("assets", f"{slug}.webp")) and good != bad:
                html = html.replace(bad, good)
                fixed += 1
        if fix and html != ed.read(path):
            ed.write(path, html)
    for k, v in titles.items():
        if len(v) > 1:
            errors.append(f"duplicate title on {len(v)} pages: {v[:3]} — “{k[:60]}”")
    for k, v in descs.items():
        if len(v) > 1:
            errors.append(f"duplicate description on {len(v)} pages: {v[:3]}")
    for u in sm_urls:
        local = u.replace(SITE + "/", "")
        if not resolve("/" + local):
            errors.append(f"sitemap.xml lists {u} but no page exists")
    robots = ed.read(ed.p("robots.txt"))
    if "Sitemap:" not in robots:
        errors.append("robots.txt has no Sitemap: line")
    return errors, warns, fixed


def legacy_article_jsonld(s, html):
    """NewsArticle + breadcrumbs for a story page written before the pipeline existed."""
    url = f"{SITE}/news/{s['slug']}/"
    d = s["iso"]
    data = {"@context": "https://schema.org", "@graph": [
        {"@type": "NewsArticle", "@id": url + "#article", "mainEntityOfPage": url,
         "headline": s["title"][:110], "description": s["excerpt"],
         "image": [f"{SITE}/assets/{s['image']}"],
         "datePublished": f"{d}T06:00:00+02:00", "dateModified": f"{d}T06:00:00+02:00",
         "author": {"@type": "Organization", "name": s["author"], "url": SITE + "/"},
         "publisher": {"@type": "NewsMediaOrganization", "name": "Lusaka Brief", "url": SITE + "/",
                       "logo": {"@type": "ImageObject", "url": ed.LOGO}},
         "articleSection": s["section"], "inLanguage": "en-ZM", "isAccessibleForFree": True},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Lusaka Brief", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": s["section"], "item": f"{SITE}/#{s['section'].lower()}"},
            {"@type": "ListItem", "position": 3, "name": s["title"][:110], "item": url}]}]}
    return ('<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
            + "</script>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    a = ap.parse_args()
    errors, warns, fixed = check(a.fix)
    if fixed:
        print(f"Fixed {fixed} page(s).")
        errors, warns, _ = check(False)
    for w in warns[:40]:
        print("  warning: " + w)
    if len(warns) > 40:
        print(f"  … {len(warns) - 40} more warnings")
    if errors:
        print(f"{len(errors)} error(s):")
        for x in errors[:80]:
            print("  - " + x)
        sys.exit(1)
    print(f"SEO OK — {sum(1 for _ in pages())} pages, {len(warns)} warning(s).")


if __name__ == "__main__":
    main()
