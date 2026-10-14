"""Derive a qa-config.json draft from the environment itself.

Nothing here is specific to a particular app suite or persona. Point it at any
export and it discovers the apps, the date window, the cast, the email domains,
the domain vocabulary and a set of candidate capabilities -- then writes a
config with every inference marked so a human can adjudicate rather than author.

Usage:
    python bootstrap_config.py --in ./export --out qa-config.json
    python bootstrap_config.py --records records.jsonl --brief brief.md \
        --out qa-config.json

Anything it is not confident about lands in "_confirm" at the top of the
output. Work that list, delete it, and the config is ready.
"""

import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

from common import arg, load_records, parse_date, text_of
from normalize import APP_ALIASES

HERE = os.path.dirname(os.path.abspath(__file__))

STOPWORDS = set("""a an the and or but if then than that this these those of in on at to for
with from by as is are was were be been being have has had do does did will would can could
should may might must not no yes it its it's we our us you your they them their he she his her
i me my am so up out about into over after before under again more most some such only own same
too very just now here there when where who whom which what why how all any both each few other
one two three new use used using need needs get got make made see seen say said go going went
also well still back down off per via etc ok okay hi hey thanks thank please sure yeah yep nope
today tomorrow yesterday week month year day time next last first second next week let lets
know think want like really actually maybe probably good great nice sorry cheers regards best
team work working works done doing did ll ve re don t s m""".split())

PERSON_FRAME = re.compile(
    r"\b(?:said|asked|replied|wrote|agreed|joined|assigned to|reviewed by|"
    r"thanks|ping|1:1 with|spoke with)\b", re.I)
ORG_FRAME = re.compile(
    r"\b(?:vendor|contract|invoice|renewal|acquired|partnership|onboarding "
    r"with|licence|license)\b", re.I)
ORG_SUFFIX = re.compile(
    r"\b(Inc|LLC|Ltd|GmbH|Corp|Co|Technologies|Labs|Systems|Solutions|"
    r"Software|Group|Holdings|Partners|Ventures|Industries)\b", re.I)
PERSON_SHAPE = re.compile(r"^[A-Z][a-z'\-]+(?:\s+[A-Z][a-z'\-]+){1,2}$")
EMAIL = re.compile(r"\b[\w.+-]+@([\w-]+\.[\w.]{2,})\b")
WORD = re.compile(r"[A-Za-z][A-Za-z'\-/]{2,}")


def infer_kind(name, corpus):
    """person | org | programme | product — from shape, then from context."""
    if ORG_SUFFIX.search(name):
        return "org"
    window = " ".join(re.findall(
        r".{0,60}%s.{0,60}" % re.escape(name), corpus, re.I)[:40])
    person_hits = len(PERSON_FRAME.findall(window))
    org_hits = len(ORG_FRAME.findall(window))
    if person_hits > org_hits and person_hits:
        return "person"
    if org_hits > person_hits and org_hits:
        return "org"
    if PERSON_SHAPE.match(name.strip()):
        return "person"
    if re.search(r"\b(migration|rollout|initiative|programme|program|project|"
                 r"phase|launch)\b", name, re.I):
        return "programme"
    return "unknown"


def discover(records):
    apps = Counter(r["app"] for r in records)
    actors = Counter()
    domains = Counter()
    dates = []
    corpus_by_app = defaultdict(list)

    for r in records:
        for person in ([r.get("author"), r.get("assignee")]
                       + (r.get("participants") or [])):
            p = (person or "").strip()
            if 2 < len(p) < 60 and not p.startswith("{"):
                actors[p] += 1
        for field in ("created", "modified"):
            dt = parse_date(r.get(field))
            if dt:
                dates.append(dt)
        blob = text_of(r)
        corpus_by_app[r["app"]].append(blob)
        for m in EMAIL.finditer(blob + " " + " ".join(
                str(v) for v in (r.get("author"), r.get("url")) if v)):
            domains[m.group(1).lower()] += 1

    return apps, actors, domains, dates, corpus_by_app


def distinctive_terms(corpus_by_app, top=40, exclude=frozenset()):
    """Terms that recur across several apps — the shared domain language.

    Personal names are excluded: they recur everywhere and say nothing about
    the domain, and they would otherwise dominate the list.
    """
    per_app = {}
    for app, docs in corpus_by_app.items():
        counts = Counter()
        for d in docs:
            for w in WORD.findall(d.lower()):
                if w not in STOPWORDS and w not in exclude and len(w) > 2:
                    counts[w] += 1
        per_app[app] = counts

    spread = Counter()
    total = Counter()
    for app, counts in per_app.items():
        for w, n in counts.items():
            spread[w] += 1
            total[w] += n
    # Cross-app spread is the signal; raw frequency only breaks ties. A term
    # in two apps once each beats a term in one app five times.
    scored = [(w, spread[w], total[w]) for w in spread
              if spread[w] >= 2 and total[w] >= 2]
    scored.sort(key=lambda x: (-x[1], -x[2]))
    return [w for w, _s, _t in scored[:top]]


def candidate_capabilities(corpus_by_app, vocab, top=14, exclude=frozenset()):
    """Frequent multi-app bigrams become draft capability names."""
    bigrams = Counter()
    bigram_apps = defaultdict(set)
    for app, docs in corpus_by_app.items():
        for d in docs:
            words = [w for w in WORD.findall(d.lower())
                     if w not in STOPWORDS and w not in exclude]
            for a, b in zip(words, words[1:]):
                if len(a) > 2 and len(b) > 2:
                    bg = "%s %s" % (a, b)
                    bigrams[bg] += 1
                    bigram_apps[bg].add(app)

    ranked = [(bg, n) for bg, n in bigrams.items()
              if len(bigram_apps[bg]) >= 2 and n >= 2]
    ranked.sort(key=lambda x: (-len(bigram_apps[x[0]]), -x[1]))

    caps, used = {}, set()
    for bg, _n in ranked:
        a, b = bg.split()
        if a in used and b in used:
            continue
        used.update((a, b))
        extras = [v for v in vocab if v not in (a, b)][:2]
        caps[bg] = [bg, a, b] + extras
        if len(caps) >= top:
            break
    return caps


def parse_brief(path, known_apps):
    """Pull claimed apps and capability statements out of a brief document."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    claimed = []
    # An explicit "Apps in scope: A, B, C" line is the strongest signal, and
    # it's the only way to catch an app the brief claims but the data lacks.
    for line in text.splitlines():
        m = re.match(r"^\s*(?:apps?|tools?|systems?|surfaces?)\b[^:]{0,30}:\s*(.+)$",
                     line, re.I)
        if m:
            for part in re.split(r"[,;/]| and ", m.group(1)):
                tok = re.sub(r"[^a-z0-9 ]", "", part.strip().lower()).strip()
                tok = tok.replace(" ", "-")
                if 1 < len(tok) < 30:
                    claimed.append(APP_ALIASES.get(tok, tok))
    # Plus anything discovered in the data that the brief also mentions.
    for app in known_apps:
        if app != "unknown" and re.search(r"\b%s\b" % re.escape(app), text, re.I):
            claimed.append(app)

    claimed = sorted(set(claimed))

    claims = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^[-*\u2022]\s+|^\d+[.)]\s+", line):
            claim = re.sub(r"^[-*\u2022\d.)\s]+", "", line).strip()
            if 8 < len(claim) < 120:
                claims.append(claim)
    return claimed, claims


def main():
    src = arg("--in")
    records_path = arg("--records")
    out = arg("--out", "qa-config.json")
    brief = arg("--brief")

    if not records_path:
        if not src:
            raise SystemExit("need --in <export dir> or --records <file>")
        records_path = os.path.join(os.path.dirname(os.path.abspath(out)) or ".",
                                    "records.jsonl")
        subprocess.run([sys.executable, os.path.join(HERE, "normalize.py"),
                        "--in", os.path.abspath(src), "--out", records_path],
                       check=True)

    records = list(load_records(records_path))
    if not records:
        raise SystemExit("no records — check the export path")

    apps, actors, domains, dates, corpus_by_app = discover(records)
    full_corpus = "\n".join(t for docs in corpus_by_app.values() for t in docs)

    # Personal-name tokens pollute both vocabulary and capability inference.
    name_tokens = set()
    for actor in actors:
        for w in WORD.findall(actor.lower()):
            name_tokens.add(w)

    vocab = distinctive_terms(corpus_by_app, exclude=name_tokens)
    caps = candidate_capabilities(corpus_by_app, vocab, exclude=name_tokens)

    confirm = []

    # --- window
    lo = min(dates).date().isoformat() if dates else "REPLACE_ME"
    hi = max(dates).date().isoformat() if dates else "REPLACE_ME"
    confirm.append("persona_start is the EARLIEST date seen (%s). If the "
                   "persona actually joined later, set it — otherwise "
                   "out-of-window records can't be detected." % lo)
    confirm.append("environment_today is the LATEST date seen (%s). If the "
                   "brief fixes a different 'today', use that instead." % hi)

    # --- roster
    roster = []
    for name, count in actors.most_common(40):
        if count < 2:
            continue
        kind = infer_kind(name, full_corpus)
        entry = {"name": name, "kind": kind, "_seen": count}
        m = EMAIL.search(name)
        if m:
            entry["email"] = name
        roster.append(entry)
    unknown_kinds = [r["name"] for r in roster if r["kind"] == "unknown"]
    if unknown_kinds:
        confirm.append("Set 'kind' for: %s. The category-mismatch check is "
                       "inert for entries left as 'unknown'."
                       % ", ".join(unknown_kinds[:8]))

    # --- domains
    ranked_domains = domains.most_common()
    allowed = [d for d, n in ranked_domains if n >= max(2, len(records) // 20)]
    rare = [d for d, n in ranked_domains if d not in allowed]
    if rare:
        confirm.append("Rare email domains found (%s). Each is either an "
                       "unscrubbed real address or an intended one-off — "
                       "decide, then add to allowed_domains or leave it to be "
                       "flagged." % ", ".join(rare[:8]))

    expected_apps = sorted(a for a in apps if a != "unknown")
    claims = []
    if brief:
        claimed_apps, claims = parse_brief(brief, expected_apps + ["unknown"])
        missing = [a for a in claimed_apps if a not in expected_apps]
        if missing:
            confirm.append("Brief names apps with no data: %s. Add to "
                           "expected_apps (they'll be flagged) or to "
                           "accepted_gaps." % ", ".join(missing))
            expected_apps = sorted(set(expected_apps) | set(claimed_apps))

    capabilities = {}
    if claims:
        for claim in claims[:20]:
            words, seen_w = [], set()
            for w in WORD.findall(claim):
                lw = w.lower()
                if lw not in STOPWORDS and lw not in seen_w:
                    seen_w.add(lw)
                    words.append(lw)
            if words:
                capabilities[claim] = words[:5]
        confirm.append("Capabilities were taken from the brief's bullet points "
                       "— check the auto-extracted keywords actually identify "
                       "each one in the data.")
    else:
        capabilities = caps
        confirm.append("No brief supplied, so capabilities were INFERRED from "
                       "frequent cross-app phrases. These describe what the "
                       "data contains, not what it should contain — replace "
                       "them with the brief's claims before reporting "
                       "coverage to a client.")

    if "unknown" in apps:
        confirm.append("%d records had no identifiable app. Name your export "
                       "subfolders after the apps and re-run."
                       % apps["unknown"])

    cfg = {
        "_generated_by": "bootstrap_config.py — a draft, not ground truth",
        "_confirm": confirm,
        "persona": {"name": "REPLACE_ME", "role": "REPLACE_ME",
                    "seniority": "REPLACE_ME"},
        "persona_start": lo,
        "environment_today": hi,
        "expected_apps": expected_apps,
        "accepted_gaps": [],
        "min_records_per_app": max(3, int(len(records) / max(len(apps), 1) / 3)),
        "roster": roster,
        "allowed_domains": allowed,
        "forbidden_org_names": [],
        "domain_vocabulary": vocab,
        "domain_apps": [a for a, n in apps.most_common() if n >= 3
                        and a != "unknown"],
        "capabilities": capabilities,
        "require_multi_app_capabilities": True,
    }

    with open(out, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)

    print("\ndraft config -> %s" % out)
    print("  apps        %s" % ", ".join("%s(%d)" % (a, n)
                                         for a, n in apps.most_common()))
    print("  window      %s .. %s" % (lo, hi))
    print("  roster      %d candidates (%d need a kind)"
          % (len(roster), len(unknown_kinds)))
    print("  domains     allowed=%s rare=%s"
          % (",".join(allowed) or "-", ",".join(rare[:5]) or "-"))
    print("  vocabulary  %d terms" % len(vocab))
    print("  capabilities %d %s" % (len(capabilities),
                                    "(from brief)" if claims else "(inferred)"))
    print("\n%d items to confirm — see '_confirm' at the top of the file."
          % len(confirm))
    print("forbidden_org_names is empty by design: only you know which real "
          "vendors are in scope.")


if __name__ == "__main__":
    main()
