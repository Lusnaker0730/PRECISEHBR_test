#!/usr/bin/env python3
"""
Emergency script to disable all optimizations and force manual mode
Use this if optimizations continue to cause hanging issues
"""

import os
import re

def disable_all_optimizations():
    """Disable all optimization features and force manual mode"""
    
    print("🚨 Emergency Optimization Disable")
    print("=" * 50)
    
    try:
        # Read APP.py
        with open('APP.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("📝 Making emergency changes to APP.py...")
        
        # 1. Force OPTIMIZATIONS_AVAILABLE to False at the beginning
        pattern1 = r'(OPTIMIZATIONS_AVAILABLE = .*?)$'
        replacement1 = 'OPTIMIZATIONS_AVAILABLE = False  # EMERGENCY DISABLE'
        content = re.sub(pattern1, replacement1, content, flags=re.MULTILINE)
        
        # 2. Replace the entire lab values section with simple manual calls
        lab_section_pattern = r'(# 2\. Fetch Lab Values \(Comprehensive Timeout Protection\).*?)app\.logger\.info\(f"Patient {patient_id} Labs:'
        
        simple_lab_section = '''# 2. Fetch Lab Values (EMERGENCY MODE: Manual Only)
    app.logger.info("🚨 EMERGENCY MODE: All optimizations disabled, using manual retrieval only")
    
    try:
        hb_value = get_hemoglobin(patient_id)
    except Exception as e:
        app.logger.error(f"Error getting hemoglobin: {e}")
        hb_value = None
    
    try:
        platelet_value = get_platelet(patient_id)
    except Exception as e:
        app.logger.error(f"Error getting platelet: {e}")
        platelet_value = None
    
    try:
        egfr_value = get_egfr_value(patient_id, age, sex)
    except Exception as e:
        app.logger.error(f"Error getting eGFR: {e}")
        egfr_value = None
    
    app.logger.info(f"Patient {patient_id} Labs:'''
        
        content = re.sub(lab_section_pattern, simple_lab_section, content, flags=re.DOTALL)
        
        # 3. Also disable patient optimization
        patient_opt_pattern = r'(if OPTIMIZATIONS_AVAILABLE:.*?else:\s+patient_resource = get_patient_data\(\))'
        patient_replacement = 'patient_resource = get_patient_data()  # EMERGENCY: Skip optimization'
        content = re.sub(patient_opt_pattern, patient_replacement, content, flags=re.DOTALL)
        
        # Write the emergency version
        with open('APP.py', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Emergency changes applied successfully!")
        print("\n📋 Changes made:")
        print("   - OPTIMIZATIONS_AVAILABLE forced to False")
        print("   - Lab values section replaced with simple manual calls")
        print("   - Patient data optimization disabled")
        print("   - All timeout mechanisms removed")
        
        print("\n🎯 Result:")
        print("   - No more hanging issues")
        print("   - Calculation will complete (may be slower)")
        print("   - Safe fallback mode activated")
        
        print("\n⚠️  To re-enable optimizations later:")
        print("   1. Set OPTIMIZATIONS_AVAILABLE = True")
        print("   2. Restore the original lab values section")
        print("   3. Test thoroughly")
        
        return True
        
    except Exception as e:
        print(f"❌ Error applying emergency changes: {e}")
        return False

def create_backup():
    """Create a backup of the current APP.py"""
    try:
        with open('APP.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        backup_name = 'APP_backup_before_emergency.py'
        with open(backup_name, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Backup created: {backup_name}")
        return True
    except Exception as e:
        print(f"❌ Could not create backup: {e}")
        return False

if __name__ == "__main__":
    print("This script will DISABLE ALL optimizations and force manual mode.")
    print("This should resolve any hanging issues but may reduce performance.")
    
    confirm = input("\nDo you want to proceed? (yes/no): ").strip().lower()
    
    if confirm in ['yes', 'y']:
        # Create backup first
        if create_backup():
            if disable_all_optimizations():
                print("\n🎉 Emergency disable complete! Restart your Flask app.")
            else:
                print("\n❌ Emergency disable failed.")
        else:
            print("\n❌ Could not create backup. Aborting for safety.")
    else:
        print("\n❌ Operation cancelled.") 