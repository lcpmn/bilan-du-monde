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
d = json.load(open(sys.argv[1], encoding="utf-8"))
assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.get("date", "")), "champ date invalide"
assert isinstance(d.get("categories"), list) and d["categories"], "aucune rubrique"
for c in d["categories"]:
    for it in c.get("items", []):
        assert it.get("title") and it.get("summary"), "sujet incomplet dans " + c.get("key", "?")
        assert str(it.get("url", "")).startswith("https://"), "URL invalide : " + it.get("title", "")
print(d["date"])
PY
)

if [[ "${SRC:A}" != "${SITE_DIR}/editions/${DATE}.json" ]]; then
  cp "$SRC" "editions/${DATE}.json"
fi

python3 -I "$SITE_DIR/scripts/build.py"

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
