#!/usr/bin/env python3
"""
Verification Script for SL Recovery Manager Implementation
Checks that all components are properly installed and integrated
"""

import os
import sys
import importlib.util
from pathlib import Path

def check_file_exists(path, description):
    """Check if a file exists"""
    if os.path.exists(path):
        print(f"✅ {description}")
        print(f"   Location: {path}")
        return True
    else:
        print(f"❌ {description} NOT FOUND")
        print(f"   Expected: {path}")
        return False

def check_module_importable(module_path, module_name):
    """Check if a Python module can be imported"""
    try:
        # Load the module
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            print(f"✅ {module_name} module is importable")
            return True
    except Exception as e:
        print(f"❌ {module_name} module import failed: {e}")
        return False

def check_class_exists(module_path, class_name):
    """Check if a class exists in a module"""
    try:
        spec = importlib.util.spec_from_file_location("temp_module", module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, class_name):
                print(f"✅ {class_name} class found in module")
                return True
            else:
                print(f"❌ {class_name} class NOT found in module")
                return False
    except Exception as e:
        print(f"❌ Failed to check class: {e}")
        return False

def check_code_snippet(filepath, snippet):
    """Check if a code snippet exists in a file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if snippet in content:
                return True
            return False
    except Exception as e:
        print(f"Error reading file: {e}")
        return False

def print_header(title):
    """Print a formatted header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def main():
    """Run all verification checks"""
    
    print_header("SL Recovery Manager Implementation Verification")
    
    all_checks_passed = True
    
    # 1. Check core module exists
    print_header("1. Core Module Files")
    
    sl_recovery_file = "backend/app/engine/sl_recovery_manager.py"
    all_checks_passed &= check_file_exists(sl_recovery_file, "SL Recovery Manager module")
    
    # 2. Check auto_trading_simple.py updates
    print_header("2. Integration in auto_trading_simple.py")
    
    auto_trading_file = "backend/app/routes/auto_trading_simple.py"
    if check_file_exists(auto_trading_file, "Auto Trading Simple route"):
        # Check for import
        if check_code_snippet(auto_trading_file, "from app.engine.sl_recovery_manager import"):
            print("   ✅ sl_recovery_manager import found")
        else:
            print("   ❌ sl_recovery_manager import NOT found")
            all_checks_passed = False
        
        # Check for recovery endpoints
        if check_code_snippet(auto_trading_file, "/recovery-status"):
            print("   ✅ /recovery-status endpoint found")
        else:
            print("   ❌ /recovery-status endpoint NOT found")
            all_checks_passed = False
        
        if check_code_snippet(auto_trading_file, "/recovery-signal"):
            print("   ✅ /recovery-signal endpoint found")
        else:
            print("   ❌ /recovery-signal endpoint NOT found")
            all_checks_passed = False
        
        # Check for SL hit recording
        if check_code_snippet(auto_trading_file, "sl_recovery_manager.record_sl_hit"):
            print("   ✅ SL hit recording found")
        else:
            print("   ❌ SL hit recording NOT found")
            all_checks_passed = False
    else:
        all_checks_passed = False
    
    # 3. Check documentation files
    print_header("3. Documentation Files")
    
    docs = [
        ("SL_RECOVERY_README.md", "Main README"),
        ("SL_RECOVERY_QUICK_REFERENCE.md", "Quick Reference Guide"),
        ("SL_RECOVERY_GUIDE.md", "Detailed Feature Guide"),
        ("SL_RECOVERY_IMPLEMENTATION.md", "Implementation Guide"),
        ("SL_RECOVERY_STRATEGY_SUMMARY.md", "Strategy Summary"),
    ]
    
    for doc_file, doc_name in docs:
        all_checks_passed &= check_file_exists(doc_file, doc_name)
    
    # 4. Check test file
    print_header("4. Test Suite")
    
    all_checks_passed &= check_file_exists("test_sl_recovery.py", "SL Recovery test suite")
    
    # 5. Check class structure (if import works)
    print_header("5. Core Classes")
    
    if os.path.exists(sl_recovery_file):
        all_checks_passed &= check_class_exists(sl_recovery_file, "SLRecoveryManager")
        all_checks_passed &= check_class_exists(sl_recovery_file, "SLHitRecord")
        all_checks_passed &= check_class_exists(sl_recovery_file, "RecoverySignal")
    
    # 6. Check README update
    print_header("6. Main README Update")
    
    readme_file = "README.md"
    if check_file_exists(readme_file, "Main README.md"):
        if check_code_snippet(readme_file, "SL Recovery Strategy"):
            print("   ✅ SL Recovery Strategy section found in README")
        else:
            print("   ⚠️  SL Recovery Strategy section NOT found in README")
            print("      (This is not critical)")
    
    # 7. Summary
    print_header("Verification Summary")
    
    if all_checks_passed:
        print("✅ ALL CHECKS PASSED!")
        print("\nThe SL Recovery Manager is properly installed and integrated.")
        print("\nNext steps:")
        print("1. Read: SL_RECOVERY_README.md")
        print("2. Run: python test_sl_recovery.py")
        print("3. Review: backend/app/engine/sl_recovery_manager.py")
        print("4. Test: curl http://localhost:8000/autotrade/recovery-status")
        return 0
    else:
        print("❌ SOME CHECKS FAILED")
        print("\nPlease review the errors above and ensure all files are present.")
        print("Check that all replacements were applied correctly.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
