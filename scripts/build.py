#!/usr/bin/env python3
"""Génère le site statique « Bilan du monde » à partir de editions/*.json.

Sorties (à la racine du dépôt, servies par GitHub Pages) :
  index.html                    dernière édition
  edition/AAAA-MM-JJ/index.html une page par édition
  archives/index.html           toutes les éditions + recherche
  feed.xml                      flux RSS
  search.json                   index de recherche
  404.html

Aucune dépendance : bibliothèque standard Python uniquement.
"""
import html
import json
import math
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_URL = "https://lcpmn.github.io/bilan-du-monde/"
REPO_URL = "https://github.com/lcpmn/bilan-du-monde"
SITE_NAME = "Bilan du monde"
TAGLINE = "L'actualité mondiale en cinq minutes, chaque matin."
PARIS = ZoneInfo("Europe/Paris")
PARIS_LAT, PARIS_LON = 48.8566, 2.3522
FONTS = ("https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;"
         "0,6..72,500;1,6..72,400&family=Schibsted+Grotesk:wght@400;500;600;700;800;900&display=swap")

RUBRIQUES = {
    "monde":    ("International",          "international"),
    "france":   ("France",                 "france"),
    "eco":      ("Économie & marchés",     "economie"),
    "tech":     ("Tech & IA",              "tech"),
    "sciences": ("Sciences & santé",       "sciences"),
    "climat":   ("Climat & environnement", "climat"),
    "sport":    ("Sport",                  "sport"),
}
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]
MOIS_COURT = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août",
              "sept.", "oct.", "nov.", "déc."]

e = lambda s: html.escape(str(s if s is not None else ""), quote=True)


# ---------- dates ----------
def parse_day(s):
    return date.fromisoformat(s)

def long_date(d):
    return f"{JOURS[d.weekday()].capitalize()} {d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"

def short_date(d):
    return f"{JOURS[d.weekday()][:3]}. {d.day} {MOIS_COURT[d.month - 1]}"

def hhmm(dt):
    return f"{dt.hour} h {dt.minute:02d}"

def sunrise_paris(d):
    """Lever du soleil à Paris (algorithme de l'Almanac for Computers, précision ~1 min)."""
    n = d.timetuple().tm_yday
    lng_hour = PARIS_LON / 15
    t = n + ((6 - lng_hour) / 24)
    m = 0.9856 * t - 3.289
    l = (m + 1.916 * math.sin(math.radians(m)) + 0.020 * math.sin(math.radians(2 * m)) + 282.634) % 360
    ra = math.degrees(math.atan(0.91764 * math.tan(math.radians(l)))) % 360
    ra = (ra + (l // 90) * 90 - (ra // 90) * 90) / 15
    sin_dec = 0.39782 * math.sin(math.radians(l))
    cos_dec = math.cos(math.asin(sin_dec))
    cos_h = (math.cos(math.radians(90.833)) - sin_dec * math.sin(math.radians(PARIS_LAT))) / (cos_dec * math.cos(math.radians(PARIS_LAT)))
    h = (360 - math.degrees(math.acos(cos_h))) / 15
    ut = (h + ra - 0.06571 * t - 6.622 - lng_hour) % 24
    utc = datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(hours=ut)
    return utc.astimezone(PARIS)


# ---------- données ----------
def load_editions():
    out = []
    folder = os.path.join(ROOT, "editions")
    for f in sorted(os.listdir(folder)):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", f):
            continue
        with open(os.path.join(folder, f), encoding="utf-8") as fh:
            d = json.load(fh)
        d["date"] = f[:-5]
        out.append(d)
    out.sort(key=lambda d: d["date"])
    for i, d in enumerate(out):
        d["_num"] = i + 1
        d["_day"] = parse_day(d["date"])
        prepare(d)
    return out

def prepare(d):
    cats = []
    for c in d.get("categories") or []:
        key = c.get("key")
        name, slug = RUBRIQUES.get(key, (c.get("name") or key, re.sub(r"[^a-z0-9-]", "", str(key).lower())))
        items = []
        for i, it in enumerate(c.get("items") or []):
            if not it.get("title"):
                continue
            it = dict(it)
            it["_id"] = f"{slug}-{i + 1}"
            items.append(it)
        cats.append({"key": key, "name": name, "slug": slug, "items": items})
    # La « une » : référencée par {key, index}, sinon le premier sujet de la première rubrique.
    une = None
    ref = d.get("une") or {}
    for c in cats:
        if c["key"] == ref.get("key") and isinstance(ref.get("index"), int) and 0 <= ref["index"] < len(c["items"]):
            une = (c, c["items"][ref["index"]])
    if une is None:
        for c in cats:
            if c["items"]:
                une = (c, c["items"][0])
                break
    if une:
        une[1]["_une"] = True
    d["_cats"] = [c for c in cats if c["items"]]
    d["_une"] = une
    words = " ".join(d.get("overview") or [])
    for c in cats:
        for it in c["items"]:
            words += " " + " ".join(str(it.get(k, "")) for k in ("title", "summary", "why"))
    d["_minutes"] = max(1, round(len(words.split()) / 220))
    d["_topics"] = sum(len(c["items"]) for c in cats)
    try:
        d["_updated"] = datetime.fromisoformat(d.get("updatedAt")).astimezone(PARIS)
    except Exception:
        d["_updated"] = None

def safe_url(u):
    u = str(u or "")
    return u if re.match(r"^https?://", u) else None


# ---------- gabarits ----------
SUN_SVG = ('<svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 17h20" />'
           '<path d="M6.5 17a5.5 5.5 0 0 1 11 0" /><path d="M12 6.5v2.5M5.3 9.3l1.7 1.7M18.7 9.3 17 11" /></svg>')

def head(title, desc, canonical, root, og_type="website"):
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canonical)}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:type" content="{og_type}">
<meta property="og:locale" content="fr_FR">
<meta name="twitter:card" content="summary">
<meta name="theme-color" content="#f4f6f9" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0a0f17" media="(prefers-color-scheme: dark)">
<link rel="icon" href="{root}assets/icon.svg" type="image/svg+xml">
<link rel="alternate" type="application/rss+xml" title="{SITE_NAME}" href="{root}feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{root}assets/style.css">
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
<script src="{root}assets/app.js" defer></script>
</head>
<body>
<a class="skip" href="#contenu">Aller au contenu</a>
"""

def masthead(root, current):
    def nav(href, label, key):
        cur = ' aria-current="page"' if key == current else ""
        return f'<a href="{href}"{cur}>{label}</a>'
    return f"""<header class="masthead">
  <div class="masthead-in">
    <a class="wordmark" href="{root}"><span class="wm-mark" aria-hidden="true"></span>Bilan du monde</a>
    <nav class="sitenav" aria-label="Site">
      {nav(root, "Aujourd'hui", "home")}
      {nav(root + "archives/", "Archives", "archives")}
      <button class="theme-btn" type="button" id="theme-btn" aria-label="Changer de thème" title="Changer de thème">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 3.5a8.5 8.5 0 0 1 0 17z" class="fill"/></svg>
      </button>
    </nav>
  </div>
</header>
"""

def footer(root):
    return f"""<footer class="site-footer">
  <div class="footer-in">
    <div class="footer-about">
      <a class="wordmark small" href="{root}"><span class="wm-mark" aria-hidden="true"></span>Bilan du monde</a>
      <p>{TAGLINE} Une nouvelle édition paraît vers 6 h, heure de Paris.</p>
    </div>
    <div class="footer-method">
      <h2>Méthode</h2>
      <p>Les éditions sont rédigées automatiquement par une IA (Claude) à partir de recherches web sur les dernières 24 heures. Chaque sujet renvoie à sa source : vérifiez-y les informations importantes.</p>
    </div>
    <nav class="footer-links" aria-label="Liens">
      <a href="{root}archives/">Toutes les éditions</a>
      <a href="{root}feed.xml">Flux RSS</a>
      <a href="{REPO_URL}">Code source</a>
    </nav>
  </div>
</footer>
</body>
</html>
"""

def item_html(it, c, root, edition_href):
    url = safe_url(it.get("url"))
    src = e(it.get("source") or "")
    src_html = f'<a class="src" href="{e(url)}" rel="noopener" target="_blank">{src}<span aria-hidden="true"> ↗</span></a>' if url else f'<span class="src">{src}</span>'
    why = f'<p class="why"><span class="why-label">Pourquoi c\'est important</span> {e(it["why"])}</p>' if it.get("why") else ""
    return f"""<article class="story" id="{it['_id']}">
  <h3>{e(it['title'])}</h3>
  <p class="summary">{e(it.get('summary'))}</p>
  {why}
  <div class="story-meta">{src_html}<button class="copy" type="button" data-copy="{e(edition_href)}#{it['_id']}">Copier le lien</button></div>
</article>"""

def edition_page(d, eds, root, is_home):
    day = d["_day"]
    idx = eds.index(d)
    prev_ed = eds[idx - 1] if idx > 0 else None
    next_ed = eds[idx + 1] if idx + 1 < len(eds) else None
    href = lambda ed: f"{root}edition/{ed['date']}/"
    canonical = SITE_URL if is_home else f"{SITE_URL}edition/{d['date']}/"
    overview = d.get("overview") or []
    desc = overview[0] if overview else TAGLINE
    title = f"{SITE_NAME} · {long_date(day)}" if not is_home else f"{SITE_NAME} · {TAGLINE}"
    sun = sunrise_paris(day)
    upd = d["_updated"]
    upd_html = f'<span>Publiée à {hhmm(upd)}</span>' if upd else ""
    out = [head(title, desc, canonical, root, "article"), masthead(root, "home" if is_home else "")]
    out.append(f"""<main id="contenu">
<div class="dateline">
  <div class="dateline-in">
    <p class="edition-date"><time datetime="{d['date']}">{long_date(day)}</time></p>
    <p class="edition-meta">
      <span>Édition n° {d['_num']}</span>
      <span>{d['_topics']} sujets</span>
      <span>{d['_minutes']} min de lecture</span>
      {upd_html}
      <span class="sunrise" title="Lever du soleil à Paris">{SUN_SVG}Paris · lever {hhmm(sun)}</span>
    </p>
  </div>
</div>
""")
    # Une + essentiel
    une_html = ""
    if d["_une"]:
        c, it = d["_une"]
        url = safe_url(it.get("url"))
        src = f'<a class="src" href="{e(url)}" rel="noopener" target="_blank">{e(it.get("source"))}<span aria-hidden="true"> ↗</span></a>' if url else f'<span class="src">{e(it.get("source"))}</span>'
        why = f'<p class="why"><span class="why-label">Pourquoi c\'est important</span> {e(it["why"])}</p>' if it.get("why") else ""
        une_html = f"""<article class="une" id="une" style="--rub: var(--r-{c['key']})">
    <p class="kicker"><span class="kicker-une">À la une</span><a href="#{c['slug']}">{e(c['name'])}</a></p>
    <h1>{e(it['title'])}</h1>
    <p class="une-summary">{e(it.get('summary'))}</p>
    {why}
    <div class="story-meta">{src}<button class="copy" type="button" data-copy="{e(canonical if not is_home else SITE_URL + 'edition/' + d['date'] + '/')}#une">Copier le lien</button></div>
  </article>"""
    ess = ""
    if overview:
        lis = "".join(f"<li>{e(t)}</li>" for t in overview)
        ess = f"""<aside class="essentiel" aria-labelledby="ess-title">
    <h2 id="ess-title">L'essentiel</h2>
    <ul>{lis}</ul>
  </aside>"""
    out.append(f'<section class="top">\n  {une_html}\n  {ess}\n</section>\n')

    # Chiffres
    ch = [x for x in (d.get("chiffres") or []) if x.get("value") and x.get("label")]
    if ch:
        cells = "".join(
            f'<div class="chiffre" style="--rub: var(--r-{e(x.get("key", "monde"))})"><p class="val">{e(x["value"])}</p><p class="lab">{e(x["label"])}</p></div>'
            for x in ch[:4])
        out.append(f'<section class="chiffres" aria-labelledby="ch-title"><h2 id="ch-title" class="section-label">Les chiffres du jour</h2><div class="chiffres-grid">{cells}</div></section>\n')

    # Filtres
    chips = ['<button type="button" class="chip" data-filter="tout" aria-pressed="true">Tout</button>']
    for c in d["_cats"]:
        n = len([i for i in c["items"] if not i.get("_une")])
        if n:
            chips.append(f'<a class="chip" href="#{c["slug"]}" data-filter="{c["slug"]}" style="--rub: var(--r-{c["key"]})"><span class="dot"></span>{e(c["name"])}<span class="n">{n}</span></a>')
    out.append(f'<nav class="filters" aria-label="Rubriques"><div class="filters-in">{"".join(chips)}</div></nav>\n')

    # Rubriques
    edition_href = SITE_URL + "edition/" + d["date"] + "/"
    secs = []
    for c in d["_cats"]:
        items = [i for i in c["items"] if not i.get("_une")]
        if not items:
            continue
        stories = "\n".join(item_html(it, c, root, edition_href) for it in items)
        secs.append(f"""<section class="rubrique" id="{c['slug']}" data-rub="{c['slug']}" style="--rub: var(--r-{c['key']})">
  <header class="rub-head"><h2>{e(c['name'])}</h2><p>{len(items)} sujet{'s' if len(items) > 1 else ''}</p></header>
  <div class="rub-body">
{stories}
  </div>
</section>""")
    out.append('<div class="rubriques">\n' + "\n".join(secs) + "\n</div>\n")

    if d.get("note"):
        out.append(f'<p class="note">{e(d["note"])}</p>\n')

    # Navigation entre éditions
    pv = f'<a class="pager-prev" href="{href(prev_ed)}"><span>Édition précédente</span>{long_date(prev_ed["_day"])}</a>' if prev_ed else "<span></span>"
    nx = f'<a class="pager-next" href="{href(next_ed) if next_ed is not eds[-1] else root}"><span>Édition suivante</span>{long_date(next_ed["_day"])}</a>' if next_ed else '<p class="pager-next pager-soon"><span>Prochaine édition</span>Demain vers 6 h</p>'
    out.append(f'<nav class="pager" aria-label="Éditions">{pv}{nx}</nav>\n</main>\n')
    out.append(footer(root))
    return "".join(out)

def archives_page(eds):
    root = "../"
    rows, current_month = [], None
    for d in reversed(eds):
        day = d["_day"]
        m = (day.year, day.month)
        if m != current_month:
            if current_month:
                rows.append("</ol></section>")
            rows.append(f'<section class="month"><h2>{MOIS[day.month - 1].capitalize()} {day.year}</h2><ol class="ed-list">')
            current_month = m
        lead = e(d["_une"][1]["title"]) if d["_une"] else ""
        rows.append(f"""<li><a href="{root}edition/{d['date']}/">
  <span class="ed-date"><b>{day.day}</b>{JOURS[day.weekday()]}</span>
  <span class="ed-body"><span class="ed-num">Édition n° {d['_num']} · {d['_topics']} sujets</span><span class="ed-lead">{lead}</span></span>
</a></li>""")
    if current_month:
        rows.append("</ol></section>")
    out = [head(f"Archives · {SITE_NAME}", "Toutes les éditions du Bilan du monde, avec une recherche dans l'ensemble des sujets.", SITE_URL + "archives/", root),
           masthead(root, "archives")]
    out.append(f"""<main id="contenu" class="archives">
  <header class="arch-head">
    <h1>Archives</h1>
    <p>{len(eds)} édition{'s' if len(eds) > 1 else ''} depuis le {long_date(eds[0]['_day']).lower()}.</p>
    <label class="search" for="q"><span class="visually-hidden">Rechercher dans toutes les éditions</span>
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg>
      <input id="q" type="search" placeholder="Rechercher un sujet, un pays, une personne…" autocomplete="off" data-search="{root}search.json" data-root="{root}">
    </label>
  </header>
  <div id="results" class="results" hidden></div>
  <div id="ed-index">
{"".join(rows)}
  </div>
</main>
""")
    out.append(footer(root))
    return "".join(out)

def page_404():
    root = "/bilan-du-monde/"
    return (head(f"Page introuvable · {SITE_NAME}", TAGLINE, SITE_URL, root) + masthead(root, "") +
            f'<main id="contenu" class="archives"><header class="arch-head"><h1>Page introuvable</h1>'
            f'<p>Cette page n\'existe pas ou plus. <a href="{root}">Lire l\'édition du jour</a> ou <a href="{root}archives/">parcourir les archives</a>.</p></header></main>'
            + footer(root))

def feed(eds):
    items = []
    for d in reversed(eds[-30:]):
        link = f"{SITE_URL}edition/{d['date']}/"
        lead = d["_une"][1]["title"] if d["_une"] else ""
        body = "".join(f"<li>{e(t)}</li>" for t in d.get("overview") or [])
        pub = d["_updated"] or datetime(d["_day"].year, d["_day"].month, d["_day"].day, 6, tzinfo=PARIS)
        items.append(f"""<item>
<title>{e(long_date(d['_day']))} · {e(lead)}</title>
<link>{link}</link>
<guid isPermaLink="true">{link}</guid>
<pubDate>{format_datetime(pub)}</pubDate>
<description>{e('<ul>' + body + '</ul>')}</description>
</item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>{SITE_NAME}</title>
<link>{SITE_URL}</link>
<description>{e(TAGLINE)}</description>
<language>fr-fr</language>
{''.join(items)}
</channel>
</rss>
"""

def search_index(eds):
    rows = []
    for d in eds:
        for c in d["_cats"]:
            for it in c["items"]:
                rows.append({"d": d["date"], "r": c["name"], "k": c["key"],
                             "t": it["title"], "s": it.get("summary", ""),
                             "a": "une" if it.get("_une") else it["_id"]})
    return rows

def write(rel, content):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)

def main():
    eds = load_editions()
    if not eds:
        sys.exit("Aucune édition dans editions/")
    for d in eds:
        write(f"edition/{d['date']}/index.html", edition_page(d, eds, "../../", False))
    write("index.html", edition_page(eds[-1], eds, "", True))
    write("archives/index.html", archives_page(eds))
    write("404.html", page_404())
    write("feed.xml", feed(eds))
    write("search.json", json.dumps(search_index(eds), ensure_ascii=False, separators=(",", ":")))
    print(f"Site généré : {len(eds)} édition(s), dernière du {eds[-1]['date']}.")

if __name__ == "__main__":
    main()
