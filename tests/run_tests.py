"""Simple test runner - works without pytest."""
import sys
import os
import traceback
import importlib.util

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import test modules
MODULE_DIR = os.path.dirname(__file__)

def _import_module(name):
    """Import a module from the test directory."""
    path = os.path.join(MODULE_DIR, name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_tests(cls):
    """Run all test methods in a class and report results."""
    passed = 0
    failed = 0
    errors = []
    
    instance = cls()
    methods = [m for m in dir(instance) if m.startswith('test_')]
    
    for method_name in sorted(methods):
        method = getattr(instance, method_name)
        try:
            method()
            passed += 1
            print(f"  PASS {method_name}")
        except Exception as e:
            failed += 1
            err_msg = f"  FAIL {method_name}: {str(e)}"
            print(err_msg)
            errors.append(err_msg)
    
    return passed, failed, errors


def run_all():
    """Run all test modules."""
    print("=" * 60)
    print("Clipshare Test Suite")
    print("=" * 60)
    
    total_passed = 0
    total_failed = 0
    
    # Test config
    print("\n[Config Tests]")
    test_config = _import_module('test_config')
    p, f, _ = run_tests(test_config.TestConfig)
    total_passed += p
    total_failed += f
    
    # Test crypto
    print("\n[Crypto Tests]")
    test_crypto = _import_module('test_crypto')
    p, f, _ = run_tests(test_crypto.TestDiffieHellman)
    total_passed += p
    total_failed += f
    
    p2, f2, _ = run_tests(test_crypto.TestAESEncryption)
    total_passed += p2
    total_failed += f2
    
    # Test protocol
    print("\n[Protocol Tests]")
    test_protocol = _import_module('test_protocol')
    p, f, _ = run_tests(test_protocol.TestMessage)
    total_passed += p
    total_failed += f
    
    p2, f2, _ = run_tests(test_protocol.TestClipboardEncoding)
    total_passed += p2
    total_failed += f2
    
    # Test discovery
    print("\n[Discovery Tests]")
    test_discovery = _import_module('test_discovery')
    p, f, _ = run_tests(test_discovery.TestDeviceInfo)
    total_passed += p
    total_failed += f
    
    p2, f2, _ = run_tests(test_discovery.TestDeviceDiscovery)
    total_passed += p2
    total_failed += f2
    
    # Test clipboard
    print("\n[Clipboard Tests]")
    test_clipboard = _import_module('test_clipboard')
    p, f, _ = run_tests(test_clipboard.TestClipboardResult)
    total_passed += p
    total_failed += f
    
    p2, f2, _ = run_tests(test_clipboard.TestClipboardBackends)
    total_passed += p2
    total_failed += f2
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {total_passed} passed, {total_failed} failed, "
          f"{total_passed + total_failed} total")
    print("=" * 60)
    
    return total_failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)