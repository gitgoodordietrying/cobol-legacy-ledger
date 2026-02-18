#!/usr/bin/env python
"""Test imports to diagnose issues."""

import sys
import traceback

print("Python:", sys.version)
print("Path:", sys.path[:3])
print()

# Test 1: Import integrity
print("Test 1: Import integrity module...")
try:
    from python.integrity import IntegrityChain
    print("  ✓ Success")
except Exception as e:
    print(f"  ✗ Failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 2: Import bridge
print("\nTest 2: Import bridge module...")
try:
    from python.bridge import COBOLBridge
    print("  ✓ Success")
except Exception as e:
    print(f"  ✗ Failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 3: Create bridge instance
print("\nTest 3: Create bridge instance...")
try:
    bridge = COBOLBridge(node="TEST")
    print(f"  ✓ Success - created bridge for {bridge.node}")
    bridge.close()
except Exception as e:
    print(f"  ✗ Failed: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n✓ All import tests passed!")
