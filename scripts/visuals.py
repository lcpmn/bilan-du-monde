"""Visuels du Bilan du monde : cartes de localisation (SVG) et images de partage (PNG).

- Cartes : fond Natural Earth 1:50m (domaine public) via world-atlas (scripts/data/countries-50m.json).
  Projection équirectangulaire centrée sur le lieu, découpée au cadre, dessinée en SVG inline
  pour suivre le thème clair/sombre du site.
- Images de partage : 1200 × 630 px, générées avec Pillow et la police Schibsted Grotesk
  (scripts/data/SchibstedGrotesk.ttf, licence SIL OFL, voir scripts/data/OFL.txt).
"""
import json
import math
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


# ======================================================================
# Cartes
# ======================================================================
_countries = None

def _load_countries():
    """Décode le TopoJSON en liste de pays : (nom, [anneaux de (lon, lat)], bbox)."""
    global _countries
    if _countries is not None:
        return _countries
    with open(os.path.join(DATA, "countries-50m.json"), encoding="utf-8") as fh:
        topo = json.load(fh)
    (sx, sy), (tx, ty) = topo["transform"]["scale"], topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(indexes):
        out = []
        for i in indexes:
            pts = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(pts if not out else pts[1:])
        return out

    countries = []
    for g in topo["objects"]["countries"]["geometries"]:
        polys = g["arcs"] if g.get("type") == "MultiPolygon" else [g.get("arcs") or []]
        rings = [ring(r) for p in polys for r in p]
        rings = [r for r in rings if len(r) > 2]
        if not rings:
            continue
        lons = [p[0] for r in rings for p in r]
        lats = [p[1] for r in rings for p in r]
        countries.append(((g.get("properties") or {}).get("name", ""), rings, (min(lons), min(lats), max(lons), max(lats))))
    _countries = countries
    return countries

def _inside(lon, lat, rings):
    """Point dans un pays (règle pair-impair sur tous ses anneaux)."""
    c = False
    for r in rings:
        j = len(r) - 1
        for i in range(len(r)):
            xi, yi = r[i]
            xj, yj = r[j]
            if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
                c = not c
            j = i
    return c

def _clip(poly, xmin, ymin, xmax, ymax):
    """Découpe d'un polygone par un rectangle (Sutherland–Hodgman)."""
    def clip_edge(pts, inside, inter):
        out = []
        if not pts:
            return out
        prev = pts[-1]
        for cur in pts:
            if inside(cur):
                if not inside(prev):
                    out.append(inter(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(inter(prev, cur))
            prev = cur
        return out

    def ix(x):
        return lambda a, b: (x, a[1] + (b[1] - a[1]) * (x - a[0]) / ((b[0] - a[0]) or 1e-12))

    def iy(y):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (y - a[1]) / ((b[1] - a[1]) or 1e-12), y)

    pts = clip_edge(poly, lambda p: p[0] >= xmin, ix(xmin))
    pts = clip_edge(pts, lambda p: p[0] <= xmax, ix(xmax))
    pts = clip_edge(pts, lambda p: p[1] >= ymin, iy(ymin))
    pts = clip_edge(pts, lambda p: p[1] <= ymax, iy(ymax))
    return pts

def _n(v):
    t = f"{v:.1f}"
    return t[:-2] if t.endswith(".0") else t

def _path(rings_px):
    parts = []
    for r in rings_px:
        if len(r) < 3:
            continue
        kept = [r[0]]
        for p in r[1:]:
            if abs(p[0] - kept[-1][0]) + abs(p[1] - kept[-1][1]) >= 1.5:
                kept.append(p)
        if len(kept) < 3:
            continue
        parts.append("M" + "L".join(f"{_n(x)} {_n(y)}" for x, y in kept) + "Z")
    return "".join(parts)

def map_svg(lat, lon, width=240, height=160, span=30.0):
    """Carte de localisation centrée sur (lat, lon). `span` = largeur couverte en degrés de longitude."""
    lat, lon = float(lat), float(lon)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return ""
    k = width / span                       # px par degré de longitude (à l'échelle du cadre)
    ky = k / max(math.cos(math.radians(lat)), 0.35)  # px par degré de latitude
    half_lon = span / 2 + 2
    half_lat = (height / 2) / ky + 2
    pad = 6

    def proj(p):
        dl = (p[0] - lon + 540) % 360 - 180
        return (width / 2 + dl * k, height / 2 - (p[1] - lat) * ky)

    # Pays du lieu : celui qui contient le point, sinon le plus proche à moins de 0,6° (côtes simplifiées).
    home, best = None, 0.6
    for name, rings, (x0, y0, x1, y1) in _load_countries():
        if not (x0 - 1 <= lon <= x1 + 1 and y0 - 1 <= lat <= y1 + 1):
            continue
        if _inside(lon, lat, rings):
            home = name
            break
        for r in rings:
            for p in r:
                dd = math.hypot(p[0] - lon, p[1] - lat)
                if dd < best:
                    best, home = dd, name

    land, hl = [], []
    for name, rings, (x0, y0, x1, y1) in _load_countries():
        if y1 < lat - half_lat or y0 > lat + half_lat:
            continue
        near = False
        for r in rings:
            for p in r[:: max(1, len(r) // 40)]:
                if abs((p[0] - lon + 540) % 360 - 180) <= half_lon + 10:
                    near = True
                    break
            if near:
                break
        if not near:
            continue
        target = hl if name == home else land
        for r in rings:
            pr = [proj(p) for p in r]
            xs = [p[0] for p in pr]
            if max(xs) - min(xs) > width * 4:   # anneau qui traverse l'antiméridien dans ce cadre
                continue
            c = _clip(pr, -pad, -pad, width + pad, height + pad)
            if len(c) > 2:
                target.append(c)
    cx, cy = width / 2, height / 2
    return (f'<svg class="map" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
            f'<rect class="map-sea" width="{width}" height="{height}"/>'
            f'<path class="map-land" d="{_path(land)}"/>'
            + (f'<path class="map-hl" d="{_path(hl)}"/>' if hl else "")
            + f'<circle class="map-ring" cx="{cx:g}" cy="{cy:g}" r="11"/>'
            f'<circle class="map-dot" cx="{cx:g}" cy="{cy:g}" r="4.5"/></svg>')


# ======================================================================
# Images de partage
# ======================================================================
OG_W, OG_H = 1200, 630
INK = (12, 20, 34)
WHITE = (240, 244, 249)
SOFT = (150, 166, 188)
SUN = (226, 144, 26)

def _font(size, weight):
    from PIL import ImageFont
    f = ImageFont.truetype(os.path.join(DATA, "SchibstedGrotesk.ttf"), size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f

def _wrap(text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.getlength(t) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def _tracked(draw, xy, text, font, fill, tracking):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + tracking
    return x

def og_image(path, headline, dateline="", kicker="", footer=""):
    """Écrit une image de partage PNG 1200 × 630."""
    from PIL import Image, ImageDraw
    scale = 2  # rendu en double résolution puis réduit, pour un lissage net
    W, H = OG_W * scale, OG_H * scale
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    s = lambda v: int(v * scale)

    # Soleil levant, en bas à droite : halo puis disque.
    cx, cy, r = s(1085), s(735), s(250)
    for i, a in enumerate((0.06, 0.1, 0.16)):
        rr = r + s(110 - i * 40)
        col = tuple(int(INK[j] + (SUN[j] - INK[j]) * a) for j in range(3))
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=col)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=SUN)

    # Marque : un soleil qui se lève dans un disque sombre (comme sur le site).
    mx, my, mr = s(72), s(58), s(17)
    mark = Image.new("RGB", (2 * mr, 2 * mr), (34, 48, 72))
    md = ImageDraw.Draw(mark)
    sr = int(mr * 1.15)
    md.ellipse((mr - sr, int(mr * 2.25) - sr, mr + sr, int(mr * 2.25) + sr), fill=SUN)
    mask = Image.new("L", (2 * mr, 2 * mr), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 2 * mr - 1, 2 * mr - 1), fill=255)
    img.paste(mark, (mx, my), mask)
    d.text((mx + 2 * mr + s(14), my + mr), "Bilan du monde", font=_font(s(32), 800), fill=WHITE, anchor="lm")

    y = s(134)
    if dateline:
        d.text((s(72), y), dateline, font=_font(s(26), 500), fill=SOFT)
        y += s(74)
    else:
        y += s(40)
    if kicker:
        _tracked(d, (s(72), y), kicker.upper(), _font(s(21), 700), SUN, s(2.2))
        y += s(46)

    # Titre : la plus grande taille qui tient sur 3 lignes.
    max_w = s(800)
    for size in (80, 74, 68, 62, 56, 50, 46):
        f = _font(s(size), 800)
        lines = _wrap(headline, f, max_w)
        if len(lines) <= 3:
            break
    lines = lines[:3]
    lh = int(s(size) * 1.04)
    for i, line in enumerate(lines):
        d.text((s(68), y + i * lh), line, font=f, fill=WHITE)

    if footer:
        d.text((s(72), s(OG_H - 64)), footer, font=_font(s(24), 500), fill=SOFT, anchor="ls")

    img = img.resize((OG_W, OG_H), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "PNG", optimize=True)
