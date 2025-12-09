# Deployment Guide - net4home Integration

This guide explains how to deploy the net4home Home Assistant integration to a test server via SSH.

## Prerequisites

- SSH access to your Home Assistant test server
- Knowledge of your Home Assistant configuration directory path
- Appropriate file permissions on the server

## Home Assistant Configuration Directory Locations

The configuration directory varies by installation type:

- **Home Assistant OS (HassOS)**: `/config/` (accessible via SSH add-on or Samba)
- **Home Assistant Container (Docker)**: Usually mounted at `/config/` or `~/homeassistant/`
- **Home Assistant Core (Python venv)**: Typically `~/.homeassistant/` or `/etc/homeassistant/`
- **Home Assistant Supervised**: `/usr/share/hassio/homeassistant/` or `/config/`

## Deployment Methods

### Method 1: Using SCP (Simple Copy)

**Step 1: Connect and verify directory structure**
```bash
# SSH into your server
ssh user@your-server-ip

# Navigate to Home Assistant config directory
cd /config  # or your HA config path

# Create custom_components directory if it doesn't exist
mkdir -p custom_components
```

**Step 2: Transfer files from your local machine**
```bash
# From your local machine (Windows PowerShell or Linux/Mac terminal)
# Transfer the entire net4home folder
scp -r custom_components/net4home user@your-server-ip:/config/custom_components/

# Or if you're already in the project root:
scp -r custom_components/net4home user@your-server-ip:/config/custom_components/
```

**Step 3: Verify file structure on server**
```bash
# SSH into server and verify
ssh user@your-server-ip
ls -la /config/custom_components/net4home/
# Should show: __init__.py, api.py, manifest.json, etc.
```

**Step 4: Set correct permissions**
```bash
# Ensure proper permissions (Home Assistant usually runs as specific user)
# Check who owns the config directory
ls -la /config/

# Set ownership if needed (adjust user:group as needed)
sudo chown -R homeassistant:homeassistant /config/custom_components/net4home
chmod -R 644 /config/custom_components/net4home/*.py
chmod 755 /config/custom_components/net4home
```

### Method 2: Using RSYNC (Recommended for Updates)

RSYNC is better for incremental updates and preserves file permissions.

**From your local machine:**
```bash
# Sync files (excludes .git, __pycache__, etc.)
rsync -avz --exclude='__pycache__' \
           --exclude='*.pyc' \
           --exclude='.git' \
           custom_components/net4home/ \
           user@your-server-ip:/config/custom_components/net4home/

# With progress and deletion of removed files (careful!)
rsync -avz --delete \
           --exclude='__pycache__' \
           --exclude='*.pyc' \
           custom_components/net4home/ \
           user@your-server-ip:/config/custom_components/net4home/
```

**Options explained:**
- `-a`: Archive mode (preserves permissions, timestamps, etc.)
- `-v`: Verbose
- `-z`: Compress during transfer
- `--delete`: Remove files on destination that don't exist in source
- `--exclude`: Skip these patterns

### Method 3: Using Git (If server has Git)

**On the server:**
```bash
# SSH into server
ssh user@your-server-ip

# Navigate to config directory
cd /config

# Clone or pull from your repository
cd custom_components
git clone https://github.com/your-username/net4home.git
# OR if already exists:
cd net4home
git pull origin main
```

### Method 4: Manual File Transfer (Samba/File Manager)

If you have Samba enabled on Home Assistant:

1. Connect to `\\your-server-ip\config` (Windows) or mount via Samba (Linux/Mac)
2. Navigate to `custom_components/`
3. Copy the `net4home` folder
4. Ensure all files are transferred

## Complete Deployment Script

Here's a complete script you can run from your local machine:

### Windows PowerShell Script

```powershell
# deploy.ps1
$SERVER = "user@your-server-ip"
$REMOTE_PATH = "/config/custom_components/net4home"
$LOCAL_PATH = "custom_components/net4home"

Write-Host "Deploying net4home integration to $SERVER..."

# Create remote directory if it doesn't exist
ssh $SERVER "mkdir -p /config/custom_components"

# Transfer files using SCP
scp -r "$LOCAL_PATH\*" "${SERVER}:${REMOTE_PATH}/"

Write-Host "Files transferred. Restarting Home Assistant..."
# Note: Restart command depends on your HA installation type
# ssh $SERVER "systemctl restart home-assistant"  # For systemd
# ssh $SERVER "ha core restart"  # For Home Assistant OS

Write-Host "Deployment complete!"
```

### Linux/Mac Bash Script

```bash
#!/bin/bash
# deploy.sh

SERVER="user@your-server-ip"
REMOTE_PATH="/config/custom_components/net4home"
LOCAL_PATH="custom_components/net4home"

echo "Deploying net4home integration to $SERVER..."

# Create remote directory
ssh $SERVER "mkdir -p /config/custom_components"

# Transfer files using rsync
rsync -avz --exclude='__pycache__' \
           --exclude='*.pyc' \
           --exclude='.git' \
           "$LOCAL_PATH/" \
           "${SERVER}:${REMOTE_PATH}/"

echo "Files transferred. Verifying..."

# Verify key files exist
ssh $SERVER "test -f $REMOTE_PATH/__init__.py && test -f $REMOTE_PATH/manifest.json && echo 'Files verified' || echo 'ERROR: Files missing!'"

echo "Deployment complete!"
echo "Don't forget to restart Home Assistant!"
```

## Restarting Home Assistant

After deployment, you need to restart Home Assistant to load the new/updated integration.

### Method 1: Via Home Assistant UI (Easiest)
1. Go to **Settings → System → Restart**
2. Click **Restart**

### Method 2: Via SSH Command

**Home Assistant OS:**
```bash
ssh user@your-server-ip
ha core restart
```

**Docker:**
```bash
ssh user@your-server-ip
docker restart homeassistant
# OR
docker-compose restart homeassistant
```

**Systemd (Home Assistant Core):**
```bash
ssh user@your-server-ip
sudo systemctl restart home-assistant
```

**Supervised:**
```bash
ssh user@your-server-ip
ha core restart
```

### Method 3: Reload Integration (Without Full Restart)

If you only changed integration code and want to avoid a full restart:

1. Go to **Settings → Devices & Services**
2. Find the **net4home** integration
3. Click the three dots menu → **Reload**

**Note:** Some changes (like manifest.json) require a full restart.

## Verification Steps

After deployment and restart, verify the integration:

### 1. Check Logs
```bash
# SSH into server
ssh user@your-server-ip

# View Home Assistant logs
tail -f /config/home-assistant.log | grep net4home

# OR if using journalctl
journalctl -u home-assistant -f | grep net4home
```

### 2. Check Integration Status
- Go to **Settings → Devices & Services**
- Look for **net4home** integration
- Verify it shows as "Connected" or "Available"

### 3. Verify Files
```bash
ssh user@your-server-ip
ls -la /config/custom_components/net4home/
# Should show all Python files, manifest.json, etc.
```

### 4. Check for Errors
- Go to **Settings → System → Logs**
- Filter for "net4home"
- Look for any import errors or missing dependencies

## Troubleshooting

### Issue: Files not appearing after transfer

**Solution:**
```bash
# Check file permissions
ssh user@your-server-ip
ls -la /config/custom_components/net4home/

# Fix permissions if needed
chmod -R 755 /config/custom_components/net4home
chown -R homeassistant:homeassistant /config/custom_components/net4home
```

### Issue: Integration not loading

**Check:**
1. Verify `manifest.json` exists and is valid JSON
2. Check for Python syntax errors:
   ```bash
   python3 -m py_compile /config/custom_components/net4home/*.py
   ```
3. Check Home Assistant logs for specific errors

### Issue: Permission denied during SCP

**Solution:**
```bash
# Ensure you have write permissions
ssh user@your-server-ip "sudo chmod 777 /config/custom_components"

# Or use sudo with SCP (less secure)
scp -r custom_components/net4home user@server:/tmp/
ssh user@server "sudo mv /tmp/net4home /config/custom_components/"
```

### Issue: Integration shows as "Not Loaded"

**Check:**
1. Verify folder structure: `custom_components/net4home/` (not `custom_components/custom_components/net4home/`)
2. Check `manifest.json` version matches Home Assistant requirements
3. Restart Home Assistant completely (not just reload)

## Quick Deployment Commands

### One-liner SCP (from project root)
```bash
scp -r custom_components/net4home user@server:/config/custom_components/ && ssh user@server "ha core restart"
```

### One-liner RSYNC (from project root)
```bash
rsync -avz --exclude='__pycache__' --exclude='*.pyc' custom_components/net4home/ user@server:/config/custom_components/net4home/ && ssh user@server "ha core restart"
```

## Automated Deployment with GitHub Actions (Advanced)

If you want to automate deployment, you can set up a GitHub Action:

```yaml
# .github/workflows/deploy.yml
name: Deploy to Test Server

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Deploy to server
        uses: appleboy/scp-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_KEY }}
          source: "custom_components/net4home"
          target: "/config/custom_components"
          
      - name: Restart Home Assistant
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_KEY }}
          script: "ha core restart"
```

## Best Practices

1. **Always backup before deployment:**
   ```bash
   ssh user@server "cp -r /config/custom_components/net4home /config/custom_components/net4home.backup"
   ```

2. **Test on test server first** before deploying to production

3. **Use version control** - Tag releases before deployment

4. **Check logs after deployment** to catch errors early

5. **Keep deployment scripts** in your repository for consistency

6. **Document server-specific paths** - Different HA installations use different paths

## File Structure Verification

After deployment, verify this structure exists on the server:

```
/config/
  custom_components/
    net4home/
      __init__.py
      api.py
      binary_sensor.py
      climate.py
      config_flow.py
      const.py
      cover.py
      helpers.py
      light.py
      manifest.json
      models.py
      n4htools.py
      sensor.py
      services.yaml
      switch.py
      translations/
        de.json
        en.json
        es.json
      icons/
        icon.png
        icon.svg
        ...
```

## Next Steps

After successful deployment:
1. Restart Home Assistant
2. Go to **Settings → Devices & Services → Add Integration**
3. Search for "net4home" and configure it
4. Verify devices appear and work correctly
5. Check logs for any errors

## Support

If you encounter issues:
1. Check Home Assistant logs
2. Verify file permissions
3. Ensure all files were transferred
4. Check Python syntax (no syntax errors)
5. Verify `manifest.json` is valid JSON

