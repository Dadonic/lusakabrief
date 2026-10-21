#!/usr/bin/env python3
"""Lusaka Brief — person profile pages.

    python3 tools/profile.py new    <slug>            # start tools/people/<slug>.json from the template
    python3 tools/profile.py check  <slug>            # validate the profile file
    python3 tools/profile.py media  <slug>            # convert tools/people/media/<slug>/* to assets/people/<slug>/*.webp
    python3 tools/profile.py preview <slug> OUT.html  # render anywhere (noindex), published or not
    python3 tools/profile.py build  <slug>            # write people/<slug>/index.html, people/index.html, sitemap
    python3 tools/profile.py build --all

A profile is a single JSON file in tools/people/. Every fact in it can carry a
source and a verification flag, and the page shows which is which. Nothing is
written to the live site unless "published" is true and the file validates.
See tools/people/README.md.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import edition as ed  # noqa: E402  (shared helpers, constants, sitemap)

PEOPLE = os.path.join(HERE, "people")
SITE = ed.SITE
esc, attr, rich = ed.esc, ed.attr, ed.rich
KIND_GROUPS = [
    ("report", "Reporting by Lusaka Brief"), ("feature", "Features"),
    ("interview", "Interviews"), ("project-update", "Project updates"),
    ("press-release", "Press releases"), ("supplied", "Supplied content"),
    ("opinion", "Opinion"),
]
EXTERNAL_KINDS = {"independent": "Independent coverage", "interview": "Interview",
                  "press-release": "Press release", "profile": "Profile",
                  "sponsored": "Sponsored"}
STATUSES = ("Planned", "Ongoing", "Completed")
RELATIONSHIP_TEXT = {
    "owner": "{name} owns Lusaka Brief.",
    "commissioned": "{name} commissioned this profile and the coverage labelled as supplied.",
    "sponsor": "{name}'s organisation sponsors content on Lusaka Brief.",
    "partner": "{name}'s organisation is a partner of Lusaka Brief.",
    "none": "Lusaka Brief has no commercial relationship with {name}.",
}


# ---------------------------------------------------------------- helpers
def path(slug):
    return os.path.join(PEOPLE, f"{slug}.json")


def load(slug):
    return json.loads(ed.read(path(slug)))


def month(s):
    """'2024-03' -> 'March 2024'; '2024-03-15' -> '15 March 2024'; '2024' -> '2024'."""
    if not s:
        return ""
    parts = s.split("-")
    if len(parts) == 1:
        return parts[0]
    m = ed.MONTHS[int(parts[1]) - 1]
    return f"{int(parts[2])} {m} {parts[0]}" if len(parts) == 3 else f"{m} {parts[0]}"


def vtag(item, default_sub=True):
    """Verification tag for any item with optional 'source' and 'verified'."""
    src = item.get("source") if isinstance(item, dict) else None
    if src and item.get("verified"):
        inner = f"Verified · {esc(src.get('publisher') or src.get('title') or 'source')}"
        cls = "ok"
    elif src:
        inner = f"Source · {esc(src.get('publisher') or src.get('title') or 'cited')}"
        cls = "src"
    elif default_sub:
        return '<span class="vtag sub" title="Stated by the subject; not independently verified">Supplied by the subject</span>'
    else:
        return ""
    if src.get("url"):
        return f'<a class="vtag {cls}" href="{attr(src["url"])}" rel="noopener" target="_blank">{inner}</a>'
    return f'<span class="vtag {cls}">{inner}</span>'


def img_url(slug, f):
    return f if f.startswith("/") else f"/assets/people/{slug}/{f}"


# ---------------------------------------------------------------- validation
def validate(pr):
    errs = []
    e = errs.append
    slug = pr.get("slug", "")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
        e("slug must be lowercase-kebab-case")
    for k in ("name", "title", "location", "intro"):
        if not pr.get(k) or not isinstance(pr[k], str):
            e(f"'{k}' is required")
    if pr.get("relationship") not in ed.RELATIONSHIP:
        e(f"'relationship' must be one of {', '.join(ed.RELATIONSHIP)}")
    if not 80 <= len(pr.get("intro", "")) <= 600:
        e("'intro' must be 80–600 characters")
    if not isinstance(pr.get("biography"), list) or not pr["biography"]:
        e("'biography' must be a non-empty list of paragraphs")
    for key in ("biography", "background"):
        for para in pr.get(key) or []:
            if "<" in para:
                e(f"'{key}' paragraphs are plain text (no HTML)")
    for k in ("published", "consent_confirmed"):
        if k in pr and not isinstance(pr[k], bool):
            e(f"'{k}' must be true or false")
    if pr.get("published") and not pr.get("consent_confirmed"):
        e("a published profile needs \"consent_confirmed\": true — the subject or an authorised "
          "representative has approved the text, photographs and contact details")
    if pr.get("published") and not re.fullmatch(r"\d{4}-\d\d-\d\d", pr.get("updated", "")):
        e("'updated' must be YYYY-MM-DD")
    for i, a in enumerate(pr.get("affiliations") or []):
        if not a.get("name"):
            e(f"affiliation {i + 1}: name required")
    for i, proj in enumerate(pr.get("projects") or []):
        w = f"project {i + 1} ({proj.get('title', '?')[:30]})"
        for k in ("title", "summary", "status"):
            if not proj.get(k):
                e(f"{w}: '{k}' required")
        if proj.get("status") not in STATUSES:
            e(f"{w}: status must be one of {', '.join(STATUSES)}")
        if proj.get("status") == "Completed" and not proj.get("end"):
            e(f"{w}: a Completed project needs an 'end' date")
        if proj.get("status") != "Completed" and proj.get("outcomes"):
            for o in proj["outcomes"]:
                if isinstance(o, dict) and o.get("verified") and proj.get("status") == "Planned":
                    e(f"{w}: a Planned project cannot have verified outcomes")
        for im in proj.get("images") or []:
            if not (im.get("file") and im.get("alt")):
                e(f"{w}: every image needs 'file' and 'alt'")
            if im.get("people_shown") and not im.get("consent"):
                e(f"{w}: image {im.get('file')} shows identifiable people and needs \"consent\": true")
    for i, m in enumerate(pr.get("milestones") or []):
        if not (m.get("date") and m.get("title")):
            e(f"milestone {i + 1}: 'date' and 'title' required")
        elif not re.fullmatch(r"\d{4}(-\d\d){0,2}", m["date"]):
            e(f"milestone {i + 1}: date must be YYYY, YYYY-MM or YYYY-MM-DD")
    for i, r in enumerate(pr.get("recognition") or []):
        if not r.get("verified") or not (r.get("source") or {}).get("url"):
            e(f"recognition {i + 1} ({r.get('title', '?')[:30]}): awards are listed only with "
              "\"verified\": true and a source url — otherwise leave them out")
    for i, c in enumerate(pr.get("coverage_external") or []):
        if not (c.get("outlet") and c.get("title") and c.get("date")
                and re.match(r"https?://", c.get("url", ""))):
            e(f"external coverage {i + 1}: outlet, title, date and url required")
        if c.get("kind", "independent") not in EXTERNAL_KINDS:
            e(f"external coverage {i + 1}: kind must be one of {', '.join(EXTERNAL_KINDS)}")
    for i, g in enumerate(pr.get("gallery") or []):
        if not (g.get("file") and g.get("alt")):
            e(f"gallery {i + 1}: 'file' and 'alt' required")
        if g.get("people_shown") and not g.get("consent"):
            e(f"gallery {i + 1}: {g.get('file')} shows identifiable people and needs \"consent\": true")
    for k, u in (pr.get("links") or {}).items():
        if u and not re.match(r"https://", u):
            e(f"links.{k} must be an https url")
    if pr.get("portrait") and not pr["portrait"].get("file"):
        e("'portrait' needs 'file'")
    # all referenced images must exist
    adir = os.path.join(ROOT, "assets", "people", slug)
    refs = [pr["portrait"]["file"]] if pr.get("portrait", {}).get("file") else []
    refs += [g["file"] for g in pr.get("gallery") or [] if g.get("file")]
    refs += [im["file"] for pj in pr.get("projects") or [] for im in pj.get("images") or [] if im.get("file")]
    refs += [m["image"] for m in pr.get("milestones") or [] if m.get("image")]
    for f in refs:
        if not f.startswith("/") and not os.path.exists(os.path.join(adir, f)):
            e(f"image assets/people/{slug}/{f} is missing (run: profile.py media {slug})")
    low = " ".join(pr.get("biography") or []).lower()
    for phrase in ed.BANNED:
        if phrase in low:
            e(f"biography: remove \"{phrase}\"")
    return errs


# ---------------------------------------------------------------- rendering
def coverage_items(pr, stories):
    out = []
    for s in stories:
        if pr["slug"] in (s.get("people") or []):
            out.append({"date": s["iso"], "title": s["title"], "url": f"/news/{s['slug']}/",
                        "kind": s.get("kind", "report"), "by": s["author"], "own": True,
                        "excerpt": s["excerpt"]})
    for c in pr.get("coverage_external") or []:
        out.append({"date": c["date"], "title": c["title"], "url": c["url"],
                    "kind": c.get("kind", "independent"), "by": c["outlet"], "own": False})
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def render_coverage(items):
    if not items:
        return ""
    lis = []
    for it in items:
        if it["own"]:
            label = dict(KIND_GROUPS).get(it["kind"], "Reporting by Lusaka Brief")
            cls = "ok" if it["kind"] in ("report", "feature") else "sub"
            where = f"Lusaka Brief · {esc(it['by'])}"
        else:
            label = EXTERNAL_KINDS.get(it["kind"], "Independent coverage")
            cls = "ok" if it["kind"] == "independent" else "src"
            where = esc(it["by"])
        ext = '' if it["own"] else ' rel="noopener" target="_blank"'
        lis.append(
            f'<li><span class="c-date">{esc(month(it["date"]))}</span><div>'
            f'<a class="c-title" href="{attr(it["url"])}"{ext}>{esc(it["title"])}</a>'
            f'<div class="c-meta"><span class="vtag {cls}">{esc(label)}</span>{where}</div></div></li>')
    return "\n".join(lis)


def render_projects(pr):
    out = []
    for pj in pr.get("projects") or []:
        if pj.get("public") is False:
            continue
        st = pj["status"]
        meta = []
        if pj.get("cause"):
            meta.append(esc(pj["cause"]))
        if pj.get("location"):
            meta.append(esc(pj["location"]))
        span = " – ".join(x for x in (month(pj.get("start")), month(pj.get("end")) or
                                      ("present" if st == "Ongoing" else "")) if x)
        if span:
            meta.append(span)
        if pj.get("organisations"):
            meta.append("With " + esc(", ".join(pj["organisations"])))
        parts = [f'<article class="project" id="project-{pj.get("id") or ed.re.sub(r"[^a-z0-9]+", "-", pj["title"].lower())[:40]}">',
                 f'<div class="project-head"><h3>{esc(pj["title"])}</h3>'
                 f'<span class="status {st.lower()}">{st}</span></div>',
                 f'<p class="project-meta">{"".join(f"<span>{m}</span>" for m in meta)}</p>',
                 f"<p>{rich(pj['summary'])}</p>"]
        if pj.get("activities"):
            parts.append('<div class="label">What was done</div><ul>' + "".join(
                f"<li>{rich(a['text']) if isinstance(a, dict) else rich(a)} "
                f"{vtag(a, False) if isinstance(a, dict) else ''}</li>" for a in pj["activities"]) + "</ul>")
        if pj.get("outcomes"):
            head = "Documented outcomes" if st == "Completed" else "Outcomes so far" if st == "Ongoing" else "Intended outcomes"
            parts.append(f'<div class="label">{head}</div><ul>' + "".join(
                f"<li>{rich(o['text']) if isinstance(o, dict) else rich(o)} "
                f"{vtag(o) if isinstance(o, dict) else vtag({})}</li>" for o in pj["outcomes"]) + "</ul>")
        if pj.get("images"):
            parts.append('<div class="project-images">' + "".join(
                f'<img src="{attr(img_url(pr["slug"], im["file"]))}" alt="{attr(im["alt"])}" loading="lazy" '
                f'title="{attr(im.get("caption", ""))}">' for im in pj["images"]) + "</div>")
        if pj.get("evidence"):
            parts.append('<p class="evidence"><strong>Supporting documentation:</strong> ' + "; ".join(
                f'<a href="{attr(ev["url"])}" rel="noopener" target="_blank">{esc(ev.get("publisher") or ev.get("title"))}</a>'
                + (f", {esc(ev['title'])}" if ev.get("publisher") and ev.get("title") else "")
                + (f" ({esc(ev['date'])})" if ev.get("date") else "")
                for ev in pj["evidence"]) + ".</p>")
        parts.append("</article>")
        out.append("\n".join(parts))
    return "\n".join(out)


def render_facts(items, fields):
    lis = []
    for it in items or []:
        main = esc(it.get(fields[0], ""))
        sub = " · ".join(esc(str(it[f])) for f in fields[1:] if it.get(f))
        lis.append(f'<li>{main} {vtag(it)}' + (f'<span class="f-sub">{sub}</span>' if sub else "") + "</li>")
    return f'<ul class="fact-list">{"".join(lis)}</ul>' if lis else ""


def render_milestones(pr, stories_by_slug):
    lis = []
    for m in sorted(pr.get("milestones") or [], key=lambda x: x["date"], reverse=True):
        body = f"<p>{rich(m['description'])}</p>" if m.get("description") else ""
        if m.get("image"):
            body += f'<img src="{attr(img_url(pr["slug"], m["image"]))}" alt="{attr(m.get("alt", m["title"]))}" loading="lazy">'
        link = ""
        if m.get("story") and m["story"] in stories_by_slug:
            link = f'<p><a href="/news/{m["story"]}/" style="color:var(--green)">Read the story →</a></p>'
        lis.append(f'<li><span class="m-date">{esc(month(m["date"]))}</span><div>'
                   f'<div class="m-title">{esc(m["title"])} {vtag(m)}</div>{body}{link}</div></li>')
    return "\n".join(lis)


def render_gallery(pr):
    figs = []
    for g in pr.get("gallery") or []:
        cap = esc(g.get("caption", ""))
        if g.get("credit"):
            cap += f" <em>Photo: {esc(g['credit'])}</em>"
        figs.append(f'<figure><img src="{attr(img_url(pr["slug"], g["file"]))}" alt="{attr(g["alt"])}" '
                    f'loading="lazy"><figcaption>{cap}</figcaption></figure>')
    return "\n".join(figs)


def jsonld(pr, coverage):
    slug = pr["slug"]
    url = f"{SITE}/people/{slug}/"
    person = {
        "@type": "Person", "@id": url + "#person", "name": pr["name"], "url": url,
        "jobTitle": pr["title"], "description": pr["intro"],
        "address": {"@type": "PostalAddress",
                    "addressLocality": pr["location"].split(",")[0].strip(), "addressCountry": "ZM"},
    }
    names = [n for n in [pr.get("preferred_name")] + (pr.get("name_variants") or []) if n and n != pr["name"]]
    if names:
        person["alternateName"] = names
    if pr.get("portrait", {}).get("file"):
        person["image"] = SITE + img_url(slug, pr["portrait"]["file"])
    same = [u for u in (pr.get("links") or {}).values() if u]
    if same:
        person["sameAs"] = same
    aff = [{"@type": "Organization", "name": a["name"], **({"url": a["url"]} if a.get("url") else {})}
           for a in pr.get("affiliations") or [] if a.get("verified")]
    if aff:
        person["affiliation"] = aff
    if pr.get("causes"):
        person["knowsAbout"] = pr["causes"]
    awards = [r["title"] for r in pr.get("recognition") or [] if r.get("verified")]
    if awards:
        person["award"] = awards
    alumni = [{"@type": "EducationalOrganization", "name": x["institution"]}
              for x in pr.get("education") or [] if x.get("verified") and x.get("institution")]
    if alumni:
        person["alumniOf"] = alumni
    subject_of = [{"@type": "Article", "url": (SITE + c["url"]) if c["own"] else c["url"],
                   "headline": c["title"][:110]} for c in coverage[:10]]
    if subject_of:
        person["subjectOf"] = subject_of
    page = {
        "@type": "ProfilePage", "@id": url, "url": url, "name": f"{pr['name']} — Lusaka Brief",
        "dateModified": pr.get("updated", dt.date.today().isoformat()),
        "mainEntity": {"@id": url + "#person"}, "inLanguage": "en-ZM",
        "publisher": {"@type": "NewsMediaOrganization", "name": "Lusaka Brief", "url": SITE + "/"},
    }
    if pr.get("created"):
        page["dateCreated"] = pr["created"]
    crumbs = {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Lusaka Brief", "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": "People", "item": SITE + "/people/"},
        {"@type": "ListItem", "position": 3, "name": pr["name"], "item": url}]}
    data = {"@context": "https://schema.org", "@graph": [page, person, crumbs]}
    return json.dumps(data, ensure_ascii=False, indent=1).replace("</", "<\\/")


def chrome(title, desc, canonical, body, extra_head="", noindex=False, og_image=None, og_type="profile"):
    """Standard page shell shared with the rest of the site."""
    robots = '<meta name="robots" content="noindex,nofollow">\n' if noindex else ""
    og_img = f'<meta property="og:image" content="{attr(og_image)}">\n' if og_image else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{attr(desc)}">
{robots}<link rel="canonical" href="{attr(canonical)}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="Lusaka Brief">
<meta property="og:title" content="{attr(title)}">
<meta property="og:description" content="{attr(desc)}">
<meta property="og:url" content="{attr(canonical)}">
{og_img}<meta property="og:locale" content="en_ZM">
<meta name="twitter:card" content="{'summary_large_image' if og_image else 'summary'}">
<link rel="alternate" type="application/rss+xml" title="Lusaka Brief" href="/feed.xml">
<link rel="icon" type="image/svg+xml" href="/assets/lusaka-brief-mark.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400..900;1,9..144,400..700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/site.css">
<link rel="stylesheet" href="/assets/people.css">
{extra_head}
</head>
<body>

<div class="topbar">
  <div class="topbar-inner">
    <span class="dateline">Lusaka, Zambia — <span id="live-date"></span> · <span id="live-clock" style="font-variant-numeric:tabular-nums;font-weight:600"></span></span>
    <span class="edition">People: <strong>Profiles of Zambians in public life</strong></span>
  </div>
</div>

<header class="masthead">
  <div class="masthead-inner">
    <img class="brand-mark" src="/assets/lusaka-brief-mark.svg" alt="Lusaka Brief eagle mark">
    <div>
      <a class="brand-word" href="/">LUSAKA <span>BRIEF</span></a>
      <div class="brand-tag">Public-interest journalism for Zambia</div>
    </div>
  </div>
</header>

<nav class="navbar">
  <div class="nav-inner">
    <a href="/">Latest</a>
    <a href="/#politics">Politics</a>
    <a href="/#economy">Economy</a>
    <a href="/#sport">Sport</a>
    <a href="/#culture">Culture</a>
    <a href="/#explained">Explained</a>
    <a href="/people/" class="active">People</a>
    <a href="/news/">Archive</a>
    <a href="/wire/">Wire</a>
  </div>
</nav>

<main class="wrap">
{body}
</main>

<footer class="footer">
  <div class="footer-inner">
    <div class="footer-brand">
      <img class="brand-mark" src="/assets/lusaka-brief-mark.svg" alt="Lusaka Brief eagle mark">
      <div>
        <div class="fname">LUSAKA <span>BRIEF</span></div>
        <p>Independent public-interest journalism from Lusaka, Zambia.</p>
      </div>
    </div>
    <p class="footer-note"><strong>About profiles.</strong> Profile pages are compiled from documents and statements supplied by the subject and from published sources. Each fact is tagged to show whether it was independently verified, cited to a source, or supplied by the subject. Corrections: <a href="mailto:newsroom@lusakabrief.com" style="color:inherit">newsroom@lusakabrief.com</a>.</p>
  </div>
  <div class="copyright">© {dt.date.today().year} Lusaka Brief · Lusaka, Zambia · All rights reserved</div>
</footer>
<script>
(function(){{function tick(){{try{{var now=new Date();var d=now.toLocaleDateString('en-GB',{{timeZone:'Africa/Lusaka',weekday:'long',day:'numeric',month:'long',year:'numeric'}});var t=now.toLocaleTimeString('en-GB',{{timeZone:'Africa/Lusaka',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}});var de=document.getElementById('live-date');var ce=document.getElementById('live-clock');if(de)de.textContent=d;if(ce)ce.textContent=t+' CAT';}}catch(e){{}}}}tick();setInterval(tick,1000);}})();
</script>
</body>
</html>
"""


def render_profile(pr, stories, noindex=False):
    slug = pr["slug"]
    url = f"{SITE}/people/{slug}/"
    name = pr["name"]
    short = pr.get("preferred_name") or name.split()[0]
    cov = coverage_items(pr, stories)
    by_slug = {s["slug"]: s for s in stories}
    portrait = pr.get("portrait") or {}
    if portrait.get("file"):
        port = (f'<figure class="profile-portrait"><img src="{attr(img_url(slug, portrait["file"]))}" '
                f'alt="{attr(portrait.get("alt", name))}" width="800" height="1000">'
                + (f'<figcaption>{esc(portrait.get("caption", ""))}'
                   + (f" <em>Photo: {esc(portrait['credit'])}</em>" if portrait.get("credit") else "")
                   + "</figcaption>" if portrait.get("caption") or portrait.get("credit") else "")
                + "</figure>")
    else:
        initials = "".join(w[0] for w in name.split()[:2]).upper()
        port = f'<div class="profile-portrait"><div class="no-photo" aria-hidden="true">{initials}</div></div>'

    rel_text = RELATIONSHIP_TEXT[pr.get("relationship", "none")].format(name=short)
    if pr.get("disclosure"):
        rel_text = pr["disclosure"]

    # --- rail
    links = pr.get("links") or {}
    link_names = {"website": "Website", "linkedin": "LinkedIn", "x": "X", "facebook": "Facebook",
                  "instagram": "Instagram", "youtube": "YouTube", "wikipedia": "Wikipedia"}
    dl = [f"<dt>Role</dt><dd>{esc(pr['title'])}</dd>", f"<dt>Based in</dt><dd>{esc(pr['location'])}</dd>"]
    if pr.get("causes"):
        dl.append("<dt>Causes</dt><dd>" + esc(", ".join(pr["causes"])) + "</dd>")
    aff = [a for a in pr.get("affiliations") or [] if a.get("current", True)]
    if aff:
        dl.append("<dt>Affiliations</dt><dd>" + "<br>".join(
            (f'<a href="{attr(a["url"])}" rel="noopener" target="_blank">{esc(a["name"])}</a>' if a.get("url") else esc(a["name"]))
            + (f" — {esc(a['role'])}" if a.get("role") else "") for a in aff) + "</dd>")
    if any(links.values()):
        dl.append("<dt>Online</dt><dd>" + " · ".join(
            f'<a href="{attr(u)}" rel="me noopener" target="_blank">{link_names.get(k, k.title())}</a>'
            for k, u in links.items() if u) + "</dd>")
    mc = pr.get("media_contact") or {}
    if mc.get("email"):
        dl.append(f'<dt>Media enquiries</dt><dd><a href="mailto:{attr(mc["email"])}">{esc(mc["email"])}</a>'
                  + (f"<br>{esc(mc['note'])}" if mc.get("note") else "") + "</dd>")
    rail = (f'<div class="rail-box"><h3>At a glance</h3><dl>{"".join(dl)}</dl></div>\n'
            f'<div class="rail-box disclosure"><h3>Disclosure</h3><p>{esc(rel_text)}</p>'
            '<p>Facts on this page are tagged: <span class="vtag ok">Verified</span> means Lusaka Brief '
            'checked it against an independent source; <span class="vtag src">Source</span> means the subject '
            'provided a document or link we have not independently confirmed; '
            '<span class="vtag sub">Supplied by the subject</span> means it rests on the subject\'s own account.</p>'
            f'<p>Last updated {esc(month(pr.get("updated", "")))}. '
            'Something wrong? <a href="mailto:newsroom@lusakabrief.com">Tell the newsroom</a>.</p></div>')

    # --- main sections
    sections = []
    bio = "".join(f"<p>{rich(x)}</p>" for x in pr.get("biography") or [])
    sections.append(f'<section id="biography"><h2>Biography</h2>{bio}</section>')
    if pr.get("background"):
        sections.append('<section id="background"><h2>Professional background</h2>'
                        + "".join(f"<p>{rich(x)}</p>" for x in pr["background"]) + "</section>")
    proj = render_projects(pr)
    if proj or pr.get("causes"):
        chips = "".join(f'<span class="chip">{esc(c)}</span>' for c in pr.get("causes") or [])
        lead = f"<p>{rich(pr['philanthropy_intro'])}</p>" if pr.get("philanthropy_intro") else ""
        sections.append(f'<section id="philanthropy"><h2>Philanthropy and community work</h2>{lead}'
                        f'<div class="chips">{chips}</div>{proj}</section>')
    career = []
    if pr.get("career"):
        career.append("<h3>Milestones</h3>" + render_facts(pr["career"], ("title", "organisation", "period")))
    if pr.get("education"):
        career.append("<h3>Education and qualifications</h3>" + render_facts(pr["education"], ("qualification", "institution", "year")))
    if pr.get("recognition"):
        career.append("<h3>Recognition</h3>" + render_facts(pr["recognition"], ("title", "by", "year")))
    if pr.get("speaking"):
        career.append("<h3>Public speaking and interviews</h3>" + render_facts(pr["speaking"], ("title", "event", "date")))
    if pr.get("publications"):
        career.append("<h3>Published work</h3>" + render_facts(pr["publications"], ("title", "publisher", "date")))
    if career:
        sections.append('<section id="career"><h2>Career and achievements</h2>' + "".join(career) + "</section>")
    cov_html = render_coverage(cov)
    if cov_html:
        sections.append('<section id="coverage"><h2>News and coverage</h2>'
                        '<p style="font-size:14.5px;color:var(--muted)">Articles published by Lusaka Brief are '
                        'labelled by kind; independent reporting is distinguished from material supplied by '
                        'the subject. External links open the original publisher.</p>'
                        f'<ul class="coverage">{cov_html}</ul></section>')
    ms = render_milestones(pr, by_slug)
    if ms:
        sections.append(f'<section id="timeline"><h2>Timeline</h2><ul class="milestones">{ms}</ul></section>')
    gal = render_gallery(pr)
    if gal:
        sections.append(f'<section id="gallery"><h2>Gallery</h2><div class="gallery">{gal}</div></section>')

    body = f"""<nav class="crumbs" aria-label="Breadcrumb"><a href="/">Lusaka Brief</a><span>›</span><a href="/people/">People</a><span>›</span>{esc(name)}</nav>
<div class="profile-layout">
  <div class="profile-main">
<header class="profile-hero">
    <span class="kicker">Profile · {esc(pr.get('kicker') or 'People')}</span>
    <h1>{esc(name)}</h1>
    <p class="profile-role">{esc(pr['title'])} · {esc(pr['location'])}</p>
    <p class="profile-intro">{rich(pr['intro'])}</p>
</header>
{chr(10).join(sections)}
  </div>
  <aside class="profile-rail">
{port}
{rail}
  </aside>
</div>"""
    seo = pr.get("seo") or {}
    title = seo.get("title") or f"{name} — {pr['title']} | Lusaka Brief"
    desc = seo.get("description") or pr["intro"][:158]
    og_image = SITE + img_url(slug, portrait["file"]) if portrait.get("file") else None
    head = f'<script type="application/ld+json">\n{jsonld(pr, cov)}\n</script>'
    return chrome(title, desc, url, body, head, noindex=noindex, og_image=og_image)


def render_index(profiles):
    cards = []
    for pr in profiles:
        img = (f'<img src="{attr(img_url(pr["slug"], pr["portrait"]["file"]))}" alt="{attr(pr["portrait"].get("alt", pr["name"]))}" loading="lazy">'
               if pr.get("portrait", {}).get("file") else
               f'<div class="no-photo" style="aspect-ratio:4/5;background:var(--green-deep);display:grid;place-items:center;color:#f0c660;font-family:var(--serif);font-weight:800;font-size:56px">{esc("".join(w[0] for w in pr["name"].split()[:2]).upper())}</div>')
        cards.append(f'''<article class="card"><a href="/people/{pr["slug"]}/">{img}</a>
<div class="card-body"><span class="tag">{esc(pr["title"])}</span>
<h3><a href="/people/{pr["slug"]}/">{esc(pr["name"])}</a></h3><p>{esc(pr["intro"][:220])}</p>
<div class="byline"><span>{esc(pr["location"])}</span></div></div></article>''')
    body = ('<div class="article-head" style="padding-top:36px"><span class="kicker" style="color:var(--green)">People</span>'
            '<h1>Profiles</h1><p class="standfirst">Documented profiles of Zambians in business, public service and community life — '
            'each fact tagged as verified, sourced or supplied by the subject.</p></div>'
            f'<section class="grid-3 people-grid" style="margin-top:28px">{"".join(cards)}</section>')
    head = ('<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "CollectionPage", "name": "People — Lusaka Brief",
        "url": f"{SITE}/people/", "hasPart": [{"@type": "ProfilePage", "url": f"{SITE}/people/{p['slug']}/",
                                                "name": p["name"]} for p in profiles]}, ensure_ascii=False)
            + "</script>")
    return chrome("People — Lusaka Brief", "Documented profiles of Zambians in business, public service and "
                  "community life, with every fact tagged as verified, sourced or supplied.",
                  f"{SITE}/people/", body, head, og_type="website")


# ---------------------------------------------------------------- commands
def cmd_new(a):
    dst = path(a.slug)
    if os.path.exists(dst):
        raise SystemExit(f"{dst} already exists")
    tpl = json.loads(ed.read(os.path.join(PEOPLE, "_template.json")))
    tpl["slug"] = a.slug
    tpl["created"] = tpl["updated"] = dt.date.today().isoformat()
    ed.write(dst, json.dumps(tpl, ensure_ascii=False, indent=2))
    print(f"Started {os.path.relpath(dst, ROOT)} — fill it in from the intake answers, then: "
          f"profile.py check {a.slug}")


def cmd_check(a):
    pr = load(a.slug)
    errs = validate(pr)
    if errs:
        print(f"{len(errs)} problem(s):")
        for x in errs:
            print("  - " + x)
        sys.exit(2)
    print(f"OK — {pr['name']} ({'published' if pr.get('published') else 'DRAFT, not published'})")


def cmd_media(a):
    from PIL import Image, ImageOps
    src = os.path.join(PEOPLE, "media", a.slug)
    dst = os.path.join(ROOT, "assets", "people", a.slug)
    if not os.path.isdir(src):
        raise SystemExit(f"put originals in {os.path.relpath(src, ROOT)}/ first")
    os.makedirs(dst, exist_ok=True)
    n = 0
    for f in sorted(os.listdir(src)):
        stem, ext = os.path.splitext(f)
        if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".heic", ".tif", ".tiff"):
            continue
        im = ImageOps.exif_transpose(Image.open(os.path.join(src, f))).convert("RGB")
        im.thumbnail((1600, 1600), Image.LANCZOS)
        out = os.path.join(dst, re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-") + ".webp")
        im.save(out, "WEBP", quality=82, method=6)   # EXIF (location etc.) is dropped
        n += 1
        print(f"  {f} -> assets/people/{a.slug}/{os.path.basename(out)} {im.size[0]}x{im.size[1]}")
    print(f"{n} image(s) converted. Reference them by file name in the profile JSON.")


def cmd_preview(a):
    pr = load(a.slug)
    errs = validate(pr)
    for x in errs:
        print("  warning: " + x)
    html = render_profile(pr, ed.load_stories(), noindex=True)
    ed.write(a.out, html)
    print(f"Preview written to {a.out} (noindex). Open it next to the site root so /assets/ resolves.")


def cmd_build(a):
    slugs = ([f[:-5] for f in sorted(os.listdir(PEOPLE)) if f.endswith(".json") and not f.startswith("_")]
             if a.all else [a.slug])
    stories = ed.load_stories()
    built = []
    for slug in slugs:
        pr = load(slug)
        errs = validate(pr)
        if errs:
            print(f"{slug}: NOT built — {len(errs)} problem(s):")
            for x in errs:
                print("  - " + x)
            if not a.all:
                sys.exit(2)
            continue
        if not pr.get("published"):
            print(f"{slug}: draft — not published (set \"published\": true when the subject has approved it)")
            continue
        ed.write(ed.p("people", slug, "index.html"), render_profile(pr, stories))
        built.append(pr)
        print(f"{slug}: written people/{slug}/index.html")
    published = [load(f[:-5]) for f in sorted(os.listdir(PEOPLE))
                 if f.endswith(".json") and not f.startswith("_")]
    published = [pr for pr in published if pr.get("published")
                 and os.path.exists(ed.p("people", pr["slug"], "index.html"))]
    if published:
        ed.write(ed.p("people", "index.html"), render_index(published))
        ed.write(ed.p("sitemap.xml"), ed.build_sitemap(ed.read(ed.p("sitemap.xml")), stories))
        print(f"people/index.html lists {len(published)} profile(s); sitemap updated.")
    if built:
        print("Next: git add -A && git commit -m \"Profile: " + ", ".join(p["name"] for p in built)
              + "\" && git push origin main")


def main():
    ap = argparse.ArgumentParser(description="Lusaka Brief person profiles")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("new"); s.add_argument("slug"); s.set_defaults(fn=cmd_new)
    s = sub.add_parser("check"); s.add_argument("slug"); s.set_defaults(fn=cmd_check)
    s = sub.add_parser("media"); s.add_argument("slug"); s.set_defaults(fn=cmd_media)
    s = sub.add_parser("preview"); s.add_argument("slug"); s.add_argument("out"); s.set_defaults(fn=cmd_preview)
    s = sub.add_parser("build"); s.add_argument("slug", nargs="?"); s.add_argument("--all", action="store_true")
    s.set_defaults(fn=cmd_build)
    a = ap.parse_args()
    if a.cmd == "build" and not (a.slug or a.all):
        ap.error("build needs a slug or --all")
    a.fn(a)


if __name__ == "__main__":
    main()
