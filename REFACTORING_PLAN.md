# Config Page Refactoring Plan

## Current Issues

1. **config.html is too large** (~1060 lines)
   - Hard to maintain and comprehend
   - Mixing HTML structure, inline styles, and JavaScript
   - Repetitive form field patterns

2. **Code organization problems**
   - Form field generation is repetitive (greeting, beep, time_exceeded sections are nearly identical)
   - JavaScript functions scattered throughout the file
   - CSS embedded in template instead of separate file

3. **DRY violations**
   - Audio file upload sections duplicated 3 times with minor variations
   - Tooltip HTML repeated for every field
   - Radio button patterns repeated throughout

## Proposed Refactoring

### Phase 1: Extract Reusable Components

#### 1.1 Create Jinja2 Macros for Common Patterns
**File**: `webserver/templates/macros/form_fields.html`

```jinja2
{# Text input field with optional tooltip #}
{% macro text_field(name, label, value, tooltip=None, placeholder='') %}
  <div class="mb-2">
    <label for="{{ name }}" class="block mb-1 flex items-center">
      {{ label }}
      {% if tooltip %}
        {{ tooltip_icon(tooltip) }}
      {% endif %}
    </label>
    <input type="text" id="{{ name }}" name="{{ name }}" 
           value="{{ value }}" placeholder="{{ placeholder }}"
           class="w-full px-3 py-2 border rounded bg-background dark:bg-dark-input-background text-text-primary dark:text-dark-input-text" />
  </div>
{% endmacro %}

{# Number input field with optional tooltip #}
{% macro number_field(name, label, value, tooltip=None, step='1', min=None, max=None) %}
  {# Similar pattern #}
{% endmacro %}

{# Radio button field #}
{% macro radio_field(name, label, current_value, tooltip=None, help_text='') %}
  {# Boolean yes/no radio buttons #}
{% endmacro %}

{# Audio file upload section #}
{% macro audio_upload_section(field_name, display_name, available_files, current_config) %}
  {# Complete audio upload/select/preview/delete section #}
{% endmacro %}

{# Tooltip icon #}
{% macro tooltip_icon(text) %}
  <span class="tooltip-trigger" title="{{ text }}">
    <i class="fas fa-info-circle"></i>
  </span>
{% endmacro %}
```

#### 1.2 Extract CSS to Separate File
**File**: `webserver/static/css/config.css`

Move all tooltip styles and config-specific styles out of the template.

#### 1.3 Extract JavaScript to Separate File
**File**: `webserver/static/js/config.js`

Move all JavaScript functions:
- `previewAudio()`
- `deleteAudio()`
- `toggleAdvancedMode()`
- `initTooltips()`
- File upload feedback

### Phase 2: Simplify Template Structure

#### 2.1 Refactor config.html to Use Macros

**Before** (60+ lines per audio section):
```html
<div class="space-y-3">
  <h3>Greeting Settings</h3>
  <div class="mb-2">
    <label for="greeting_select">Active Greeting</label>
    <select id="greeting_select" name="greeting">
      {% for file in available_greetings %}
        <option value="...">{{ file }}</option>
      {% endfor %}
    </select>
    <!-- 50 more lines... -->
  </div>
</div>
```

**After** (3 lines):
```html
{{ macros.audio_upload_section('greeting', 'Greeting', available_greetings, config) }}
```

#### 2.2 Group Related Settings

Create sub-templates for major sections:
- `config/_audio_files.html` (audio file management)
- `config/_recording.html` (recording settings)
- `config/_hardware.html` (audio & GPIO settings)
- `config/_ai.html` (OpenAI settings)
- `config/_system.html` (shutdown settings)

Main template becomes:
```html
{% include 'config/_audio_files.html' %}
<div id="advancedSettings">
  {% include 'config/_recording.html' %}
  {% include 'config/_hardware.html' %}
  {% include 'config/_system.html' %}
  {% include 'config/_ai.html' %}
</div>
```

### Phase 3: Backend Improvements

#### 3.1 Config Form Handler Refactoring
**File**: `webserver/forms.py` (new)

Create WTForms classes for type safety and validation:
```python
class AudioFileForm(FlaskForm):
    greeting = SelectField('Greeting')
    greeting_volume = FloatField('Volume', validators=[NumberRange(0, 1)])
    # ... etc

class RecordingSettingsForm(FlaskForm):
    recording_limit = IntegerField('Recording Limit')
    # ... etc
```

#### 3.2 Config Update Logic
Move config update logic from inline code to dedicated functions:
- `update_audio_settings(form_data)`
- `update_recording_settings(form_data)`
- `update_openai_settings(form_data)`

### Phase 4: Testing & Validation

- Add form validation (currently minimal)
- Add unit tests for config update functions
- Test all form fields save/load correctly
- Verify service restarts work
- Test on actual Pi hardware

## Expected Benefits

1. **Maintainability**: ~1060 lines → ~300 lines in main template
2. **Reusability**: Macros can be used in other forms
3. **Clarity**: Each section has clear purpose
4. **DRY**: No repeated code patterns
5. **Testability**: Backend logic can be unit tested
6. **Performance**: Browser caches separate CSS/JS files

## Implementation Order

1. ✅ Write this plan
2. Create `form_fields.html` macros
3. Create `config.css` and move styles
4. Create `config.js` and move JavaScript
5. Refactor audio files section to use macros (test first)
6. Refactor other sections incrementally
7. Extract sub-templates
8. Test thoroughly
9. Deploy when stable

## Rollback Strategy

- Keep original `config.html` as `config.html.backup`
- Deploy incrementally section by section
- Test each section before moving to next
- Can revert individual sections if issues arise

## Estimated Time

- Phase 1: 2-3 hours
- Phase 2: 2-3 hours  
- Phase 3: 2-3 hours
- Phase 4: 1-2 hours
- **Total**: 7-11 hours

## Notes

- This refactoring should be done AFTER OpenAI integration is stable and tested
- No functionality changes - pure code organization
- Should result in identical UI and behavior
- Focus on maintainability for future features
