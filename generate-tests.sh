#!/bin/bash

echo "Generating automated tests for user code..."

cat > user_code_test.py <<'PYTEST'
import subprocess
import sys

def test_user_code_syntax():
    """Test 1: Check Python syntax"""
    print("\n=== Test 1: Syntax Check ===")
    try:
        with open('/tmp/user_code.py', 'r') as f:
            code = f.read()
            compile(code, '/tmp/user_code.py', 'exec')
        print("✓ Syntax is valid")
        return True
    except SyntaxError as e:
        print(f"✗ Syntax Error: {e}")
        return False

def test_user_code_structure():
    """Test 2: Check code structure"""
    print("\n=== Test 2: Code Structure ===")
    with open('/tmp/user_code.py', 'r') as f:
        code = f.read()
    
    checks = {
        "Has main function": "def main(" in code,
        "Has if __name__": 'if __name__' in code,
        "Has print statements": "print(" in code,
    }
    
    all_passed = True
    for check, result in checks.items():
        status = "✓" if result else "✗"
        print(f"{status} {check}")
        if not result:
            all_passed = False
    
    return all_passed

def test_user_code_length():
    """Test 3: Code length check"""
    print("\n=== Test 3: Code Quality ===")
    with open('/tmp/user_code.py', 'r') as f:
        lines = f.readlines()
    
    line_count = len(lines)
    print(f"Lines of code: {line_count}")
    
    if line_count < 5:
        print("✗ Code too short (minimum 5 lines)")
        return False
    elif line_count > 1000:
        print("✗ Code too long (maximum 1000 lines)")
        return False
    else:
        print("✓ Code length acceptable")
        return True

def test_user_code_imports():
    """Test 4: Check for dangerous imports"""
    print("\n=== Test 4: Security Check ===")
    with open('/tmp/user_code.py', 'r') as f:
        code = f.read()
    
    dangerous = ['os.system', 'subprocess', 'eval(', 'exec(', '__import__']
    found_issues = []
    
    for danger in dangerous:
        if danger in code:
            found_issues.append(danger)
    
    if found_issues:
        print(f"⚠️  Warning: Potentially dangerous code: {', '.join(found_issues)}")
        return False
    else:
        print("✓ No security issues detected")
        return True

if __name__ == '__main__':
    print("\n" + "="*50)
    print("AUTOMATED CODE TESTING")
    print("="*50)
    
    results = []
    results.append(("Syntax Check", test_user_code_syntax()))
    results.append(("Structure Check", test_user_code_structure()))
    results.append(("Quality Check", test_user_code_length()))
    results.append(("Security Check", test_user_code_imports()))
    
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Code is ready for deployment.")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed. Please review your code.")
        sys.exit(1)
PYTEST

echo "✓ Test file generated: user_code_test.py"

# Upload to Jenkins
export KUBECONFIG=./k3s.yaml
kubectl cp user_code_test.py cicd/jenkins-b74dbbb-l7tbd:/tmp/user_code_test.py

echo "✓ Tests uploaded to Jenkins"
