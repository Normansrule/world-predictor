#!/usr/bin/env bash
# Create the public GitHub repository (if needed) and push this project to it.
# Usage: scripts/publish_to_github.sh [owner] [repo-name]
set -euo pipefail

OWNER="${1:-Normansrule}"
NAME="${2:-world-predictor}"
URL="https://github.com/${OWNER}/${NAME}.git"
DESCRIPTION="Seldon-style psychohistory experiments: forecasting world news, markets (stocks, gold, silver) and technology adoption with Google's open-source TimesFM."

cd "$(dirname "$0")/.."

if [ ! -d .git ]; then
  git init -b main
  git add -A
  git commit -m "World Predictor: Seldon-style forecasting with Google's TimesFM"
fi
git branch -M main

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  if gh repo view "${OWNER}/${NAME}" >/dev/null 2>&1; then
    echo "Repository ${OWNER}/${NAME} already exists; pushing to it."
  else
    gh repo create "${OWNER}/${NAME}" --public --description "${DESCRIPTION}"
  fi
else
  echo "GitHub CLI not available or not logged in."
  echo "Create an EMPTY public repo named '${NAME}' at https://github.com/new (no README, no licence),"
  read -r -p "then press Enter to push... " _
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "${URL}"
else
  git remote add origin "${URL}"
fi
git push -u origin main
echo "Done: https://github.com/${OWNER}/${NAME}"
