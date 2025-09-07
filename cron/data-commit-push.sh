#!/bin/bash

# Cronjob:
# See "deploy-commit.push.sh"

# Navigate to the project directory
cd /opt/valgresultat.no-copy/app || exit

# Commit and push any new data changes
if [[ -n $(git status --porcelain data) ]]; then
  echo "[$(date)] Data changed. Commiting and pushing."
  git add data
  git commit -m "[bot] Automated commit of new data" || echo "No changes to commit"
  git push origin main || echo "Failed to push changes"
fi