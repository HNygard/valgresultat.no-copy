#!/bin/bash

# Cronjob:
# */10 * * * * /bin/bash /opt/valgresultat.no-copy/app/cron/deploy-commit-push.sh >> /opt/valgresultat.no-copy/logs/deploy-cronjob.log 2>&1

# Navigate to the project directory
cd /opt/valgresultat.no-copy/app || exit

export GIT_SSH_COMMAND="ssh -i /opt/valgresultat.no-copy/secrets/id_ed25519 -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes"

# Fetch the latest changes from the remote repository
git fetch origin main

# Check if there are new commits
LOCAL_HASH=$(git rev-parse HEAD)
REMOTE_HASH=$(git rev-parse origin/main)

if [ "$LOCAL_HASH" != "$REMOTE_HASH" ]; then
  # New commits detected, proceed with deployment
  echo "[$(date)] New commits detected. Pulling changes and redeploying..."

  # Pull the latest changes
  git pull origin main

  # Build election-monitor image locally (it has its own Dockerfile)
  echo "[$(date)] Building election-monitor image..."
  docker compose build election-monitor

  # Pull other images from registry
  echo "[$(date)] Pulling other images..."
  docker compose pull

  # Restart all services
  echo "[$(date)] Restarting services..."
  docker compose up -d

  echo "[$(date)] Deployment completed."
fi

./cron/data-commit-push.sh
