#!/bin/bash

# Set up variables

# Raspberry Pi (target device)
RPI_USER="admin"
RPI_HOST="blackbox"  # Default hostname
RPI_PROJECT_DIR="/home/${RPI_USER}/rotary-phone-audio-guestbook"
RPI_SYSTEMD_DIR="/etc/systemd/system"

# Parse command-line arguments
SKIP_BACKUP=true
QUICK_MODE=false

for arg in "$@"; do
    case $arg in
        --backup)
            SKIP_BACKUP=false
            ;;
        --quick|--sync)
            QUICK_MODE=true
            ;;
        *)
            # Assume it's the hostname/IP
            RPI_HOST="$arg"
            ;;
    esac
done

# Image backup settings
IMG_VERSION="v1.0.4"
IMG_BACKUP_NAME="rpizero_rotary_phone_audio_guestbook_${IMG_VERSION}_imagebackup.img"
IMG_PATH="/mnt/${IMG_BACKUP_NAME}"

# Local backup directory
BACKUP_DIR="./backup"

if [ "$QUICK_MODE" = true ]; then
    echo "=== Quick Sync Mode (--quick) ==="
    echo "Syncing files only - skipping dependency installation"
else
    echo "=== Full Deploy Mode ==="
    echo "Installing dependencies and restarting services"
fi
echo "Target: ${RPI_HOST}"

# Step 0: Build frontend assets locally (CSS/JS)
echo "Building frontend assets (Tailwind/PostCSS)..."
if command -v npm >/dev/null 2>&1; then
    (cd webserver && npm ci --no-audit --no-fund && npm run build) || { echo "Frontend build failed"; exit 1; }
else
    echo "npm not found - skipping frontend build"
fi

# Step 1: Sync files from local machine to Raspberry Pi
echo "Syncing files from local machine to Raspberry Pi..."
RSYNC_OUTPUT=$(rsync -avz --itemize-changes --exclude-from='./rsync-exclude.txt' ./ ${RPI_USER}@${RPI_HOST}:${RPI_PROJECT_DIR}/ 2>&1)
RSYNC_EXIT=$?
echo "$RSYNC_OUTPUT"

# Step 2: SSH into the Raspberry Pi to execute commands there
if [ "$QUICK_MODE" = true ]; then
    echo "Quick mode: Skipping dependency installation"
    # Just merge config in quick mode
    ssh ${RPI_USER}@${RPI_HOST} "bash ${RPI_PROJECT_DIR}/scripts/merge_config_remote.sh ${RPI_PROJECT_DIR}"
else
    echo "Connecting to Raspberry Pi to complete deployment..."
    ssh ${RPI_USER}@${RPI_HOST} <<ENDSSH
        # Install system dependencies
        echo "Installing system dependencies..."
        sudo apt-get update
        sudo apt-get install -y ffmpeg python3-venv
    
    # Ensure user is in gpio group for hardware access
    if ! groups | grep -q gpio; then
        echo "Adding ${RPI_USER} to gpio group..."
        sudo usermod -a -G gpio ${RPI_USER}
        echo "Note: GPIO group added. You may need to log out/in for changes to take effect."
    fi
    
    # Ensure venv exists and has pip
    cd ${RPI_PROJECT_DIR}
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv .venv
        echo "Installing pip setuptools wheel..."
        .venv/bin/pip install --upgrade pip setuptools wheel
        # Force install on new venv
        FORCE_INSTALL=true
    else
        FORCE_INSTALL=false
    fi
    
    # Check if requirements.txt changed
    REQUIREMENTS_CHANGED=false
    if [ -f "requirements.txt" ]; then
        if [ -f ".requirements.txt.md5" ]; then
            OLD_MD5=\$(cat .requirements.txt.md5)
            NEW_MD5=\$(md5sum requirements.txt | cut -d' ' -f1)
            if [ "\$OLD_MD5" != "\$NEW_MD5" ]; then
                REQUIREMENTS_CHANGED=true
                echo "Detected requirements change (old: \$OLD_MD5, new: \$NEW_MD5)"
            fi
        else
            REQUIREMENTS_CHANGED=true
            echo "No previous requirements hash found, will install packages"
        fi
    fi
    
    # Install packages if requirements changed OR venv was just created
    if [ "\$REQUIREMENTS_CHANGED" = "true" ] || [ "\$FORCE_INSTALL" = "true" ]; then
        echo "Installing Python packages..."
        echo "Stopping services to free up resources..."
        sudo systemctl stop audioGuestBook.service audioGuestBookWebServer.service 2>/dev/null || true
        
        if [ -f "requirements.txt" ]; then
            # Install into venv using pip
            echo "Installing from requirements.txt..."
            .venv/bin/pip install -r requirements.txt
            md5sum requirements.txt | cut -d' ' -f1 > .requirements.txt.md5
            echo "Packages installed successfully"
        else
            echo "Warning: requirements.txt not found, installing base packages..."
            .venv/bin/pip install openai requests flask gunicorn gevent gpiozero ruamel-yaml psutil
        fi
    else
        echo "Requirements unchanged (MD5: \$(cat .requirements.txt.md5 2>/dev/null || echo 'unknown')), skipping package installation"
    fi
    
    # Merge config.yaml to preserve user settings while adding new defaults
    bash ${RPI_PROJECT_DIR}/scripts/merge_config_remote.sh ${RPI_PROJECT_DIR}
    
    # Configure passwordless sudo for WiFi management
    echo "Configuring WiFi management permissions..."
    bash ${RPI_PROJECT_DIR}/scripts/configure-wifi-sudo.sh
    
    # Copy service files to systemd directory
    echo "Copying service files to systemd directory..."
    sudo cp ${RPI_PROJECT_DIR}/*.service ${RPI_SYSTEMD_DIR}/

    # Enable and restart services
    echo "Enabling and restarting services..."
    sudo systemctl daemon-reload
    sudo systemctl enable audioGuestBook.service
    sudo systemctl restart audioGuestBook.service
    sudo systemctl enable audioGuestBookWebServer.service
    sudo systemctl restart audioGuestBookWebServer.service

        # Wait for services to settle
        sleep 5
ENDSSH

    # Check if SSH command was successful
    if [ $? -ne 0 ]; then
        echo "Error: SSH connection or remote commands failed."
        exit 1
    fi

    echo "=== Services restarted successfully ==="
fi

# Smart restart logic for quick mode
if [ "$QUICK_MODE" = true ]; then
    # Check if templates or static files changed - if so, restart web server
    if echo "$RSYNC_OUTPUT" | grep -qE "(webserver/templates/|webserver/static/)"; then
        echo ""
        echo "📝 Detected changes to templates or static files"
        echo "🔄 Auto-restarting web server..."
        ssh ${RPI_USER}@${RPI_HOST} "sudo systemctl restart audioGuestBookWebServer.service"
        if [ $? -eq 0 ]; then
            echo "✅ Web server restarted successfully"
        else
            echo "❌ Failed to restart web server"
        fi
    fi
    
    # Check if Python source files changed - if so, suggest restart
    if echo "$RSYNC_OUTPUT" | grep -qE "\.(py)$"; then
        echo ""
        echo "📝 Python source files changed"
        echo "💡 You may want to restart services:"
        echo "   ssh ${RPI_USER}@${RPI_HOST} 'sudo systemctl restart audioGuestBook.service audioGuestBookWebServer.service'"
    fi
    
    echo ""
    echo "✅ Quick sync completed"
    echo "Test at: http://${RPI_HOST}:8080"
    exit 0
fi

# Optional: Create backup if requested
if [ "$SKIP_BACKUP" = false ]; then
    echo "Creating image backup..."
    ssh ${RPI_USER}@${RPI_HOST} <<BACKUPSSH

        # Check if current version backup exists
        if [ -f "${IMG_PATH}" ]; then
            echo "Current version backup found. Performing incremental backup..."
            sudo image-backup "${IMG_PATH}"
        else
            # Try to find previous versions (v1.0.3, v1.0.2, etc.)
            PREV_FOUND=false

            # Try v1.0.3
            PREV_PATH="/mnt/rpizero_rotary_phone_audio_guestbook_v1.0.3_imagebackup.img"
            if [ -f "\${PREV_PATH}" ]; then
                echo "Found previous version v1.0.3. Using for incremental backup..."
                sudo image-backup "\${PREV_PATH}" "${IMG_PATH}"
                PREV_FOUND=true
            fi

            # If previous not found, check v1.0.2
            if [ "\${PREV_FOUND}" = "false" ]; then
                PREV_PATH="/mnt/rpizero_rotary_phone_audio_guestbook_v1.0.2_imagebackup.img"
                if [ -f "\${PREV_PATH}" ]; then
                    echo "Found previous version v1.0.2. Using for incremental backup..."
                    sudo image-backup "\${PREV_PATH}" "${IMG_PATH}"
                    PREV_FOUND=true
                fi
            fi

            # If still no previous version, do full backup
            if [ "\${PREV_FOUND}" = "false" ]; then
                echo "No previous versions found. Performing full backup..."
                sudo image-backup -i "${IMG_PATH}"
            fi
        fi

        # Verify the backup was created
        if [ -f "${IMG_PATH}" ]; then
            echo "Backup image created successfully."
            echo "Calculating MD5 checksum..."
            md5sum "${IMG_PATH}"
        else
            echo "Error: Backup image not created!"
            exit 1
        fi
BACKUPSSH

    # Check if SSH command was successful
    if [ $? -ne 0 ]; then
        echo "Error: Backup creation failed."
        exit 1
    fi

    # Step 3: Copy the backup image from Raspberry Pi to development machine
    echo "Copying backup image from Raspberry Pi to local machine..."
    mkdir -p "${BACKUP_DIR}"
    rsync -avz ${RPI_USER}@${RPI_HOST}:${IMG_PATH} "${BACKUP_DIR}/"

    if [ $? -eq 0 ]; then
        echo "Backup image copied to local machine successfully."
    else
        echo "Error during backup image transfer. Please check the connection or destination."
        exit 1
    fi

    # Step 4: Ask if you want to delete the backup from the Raspberry Pi
    read -p "Do you want to delete the backup image from the Raspberry Pi? (y/n): " delete_choice

    if [[ "$delete_choice" == "y" || "$delete_choice" == "Y" ]]; then
        echo "Deleting backup image from Raspberry Pi..."
        ssh ${RPI_USER}@${RPI_HOST} "sudo rm -f ${IMG_PATH}"

        if [ $? -eq 0 ]; then
            echo "Backup image deleted from Raspberry Pi successfully."
        else
            echo "Error deleting the backup image from Raspberry Pi."
        fi
    else
        echo "Backup image retained on Raspberry Pi at ${IMG_PATH}."
    fi
else
    echo "Skipping backup (use --backup flag to enable)"
fi

echo "=== Deploy Script Completed Successfully ==="
