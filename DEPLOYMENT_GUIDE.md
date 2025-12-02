# Deployment Guide

## Quick Reference

| Task | Script | When to Use |
|------|--------|-------------|
| Full deployment with dependencies | `./deploy.sh camphone` | First deploy, dependency changes, significant updates |
| Quick code sync for iteration | `./sync-to-pi.sh camphone` | Rapid development, minor code changes |

## deploy.sh - Full Deployment

**What it does:**
1. Syncs all code files to Pi (excluding config.yaml)
2. Installs system dependencies (ffmpeg)
3. Installs Python packages from requirements.txt (if changed)
4. **Merges config.yaml** - Preserves your settings while adding new defaults
5. Copies systemd service files
6. Restarts both services

**Use when:**
- First deployment to new Pi
- requirements.txt changed (new Python packages)
- Config structure changed (new fields added to config.yaml.template)
- Service files changed
- Major feature additions

**Example:**
```bash
./deploy.sh camphone
./deploy.sh camphone --backup  # Also create system backup
```

**Key feature:** Uses `scripts/merge_config.py` to safely merge config changes without losing user settings like API keys, GPIO pins, etc.

## sync-to-pi.sh - Quick Code Sync

**What it does:**
1. Syncs all code files to Pi (excluding config.yaml)
2. That's it - no restart, no dependency install

**Use when:**
- Iterating on Python code changes
- Template/HTML changes
- JavaScript/CSS changes
- Minor bug fixes during development

**Example:**
```bash
./sync-to-pi.sh camphone
# Then manually restart if needed:
ssh admin@camphone "sudo systemctl restart audioGuestBook.service audioGuestBookWebServer.service"
```

**Key feature:** Fast - no waiting for apt-get or pip install

## Config Protection

Both scripts use `rsync-exclude.txt` which includes:
```
config.yaml
config.yaml.merged
```

This means **your Pi's config.yaml is NEVER overwritten** by either script. Your API keys, custom settings, and GPIO configurations are always safe.

## When Config Changes Are Needed

If you add new config fields:

1. Update `config.yaml.template` with new fields and defaults
2. Run `./deploy.sh camphone`
3. The merge script will:
   - Keep all your existing settings
   - Add only the new fields with their default values
   - Log how many values were preserved

## Best Practice Workflow

**During active development:**
```bash
# Make code changes locally
vim webserver/server.py

# Quick sync
./sync-to-pi.sh camphone

# Restart service to test
ssh admin@camphone "sudo systemctl restart audioGuestBookWebServer.service"

# Check logs
ssh admin@camphone "sudo journalctl -u audioGuestBookWebServer.service -f"
```

**For releases:**
```bash
# Full deploy with all checks
./deploy.sh camphone

# Optional: Create backup
./deploy.sh camphone --backup
```

## Troubleshooting

**If deploy.sh fails mid-way:**
- Services should still work with old code
- Re-run deploy.sh to complete
- Config is always preserved

**If you accidentally deleted config.yaml on Pi:**
```bash
# Copy template as starting point
ssh admin@camphone "cp config.yaml.template config.yaml"
# Edit to add your settings
ssh admin@camphone "nano config.yaml"
```

**To see what files would be synced:**
```bash
rsync -avzn --exclude-from='./rsync-exclude.txt' ./ admin@camphone:/home/admin/rotary-phone-audio-guestbook/
# The -n flag is dry-run mode
```
