# Person profiles — how they work

A profile lives at `/people/<slug>/` and is built from one file,
`tools/people/<slug>.json`, by `tools/profile.py`. The page is a documented
biography, not a promotional landing page: every fact carries a tag that says
whether Lusaka Brief verified it against an independent source, whether the
subject supplied a document or link for it, or whether it rests on the
subject's own account. Readers see the tags. So do search engines, through
the structured data, which only includes facts marked verified.

## The workflow

1. **Intake.** Send the subject (or his representative) `INTAKE.md` and collect
   the answers, documents, photographs and links. Ask only for what is missing.
2. **Start the file.** `python3 tools/profile.py new <slug>` copies the
   template. Fill it in from the intake answers. Delete any section you have
   nothing for — an empty section is not rendered; a placeholder is.
3. **Photographs.** Put originals in `tools/people/media/<slug>/` and run
   `python3 tools/profile.py media <slug>`. They are resized, converted to
   WebP and stripped of camera metadata (including GPS). Every image needs
   alt text, and any image showing identifiable people needs
   `"people_shown": true, "consent": true`, which the builder enforces.
4. **Verify.** For each affiliation, outcome, award, qualification and
   milestone, look for an independent source: a regulator's register, a
   published annual report, a news report, an event programme. Record it in
   `source` and set `"verified": true` only when you have seen it yourself.
   Awards and qualifications without a source are not listed at all.
5. **Check and preview.** `python3 tools/profile.py check <slug>` lists
   problems; `python3 tools/profile.py preview <slug> /tmp/x.html` renders the
   page with a noindex tag for the subject to review.
6. **Approval.** When the subject or an authorised representative has approved
   the text, photographs and contact details in writing, set
   `"consent_confirmed": true` and `"published": true`, update `updated`.
7. **Publish.** `python3 tools/profile.py build <slug>` writes the page, the
   `/people/` index and the sitemap entry. Commit and push to `main`; it is
   live within five minutes. The commit history is the audit log.

## Disclosure

`relationship` is required and is printed on the profile and on every article
tagged to the person:

| value | printed as |
|---|---|
| `commissioned` | commissioned this profile and the coverage labelled as supplied |
| `owner` | owns Lusaka Brief |
| `sponsor` | organisation sponsors content on Lusaka Brief |
| `partner` | organisation is a partner of Lusaka Brief |
| `none` | no commercial relationship |

Use `disclosure` for a more specific sentence if the standard one is not
accurate. Never choose `none` for someone who paid for or requested the
coverage.

## Articles about a profiled person

Stories in an edition can carry `"people": ["<slug>"]` and a `kind`:

| kind | meaning | rules |
|---|---|---|
| `report` | independent reporting | at least two sources that are not the subject's own channels |
| `feature` | longer independent piece | same as report |
| `interview` | written Q&A supplied by the subject | labelled; disclosure printed |
| `project-update` | progress report from project documentation | labelled; figures shown as reported by the project |
| `press-release` | announcement issued by the subject | labelled; published as supplied |
| `supplied` | any other material from the subject | labelled |
| `opinion` | article in the subject's own name | labelled; views attributed to the author |

The lead story of an edition is always independent reporting. Labelled
articles appear on cards and in the feed with their label, and the article
page opens with a disclosure that names the person and the relationship.
Coverage of a person — Lusaka Brief's own and external — is listed
automatically on the profile, grouped and labelled.

## What is deliberately not built

The site is static HTML in a Git repository; there is no database, login or
admin dashboard, and adding them would mean a different, larger attack surface
on a shared server. The equivalents here are: drafts are JSON files with
`published: false`; approval is the commit that flips it; the audit log is
`git log`; roles are GitHub repository permissions; analytics come from Google
Search Console and whatever analytics tag the owner adds. `tools/seo_check.py`
replaces the "SEO health" screen.
