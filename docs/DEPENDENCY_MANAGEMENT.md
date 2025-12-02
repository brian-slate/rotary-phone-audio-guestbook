# Dependency Management

## Architecture

Both services now use a **single shared virtual environment** for consistency and isolation.

### Services

**audioGuestBook.service** (Main hardware controller)
- Runs as: `admin` user
- Python: `.venv/bin/python3`
- Needs: GPIO access (via `gpio` group membership)
- Dependencies: gpiozero, openai, requests, ruamel-yaml

**audioGuestBookWebServer.service** (Web interface)
- Runs as: `admin` user  
- Python: `.venv/bin/python3`
- Needs: Network access only
- Dependencies: flask, gunicorn, gevent, openai, requests, psutil

## Why Virtual Environment?

**Benefits:**
- **Isolation**: Dependencies don't pollute system Python
- **Consistency**: Both services use identical package versions
- **Portability**: Easy to replicate on new Pi
- **Safety**: No `sudo pip` required for updates
- **Version control**: Pin exact versions in requirements.txt

**Alternative (not used):**
- System-wide packages (`sudo pip3 install`)
- Requires root privileges
- Can conflict with OS packages
- Harder to track versions

## GPIO Access

Since services run as `admin` (not root), GPIO access is granted via group membership:

```bash
sudo usermod -a -G gpio admin
```

This allows non-root processes to access `/dev/gpiomem`.

## Dependency Installation

### During Deployment

The `deploy.sh` script:

1. **Creates venv if missing**:
   ```bash
   python3 -m venv /home/admin/rotary-phone-audio-guestbook/.venv
   ```

2. **Adds admin to gpio group** (one-time setup)

3. **Installs from requirements.txt**:
   ```bash
   .venv/bin/pip install -r requirements.txt
   ```

4. **Tracks changes via MD5**:
   - Only reinstalls if requirements.txt changed
   - Saves time on repeated deploys

### Manual Installation

If you need to add a package:

```bash
# SSH into Pi
ssh admin@camphone

# Activate venv
cd ~/rotary-phone-audio-guestbook
source .venv/bin/activate

# Install package
pip install <package-name>

# Update requirements.txt
pip freeze > requirements.txt

# Exit venv
deactivate
```

Then commit the updated requirements.txt to git.

## Requirements.txt

Managed via pip freeze for exact reproducibility:

```txt
openai==1.55.3
requests==2.32.3
flask==3.0.0
gunicorn==23.0.0
gevent==24.10.1
gpiozero==2.0.1
ruamel.yaml==0.18.6
psutil==6.0.0
```

All dependencies are pinned to specific versions.

## Troubleshooting

### "Module not found" errors

Check which Python is running:
```bash
ssh admin@camphone
sudo systemctl status audioGuestBook.service
# Look for: ExecStart=/home/admin/.../.venv/bin/python3
```

Verify venv has packages:
```bash
ssh admin@camphone
/home/admin/rotary-phone-audio-guestbook/.venv/bin/pip list
```

### GPIO permission denied

Check group membership:
```bash
ssh admin@camphone
groups
# Should include: admin gpio
```

If gpio is missing:
```bash
sudo usermod -a -G gpio admin
# Then logout/login or reboot
```

### Different package versions between services

This shouldn't happen since they share a venv, but if it does:
```bash
ssh admin@camphone
cd ~/rotary-phone-audio-guestbook
source .venv/bin/activate
pip install --force-reinstall -r requirements.txt
```

## Best Practices

1. **Always use venv pip**: Never `sudo pip3 install` 
2. **Pin versions**: Use `pip freeze > requirements.txt`
3. **Test after deploy**: Check both services start cleanly
4. **Update together**: Keep requirements.txt in sync with code changes
5. **Document new deps**: Note why each package is needed

## Migration Notes

**Previous setup (v1.0.4 and earlier):**
- audioGuestBook: Ran as root, system Python
- audioGuestBookWebServer: Ran as admin, venv Python
- Inconsistent dependency locations

**Current setup (v2.1+):**
- Both services: Run as admin, shared venv
- Unified dependency management
- GPIO via group membership

If upgrading from old setup:
```bash
# Remove old system packages (optional cleanup)
ssh admin@camphone
sudo pip3 uninstall openai requests

# Deploy new version
./deploy.sh camphone
```
