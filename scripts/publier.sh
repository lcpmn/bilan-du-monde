#!/bin/zsh
# Publie une édition du Bilan du monde.
# Usage : scripts/publier.sh chemin/vers/AAAA-MM-JJ.json
# Vérifie le fichier, le copie dans editions/,
# régénère les pages du site (scripts/build.py), puis fait un commit et un push.
set -euo pipefail

SITE_DIR="${0:A:h:h}"
SRC="${1:?Indique le fichier JSON de l'édition}"
cd "$SITE_DIR"

BRANCH=$(git branch --show-current)
if [[ "$BRANCH" != "main" ]]; then
  echo "Erreur : le dépôt est sur la branche $BRANCH au lieu de main. Publication annulée." >&2
  exit 1
fi

DATE=$(python3 -I - "$SRC" <<'PY'
import json, re, sys
from urllib.parse import urlparse

# Sites qui ne sont pas des sources d'origine (newsletters, agrégateurs, revues de presse).
AGREGATEURS = ("substack.com", "ground.news", "biztoc.com", "newswav.com", "presse-evasion.fr",
               "titrespresse.com", "digg.com", "feedbagel.com", "news.google.com")

def lien_article(u):
    """Vrai si l'URL pointe vers un article précis, pas vers une page d'accueil ou de rubrique."""
    p = urlparse(u)
    segs = [x for x in p.path.split("/") if x]
    if re.search(r"\d{4,}", p.path + "?" + p.query):
        return True
    return bool(segs) and segs[-1].count("-") >= 3

d = json.load(open(sys.argv[1], encoding="utf-8"))
assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.get("date", "")), "champ date invalide"
assert isinstance(d.get("categories"), list) and d["categories"], "aucune rubrique"
for c in d["categories"]:
    for it in c.get("items", []):
        assert it.get("title") and it.get("summary"), "sujet incomplet dans " + c.get("key", "?")
        url = str(it.get("url", ""))
        titre = it.get("title", "")
        assert url.startswith("https://"), "URL invalide : " + titre
        assert lien_article(url), "le lien doit mener à l'article précis, pas à une page d'accueil ou de rubrique : " + titre + " → " + url
        hote = urlparse(url).netloc.lower()
        assert not any(hote == a or hote.endswith("." + a) for a in AGREGATEURS), "source non originale (agrégateur ou newsletter) : " + titre + " → " + hote
        assert it.get("source"), "nom du média manquant : " + titre
        if it.get("sourceDate"):
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(it["sourceDate"])), "sourceDate doit être au format AAAA-MM-JJ : " + titre
        lieu = it.get("lieu")
        if lieu is not None:
            assert isinstance(lieu, dict) and lieu.get("nom"), "lieu sans nom : " + it.get("title", "")
            assert -90 <= float(lieu["lat"]) <= 90 and -180 <= float(lieu["lon"]) <= 180, "coordonnées invalides : " + it.get("title", "")
print(d["date"])
PY
)

if [[ "${SRC:A}" != "${SITE_DIR}/editions/${DATE}.json" ]]; then
  cp "$SRC" "editions/${DATE}.json"
fi

python3 "$SITE_DIR/scripts/build.py"

git add -A
if git diff --cached --quiet; then
  echo "Rien de nouveau à publier."
  exit 0
fi
git commit -q -m "Édition du ${DATE}"
if git remote get-url origin >/dev/null 2>&1; then
  git push -q origin HEAD
  echo "Édition du ${DATE} publiée."
else
  echo "Édition du ${DATE} enregistrée localement (aucun dépôt distant configuré)."
fi
