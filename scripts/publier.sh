#!/bin/zsh
# Publie une édition du Bilan du monde.
# Usage : scripts/publier.sh chemin/vers/AAAA-MM-JJ.json
# Vérifie le fichier, le copie dans editions/, régénère editions/index.json,
# puis fait un commit et un push (si un dépôt distant est configuré).
set -euo pipefail

SITE_DIR="${0:A:h:h}"
SRC="${1:?Indique le fichier JSON de l'édition}"
cd "$SITE_DIR"

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

python3 -I - <<'PY'
import json, os, re
dates = sorted((f[:-5] for f in os.listdir("editions") if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", f)), reverse=True)
with open("editions/index.json", "w", encoding="utf-8") as fh:
    json.dump({"editions": dates}, fh, ensure_ascii=False, indent=1)
print(f"{len(dates)} édition(s) dans l'index")
PY

git add editions
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
