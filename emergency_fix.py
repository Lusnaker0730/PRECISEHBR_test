#!/usr/bin/env python3
"""
Emergency fix for stuck risk calculation
Forces Phase 1 optimization and adds timeout handling
"""

def apply_emergency_fix():
    """Apply emergency fix to APP.py to resolve stuck calculation"""
    
    # Read the current APP.py
    with open('APP.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the calculate_risk_ui_page function
    import re
    
    # Look for the Phase 2 optimization section
    phase2_pattern = r'(\s+# Phase 2: Try batch optimization.*?except Exception as e2:.*?print\(f"Phase 2 failed: \{e2\}"\)\s+)'
    
    if re.search(phase2_pattern, content, re.DOTALL):
        print("Found Phase 2 optimization section")
        
        # Create the emergency fix - force Phase 1 by disabling Phase 2
        emergency_code = '''
        # EMERGENCY FIX: Temporarily disable Phase 2 to resolve calculation hanging
        print("🚨 Emergency mode: Skipping Phase 2 batch optimization")
        phase2_success = False  # Force Phase 1 usage
        
        # Phase 2: Disabled for emergency fix
        # try:'''
        
        # Replace the Phase 2 section
        fixed_content = re.sub(
            r'(\s+# Phase 2: Try batch optimization.*?try:)',
            emergency_code,
            content,
            flags=re.DOTALL
        )
        
        # Also add timeout handling to Phase 1
        phase1_pattern = r'(# Phase 1: Try individual optimized calls.*?lab_values = get_lab_values_optimized\(smart_client, patient_id\))'
        
        phase1_with_timeout = r'''\1
                # Add timeout handling
                import signal
                def timeout_handler(signum, frame):
                    raise TimeoutError("Lab values fetch timed out")
                
                # Set 30 second timeout
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)
                
                try:
                    lab_values = get_lab_values_optimized(smart_client, patient_id)
                    signal.alarm(0)  # Cancel timeout
                except TimeoutError:
                    print("⚠️ Lab values fetch timed out, using manual method")
                    signal.alarm(0)
                    phase1_success = False'''
        
        fixed_content = re.sub(phase1_pattern, phase1_with_timeout, fixed_content, flags=re.DOTALL)
        
        # Write the emergency fix
        with open('APP.py', 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        
        print("✅ Emergency fix applied to APP.py")
        print("📝 Changes made:")
        print("   - Phase 2 batch optimization temporarily disabled")
        print("   - Phase 1 optimization with timeout handling")
        print("   - Fallback to manual method if timeout occurs")
        
        return True
    else:
        print("❌ Could not find Phase 2 optimization section")
        return False

if __name__ == "__main__":
    apply_emergency_fix() 