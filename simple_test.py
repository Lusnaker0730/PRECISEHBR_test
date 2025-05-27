#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Test Runner - 簡單測試運行器
避免複雜的字符串處理，提供清潔的測試執行
"""

import os
import sys
import unittest

def setup_environment():
    """設置測試環境"""
    os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'
    os.environ['SMART_CLIENT_ID'] = 'test-client-id'
    os.environ['SMART_REDIRECT_URI'] = 'http://localhost:8080/callback'
    
    # 設置測試配置文件
    test_config = os.path.join(os.path.dirname(__file__), "test_config.json")
    if os.path.exists(test_config):
        os.environ['CDSS_CONFIG_PATH'] = test_config
        print("✓ 測試配置已設置")
    else:
        print("⚠️ 測試配置文件不存在")

def main():
    """主函數"""
    print("=" * 60)
    print("SMART FHIR Bleeding Risk Calculator - 單元測試")
    print("=" * 60)
    
    # 設置環境
    setup_environment()
    
    # 檢查必要文件
    required_files = ['APP.py', 'test_app.py']
    missing = [f for f in required_files if not os.path.exists(f)]
    
    if missing:
        print("❌ 缺少文件:", ', '.join(missing))
        return False
    
    print("✓ 所有必要文件存在")
    
    try:
        # 導入並運行測試
        from test_app import create_test_suite
        
        suite = create_test_suite()
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # 顯示結果
        print("\n" + "=" * 60)
        print("測試結果摘要")
        print("=" * 60)
        print("測試總數:", result.testsRun)
        print("失敗數量:", len(result.failures))
        print("錯誤數量:", len(result.errors))
        
        if result.testsRun > 0:
            success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun) * 100
            print("成功率: {:.1f}%".format(success_rate))
        
        if result.failures:
            print("\n失敗的測試:")
            for test, _ in result.failures:
                print("  -", str(test))
        
        if result.errors:
            print("\n錯誤的測試:")
            for test, _ in result.errors:
                print("  -", str(test))
        
        if result.wasSuccessful():
            print("\n✅ 所有測試通過!")
            return True
        else:
            print("\n❌ 部分測試失敗")
            return False
            
    except ImportError as e:
        print("❌ 導入錯誤:", str(e))
        print("請確保 APP.py 在同一目錄下")
        return False
    except Exception as e:
        print("❌ 運行錯誤:", str(e))
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1) 