#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick Test Script - 快速測試腳本
驗證測試環境設置是否正確
"""

import os
import sys
import unittest

def setup_test_environment():
    """設置測試環境"""
    # 設置必要的環境變數
    os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'
    os.environ['SMART_CLIENT_ID'] = 'test-client-id'
    os.environ['SMART_REDIRECT_URI'] = 'http://localhost:8080/callback'
    
    # 設置測試配置文件路徑
    test_config_path = os.path.join(os.path.dirname(__file__), "test_config.json")
    if os.path.exists(test_config_path):
        os.environ['CDSS_CONFIG_PATH'] = test_config_path
        print(f"✓ 使用測試配置文件: {test_config_path}")
    else:
        print(f"⚠️  測試配置文件不存在: {test_config_path}")

def run_quick_tests():
    """運行快速測試"""
    print("🧪 運行快速測試...")
    print("=" * 50)
    
    try:
        # 導入測試模組
        from test_app import TestUtilityFunctions, TestBleedingRiskCalculation
        
        # 創建測試套件
        suite = unittest.TestSuite()
        
        # 添加關鍵測試
        suite.addTest(TestUtilityFunctions('test_calculate_age'))
        suite.addTest(TestUtilityFunctions('test_get_human_name_text'))
        suite.addTest(TestBleedingRiskCalculation('test_high_risk_calculation'))
        suite.addTest(TestBleedingRiskCalculation('test_low_risk_calculation'))
        
        # 運行測試
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # 顯示結果
        print("\n" + "=" * 50)
        if result.wasSuccessful():
            print("✅ 快速測試通過! 測試環境設置正確。")
            print("💡 現在可以運行完整測試: python run_tests.py")
            return True
        else:
            print("❌ 快速測試失敗")
            if result.failures:
                print("失敗的測試:")
                for test, error in result.failures:
                    print(f"  - {test}")
            if result.errors:
                print("錯誤的測試:")
                for test, error in result.errors:
                    print(f"  - {test}")
            return False
            
    except ImportError as e:
        print(f"❌ 導入錯誤: {e}")
        print("請確保 APP.py 和 test_app.py 在同一目錄下")
        return False
    except Exception as e:
        print(f"❌ 運行測試時發生錯誤: {e}")
        return False

def check_files():
    """檢查必要文件"""
    required_files = ['APP.py', 'test_app.py', 'test_config.json']
    missing_files = []
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file}")
        else:
            print(f"❌ {file} (缺少)")
            missing_files.append(file)
    
    return len(missing_files) == 0

def main():
    """主函數"""
    print("🔍 SMART FHIR App - 快速測試檢查")
    print("=" * 50)
    
    # 檢查文件
    print("檢查必要文件:")
    if not check_files():
        print("\n❌ 缺少必要文件，無法運行測試")
        return False
    
    print("\n設置測試環境:")
    setup_test_environment()
    
    print("\n運行快速測試:")
    success = run_quick_tests()
    
    return success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1) 