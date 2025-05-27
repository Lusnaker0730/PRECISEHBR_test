#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Runner for SMART FHIR Bleeding Risk Calculator
簡化的測試運行腳本
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def setup_test_environment():
    """設置測試環境變數"""
    test_env = {
        'FLASK_SECRET_KEY': 'test-secret-key-for-unit-tests',
        'SMART_CLIENT_ID': 'test-client-id',
        'SMART_REDIRECT_URI': 'http://localhost:8080/callback',
        'SMART_SCOPES': 'launch/patient openid fhirUser profile email patient/Patient.read patient/Observation.read patient/Condition.read patient/MedicationRequest.read',
        'APP_BASE_URL': 'http://localhost:8080',
        'FLASK_ENV': 'testing'
    }
    
    for key, value in test_env.items():
        os.environ[key] = value
    
    print("✓ 測試環境變數已設置")

def check_dependencies():
    """檢查測試依賴"""
    required_files = [
        'APP.py',
        'test_app.py'
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ 缺少必要文件: {', '.join(missing_files)}")
        return False
    
    print("✓ 所有必要文件都存在")
    return True

def run_specific_test(test_class=None, test_method=None):
    """運行特定測試"""
    if not check_dependencies():
        return False
    
    setup_test_environment()
    
    cmd = [sys.executable, '-m', 'unittest']
    
    if test_class and test_method:
        cmd.append(f'test_app.{test_class}.{test_method}')
    elif test_class:
        cmd.append(f'test_app.{test_class}')
    else:
        cmd.extend(['-v', 'test_app'])
    
    print(f"運行命令: {' '.join(cmd)}")
    print("=" * 60)
    
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 運行測試時發生錯誤: {e}")
        return False

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='SMART FHIR App 測試運行器')
    parser.add_argument('--class', dest='test_class', help='運行特定測試類別')
    parser.add_argument('--method', dest='test_method', help='運行特定測試方法')
    parser.add_argument('--list', action='store_true', help='列出所有可用的測試')
    
    args = parser.parse_args()
    
    if args.list:
        print("可用的測試類別:")
        test_classes = [
            'TestUtilityFunctions - 工具函數測試',
            'TestBleedingRiskCalculation - 出血風險計算測試',
            'TestPrefetchFunctions - Prefetch 函數測試',
            'TestValueSetFunctions - ValueSet 函數測試',
            'TestFlaskRoutes - Flask 路由測試',
            'TestConfigurationLoading - 配置加載測試',
            'TestErrorHandling - 錯誤處理測試'
        ]
        for test_class in test_classes:
            print(f"  - {test_class}")
        return
    
    print("🧪 SMART FHIR Bleeding Risk Calculator - 單元測試")
    print("=" * 60)
    
    success = run_specific_test(args.test_class, args.test_method)
    
    if success:
        print("\n✅ 所有測試通過!")
        sys.exit(0)
    else:
        print("\n❌ 部分測試失敗")
        sys.exit(1)

if __name__ == '__main__':
    main() 