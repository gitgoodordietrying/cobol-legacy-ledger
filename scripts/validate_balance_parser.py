#!/usr/bin/env python3
"""
Balance Parser Validation Script

Tests bridge.py's _parse_balance() method against expected COBOL output formats.
Run this after SMOKETEST.cob to validate the parser matches actual GnuCOBOL output.

Usage:
    python scripts/validate_balance_parser.py
    python scripts/validate_balance_parser.py --format "00000012345.67"
    python scripts/validate_balance_parser.py --format "000001234567"
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from python.bridge import COBOLBridge


def test_balance_format(balance_str: str, expected: float, description: str) -> bool:
    """Test a specific balance format string."""
    bridge = COBOLBridge(node="TEST", data_dir=".", bin_dir="cobol/bin")
    
    try:
        balance_bytes = balance_str.encode('ascii')
        parsed = bridge._parse_balance(balance_bytes)
        match = abs(parsed - expected) < 0.01  # Allow floating point tolerance
        
        status = "[PASS]" if match else "[FAIL]"
        print(f"{status} {description}")
        print(f"   Input:    {balance_str!r} ({len(balance_str)} chars)")
        print(f"   Parsed:   {parsed}")
        print(f"   Expected: {expected}")
        print(f"   Match:    {match}")
        print()
        
        return match
    except Exception as e:
        print(f"[FAIL] {description}")
        print(f"   Error: {e}")
        print()
        return False
    finally:
        bridge.close()


def main():
    """Run all balance format tests."""
    print("=" * 70)
    print("Balance Parser Validation")
    print("=" * 70)
    print()
    
    # Test value: 12345.67 (from SMOKETEST.cob)
    expected_value = 12345.67
    
    # Test all possible formats
    test_cases = [
        # Format 1: 12 digits, no decimal point (most likely for internal storage)
        ("000001234567", expected_value, "12 digits, no decimal (internal format)"),
        
        # Format 2: 13 chars with decimal point (possible DISPLAY format)
        ("00000012345.67", expected_value, "13 chars with decimal point"),
        
        # Format 3: Leading spaces instead of zeros
        ("     12345.67", expected_value, "Leading spaces with decimal"),
        ("     1234567", expected_value, "Leading spaces, no decimal"),
        
        # Format 4: No leading zeros
        ("12345.67", expected_value, "No leading zeros, with decimal"),
        ("1234567", expected_value, "No leading zeros, no decimal"),
        
        # Edge cases
        ("000000000000", 0.00, "Zero value"),
        ("000000000001", 0.01, "One cent"),
        ("999999999999", 9999999999.99, "Maximum value"),
        
        # Negative values (if sign appears)
        ("-000001234567", -expected_value, "Negative with minus sign"),
        ("000001234567-", -expected_value, "Negative with trailing sign"),
    ]
    
    print(f"Testing parser against expected value: {expected_value}")
    print()
    
    results = []
    for balance_str, expected, description in test_cases:
        result = test_balance_format(balance_str, expected, description)
        results.append((description, result))
    
    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for description, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {description}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[PASS] All tests passed! Parser handles all expected formats.")
        return 0
    else:
        print(f"\n[FAIL] {total - passed} test(s) failed. Parser may need adjustment.")
        return 1


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate balance parser against COBOL output formats")
    parser.add_argument("--format", help="Test a specific format string")
    parser.add_argument("--expected", type=float, default=12345.67, help="Expected parsed value")
    
    args = parser.parse_args()
    
    if args.format:
        # Test single format
        bridge = COBOLBridge(node="TEST", data_dir=".", bin_dir="cobol/bin")
        try:
            balance_bytes = args.format.encode('ascii')
            parsed = bridge._parse_balance(balance_bytes)
            print(f"Input:    {args.format!r}")
            print(f"Parsed:   {parsed}")
            print(f"Expected: {args.expected}")
            print(f"Match:    {abs(parsed - args.expected) < 0.01}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
        finally:
            bridge.close()
    else:
        # Run all tests
        sys.exit(main())
