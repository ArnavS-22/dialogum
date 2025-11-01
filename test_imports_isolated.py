#!/usr/bin/env python3
"""Test if we can import the modules without triggering gum.__init__"""

import sys
import importlib.util

# Load modules directly without going through gum.__init__
def load_module_direct(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

base_path = "/Users/arnavsharma/.cursor/worktrees/gum-elicitation/moVjG/gum/clarification"

print("Testing direct module loads...")

try:
    config = load_module_direct("question_config", f"{base_path}/question_config.py")
    print(f"✓ question_config loaded")
    print(f"  Factor 1: {config.get_factor_name(1)}")
except Exception as e:
    print(f"✗ question_config failed: {e}")
    import traceback
    traceback.print_exc()

