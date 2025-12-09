#!/bin/bash

REMOTE_USER="root"
REMOTE_HOST="192.168.5.135"
REMOTE_PATH="/homeassistant/custom_components/net4home"

echo "Deploying to test system..."

# Sync code to the test system
rsync -avz --delete ./ $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/

# Optional: Restart service remotely
ssh $REMOTE_USER@$REMOTE_HOST "ha core restart"

echo "Deployment complete."
