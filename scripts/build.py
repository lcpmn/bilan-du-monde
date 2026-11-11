#!/usr/bin/env python3
"""Génère le site statique « Bilan du monde » (français + anglais) à partir de editions/*.json.

Sorties (à la racine du dépôt, servies par GitHub Pages) :
  index.html, edition/AAAA-MM-JJ/, archives/, feed.xml, search.json      version française
  en/index.html, en/edition/AAAA-MM-JJ/, en/archives/, en/feed.xml, ...   version anglaise
  404.html

Les textes anglais d'une édition sont facultatifs : champs "en" des sujets ({title, summary, why}),
"overview_en", "note_en", "label_en"/"value_en" des chiffres, "nom_en" des lieux. À défaut, le texte
français est repris.
"""
import html
import json
import math
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import visuals  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_URL = "https://lcpmn.github.io/bilan-du-monde/"
REPO_URL = "https://github.com/lcpmn/bilan-du-monde"
SITE_NAME = "Bilan du monde"
PARIS = ZoneInfo("Europe/Paris")
PARIS_LAT, PARIS_LON = 48.8566, 2.3522
FONTS = ("https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;"
         "0,6..72,500;1,6..72,400&family=Schibsted+Grotesk:wght@400;500;600;700;800;900&display=swap")

SLUGS = {"monde": "international", "france": "france", "eco": "economie", "tech": "tech",
         "sciences": "sciences", "climat": "climat", "sport": "sport"}


# ======================================================================
# Langues
# ======================================================================
class Lang:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def tx(self, obj, field):
        """Texte d'un sujet dans la langue, avec repli sur le français."""
        if self.code == "en":
            v = (obj.get("en") or {}).get(field)
            if v:
                return v
        return obj.get(field)

    def top(self, d, field):
        if self.code == "en" and d.get(field + "_en"):
            return d[field + "_en"]
        return d.get(field)


FR = Lang(
    code="fr", prefix="", locale="fr_FR", rss_lang="fr-fr",
    tagline="L'actualité mondiale en cinq minutes, chaque matin.",
    rub={"monde": "International", "france": "France", "eco": "Économie & marchés", "tech": "Tech & IA",
         "sciences": "Sciences & santé", "climat": "Climat & environnement", "sport": "Sport"},
    days=["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
    months=["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
            "septembre", "octobre", "novembre", "décembre"],
    months_short=["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août",
                  "sept.", "oct.", "nov.", "déc."],
    s=dict(
        skip="Aller au contenu", today="Aujourd'hui", archives="Archives", theme="Changer de thème",
        lang_label="Langue", edition_no="Édition n° {n}", topics="{n} sujets", topic1="{n} sujet",
        minutes="{n} min de lecture", published="Publiée à {t}", sunrise_title="Lever du soleil à Paris",
        sunrise="Paris · lever {t}", une="À la une", essentials="L'essentiel", numbers="Les chiffres du jour",
        why="Pourquoi c'est important", source="Source", share="Partager", share_ed="Partager l'édition", all="Tout",
        sections="Rubriques", prev="Édition précédente", next="Édition suivante", soon="Prochaine édition",
        tomorrow="Demain vers 6 h", editions_nav="Éditions",
        about="Une nouvelle édition paraît vers 6 h, heure de Paris.", method="Méthode",
        method_text="Les éditions sont rédigées automatiquement par une IA (Claude) à partir de recherches web sur les dernières 24 heures. Chaque sujet renvoie à l'article d'origine qui le rapporte (média, titre, date) : vérifiez-y les informations importantes. Fonds de carte : Natural Earth.",
        all_editions="Toutes les éditions", rss="Flux RSS", code="Code source", links="Liens",
        arch_desc="Toutes les éditions du Bilan du monde, avec une recherche dans l'ensemble des sujets.",
        arch_count1="{n} édition depuis le {d}.", arch_count="{n} éditions depuis le {d}.",
        search_label="Rechercher dans toutes les éditions",
        search_ph="Rechercher un sujet, un pays, une personne…",
        og_tag="La matinale de l'actualité mondiale", og_when="Chaque matin vers 6 h, heure de Paris",
        home_title="Bilan du monde · L'actualité du jour résumée en 5 minutes",
        site_desc="Chaque matin vers 6 h, l'essentiel de l'actualité mondiale résumé en cinq minutes : international, France, économie, tech, sciences, climat et sport, avec la source de chaque information.",
    ),
)

EN = Lang(
    code="en", prefix="en/", locale="en_GB", rss_lang="en",
    tagline="World news in five minutes, every morning.",
    rub={"monde": "World", "france": "France", "eco": "Economy & markets", "tech": "Tech & AI",
         "sciences": "Science & health", "climat": "Climate & environment", "sport": "Sport"},
    days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    months=["January", "February", "March", "April", "May", "June", "July", "August",
            "September", "October", "November", "December"],
    months_short=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    s=dict(
        skip="Skip to content", today="Today", archives="Archive", theme="Switch theme",
        lang_label="Language", edition_no="Edition no. {n}", topics="{n} stories", topic1="{n} story",
        minutes="{n} min read", published="Published at {t}", sunrise_title="Sunrise in Paris",
        sunrise="Paris · sunrise {t}", une="Top story", essentials="The essentials", numbers="Numbers of the day",
        why="Why it matters", source="Source", share="Share", share_ed="Share this edition", all="All",
        sections="Sections", prev="Previous edition", next="Next edition", soon="Next edition",
        tomorrow="Tomorrow around 6 am (Paris time)", editions_nav="Editions",
        about="A new edition comes out around 6 am, Paris time.", method="Method",
        method_text="Editions are written automatically by an AI (Claude) from web searches covering the last 24 hours, in French, then translated into English. Every story links to the original article that reports it (outlet, headline, date): check important facts there. Base maps: Natural Earth.",
        all_editions="All editions", rss="RSS feed", code="Source code", links="Links",
        arch_desc="Every edition of Bilan du monde, with search across all stories.",
        arch_count1="{n} edition since {d}.", arch_count="{n} editions since {d}.",
        search_label="Search all editions",
        search_ph="Search for a story, a country, a person…",
        og_tag="Your morning world news briefing", og_when="Every morning around 6 am, Paris time",
        home_title="Bilan du monde · Today's world news in 5 minutes",
        site_desc="Every morning around 6 am (Paris time), the world's news summarised in five minutes: world, France, economy, tech, science, climate and sport, with the source of every story.",
    ),
)
LANGS = (FR, EN)
CUR = FR  # langue en cours de rendu (règles typographiques)


# ---------- typographie ----------
def typo(s):
    """Espaces insécables à la française (milliers, %, ponctuation double, guillemets) ; rien en anglais."""
    if CUR.code != "fr":
        return s
    s = re.sub(r"(?<=\d) (?=\d{3}\b)", " ", s)
    s = re.sub(r" (?=[%:;!?»])", " ", s)
    return s.replace("« ", "« ")

def e(s):
    return html.escape(typo(str(s if s is not None else "")), quote=True)


# ---------- dates ----------
def long_date(d, L):
    if L.code == "en":
        return f"{L.days[d.weekday()]}, {L.months[d.month - 1]} {d.day}, {d.year}"
    return f"{L.days[d.weekday()].capitalize()} {d.day}{'er' if d.day == 1 else ''} {L.months[d.month - 1]} {d.year}"

def day_date(d, L):
    if L.code == "en":
        return f"{L.months[d.month - 1]} {d.day}, {d.year}"
    return f"{d.day}{'er' if d.day == 1 else ''} {L.months[d.month - 1]} {d.year}"

def short_src_date(d, L):
    if L.code == "en":
        return f"{L.months_short[d.month - 1]} {d.day}, {d.year}"
    return f"{d.day} {L.months_short[d.month - 1]} {d.year}"

def hhmm(dt, L):
    if L.code == "en":
        h = dt.hour % 12 or 12
        return f"{h}:{dt.minute:02d} {'am' if dt.hour < 12 else 'pm'}"
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
        d["_day"] = date.fromisoformat(d["date"])
        prepare(d)
    return out

def prepare(d):
    cats = []
    for c in d.get("categories") or []:
        key = c.get("key")
        slug = SLUGS.get(key) or re.sub(r"[^a-z0-9-]", "", str(key).lower())
        items = []
        for i, it in enumerate(c.get("items") or []):
            if not it.get("title"):
                continue
            it = dict(it)
            it["_id"] = f"{slug}-{i + 1}"
            items.append(it)
        cats.append({"key": key, "slug": slug, "items": items, "fallback": c.get("name") or key})
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
    d["_topics"] = sum(len(c["items"]) for c in cats)
    try:
        d["_updated"] = datetime.fromisoformat(d.get("updatedAt")).astimezone(PARIS)
    except Exception:
        d["_updated"] = None

def rub_name(c, L):
    return L.rub.get(c["key"], c["fallback"])

def minutes(d, L):
    words = " ".join(L.top(d, "overview") or [])
    for c in d["_cats"]:
        for it in c["items"]:
            words += " " + " ".join(str(L.tx(it, k) or "") for k in ("title", "summary", "why"))
    return max(1, round(len(words.split()) / 220))

def safe_url(u):
    u = str(u or "")
    return u if re.match(r"^https?://", u) else None


# ======================================================================
# Gabarits
# ======================================================================
SUN_SVG = ('<svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 17h20" />'
           '<path d="M6.5 17a5.5 5.5 0 0 1 11 0" /><path d="M12 6.5v2.5M5.3 9.3l1.7 1.7M18.7 9.3 17 11" /></svg>')

def page_path(kind, L, day=None):
    """Chemin d'une page depuis la racine du site."""
    base = L.prefix
    if kind == "home":
        return base
    if kind == "edition":
        return f"{base}edition/{day}/"
    return f"{base}archives/"

def depth_root(path):
    """Chemin relatif vers la racine du site depuis une page."""
    return "../" * path.count("/")

def ld_json(obj):
    """Bloc de données structurées schema.org (JSON-LD)."""
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'\n<script type="application/ld+json">{txt}</script>'

def head(L, title, desc, path, og_type="website", og_image=None, og_alt=SITE_NAME, alt_paths=None, extra="", ld=None):
    root = depth_root(path)
    canonical = SITE_URL + path
    og_image = og_image or ("assets/og/site.png" if L.code == "fr" else "assets/og/en/site.png")
    alts = ""
    if alt_paths:
        alts = "".join(f'<link rel="alternate" hreflang="{code}" href="{e(SITE_URL + p)}">\n' for code, p in alt_paths)
        alts += f'<link rel="alternate" hreflang="x-default" href="{e(SITE_URL + dict(alt_paths)["fr"])}">\n'
    return f"""<!doctype html>
<html lang="{L.code}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta name="robots" content="max-image-preview:large">
<link rel="canonical" href="{e(canonical)}">
{alts}<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:type" content="{og_type}">
<meta property="og:locale" content="{L.locale}">
<meta property="og:image" content="{e(SITE_URL + og_image)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(og_alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{e(SITE_URL + og_image)}">
<meta name="theme-color" content="#f4f6f9" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0a0f17" media="(prefers-color-scheme: dark)">
<link rel="icon" href="{root}assets/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{root}assets/app-180.png">
<link rel="manifest" href="{root}{L.prefix}manifest.webmanifest">
<link rel="alternate" type="application/rss+xml" title="{SITE_NAME}" href="{root}{L.prefix}feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{root}assets/style.css">
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>{extra}{"".join(ld_json(x) for x in ld or [])}
<script src="{root}assets/app.js" defer></script>
</head>
<body>
<a class="skip" href="#contenu">{L.s['skip']}</a>
"""

def masthead(L, path, current, alt_paths):
    root = depth_root(path)
    lroot = root + L.prefix
    def nav(href, label, key):
        cur = ' aria-current="page"' if key == current else ""
        return f'<a href="{href}"{cur}>{label}</a>'
    switch = []
    for code, p in alt_paths:
        label = code.upper()
        if code == L.code:
            switch.append(f'<span class="lang-cur" aria-current="true" lang="{code}">{label}</span>')
        else:
            name = "Français" if code == "fr" else "English"
            switch.append(f'<a class="lang-alt" href="{root}{p}" hreflang="{code}" lang="{code}" data-lang="{code}" title="{name}">{label}</a>')
    return f"""<header class="masthead">
  <div class="masthead-in">
    <a class="wordmark" href="{lroot}"><span class="wm-mark" aria-hidden="true"></span>Bilan du monde</a>
    <nav class="sitenav" aria-label="Site">
      {nav(lroot, L.s['today'], "home")}
      {nav(lroot + "archives/", L.s['archives'], "archives")}
      <span class="lang-switch" role="group" aria-label="{L.s['lang_label']}">{''.join(switch)}</span>
      <button class="theme-btn" type="button" id="theme-btn" aria-label="{L.s['theme']}" title="{L.s['theme']}">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 3.5a8.5 8.5 0 0 1 0 17z" class="fill"/></svg>
      </button>
    </nav>
  </div>
</header>
"""

def footer(L, path):
    lroot = depth_root(path) + L.prefix
    return f"""<footer class="site-footer">
  <div class="footer-in">
    <div class="footer-about">
      <a class="wordmark small" href="{lroot}"><span class="wm-mark" aria-hidden="true"></span>Bilan du monde</a>
      <p>{e(L.tagline)} {e(L.s['about'])}</p>
    </div>
    <div class="footer-method">
      <h2>{L.s['method']}</h2>
      <p>{e(L.s['method_text'])}</p>
    </div>
    <nav class="footer-links" aria-label="{L.s['links']}">
      <a href="{lroot}archives/">{L.s['all_editions']}</a>
      <a href="{lroot}feed.xml">{L.s['rss']}</a>
      <a href="{REPO_URL}">{L.s['code']}</a>
    </nav>
  </div>
</footer>
</body>
</html>
"""

def source_html(it, L):
    """Citation explicite : média, titre de l'article d'origine, site et date de publication."""
    url = safe_url(it.get("url"))
    name = e(it.get("source") or "Source")
    link = (lambda inner, cls: f'<a class="{cls}" href="{e(url)}" rel="noopener" target="_blank">{inner}</a>') if url \
        else (lambda inner, cls: f'<span class="{cls}">{inner}</span>')
    parts = [f'<span class="src-label">{L.s["source"]}</span>', link(name + '<span aria-hidden="true"> ↗</span>', "src-name")]
    if it.get("sourceTitle"):
        q1, q2 = ("« ", " »") if L.code == "fr" else ("“", "”")
        parts.append(f'<cite class="src-title">{link(q1 + e(it["sourceTitle"]) + q2, "src-title-link")}</cite>')
    meta = []
    if url:
        meta.append(e(urlparse(url).netloc.removeprefix("www.")))
    try:
        sd = date.fromisoformat(str(it.get("sourceDate")))
        meta.append(f'<time datetime="{sd.isoformat()}">{short_src_date(sd, L)}</time>')
    except ValueError:
        pass
    if meta:
        parts.append(f'<span class="src-meta">{" · ".join(meta)}</span>')
    return f'<p class="src">{"".join(parts)}</p>'

ECHELLES = {"ville": 6, "proche": 10, "pays": 16, "region": 30, "continent": 60}

def map_figure(it, key, L, une=False):
    """Carte de localisation d'un sujet, si son lieu est connu."""
    lieu = it.get("lieu") or {}
    try:
        lat, lon = float(lieu["lat"]), float(lieu["lon"])
    except (KeyError, TypeError, ValueError):
        return ""
    span = ECHELLES.get(lieu.get("echelle"), 12 if key == "france" else 30)
    svg = (visuals.map_svg(lat, lon, 520, 190, span * 1.8) if une
           else visuals.map_svg(lat, lon, 240, 160, span))
    if not svg:
        return ""
    nom = (lieu.get("nom_en") if L.code == "en" else None) or lieu.get("nom") or ""
    cls = "une-map" if une else "story-map"
    return (f'<figure class="{cls}">{svg}<figcaption><svg class="pin" viewBox="0 0 12 12" aria-hidden="true">'
            f'<circle cx="6" cy="6" r="3.2"/></svg>{e(nom)}</figcaption></figure>')

def why_html(it, L):
    w = L.tx(it, "why")
    return f'<p class="why"><span class="why-label">{e(L.s["why"])}</span> {e(w)}</p>' if w else ""

def share_btn(url, title, L, label=None, cls="share"):
    return (f'<button class="{cls}" type="button" data-share="{e(url)}" data-title="{e(title)}">'
            f'{label or L.s["share"]}</button>')

def item_html(it, c, L, edition_url):
    fig = map_figure(it, c["key"], L)
    return f"""<article class="story{' has-map' if fig else ''}" id="{it['_id']}">
  <div class="story-text">
  <h3>{e(L.tx(it, 'title'))}</h3>
  <p class="summary">{e(L.tx(it, 'summary'))}</p>
  {why_html(it, L)}
  <div class="story-meta">{source_html(it, L)}{share_btn(edition_url + "#" + it["_id"], L.tx(it, "title"), L)}</div>
  </div>
  {fig}
</article>"""

def edition_page(d, eds, L, is_home):
    global CUR
    CUR = L
    day = d["_day"]
    path = page_path("home", L) if is_home else page_path("edition", L, d["date"])
    alt_paths = [(X.code, page_path("home", X) if is_home else page_path("edition", X, d["date"])) for X in LANGS]
    root = depth_root(path)
    lroot = root + L.prefix
    idx = eds.index(d)
    prev_ed = eds[idx - 1] if idx > 0 else None
    next_ed = eds[idx + 1] if idx + 1 < len(eds) else None
    edition_url = SITE_URL + page_path("edition", L, d["date"])
    overview = L.top(d, "overview") or []
    une_title = L.tx(d["_une"][1], "title") if d["_une"] else long_date(day, L)
    heading = f"{day_date(day, L)} — {une_title}" if d["_une"] else long_date(day, L)
    if is_home:
        title, desc = L.s["home_title"], L.s["site_desc"]
    else:
        title, desc = f"{heading} · {SITE_NAME}", (overview[0] if overview else L.tagline)
    upd = d["_updated"]
    upd_html = f'<span>{L.s["published"].format(t=hhmm(upd, L))}</span>' if upd else ""
    og = f"assets/og/{d['date']}.png" if L.code == "fr" else f"assets/og/en/{d['date']}.png"
    ld = [ld_website(L)] if is_home else [ld_edition(d, L, edition_url, og, heading)]
    extra = ""
    if is_home and L.code == "fr":
        # Préférence mémorisée : un lecteur qui a choisi l'anglais arrive directement sur la version anglaise.
        extra = '\n<script>try{if(localStorage.getItem("lang")==="en")location.replace("en/"+location.hash)}catch(e){}</script>'
    topics = (L.s["topic1"] if d["_topics"] == 1 else L.s["topics"]).format(n=d["_topics"])
    out = [head(L, title, desc, path, "website" if is_home else "article", og, une_title, alt_paths, extra, ld),
           masthead(L, path, "home" if is_home else "", alt_paths)]
    out.append(f"""<main id="contenu">
<div class="dateline">
  <div class="dateline-in">
    <p class="edition-date"><time datetime="{d['date']}">{long_date(day, L)}</time></p>
    <p class="edition-meta">
      <span>{L.s['edition_no'].format(n=d['_num'])}</span>
      <span>{topics}</span>
      <span>{L.s['minutes'].format(n=minutes(d, L))}</span>
      {upd_html}
      <span class="sunrise" title="{L.s['sunrise_title']}">{SUN_SVG}{L.s['sunrise'].format(t=hhmm(sunrise_paris(day), L))}</span>
    </p>
  </div>
</div>
""")
    une_html = ""
    if d["_une"]:
        c, it = d["_une"]
        une_html = f"""<article class="une" id="une" style="--rub: var(--r-{c['key']})">
    <p class="kicker"><span class="kicker-une">{L.s['une']}</span><a href="#{c['slug']}">{e(rub_name(c, L))}</a></p>
    <h1>{e(L.tx(it, 'title'))}</h1>
    <p class="une-summary">{e(L.tx(it, 'summary'))}</p>
    {why_html(it, L)}
    <div class="story-meta">{source_html(it, L)}{share_btn(edition_url + "#une", L.tx(it, "title"), L)}</div>
    {map_figure(it, c['key'], L, une=True)}
  </article>"""
    ess = ""
    if overview:
        lis = "".join(f"<li>{e(t)}</li>" for t in overview)
        ess = f"""<aside class="essentiel" aria-labelledby="ess-title">
    <h2 id="ess-title">{L.s['essentials']}</h2>
    <ul>{lis}</ul>
    {share_btn(edition_url, title if not is_home else f"{heading} · {SITE_NAME}", L, L.s['share_ed'], "share share-ed")}
  </aside>"""
    out.append(f'<section class="top">\n  {une_html}\n  {ess}\n</section>\n')

    ch = [x for x in (d.get("chiffres") or []) if x.get("value") and x.get("label")]
    if ch:
        cells = "".join(
            f'<div class="chiffre" style="--rub: var(--r-{e(x.get("key", "monde"))})">'
            f'<p class="val">{e((x.get("value_en") if L.code == "en" else None) or x["value"])}</p>'
            f'<p class="lab">{e((x.get("label_en") if L.code == "en" else None) or x["label"])}</p></div>'
            for x in ch[:4])
        out.append(f'<section class="chiffres" aria-labelledby="ch-title"><h2 id="ch-title" class="section-label">{L.s["numbers"]}</h2><div class="chiffres-grid">{cells}</div></section>\n')

    chips = [f'<button type="button" class="chip" data-filter="tout" aria-pressed="true">{L.s["all"]}</button>']
    for c in d["_cats"]:
        n = len([i for i in c["items"] if not i.get("_une")])
        if n:
            chips.append(f'<a class="chip" href="#{c["slug"]}" data-filter="{c["slug"]}" style="--rub: var(--r-{c["key"]})"><span class="dot"></span>{e(rub_name(c, L))}<span class="n">{n}</span></a>')
    out.append(f'<nav class="filters" aria-label="{L.s["sections"]}"><div class="filters-in">{"".join(chips)}</div></nav>\n')

    secs = []
    for c in d["_cats"]:
        items = [i for i in c["items"] if not i.get("_une")]
        if not items:
            continue
        stories = "\n".join(item_html(it, c, L, edition_url) for it in items)
        count = (L.s["topic1"] if len(items) == 1 else L.s["topics"]).format(n=len(items))
        secs.append(f"""<section class="rubrique" id="{c['slug']}" data-rub="{c['slug']}" style="--rub: var(--r-{c['key']})">
  <header class="rub-head"><h2>{e(rub_name(c, L))}</h2><p>{count}</p></header>
  <div class="rub-body">
{stories}
  </div>
</section>""")
    out.append('<div class="rubriques">\n' + "\n".join(secs) + "\n</div>\n")

    note = L.top(d, "note")
    if note:
        out.append(f'<p class="note">{e(note)}</p>\n')

    href = lambda ed: lroot + f"edition/{ed['date']}/"
    pv = (f'<a class="pager-prev" href="{href(prev_ed)}"><span>{L.s["prev"]}</span>{long_date(prev_ed["_day"], L)}</a>'
          if prev_ed else "<span></span>")
    nx = (f'<a class="pager-next" href="{href(next_ed) if next_ed is not eds[-1] else lroot}"><span>{L.s["next"]}</span>{long_date(next_ed["_day"], L)}</a>'
          if next_ed else f'<p class="pager-next pager-soon"><span>{L.s["soon"]}</span>{L.s["tomorrow"]}</p>')
    out.append(f'<nav class="pager" aria-label="{L.s["editions_nav"]}">{pv}{nx}</nav>\n</main>\n')
    out.append(footer(L, path))
    return "".join(out)

def org(L):
    return {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL + L.prefix,
            "logo": {"@type": "ImageObject", "url": SITE_URL + "assets/app-512.png", "width": 512, "height": 512}}

def ld_website(L):
    return {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": SITE_URL + L.prefix,
            "inLanguage": L.code, "description": L.s["site_desc"], "publisher": org(L)}

def published(d):
    day = d["_day"]
    return d["_updated"] or datetime(day.year, day.month, day.day, 6, tzinfo=PARIS)

def ld_edition(d, L, url, og, heading):
    """L'édition comme article d'actualité (NewsArticle), avec ses rubriques et les articles cités."""
    overview = L.top(d, "overview") or []
    when = published(d).isoformat(timespec="seconds")
    sources = []
    for c in d["_cats"]:
        for it in c["items"]:
            u = safe_url(it.get("url"))
            if u and u not in sources:
                sources.append(u)
    return {"@context": "https://schema.org", "@type": "NewsArticle",
            "headline": heading if len(heading) <= 110 else heading[:109].rstrip() + "…",
            "description": " ".join(overview[:2]) or L.tagline,
            "datePublished": when, "dateModified": when, "inLanguage": L.code,
            "url": url, "mainEntityOfPage": url, "image": [SITE_URL + og],
            "isAccessibleForFree": True, "articleSection": [rub_name(c, L) for c in d["_cats"]],
            "author": org(L), "publisher": org(L), "isBasedOn": sources}

def sitemap(eds):
    """Plan du site pour les moteurs de recherche, avec les équivalences français / anglais."""
    def entry(kind, day, lastmod):
        alts = "".join(f'<xhtml:link rel="alternate" hreflang="{X.code}" href="{SITE_URL}{page_path(kind, X, day)}"/>'
                       for X in LANGS)
        alts += f'<xhtml:link rel="alternate" hreflang="x-default" href="{SITE_URL}{page_path(kind, FR, day)}"/>'
        return "".join(f"<url><loc>{SITE_URL}{page_path(kind, L, day)}</loc><lastmod>{lastmod}</lastmod>{alts}</url>\n"
                       for L in LANGS)
    last = published(eds[-1]).isoformat(timespec="seconds")
    rows = [entry("home", None, last), entry("archives", None, last)]
    rows += [entry("edition", d["date"], published(d).isoformat(timespec="seconds")) for d in reversed(eds)]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "".join(rows) + "</urlset>\n")

def manifest(L):
    """Manifeste d'application : « Ajouter à l'écran d'accueil » sur téléphone."""
    up = "../" if L.prefix else ""
    return json.dumps({
        "name": SITE_NAME, "short_name": SITE_NAME, "description": L.tagline, "lang": L.code,
        "start_url": "./", "scope": "./", "display": "standalone",
        "background_color": "#0c1422", "theme_color": "#0c1422",
        "icons": [{"src": f"{up}assets/app-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": f"{up}assets/app-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": f"{up}assets/app-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
    }, ensure_ascii=False, indent=1)

def archives_page(eds, L):
    global CUR
    CUR = L
    path = page_path("archives", L)
    alt_paths = [(X.code, page_path("archives", X)) for X in LANGS]
    root = depth_root(path)
    lroot = root + L.prefix
    rows, current_month = [], None
    for d in reversed(eds):
        day = d["_day"]
        m = (day.year, day.month)
        if m != current_month:
            if current_month:
                rows.append("</ol></section>")
            rows.append(f'<section class="month"><h2>{L.months[day.month - 1].capitalize()} {day.year}</h2><ol class="ed-list">')
            current_month = m
        lead = e(L.tx(d["_une"][1], "title")) if d["_une"] else ""
        topics = (L.s["topic1"] if d["_topics"] == 1 else L.s["topics"]).format(n=d["_topics"])
        rows.append(f"""<li><a href="{lroot}edition/{d['date']}/">
  <span class="ed-date"><b>{day.day}</b>{L.days[day.weekday()]}</span>
  <span class="ed-body"><span class="ed-num">{L.s['edition_no'].format(n=d['_num'])} · {topics}</span><span class="ed-lead">{lead}</span></span>
</a></li>""")
    if current_month:
        rows.append("</ol></section>")
    first = long_date(eds[0]["_day"], L)
    count = (L.s["arch_count1"] if len(eds) == 1 else L.s["arch_count"]).format(
        n=len(eds), d=first.lower() if L.code == "fr" else first)
    out = [head(L, f"{L.s['archives']} · {SITE_NAME}", L.s["arch_desc"], path, alt_paths=alt_paths),
           masthead(L, path, "archives", alt_paths)]
    out.append(f"""<main id="contenu" class="archives">
  <header class="arch-head">
    <h1>{L.s['archives']}</h1>
    <p>{e(count)}</p>
    <label class="search" for="q"><span class="visually-hidden">{L.s['search_label']}</span>
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg>
      <input id="q" type="search" placeholder="{e(L.s['search_ph'])}" autocomplete="off" data-search="{lroot}search.json" data-root="{lroot}">
    </label>
  </header>
  <div id="results" class="results" hidden></div>
  <div id="ed-index">
{"".join(rows)}
  </div>
</main>
""")
    out.append(footer(L, path))
    return "".join(out)

def page_404():
    global CUR
    CUR = FR
    root = "/bilan-du-monde/"
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Page introuvable · {SITE_NAME}</title>
<link rel="icon" href="{root}assets/icon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{root}assets/style.css">
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
</head>
<body>
<header class="masthead"><div class="masthead-in"><a class="wordmark" href="{root}"><span class="wm-mark" aria-hidden="true"></span>Bilan du monde</a></div></header>
<main id="contenu" class="archives"><header class="arch-head">
<h1>Page introuvable</h1>
<p>Cette page n'existe pas ou plus. <a href="{root}">Lire l'édition du jour</a> ou <a href="{root}archives/">parcourir les archives</a>.</p>
<p lang="en">This page doesn't exist. <a href="{root}en/">Read today's edition in English</a> or <a href="{root}en/archives/">browse the archive</a>.</p>
</header></main>
</body>
</html>
"""

def feed(eds, L):
    global CUR
    CUR = L
    items = []
    for d in reversed(eds[-30:]):
        link = SITE_URL + page_path("edition", L, d["date"])
        lead = L.tx(d["_une"][1], "title") if d["_une"] else ""
        body = "".join(f"<li>{e(t)}</li>" for t in L.top(d, "overview") or [])
        pub = d["_updated"] or datetime(d["_day"].year, d["_day"].month, d["_day"].day, 6, tzinfo=PARIS)
        items.append(f"""<item>
<title>{e(long_date(d['_day'], L))} · {e(lead)}</title>
<link>{link}</link>
<guid isPermaLink="true">{link}</guid>
<pubDate>{format_datetime(pub)}</pubDate>
<description>{html.escape('<ul>' + body + '</ul>')}</description>
</item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>{SITE_NAME}</title>
<link>{SITE_URL}{L.prefix}</link>
<description>{e(L.tagline)}</description>
<language>{L.rss_lang}</language>
{''.join(items)}
</channel>
</rss>
"""

def search_index(eds, L):
    rows = []
    for d in eds:
        for c in d["_cats"]:
            for it in c["items"]:
                rows.append({"d": d["date"], "r": rub_name(c, L), "k": c["key"],
                             "t": L.tx(it, "title"), "s": L.tx(it, "summary") or "",
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
    host = SITE_URL.split("://", 1)[1].rstrip("/")
    for size in (180, 192, 512):
        visuals.app_icon(os.path.join(ROOT, "assets", f"app-{size}.png"), size)
    for L in LANGS:
        og_dir = os.path.join(ROOT, "assets", "og", *(["en"] if L.code == "en" else []))
        for d in eds:
            une = d["_une"]
            visuals.og_image(os.path.join(og_dir, f"{d['date']}.png"),
                             L.tx(une[1], "title") if une else L.tagline,
                             f"{long_date(d['_day'], L)} · {L.s['edition_no'].format(n=d['_num'])}",
                             f"{L.s['une']} · {rub_name(une[0], L)}" if une else "",
                             f"{host}{'/en' if L.code == 'en' else ''} · {L.s['minutes'].format(n=minutes(d, L))}")
        visuals.og_image(os.path.join(og_dir, "site.png"), L.tagline, L.s["og_when"], L.s["og_tag"], host)
        for d in eds:
            write(page_path("edition", L, d["date"]) + "index.html", edition_page(d, eds, L, False))
        write(page_path("home", L) + "index.html", edition_page(eds[-1], eds, L, True))
        write(page_path("archives", L) + "index.html", archives_page(eds, L))
        write(L.prefix + "feed.xml", feed(eds, L))
        write(L.prefix + "search.json", json.dumps(search_index(eds, L), ensure_ascii=False, separators=(",", ":")))
        write(L.prefix + "manifest.webmanifest", manifest(L))
    write("sitemap.xml", sitemap(eds))
    write("404.html", page_404())
    missing = [d["date"] for d in eds if not d.get("overview_en")]
    print(f"Site généré : {len(eds)} édition(s), dernière du {eds[-1]['date']}."
          + (f" Éditions sans traduction anglaise : {', '.join(missing)}." if missing else ""))

if __name__ == "__main__":
    main()
