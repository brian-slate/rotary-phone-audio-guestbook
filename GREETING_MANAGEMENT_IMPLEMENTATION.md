# Multi-Greeting Management Implementation Guide

## Overview
Add support for managing multiple greeting, beep, and time_exceeded audio files with the ability to:
- Upload audio files in various formats (m4a, aac, mp3, wav)
- Auto-convert non-WAV files to WAV using ffmpeg
- Name and organize multiple versions of each audio type
- Select which audio file is active
- Preview audio files before activating
- Delete audio files (with protection against deleting the last one)

## Goals
1. Allow users to record voice memos on their phones and upload them
2. Keep multiple versions of greetings/beeps without overwriting
3. Switch between different audio files easily
4. Maintain backward compatibility with existing config structure

## Directory Structure Changes

### Current:
```
sounds/
  greeting.wav
  beep.wav
  time_exceeded.wav
```

### New:
```
sounds/
  greetings/
    default.wav
    wedding-greeting.wav
    birthday-party.wav
  beeps/
    default.wav
    custom-beep.wav
  time_exceeded/
    default.wav
    polite-reminder.wav
```

## Implementation Details

### 1. Backend Changes (server.py)

#### A. Modify `/config` GET endpoint (lines 145-191)
- Before rendering template, scan subdirectories in sounds folder
- Build lists of available files for each type (greetings, beeps, time_exceeded)
- Pass these lists to template along with current config
- Extract current filename from config paths for dropdown selection

#### B. Modify `/config` POST endpoint (lines 145-191)
**Current behavior:** File upload overwrites existing audio files

**New behavior:**
1. Accept additional form field: `<type>_name` (e.g., "greeting_name")
2. Check if uploaded file is WAV format
3. If not WAV, use ffmpeg to convert to WAV format:
   ```python
   subprocess.run([
       "ffmpeg", "-i", str(temp_input),
       "-ar", "44100", "-ac", "2",
       "-f", "wav", str(output_path)
   ], check=True)
   ```
4. Save converted/uploaded file to appropriate subdirectory with given name
5. Update config path to point to new file
6. Keep other files intact (don't delete old greetings)

#### C. Add/Modify delete endpoint
**Option 1:** Expand existing `/delete/<filename>` to handle audio files
**Option 2:** Create `/delete-audio/<type>/<filename>`

**Validation required:**
1. Check if more than one file exists in that subdirectory
2. If deleting the currently active file, auto-switch config to first remaining file
3. Return error if trying to delete the last file

#### D. Add audio preview/serving
**Option 1:** Extend `/recordings/<filename>` to handle sounds subdirectories
**Option 2:** Create new endpoint `/sounds/<type>/<filename>`

Use existing streaming logic from `/recordings/<filename>` (lines 194-246)

### 2. Frontend Changes (config.html)

#### Replace each audio upload section with:

**Current UI (per audio type):**
```html
<div class="mb-2">
  <label for="greeting_file">Greeting File</label>
  <input type="file" id="greeting_file" name="greeting_file" />
  <span class="text-xs">uploads/greeting.wav</span>
</div>
```

**New UI (per audio type):**
```html
<div class="mb-2">
  <label>Active Greeting</label>
  <select name="greeting" id="greeting_select">
    <option value="sounds/greetings/default.wav">default.wav</option>
    <option value="sounds/greetings/wedding.wav" selected>wedding.wav</option>
  </select>
  
  <div class="flex gap-2 mt-2">
    <button type="button" onclick="previewAudio('greeting')">
      <i class="fas fa-play"></i> Preview
    </button>
    <button type="button" onclick="deleteAudio('greeting')">
      <i class="fas fa-trash"></i> Delete Current
    </button>
  </div>
</div>

<div class="mb-2 mt-4">
  <label>Upload New Greeting</label>
  <input type="file" name="greeting_file" accept="audio/*" />
  <input type="text" name="greeting_name" placeholder="Name this greeting" />
</div>
```

#### JavaScript additions:
```javascript
// Handle dropdown change - auto-submit form to update config
document.getElementById('greeting_select').addEventListener('change', function() {
  // Submit form or AJAX update config
});

// Preview audio file
function previewAudio(type) {
  const select = document.getElementById(type + '_select');
  const audioPath = select.value;
  // Play audio using HTML5 audio element or existing player
}

// Delete audio file with validation
function deleteAudio(type) {
  const select = document.getElementById(type + '_select');
  const filename = select.value.split('/').pop();
  
  if (select.options.length <= 1) {
    alert('Cannot delete the last audio file');
    return;
  }
  
  if (confirm('Delete ' + filename + '?')) {
    fetch('/delete-audio/' + type + '/' + filename, { method: 'POST' })
      .then(() => location.reload());
  }
}
```

### 3. Migration Strategy

#### First run setup:
1. Check if subdirectories exist, create if not
2. Move existing greeting.wav → greetings/default.wav
3. Move existing beep.wav → beeps/default.wav
4. Move existing time_exceeded.wav → time_exceeded/default.wav
5. Update config.yaml paths

#### Or: Add migration script
```python
# migrate_audio_files.py
# Run once to move existing files to new structure
```

### 4. Dependencies

#### System requirements:
- `ffmpeg` must be installed on Raspberry Pi
  ```bash
  sudo apt-get install ffmpeg
  ```

#### Supported input formats:
- .wav (pass through, no conversion)
- .m4a (iPhone voice memos)
- .aac (Android)
- .mp3 (common format)
- .ogg, .flac, .wma (bonus support via ffmpeg)

### 5. Edge Cases to Handle

1. **File naming conflicts:** If name exists, append number (greeting-1.wav, greeting-2.wav)
2. **Invalid file uploads:** Validate file is actually audio before processing
3. **FFmpeg conversion failures:** Show error message, don't save file
4. **Empty filenames:** Generate name from timestamp or original filename
5. **Deleting active file:** Automatically switch to first remaining file
6. **Config path format:** Ensure paths are relative to BASE_DIR for portability
7. **Concurrent uploads:** Handle multiple files uploaded at once

### 6. Testing Checklist

- [ ] Upload WAV file directly (no conversion)
- [ ] Upload M4A file (iPhone voice memo) - verify conversion
- [ ] Upload AAC/MP3 file - verify conversion
- [ ] Switch between multiple greetings via dropdown
- [ ] Preview audio before activating
- [ ] Delete non-active audio file
- [ ] Attempt to delete last audio file (should fail)
- [ ] Delete active audio file (should switch to next)
- [ ] Verify phone plays new greeting correctly after restart
- [ ] Upload file with same name (should handle conflict)
- [ ] Upload invalid file format (should show error)

## Files Modified

1. `webserver/server.py` - Backend logic
2. `webserver/templates/config.html` - UI changes
3. `sounds/` directory - Restructure with subdirectories
4. `config.yaml` - Paths updated to point to subdirectories

## Backward Compatibility

- Existing config.yaml still works (single file paths)
- Config structure unchanged (still just file paths)
- No changes to audioGuestBook.py or audioInterface.py
- Audio playback logic untouched

## Future Enhancements (Not in Scope)

- Bulk upload multiple files
- Audio trimming/editing in browser
- Waveform visualization
- Schedule greetings by date/time
- Different greetings for different callers
