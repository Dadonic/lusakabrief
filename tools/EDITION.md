# Lusaka Brief — daily edition runbook

This is the standing brief for whoever (or whatever) produces the daily edition.
Read all of it before writing anything.

Lusaka Brief (https://lusakabrief.com) is a static site. Anything pushed to
`main` is live within five minutes. An edition is 8–10 stories compiled from
**published reporting by other outlets and official sources**, each one credited
and linked. The desk does no interviews and makes no enquiries, and the copy
must never suggest otherwise.

---

## 1. Run order

```bash
python3 tools/edition.py status
```

1. **If `already_published_today` is true, stop.** Another pipeline has already
   published today's edition. Change nothing, push nothing, and say so in your
   report. (One edition a day, never two.)
2. Note `today_in_lusaka`, `next_edition_number` and `recent_stories` — the last
   few days of coverage, so that follow-ups move a story forward instead of
   repeating it and no slug is reused.
3. Research the last 24–36 hours of Zambian news (section 2).
4. Write the edition to `tools/editions/<today>.json` (section 4).
5. Validate, then publish into the working tree:
   ```bash
   python3 tools/edition.py build tools/editions/<today>.json --dry-run
   python3 tools/edition.py build tools/editions/<today>.json
   python3 tools/edition.py check
   ```
   Fix every problem the validator lists. Do not weaken the validator to get an
   edition through.
6. Read back the lead story page and one other page in `news/<slug>/index.html`
   and re-check each figure, name, title and date in them against your sources.
7. Commit and push:
   ```bash
   git add -A
   git commit -F tools/.commit-message
   git push origin main
   ```
   If the push is rejected because `main` moved: `git fetch origin`, copy your
   edition JSON somewhere safe, `git reset --hard origin/main`, run `status`
   again. If today's edition now exists, stop. Otherwise restore the JSON,
   rebuild and push once more.
8. Report: edition number, the headlines, anything you left out because it
   could not be verified, and any past story that today's reporting shows to be
   wrong (do not silently edit old stories — flag them).

**Never touch** `wire.json`, `wire.php`, `api/`, `assets/site.css`,
`veteran-refinery/`, or any part of `index.html` the script does not manage.
`wire.json` is rewritten on the server every two hours; committing it breaks the
deploy.

If fewer than five stories can be properly sourced, publish nothing and report
why. A missed day is better than a thin or unverified edition.

---

## 2. Research

Search the web and open the pages. A search-result snippet is not a source: only
cite a page you have actually fetched and read during this run, and cite the URL
you read.

Where to look:

- **Zambian newsrooms:** Lusaka Times, News Diggers, Times of Zambia, Zambia
  Daily Mail, ZNBC, Mwebantu, Zambia Monitor, MakanDay, Kalemba, Open Zambia.
- **Wires and international:** Reuters, Bloomberg, AFP, BBC, Africanews,
  AllAfrica, The Africa Report, Mining.com.
- **Primary sources:** State House, National Assembly, Ministry statements,
  Bank of Zambia, ZamStats, ERB, ECZ, the Judiciary, ZESCO, FAZ, CAF, the IMF and
  World Bank, UN bodies.

Do not use your own memory for anything current — officeholders, prices,
exchange rates, scores, case status. If you cannot find it on a page today, it
does not go in.

A normal edition: one lead; 2–3 Politics; 2 Economy; 1–2 from Health and Courts;
1–2 Sport; 1–2 Culture. Let the news decide the mix.

---

## 3. Editorial rules

**Sourcing**

- Every factual statement must be traceable to a source listed under that story.
- Politics, Economy, Health and Courts stories need at least two different
  outlets. If only one outlet has it, either leave it out or write it as that
  outlet's report ("News Diggers reports that…") inside a story that has a
  second source for its main facts.
- Sport and Culture may run on one solid source.
- Social-media rumour is not news. An unverified claim goes in only when an
  established outlet has reported it and it matters, and then it is labelled
  unverified in the text and in the confirmed/unverified block.

**No invented reporting**

- Never write "told Lusaka Brief", "Lusaka Brief has learned", "sources say",
  "was contacted for comment" or anything else implying interviews or enquiries.
  The validator rejects these phrases, but the rule is the meaning, not the
  wording.
- Quotes are verbatim from a source, short, and attributed to the speaker and
  the occasion ("he told Parliament on Friday", "she said in a statement carried
  by ZNBC"). Never compose, merge or tidy a quote.
- Bylines are desk bylines and are set by the script. Never add a person's name
  as author, and never invent a staff member, editor or correspondent.

**Fairness and legal care**

- Charged is not guilty. Use "alleged", "is charged with", "denies"; give the
  accused's response where it has been reported; never speculate about guilt or
  motive.
- Do not name children, victims of sexual offences, or private individuals
  accused of wrongdoing unless they have been charged in court and at least two
  established outlets have named them.
- In political stories give the government's position and its critics' position
  where both have been reported. No loaded adjectives.
- No medical, legal or investment advice beyond what an official body has said.

**Writing**

- Write in your own words. Do not copy sentences from the outlets you cite.
- British spelling. Explicit dates ("on Friday 9 October"). `US$` and `K` for
  money. Specific headlines, no clickbait, no question headlines.
- The lead story carries a `confirmed` block separating what is established
  from what is alleged or not yet known. Use one on any Courts story too.
- Mark a story `"developing": true` only if a decisive event is still pending.

**Analysis pieces** (the band at the foot of the front page)

Two or three short pieces, 110–200 words each, tagged "Analysis" and signed by a
desk. They explain what a development means, what is still unknown and what to
watch next, and they set out the strongest version of each side of a dispute.
They do not campaign: no calls to vote for or against anyone, no verdicts on
who is right in a contested political argument, no first person singular.

---

## 4. The edition file

`tools/editions/YYYY-MM-DD.json` — plain text everywhere, no HTML. `**bold**` is
allowed inside paragraphs.

```json
{
  "date": "2026-10-11",
  "strapline": "The Solwezi ruling, the kwacha at 20, and a decider in Ndola",
  "stories": [
    {
      "lead": true,
      "developing": false,
      "slug": "solwezi-court-rules-jurisdiction-mundubile-zulu-sedition-case",
      "section": "Courts",
      "title": "Headline, 30–180 characters",
      "excerpt": "Standfirst, 120–560 characters. It appears under the headline, on cards, in the feed and in the daily email.",
      "dateline": "SOLWEZI",
      "image": {
        "key": "solwezi",
        "motif": "scales",
        "label": "The Solwezi file",
        "caption": "One sentence that says what the story is about."
      },
      "body": [
        "First paragraph.",
        "Second paragraph.",
        {"type": "subhead", "text": "What the court decided"},
        "Third paragraph.",
        {"type": "quote", "text": "Verbatim words.", "attribution": "Name, role, where and when it was said"},
        {"type": "box", "title": "Key dates", "items": ["13 October — ruling", "26 October — petition hearing"]},
        {"type": "confirmed",
         "confirmed": "What is established, and by which source.",
         "unverified": "What is alleged, disputed or not yet known."}
      ],
      "sources": [
        {"outlet": "Times of Zambia", "title": "Exact headline of the page", "date": "10 Oct 2026", "url": "https://…"},
        {"outlet": "ZNBC", "title": "Exact headline of the page", "date": "10 Oct 2026", "url": "https://…"}
      ]
    },
    {
      "slug": "…",
      "section": "Economy",
      "tag": "Economy · Currency",
      "…": "non-lead stories also need a tag: \"<Section> · <Topic>\""
    }
  ],
  "analysis": [
    {"desk": "Courts", "title": "Up to 90 characters", "body": "110–200 words."},
    {"desk": "Economy", "title": "…", "body": "…"}
  ]
}
```

- **section** — Politics, Economy, Health, Courts, Sport or Culture.
- **slug** — lowercase words and hyphens, 15–110 characters, never reused.
- **Minimum length** — lead 420 words, others 260; at least three paragraphs.
- **image.motif** — one of `assembly`, `ballot`, `scales`, `columns`, `bars`,
  `coins`, `ingots`, `power`, `drop`, `pulse`, `pitch`, `sun`, `globe`, `book`,
  `road`. Leave it out to get the section's default. **image.label** is the
  3–34 character title printed on the illustration; **image.key** is a short
  unique word used in the file name.

Illustrations are drawn by `tools/art.py` and captioned "Illustration". Do not
add photographs or generated photorealistic images: a picture that looks like a
news photograph of an event is a claim about that event.

---

## 5. What the script does

`build` writes `news/<slug>/index.html` for each story, draws
`assets/ed<N>-<key>.webp`, prepends the stories to `assets/stories.json`, and
updates the front page (head tags, date, strapline, lead, section grids,
analysis band), the archive, `feed.xml` and `sitemap.xml`. Front-page section
grids are topped up to three cards with the most recent earlier stories. Nothing
is written unless the whole edition validates.

`regen` rebuilds the archive, feed and sitemap from `assets/stories.json`.
`check` verifies that every story has its page and image and that the front
page, archive, feed and sitemap agree with `stories.json`.

The daily email (`api/digest.php`, run on the server at 12:35 CAT) reads
`assets/stories.json` and sends the stories dated today, so the edition must be
pushed before then.
