#!/usr/bin/env python3
"""
Merge repository config template with existing Pi config.
Preserves user's existing values while adding any new keys with defaults.
"""
import sys
from pathlib import Path
from ruamel.yaml import YAML

def merge_configs(template_path: Path, existing_path: Path, output_path: Path):
    """
    Merge template config with existing config.
    
    Args:
        template_path: Path to repo's config.yaml (has all keys with defaults)
        existing_path: Path to Pi's current config.yaml (user's settings)
        output_path: Path to write merged config
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    
    # Load template (source of new keys/defaults)
    with open(template_path, 'r') as f:
        template = yaml.load(f)
    
    # Load existing config (user's values take precedence)
    try:
        with open(existing_path, 'r') as f:
            existing = yaml.load(f)
    except FileNotFoundError:
        # No existing config, use template as-is
        existing = {}
    
    # Merge: existing values override template, template adds new keys
    merged = template.copy()
    for key, value in existing.items():
        if key in merged:
            # Preserve user's existing value
            merged[key] = value
        # Note: we don't add keys from existing that aren't in template
        # This prevents deprecated keys from persisting
    
    # Write merged config
    with open(output_path, 'w') as f:
        yaml.dump(merged, f)
    
    # Report changes
    added_keys = set(template.keys()) - set(existing.keys())
    preserved_keys = set(template.keys()) & set(existing.keys())
    
    if added_keys:
        print(f"Added {len(added_keys)} new config keys with defaults:")
        for key in sorted(added_keys):
            print(f"  - {key}: {template[key]}")
    
    if preserved_keys:
        print(f"Preserved {len(preserved_keys)} existing config values")
    
    return True

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: merge_config.py <template_config> <existing_config> <output_config>")
        sys.exit(1)
    
    template_path = Path(sys.argv[1])
    existing_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])
    
    if not template_path.exists():
        print(f"Error: Template config not found: {template_path}")
        sys.exit(1)
    
    try:
        merge_configs(template_path, existing_path, output_path)
        print("Config merge completed successfully")
    except Exception as e:
        print(f"Error merging configs: {e}")
        sys.exit(1)
