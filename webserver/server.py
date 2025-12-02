import io
import logging
import os
import re
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path

from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from ruamel.yaml import YAML

# Set up logging and app configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get absolute paths for reliable file locations regardless of where the app is started
WEBSERVER_DIR = Path(__file__).parent.absolute()
BASE_DIR = WEBSERVER_DIR.parent
STATIC_DIR = WEBSERVER_DIR / "static"

# Log critical paths for debugging
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Webserver directory: {WEBSERVER_DIR}")
logger.info(f"Base directory: {BASE_DIR}")
logger.info(f"Static directory: {STATIC_DIR}")

# Create Flask app with absolute path to static folder
app = Flask(__name__,
           static_url_path="/static",
           static_folder=str(STATIC_DIR))
app.secret_key = "supersecretkey"  # Needed for flashing messages

# Shared path for persisting last OpenAI error
ERROR_FILE = WEBSERVER_DIR / "last_openai_error.json"

def _read_last_openai_error():
    """Return dict with last error if OpenAI is enabled and error file exists."""
    try:
        if not config.get('openai_enabled', False):
            return None
        if ERROR_FILE.exists():
            import json
            return json.loads(ERROR_FILE.read_text())
    except Exception as e:
        logger.warning(f"Failed to read last OpenAI error: {e}")
    return None


def _clear_last_openai_error():
    try:
        if ERROR_FILE.exists():
            ERROR_FILE.unlink()
    except Exception as e:
        logger.warning(f"Failed to clear last OpenAI error: {e}")


@app.context_processor
def inject_template_variables():
    # Makes variables available to all templates
    return {
        "ai_processing_error": _read_last_openai_error(),
        "version": "3.0.0"  # Major release: AI transcription & metadata extraction, LED indicators, modern UI
    }

# Define other important paths
config_path = BASE_DIR / "config.yaml"
upload_folder = BASE_DIR / "uploads"
upload_folder.mkdir(parents=True, exist_ok=True)

logger.info(f"Config path: {config_path}")
logger.info(f"Upload folder: {upload_folder}")

# Initialize ruamel.yaml
yaml = YAML()

# Attempt to grab recording path from the configuration file
try:
    with config_path.open("r") as f:
        config = yaml.load(f)
        logger.info(f"Config loaded successfully from {config_path}")
except FileNotFoundError as e:
    logger.error(f"Configuration file not found: {e}")
    sys.exit(1)
except Exception as e:
    logger.error(f"Error loading configuration: {e}")
    sys.exit(1)

# Ensure recordings_path is an absolute path
recordings_path_str = config.get("recordings_path", "recordings")
recordings_path = Path(recordings_path_str)
if not recordings_path.is_absolute():
    recordings_path = BASE_DIR / recordings_path_str
    logger.info(f"Converted relative recordings path to absolute: {recordings_path}")

# Verify recordings directory exists and is accessible
if not recordings_path.exists():
    logger.warning(f"Recordings directory does not exist: {recordings_path}")
    try:
        recordings_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created recordings directory: {recordings_path}")
    except Exception as e:
        logger.error(f"Failed to create recordings directory: {e}")
        sys.exit(1)
elif not recordings_path.is_dir():
    logger.error(f"Recordings path exists but is not a directory: {recordings_path}")
    sys.exit(1)
else:
    logger.info(f"Recordings directory verified: {recordings_path}")

def normalize_path(path):
    """Normalize and convert paths to Unix format."""
    return str(path.as_posix())


def get_audio_files(audio_type):
    """Get list of available audio files for a specific type."""
    sounds_dir = BASE_DIR / "sounds" / audio_type
    if not sounds_dir.exists():
        sounds_dir.mkdir(parents=True, exist_ok=True)
    
    files = [f.name for f in sounds_dir.iterdir() if f.is_file() and f.suffix.lower() == '.wav']
    return sorted(files)


def convert_audio_to_wav(input_path, output_path, sample_rate=44100, channels=2):
    """Convert audio file to WAV format using ffmpeg."""
    try:
        subprocess.run([
            "ffmpeg", "-i", str(input_path),
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-f", "wav",
            "-y",  # Overwrite output file if exists
            str(output_path)
        ], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg conversion failed: {e.stderr.decode()}")
        return False
    except FileNotFoundError:
        logger.error("FFmpeg not found. Please install ffmpeg.")
        return False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/<filename>", methods=["GET"])
def download_file(filename):
    """Download a file dynamically from the recordings folder."""
    return send_from_directory(recordings_path, filename, as_attachment=True)


@app.route("/delete/<filename>", methods=["POST"])
def delete_file(filename):
    """Delete a specific recording."""
    file_path = recordings_path / filename
    try:
        file_path.unlink()
        # Clean up metadata
        try:
            from metadata_manager import MetadataManager
            metadata_mgr = MetadataManager(recordings_path)
            metadata_mgr.remove_recording(filename)
        except Exception as meta_error:
            logger.warning(f"Failed to clean up metadata for {filename}: {meta_error}")
        return jsonify({"success": True, "message": f"{filename} has been deleted."})
    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Error deleting file: {str(e)}"}
        ), 500


@app.route("/api/recordings")
def get_recordings():
    """API route to get a list of all recordings with AI metadata."""
    try:
        # Try to use metadata manager if available
        try:
            from metadata_manager import MetadataManager
            metadata_mgr = MetadataManager(recordings_path)
            recordings = metadata_mgr.get_all_recordings()
            
            # Return with metadata
            return jsonify([
                {
                    'filename': rec['filename'],
                    'title': rec.get('ai_metadata', {}).get('summary') if rec.get('ai_metadata') else rec['filename'],
                    'speaker_names': rec.get('ai_metadata', {}).get('speaker_names', []) if rec.get('ai_metadata') else [],
                    'category': rec.get('ai_metadata', {}).get('category') if rec.get('ai_metadata') else None,
                    'transcription': rec.get('ai_metadata', {}).get('transcription') if rec.get('ai_metadata') else None,
                    'processing_status': rec.get('ai_metadata', {}).get('processing_status') if rec.get('ai_metadata') else None,
                    'confidence': rec.get('ai_metadata', {}).get('confidence') if rec.get('ai_metadata') else None,
                    'created_at': rec.get('created_at'),
                    'file_size': rec.get('file_size_bytes')
                }
                for rec in recordings
            ])
        except ImportError:
            # Fallback to simple file list if AI components not available
            logger.warning("Metadata manager not available, returning simple file list")
            if recordings_path.exists() and recordings_path.is_dir():
                all_items = list(sorted(recordings_path.iterdir(), key=lambda f:f.stat().st_mtime, reverse=True))
                # Only include WAV files, exclude metadata JSON and other files
                files = [f.name for f in all_items if f.is_file() and f.suffix.lower() == '.wav']
                return jsonify(files)
            else:
                logger.error(f"Recordings path is not a valid directory: {recordings_path}")
                return jsonify({"error": "Recordings directory not found"}), 404

    except Exception as e:
        logger.error(f"Error accessing recordings directory: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/transcription/<filename>")
def get_transcription(filename):
    """Get full transcription for a recording."""
    try:
        from metadata_manager import MetadataManager
        metadata_mgr = MetadataManager(recordings_path)
        metadata = metadata_mgr.get_metadata(filename)
        
        if not metadata or 'ai_metadata' not in metadata:
            return jsonify({
                'transcription': None,
                'status': 'not_processed'
            })
        
        return jsonify({
            'transcription': metadata['ai_metadata'].get('transcription'),
            'status': metadata['ai_metadata'].get('processing_status'),
            'speaker_names': metadata['ai_metadata'].get('speaker_names', []),
            'category': metadata['ai_metadata'].get('category'),
            'confidence': metadata['ai_metadata'].get('confidence')
        })
    except Exception as e:
        logger.error(f"Error getting transcription: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/process-pending", methods=["POST"])
def process_pending_recordings():
    """Manually trigger processing of all unprocessed recordings."""
    try:
        from metadata_manager import MetadataManager
        
        metadata_mgr = MetadataManager(recordings_path)
        unprocessed = metadata_mgr.get_unprocessed_recordings()
        
        # Note: This assumes the processing queue is accessible
        # For now, just return success - actual processing will be handled by the queue
        count = len(unprocessed)
        
        return jsonify({
            'success': True,
            'message': f'Found {count} recording(s) pending processing. They will be processed when the phone is idle.',
            'count': count
        })
    except Exception as e:
        logger.error(f"Error processing pending recordings: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


def validate_openai_api_key(api_key):
    """Validate OpenAI API key by making a test request."""
    if not api_key or len(api_key) < 20:
        return False, "API key is too short or empty"
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # Test with a minimal API call to list models
        # This verifies the key works and has basic permissions
        models = client.models.list()
        return True, "API key verified successfully"
    except Exception as e:
        error_msg = str(e)
        if "invalid_api_key" in error_msg.lower() or "incorrect api key" in error_msg.lower():
            return False, "Invalid API key"
        elif "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
            return False, "API key lacks required permissions"
        elif "rate_limit" in error_msg.lower():
            return False, "Rate limit exceeded - try again in a moment"
        else:
            return False, f"Verification failed: {error_msg[:100]}"

@app.route("/config", methods=["GET", "POST"])
def edit_config():
    """Handle GET and POST requests to edit the configuration."""
    if request.method == "POST":
        logger.info("Form data received:")
        for key, value in request.form.items():
            logger.info(f"  {key}: {value}")
        try:
            # Validate OpenAI API key if it was changed
            if 'openai_api_key' in request.form:
                new_api_key = request.form['openai_api_key'].strip()
                old_api_key = config.get('openai_api_key', '')
                
                # Only validate if the key actually changed and is not empty
                if new_api_key and new_api_key != old_api_key:
                    logger.info("Validating new OpenAI API key...")
                    is_valid, message = validate_openai_api_key(new_api_key)
                    
                    if not is_valid:
                        logger.error(f"API key validation failed: {message}")
                        flash(f"OpenAI API Key Error: {message}", "error")
                        return redirect(url_for("edit_config"))
                    else:
                        logger.info("API key validated successfully")
                        config['openai_key_verified'] = True
                        flash("OpenAI API key verified successfully!", "success")
                        # Clear any prior AI error now that key is valid
                        _clear_last_openai_error()
                elif not new_api_key and old_api_key:
                    # Key was cleared - this is intentional removal
                    config['openai_key_verified'] = False
                elif not new_api_key and not old_api_key:
                    # Both empty - user is trying to enable AI without a key
                    if request.form.get('openai_enabled') == 'true':
                        logger.error("Attempted to enable AI without API key")
                        flash("OpenAI API Key Error: Please provide an API key before enabling AI processing", "error")
                        return redirect(url_for("edit_config"))
                # else: new_api_key is empty but old_api_key exists - user is just saving other settings, keep existing key
            
            # Track which fields had file uploads
            uploaded_fields = []
            
            # Handle file uploads
            for field in ["greeting", "beep", "time_exceeded"]:
                if f"{field}_file" in request.files:
                    file = request.files[f"{field}_file"]
                    if file.filename:
                        # Get custom name or use original filename
                        custom_name = request.form.get(f"{field}_name", "").strip()
                        if custom_name:
                            # Sanitize filename
                            custom_name = custom_name.replace(" ", "-").replace("/", "-")
                            base_name = custom_name if custom_name.endswith(".wav") else f"{custom_name}.wav"
                        else:
                            # Use original filename without extension, add .wav
                            base_name = Path(file.filename).stem + ".wav"
                        
                        # Determine subdirectory based on field type
                        subdir_map = {
                            "greeting": "greetings",
                            "beep": "beeps",
                            "time_exceeded": "time_exceeded"
                        }
                        subdir = subdir_map[field]
                        target_dir = BASE_DIR / "sounds" / subdir
                        target_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Handle duplicate filenames
                        final_path = target_dir / base_name
                        counter = 1
                        while final_path.exists():
                            stem = Path(base_name).stem
                            final_path = target_dir / f"{stem}-{counter}.wav"
                            counter += 1
                        
                        # Check if file is already WAV
                        file_ext = Path(file.filename).suffix.lower()
                        if file_ext == ".wav":
                            # Save directly
                            file.save(str(final_path))
                            logger.info(f"Saved WAV file directly: {final_path}")
                        else:
                            # Save to temp location and convert
                            temp_path = upload_folder / file.filename
                            file.save(str(temp_path))
                            logger.info(f"Converting {file_ext} to WAV: {temp_path} -> {final_path}")
                            
                            if convert_audio_to_wav(temp_path, final_path):
                                logger.info(f"Successfully converted to WAV: {final_path}")
                                temp_path.unlink()  # Delete temp file
                            else:
                                flash(f"Failed to convert {file.filename} to WAV. Please try a different file.", "error")
                                if temp_path.exists():
                                    temp_path.unlink()
                                continue
                        
                        # Update config to point to new file
                        config[field] = normalize_path(final_path.relative_to(BASE_DIR))
                        logger.info(f"Updated config[{field}] to: {config[field]}")
                        uploaded_fields.append(field)

            update_config(request.form, skip_fields=uploaded_fields)

            with config_path.open("w") as f:
                yaml.dump(config, f)

            # If AI was disabled via this save, clear any previous error
            if not config.get('openai_enabled', False):
                _clear_last_openai_error()

            # Restart the audioGuestBook service to apply changes
            try:
                subprocess.run(["sudo", "systemctl", "restart", "audioGuestBook.service"], check=True)
                logger.info("Successfully restarted audioGuestBook service")
                flash("Configuration updated and service restarted successfully!", "success")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to restart audioGuestBook service: {e}")
                flash("Configuration updated but failed to restart service. Please restart manually.", "warning")

            return redirect(url_for("edit_config"))
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            flash(f"Error updating configuration: {str(e)}", "error")
            # Continue with current configuration but show error

    # Load the current configuration
    try:
        with config_path.open("r") as f:
            current_config = yaml.load(f)
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        current_config = {}

    # Get available audio files for each type
    available_greetings = get_audio_files("greetings")
    available_beeps = get_audio_files("beeps")
    available_time_exceeded = get_audio_files("time_exceeded")

    return render_template(
        "config.html",
        config=current_config,
        available_greetings=available_greetings,
        available_beeps=available_beeps,
        available_time_exceeded=available_time_exceeded
    )


@app.route("/delete-audio/<audio_type>/<filename>", methods=["POST"])
def delete_audio(audio_type, filename):
    """Delete a specific audio file from sounds directory."""
    # Validate audio type
    valid_types = ["greetings", "beeps", "time_exceeded"]
    if audio_type not in valid_types:
        return jsonify({"success": False, "message": "Invalid audio type"}), 400
    
    audio_dir = BASE_DIR / "sounds" / audio_type
    file_path = audio_dir / filename
    
    # Check if more than one file exists
    available_files = get_audio_files(audio_type)
    if len(available_files) <= 1:
        return jsonify({
            "success": False,
            "message": "Cannot delete the last audio file. At least one must remain."
        }), 400
    
    try:
        # Check if this is the currently active file in config
        with config_path.open("r") as f:
            current_config = yaml.load(f)
        
        # Map audio_type to config field
        type_to_field = {
            "greetings": "greeting",
            "beeps": "beep",
            "time_exceeded": "time_exceeded"
        }
        field = type_to_field[audio_type]
        current_file = Path(current_config.get(field, "")).name
        
        # Delete the file
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted audio file: {file_path}")
            
            # If we deleted the active file, switch to the first remaining one
            if current_file == filename:
                remaining_files = get_audio_files(audio_type)
                if remaining_files:
                    new_path = audio_dir / remaining_files[0]
                    current_config[field] = normalize_path(new_path.relative_to(BASE_DIR))
                    with config_path.open("w") as f:
                        yaml.dump(current_config, f)
                    logger.info(f"Switched active {field} to: {remaining_files[0]}")
                    
                    # Restart service
                    try:
                        subprocess.run(["sudo", "systemctl", "restart", "audioGuestBook.service"], check=True)
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Failed to restart service: {e}")
            
            return jsonify({
                "success": True,
                "message": f"{filename} has been deleted."
            })
        else:
            return jsonify({
                "success": False,
                "message": "File not found."
            }), 404
    except Exception as e:
        logger.error(f"Error deleting audio file: {e}")
        return jsonify({
            "success": False,
            "message": f"Error deleting file: {str(e)}"
        }), 500


@app.route("/sounds/<audio_type>/<filename>")
def serve_sound(audio_type, filename):
    """Serve a sound file for preview with streaming support."""
    valid_types = ["greetings", "beeps", "time_exceeded"]
    if audio_type not in valid_types:
        return jsonify({"error": "Invalid audio type"}), 400
    
    audio_dir = BASE_DIR / "sounds" / audio_type
    file_path = audio_dir / filename
    
    if not file_path.exists():
        logger.error(f"Sound file not found: {file_path}")
        return jsonify({"error": "File not found"}), 404
    
    # Get file size for range requests
    file_size = file_path.stat().st_size
    
    # Parse Range header
    range_header = request.headers.get('Range', None)
    
    if range_header:
        # Parse the range header
        byte1, byte2 = 0, None
        match = re.search(r'(\d+)-(\d*)', range_header)
        groups = match.groups()
        
        if groups[0]:
            byte1 = int(groups[0])
        if groups[1]:
            byte2 = int(groups[1])
        
        if byte2 is None:
            byte2 = file_size - 1
        
        length = byte2 - byte1 + 1
        
        # Create the response with the proper headers for range request
        resp = Response(
            generate_file_chunks(str(file_path), byte1, byte2),
            status=206,
            mimetype='audio/wav',
            direct_passthrough=True
        )
        
        resp.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
        resp.headers.add('Accept-Ranges', 'bytes')
        resp.headers.add('Content-Length', str(length))
        return resp
    
    # If no range header, serve the whole file
    resp = Response(
        generate_file_chunks(str(file_path), 0, file_size - 1),
        mimetype='audio/wav'
    )
    resp.headers.add('Accept-Ranges', 'bytes')
    resp.headers.add('Content-Length', str(file_size))
    return resp


@app.route("/recordings/<filename>")
def serve_recording(filename):
    """Serve a specific recording with proper streaming and range support."""
    file_path = recordings_path / filename

    # Verify file exists
    if not file_path.exists():
        logger.error(f"Recording file not found: {file_path}")
        return jsonify({"error": "File not found"}), 404

    # Get file size for range requests
    file_size = file_path.stat().st_size

    # Parse Range header
    range_header = request.headers.get('Range', None)

    if range_header:
        # Parse the range header
        byte1, byte2 = 0, None
        match = re.search(r'(\d+)-(\d*)', range_header)
        groups = match.groups()

        if groups[0]:
            byte1 = int(groups[0])
        if groups[1]:
            byte2 = int(groups[1])

        if byte2 is None:
            byte2 = file_size - 1

        length = byte2 - byte1 + 1

        # Create the response with the proper headers for range request
        resp = Response(
            generate_file_chunks(str(file_path), byte1, byte2),
            status=206,
            mimetype='audio/wav',
            direct_passthrough=True
        )

        resp.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
        resp.headers.add('Accept-Ranges', 'bytes')
        resp.headers.add('Content-Length', str(length))
        return resp

    # If no range header, serve the whole file
    resp = Response(
        generate_file_chunks(str(file_path), 0, file_size - 1),
        mimetype='audio/wav'
    )
    resp.headers.add('Accept-Ranges', 'bytes')
    resp.headers.add('Content-Length', str(file_size))
    return resp


def generate_file_chunks(file_path, byte1=0, byte2=None):
    """Generator to stream file in chunks with range support."""
    with open(file_path, 'rb') as f:
        f.seek(byte1)
        while True:
            buffer_size = 8192
            if byte2:
                buffer_size = min(buffer_size, byte2 - f.tell() + 1)
                if buffer_size <= 0:
                    break
            chunk = f.read(buffer_size)
            if not chunk:
                break
            yield chunk


@app.route("/download-all")
def download_all():
    """Download all recordings as a zip file."""
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w") as zf:
        wav_files = [f for f in recordings_path.iterdir() if f.is_file() and f.suffix.lower() == ".wav"]

        # Log the files being added to the zip
        logger.info(f"Adding {len(wav_files)} files to zip")

        for file_path in wav_files:
            # Use absolute path for reading
            abs_path = str(file_path.absolute())
            logger.info(f"Adding file: {abs_path}")

            # Verify file exists and is readable
            if os.path.exists(abs_path) and os.access(abs_path, os.R_OK):
                # Add to zip with just the filename as the internal path
                zf.write(abs_path, arcname=file_path.name)
            else:
                logger.error(f"Cannot access file: {abs_path}")

    memory_file.seek(0)

    logger.info(f"Zip file size: {memory_file.getbuffer().nbytes} bytes")

    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name="recordings.zip",
    )


@app.route("/download-selected", methods=["POST"])
def download_selected():
    """Download selected recordings as a zip file."""
    selected_files = request.form.getlist("files[]")
    logger.info(f"Selected files for download: {selected_files}")

    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, "w") as zf:
        for filename in selected_files:
            file_path = recordings_path / filename
            if file_path.exists() and os.access(str(file_path), os.R_OK):
                logger.info(f"Adding to zip: {file_path}")
                zf.write(str(file_path), filename)
            else:
                logger.error(f"Cannot access file: {file_path}")

    memory_file.seek(0)
    logger.info(f"Zip file size: {memory_file.getbuffer().nbytes} bytes")

    return send_file(
        memory_file,
        mimetype="application/zip",
        download_name="selected_recordings.zip",
        as_attachment=True,
    )


@app.route("/rename/<old_filename>", methods=["POST"])
def rename_recording(old_filename):
    """Rename a recording."""
    new_filename = request.json["newFilename"]
    old_path = recordings_path / old_filename
    new_path = recordings_path / new_filename

    if old_path.exists():
        os.rename(str(old_path), str(new_path))
        return jsonify(success=True)
    else:
        return jsonify(success=False), 404


@app.route("/reboot", methods=["POST"])
def reboot():
    """Reboot the system."""
    try:
        os.system("sudo reboot now")
        return jsonify({"success": True, "message": "System is rebooting..."})
    except Exception as e:
        logger.error(f"Failed to reboot: {e}")
        return jsonify(
            {"success": False, "message": "Failed to reboot the system!"}
        ), 500


@app.route("/shutdown", methods=["POST"])
def shutdown():
    """Shut down the system."""
    try:
        os.system("sudo shutdown now")
        return jsonify({"success": True, "message": "System is shutting down..."})
    except Exception as e:
        logger.error(f"Failed to shut down: {e}")
        return jsonify(
            {"success": False, "message": "Failed to shut down the system!"}
        ), 500


def update_config(form_data, skip_fields=None):
    """Update the YAML configuration with form data."""
    if skip_fields is None:
        skip_fields = []
    
    for key, value in form_data.items():
        # Skip CSRF token if it exists
        if key == 'csrf_token':
            continue
        
        # Skip fields that had file uploads (already updated)
        if key in skip_fields:
            logger.info(f"Skipping '{key}' - file was uploaded")
            continue

        # Check if key exists in config
        if key not in config and key != 'invert_hook':
            logger.warning(f"Form field '{key}' not found in config, skipping")
            continue

        # Log the conversion attempt
        logger.info(f"Updating '{key}': {config.get(key, 'Not set')} (type: {type(config.get(key, '')).__name__}) → '{value}'")

        try:
            # Convert value based on the type in config or for new boolean fields
            if key == 'invert_hook' or isinstance(config.get(key), bool):
                # Convert string to boolean
                new_value = (value.lower() == "true")
                logger.info(f"Converting to boolean: {value} → {new_value}")
                config[key] = new_value
            elif isinstance(config.get(key), int):
                config[key] = int(value)
            elif isinstance(config.get(key), float):
                config[key] = float(value)
            elif isinstance(config.get(key), list):
                # Handle list fields (comma-separated strings)
                if value and value.strip():
                    # Split by comma, strip whitespace, filter empty strings
                    config[key] = [item.strip() for item in value.split(',') if item.strip()]
                    logger.info(f"Converting to list: {value} → {config[key]}")
                else:
                    config[key] = []
            else:
                config[key] = value

            # Verify the conversion worked
            logger.info(f"Updated '{key}' to: {config[key]} (type: {type(config[key]).__name__})")

        except (ValueError, TypeError) as e:
            logger.error(f"Failed to update '{key}': {e}")

@app.route("/api/system-status")
def system_status():
    """Return basic system information for the dashboard."""
    try:
        import psutil

        cpu_usage = psutil.cpu_percent()
        memory_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage("/").percent
        recording_count = len([f for f in recordings_path.iterdir() if f.is_file()])

        return jsonify(
            {
                "success": True,
                "cpu": cpu_usage,
                "memory": memory_usage,
                "disk": disk_usage,
                "recordings": recording_count,
            }
        )
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/delete-recordings", methods=["POST"])
def delete_recordings():
    """Delete multiple recordings in bulk."""
    try:
        data = request.get_json()
        if not data or 'ids' not in data:
            return jsonify({"success": False, "message": "No recordings specified for deletion"}), 400

        deleted_files = []
        failed_files = []

        # Initialize metadata manager for cleanup
        try:
            from metadata_manager import MetadataManager
            metadata_mgr = MetadataManager(recordings_path)
        except Exception as e:
            logger.warning(f"Metadata manager not available: {e}")
            metadata_mgr = None
        
        for filename in data['ids']:
            file_path = recordings_path / filename
            try:
                if file_path.exists():
                    file_path.unlink()
                    deleted_files.append(filename)
                    logger.info(f"Successfully deleted: {filename}")
                    # Clean up metadata
                    if metadata_mgr:
                        try:
                            metadata_mgr.remove_recording(filename)
                        except Exception as meta_error:
                            logger.warning(f"Failed to clean up metadata for {filename}: {meta_error}")
                else:
                    failed_files.append(filename)
                    logger.warning(f"File not found: {filename}")
            except Exception as e:
                failed_files.append(filename)
                logger.error(f"Error deleting {filename}: {str(e)}")

        if failed_files:
            message = f"Deleted {len(deleted_files)} files, failed to delete {len(failed_files)}"
            return jsonify({
                "success": False,
                "message": message,
                "deleted": deleted_files,
                "failed": failed_files
            }), 207  # Multi-status response

        return jsonify({
            "success": True,
            "message": f"Successfully deleted {len(deleted_files)} recordings",
            "deleted": deleted_files
        })

    except Exception as e:
        logger.error(f"Error in bulk deletion: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Server error during bulk deletion: {str(e)}"
        }), 500

if __name__ == "__main__":
    # Print summary of configuration for debugging
    logger.info("=== Starting Audio Guestbook Server ===")
    logger.info(f"Static files location: {STATIC_DIR}")
    logger.info(f"Recordings location: {recordings_path}")
    logger.info("=====================================")
