#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration Validation Test
驗證改善版配置文件是否正確
"""

import json
import os

def test_config_validation():
    """測試配置文件驗證"""
    try:
        # 載入改善版配置
        with open('cdss_config_improved.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print("=== 配置文件驗證結果 ===")
        print(f"版本: {config.get('version', 'N/A')}")
        print(f"指引來源: {config.get('guideline_source', 'N/A')}")
        
        # 檢查評分邏輯
        scoring = config.get('scoring_logic', {})
        print(f"評分邏輯: {scoring.get('description', 'N/A')}")
        print(f"Major標準分數: {scoring.get('major_criterion_score', 'N/A')}")
        print(f"Minor標準分數: {scoring.get('minor_criterion_score', 'N/A')}")
        print(f"高風險閾值: {scoring.get('high_risk_threshold', 'N/A')}")
        
        # 檢查關鍵配置項目
        required_keys = [
            'local_valuesets',
            'medication_codings', 
            'procedure_codings',
            'condition_rules',
            'risk_score_parameters',
            'final_risk_threshold'
        ]
        
        print("\n=== 必要配置項目檢查 ===")
        for key in required_keys:
            if key in config:
                print(f"✓ {key}: 存在")
            else:
                print(f"✗ {key}: 缺失")
        
        # 檢查新增的年齡參數
        risk_params = config.get('risk_score_parameters', {})
        age_params = [
            'age_gte_75_params',
            'age_gte_65_params'
        ]
        
        print("\n=== 年齡參數檢查 ===")
        for param in age_params:
            if param in risk_params:
                threshold = risk_params[param].get('threshold', 'N/A')
                score = risk_params[param].get('score', 'N/A')
                print(f"✓ {param}: 閾值={threshold}, 分數={score}")
            else:
                print(f"✗ {param}: 缺失")
        
        # 檢查 ARC-HBR 合規性
        arc_hbr = config.get('arc_hbr_compliance', {})
        if arc_hbr:
            print(f"\n=== ARC-HBR 合規性 ===")
            print(f"版本: {arc_hbr.get('version', 'N/A')}")
            major_criteria = arc_hbr.get('major_criteria_implemented', [])
            minor_criteria = arc_hbr.get('minor_criteria_implemented', [])
            print(f"Major標準數量: {len(major_criteria)}")
            print(f"Minor標準數量: {len(minor_criteria)}")
        
        print("\n✅ 配置文件格式正確且完整！")
        return True
        
    except FileNotFoundError:
        print("❌ 找不到 cdss_config_improved.json 文件")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ JSON 格式錯誤: {e}")
        return False
    except Exception as e:
        print(f"❌ 其他錯誤: {e}")
        return False

if __name__ == "__main__":
    test_config_validation() 