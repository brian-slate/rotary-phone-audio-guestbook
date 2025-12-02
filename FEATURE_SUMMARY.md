# Multi-Greeting Management Feature - Implementation Summary

## Branch
`feature/multi-greeting-management`

## What Was Implemented

### Backend Changes (server.py)

1. **Helper Functions Added:**
   - `get_audio_files(audio_type)` - Lists available audio files for a specific type
   - `convert_audio_to_wav()` - Converts non-WAV files to WAV format using ffmpeg

2. **Modified `/config` GET Endpoint:**
   - Now scans `sounds/greetings/`, `sounds/beeps/`, and `sounds/time_exceeded/` directories
   - Passes lists of available files to the template

3. **Modified `/config` POST Endpoint:**
   - Accepts optional custom name for uploaded files
   - Detects file format and converts to WAV if needed (using ffmpeg)
   - Saves files to appropriate subdirectory
   - Handles duplicate filenames by appending numbers
   - Updates config to point to the new file

4. **New Endpoints:**
   - `/delete-audio/<audio_type>/<filename>` (POST) - Deletes audio files with validation
   - `/sounds/<audio_type>/<filename>` (GET) - Serves audio files for preview with streaming support

### Frontend Changes (config.html)

1. **New UI for Each Audio Type (greeting, beep, time_exceeded):**
   - Dropdown selector to choose active audio file
   - Preview button to play the selected audio
   - Delete button with protection against deleting the last file
   - Upload section with file input and optional name field
   - Accepts all audio formats: WAV, M4A, AAC, MP3

2. **JavaScript Functions:**
   - `previewAudio(type)` - Plays the selected audio file
   - `deleteAudio(type)` - Deletes audio file with confirmation
   - Auto-fills name field based on uploaded filename

### Directory Structure

```
sounds/
  greetings/
    default.wav          (copied from existing greeting.wav)
  beeps/
    default.wav          (copied from existing beep.wav)
  time_exceeded/
    default.wav          (copied from existing time_exceeded.wav)
```

## Key Features

✅ Upload audio in multiple formats (WAV, M4A, AAC, MP3)
✅ Auto-convert non-WAV files to WAV using ffmpeg
✅ Keep multiple versions of each audio type
✅ Select active audio from dropdown
✅ Preview audio before activating
✅ Delete audio files (with protection)
✅ Auto-switch to next file when deleting active one
✅ Custom naming for uploaded files
✅ Backward compatible with existing config structure

## Dependencies Required

The Raspberry Pi must have `ffmpeg` installed:
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

## Deployment Instructions

1. **Sync Files to Pi:**
   ```bash
   ./sync-to-pi.sh camphone
   # Or use camphone.local if DNS doesn't resolve
   ./sync-to-pi.sh camphone.local
   ```

2. **SSH into Pi and Install ffmpeg:**
   ```bash
   ssh admin@camphone
   sudo apt-get update
   sudo apt-get install ffmpeg
   ```

3. **Restart Services:**
   ```bash
   sudo systemctl restart audioGuestBook.service
   sudo systemctl restart audioGuestBookWebServer.service
   ```

4. **Test:**
   - Navigate to `http://camphone:8080/config` or `http://camphone.local:8080/config`
   - You should see the new dropdown selectors and upload sections
   - Try uploading an M4A file from your iPhone

## Testing Checklist

- [ ] Verify dropdowns show "default.wav" for all three audio types
- [ ] Preview greeting audio
- [ ] Upload WAV file directly
- [ ] Upload M4A file from iPhone (should convert to WAV)
- [ ] Upload with custom name
- [ ] Upload without custom name (should use filename)
- [ ] Switch active audio via dropdown
- [ ] Try to delete when only one file exists (should fail)
- [ ] Delete non-active audio file
- [ ] Delete active audio file (should switch to next available)
- [ ] Verify rotary phone plays the newly selected greeting

## Configuration Migration

The system automatically migrates existing audio files:
- Old: `sounds/greeting.wav`
- New: `sounds/greetings/default.wav`

The config.yaml still uses file paths, so no breaking changes:
```yaml
greeting: sounds/greetings/default.wav
beep: sounds/beeps/default.wav
time_exceeded: sounds/time_exceeded/default.wav
```

## Rollback Plan

If issues occur:
1. Checkout main branch: `git checkout main`
2. Sync to Pi: `./sync-to-pi.sh camphone`
3. Restart services

## Known Limitations

1. Requires ffmpeg to be installed
2. File conversion happens synchronously (may take a few seconds for large files)
3. No progress indicator during conversion
4. No file size validation (could upload very large files)

## Future Enhancements (Not in This PR)

- Bulk upload multiple files
- Audio trimming/editing
- Waveform visualization
- File size validation
- Async conversion with progress bar
- Schedule different greetings by time/date
