#!/usr/bin/env python3
"""
事件规则验证工具
用于验证YAML配置文件的正确性和完整性
"""

import yaml
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple


def validate_event_rules(config_file: str = "config/event_rules.yaml") -> Tuple[bool, List[str]]:
    """验证事件规则配置文件"""
    errors = []
    
    try:
        # 加载配置文件
        with open(config_file, 'r', encoding='utf-8') as f:
            rules = yaml.safe_load(f)
        
        if not rules:
            errors.append("配置文件为空或格式错误")
            return False, errors
        
        # 验证全局配置
        errors.extend(validate_global_config(rules.get('global', {})))
        
        # 验证事件类型定义
        errors.extend(validate_event_types(rules.get('event_types', {})))
        
        # 验证识别规则
        errors.extend(validate_recognition_rules(rules.get('recognition_rules', {})))
        
        # 验证冲突规则
        errors.extend(validate_conflict_rules(rules.get('conflict_rules', {})))
        
        # 验证时间模式
        errors.extend(validate_time_patterns(rules.get('time_patterns', {})))
        
        # 验证规则引用一致性
        errors.extend(validate_rule_consistency(rules))
        
        return len(errors) == 0, errors
        
    except Exception as e:
        errors.append(f"配置文件加载失败: {e}")
        return False, errors


def validate_global_config(global_config: Dict[str, Any]) -> List[str]:
    """验证全局配置"""
    errors = []
    
    # 检查必需字段
    required_fields = ['confidence_threshold']
    for field in required_fields:
        if field not in global_config:
            errors.append(f"全局配置缺少必需字段: {field}")
    
    # 验证置信度阈值
    threshold = global_config.get('confidence_threshold')
    if threshold is not None:
        if not isinstance(threshold, (int, float)) or not (0 <= threshold <= 1):
            errors.append("置信度阈值必须在0-1之间")
    
    # 验证LLM配置
    llm_config = global_config.get('llm_fallback', {})
    if llm_config.get('enabled', False):
        llm_threshold = llm_config.get('threshold')
        if llm_threshold is not None and not (0 <= llm_threshold <= 1):
            errors.append("LLM阈值必须在0-1之间")
    
    return errors


def validate_event_types(event_types: Dict[str, Dict[str, Any]]) -> List[str]:
    """验证事件类型定义"""
    errors = []
    
    if not event_types:
        errors.append("事件类型定义不能为空")
        return errors
    
    required_fields = ['name', 'category', 'description']
    valid_categories = ['work_related', 'health_related', 'personal', 'social', 'special']
    
    for event_type, config in event_types.items():
        # 检查必需字段
        for field in required_fields:
            if field not in config:
                errors.append(f"事件类型 '{event_type}' 缺少必需字段: {field}")
        
        # 验证分类
        category = config.get('category')
        if category and category not in valid_categories:
            errors.append(f"事件类型 '{event_type}' 的分类 '{category}' 无效，有效值: {valid_categories}")
        
        # 验证影响等级
        impact_level = config.get('impact_level')
        if impact_level is not None and (not isinstance(impact_level, int) or not (1 <= impact_level <= 5)):
            errors.append(f"事件类型 '{event_type}' 的影响等级必须在1-5之间")
        
        # 验证优先级
        priority = config.get('priority')
        if priority is not None and (not isinstance(priority, int) or priority < 0):
            errors.append(f"事件类型 '{event_type}' 的优先级必须是非负整数")
    
    return errors


def validate_recognition_rules(recognition_rules: Dict[str, Dict[str, Any]]) -> List[str]:
    """验证识别规则"""
    errors = []
    
    if not recognition_rules:
        errors.append("识别规则不能为空")
        return errors
    
    for event_type, rules in recognition_rules.items():
        # 验证关键词列表
        keyword_fields = ['exact_keywords', 'variant_keywords', 'semantic_keywords']
        for field in keyword_fields:
            keywords = rules.get(field, [])
            if not isinstance(keywords, list):
                errors.append(f"事件类型 '{event_type}' 的 {field} 必须是列表")
            elif keywords:
                for keyword in keywords:
                    if not isinstance(keyword, str):
                        errors.append(f"事件类型 '{event_type}' 的 {field} 包含非字符串元素")
        
        # 验证正则模式
        patterns = rules.get('patterns', [])
        if not isinstance(patterns, list):
            errors.append(f"事件类型 '{event_type}' 的 patterns 必须是列表")
        elif patterns:
            for pattern in patterns:
                if not isinstance(pattern, str):
                    errors.append(f"事件类型 '{event_type}' 的 patterns 包含非字符串元素")
                else:
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        errors.append(f"事件类型 '{event_type}' 的正则表达式错误 '{pattern}': {e}")
        
        # 验证权重配置
        weights = rules.get('weights', {})
        if weights:
            valid_weight_fields = ['exact_keywords', 'variant_keywords', 'patterns', 'semantic_keywords']
            for field, weight in weights.items():
                if field not in valid_weight_fields:
                    errors.append(f"事件类型 '{event_type}' 的权重字段 '{field}' 无效，有效值: {valid_weight_fields}")
                elif not isinstance(weight, (int, float)) or not (0 <= weight <= 1):
                    errors.append(f"事件类型 '{event_type}' 的权重 '{field}' 必须在0-1之间")
    
    return errors


def validate_conflict_rules(conflict_rules: Dict[str, Dict[str, Any]]) -> List[str]:
    """验证冲突规则"""
    errors = []
    
    if not conflict_rules:
        errors.append("冲突规则不能为空")
        return errors
    
    valid_plan_types = ['exercise', 'diet', 'weight', 'sleep']
    
    for plan_type, rules in conflict_rules.items():
        if plan_type not in valid_plan_types:
            errors.append(f"冲突规则的计划类型 '{plan_type}' 无效，有效值: {valid_plan_types}")
        
        conflicting_events = rules.get('conflicting_events', [])
        if not isinstance(conflicting_events, list):
            errors.append(f"计划类型 '{plan_type}' 的 conflicting_events 必须是列表")
        elif conflicting_events:
            for event_type in conflicting_events:
                if not isinstance(event_type, str):
                    errors.append(f"计划类型 '{plan_type}' 的 conflicting_events 包含非字符串元素")
    
    return errors


def validate_time_patterns(time_patterns: Dict[str, str]) -> List[str]:
    """验证时间模式"""
    errors = []
    
    required_patterns = ['today', 'tonight', 'tomorrow', 'specific_time']
    
    for pattern_name in required_patterns:
        if pattern_name not in time_patterns:
            errors.append(f"时间模式缺少必需字段: {pattern_name}")
    
    for pattern_name, pattern in time_patterns.items():
        if not isinstance(pattern, str):
            errors.append(f"时间模式 '{pattern_name}' 必须是字符串")
        else:
            try:
                re.compile(pattern)
            except re.error as e:
                errors.append(f"时间模式 '{pattern_name}' 的正则表达式错误: {e}")
    
    return errors


def validate_rule_consistency(rules: Dict[str, Any]) -> List[str]:
    """验证规则一致性"""
    errors = []
    
    # 获取所有事件类型
    event_types = set(rules.get('event_types', {}).keys())
    recognition_rules = set(rules.get('recognition_rules', {}).keys())
    
    # 检查识别规则是否都有对应的事件类型定义
    missing_event_types = recognition_rules - event_types
    if missing_event_types:
        errors.append(f"识别规则对应的事件类型未定义: {sorted(missing_event_types)}")
    
    # 检查冲突规则中的事件类型是否都存在
    conflict_rules = rules.get('conflict_rules', {})
    for plan_type, rules in conflict_rules.items():
        conflicting_events = rules.get('conflicting_events', [])
        for event_type in conflicting_events:
            if event_type not in event_types:
                errors.append(f"冲突规则 '{plan_type}' 中的事件类型 '{event_type}' 未定义")
    
    return errors


def validate_rule_file_structure(config_file: str = "config/event_rules.yaml") -> Tuple[bool, List[str]]:
    """验证规则文件结构完整性"""
    errors = []
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            rules = yaml.safe_load(f)
        
        # 检查必需顶级字段
        required_sections = ['global', 'event_types', 'recognition_rules', 'conflict_rules', 'time_patterns']
        for section in required_sections:
            if section not in rules:
                errors.append(f"配置文件缺少必需章节: {section}")
        
        # 检查事件类型和识别规则的对应关系
        if 'event_types' in rules and 'recognition_rules' in rules:
            event_types = set(rules['event_types'].keys())
            recognition_rules = set(rules['recognition_rules'].keys())
            
            # 建议每个事件类型都有对应的识别规则
            missing_rules = event_types - recognition_rules
            if missing_rules:
                errors.append(f"以下事件类型缺少识别规则: {sorted(missing_rules)}")
        
        return len(errors) == 0, errors
        
    except Exception as e:
        errors.append(f"文件结构验证失败: {e}")
        return False, errors


def generate_validation_report(config_file: str = "config/event_rules.yaml") -> Dict[str, Any]:
    """生成详细的验证报告"""
    report = {
        'config_file': config_file,
        'file_exists': Path(config_file).exists(),
        'validation_passed': False,
        'errors': [],
        'warnings': [],
        'statistics': {}
    }
    
    if not report['file_exists']:
        report['errors'].append("配置文件不存在")
        return report
    
    # 验证规则文件结构
    structure_valid, structure_errors = validate_rule_file_structure(config_file)
    report['errors'].extend(structure_errors)
    
    # 验证详细规则内容
    rules_valid, rules_errors = validate_event_rules(config_file)
    report['errors'].extend(rules_errors)
    
    # 加载规则统计信息
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            rules = yaml.safe_load(f)
        
        report['statistics'] = {
            'event_types_count': len(rules.get('event_types', {})),
            'recognition_rules_count': len(rules.get('recognition_rules', {})),
            'conflict_rules_count': len(rules.get('conflict_rules', {})),
            'time_patterns_count': len(rules.get('time_patterns', {})),
            'total_keywords': sum(len(rules.get('recognition_rules', {}).get(event_type, {}).get('exact_keywords', [])) 
                                for event_type in rules.get('recognition_rules', {})),
            'total_patterns': sum(len(rules.get('recognition_rules', {}).get(event_type, {}).get('patterns', [])) 
                                for event_type in rules.get('recognition_rules', {}))
        }
    except Exception as e:
        report['errors'].append(f"统计信息生成失败: {e}")
    
    report['validation_passed'] = len(report['errors']) == 0
    
    return report


def main():
    """主函数"""
    config_file = "config/event_rules.yaml"
    
    print("=" * 60)
    print("事件规则配置文件验证工具")
    print("=" * 60)
    
    # 生成验证报告
    report = generate_validation_report(config_file)
    
    print(f"配置文件: {report['config_file']}")
    print(f"文件存在: {'✅' if report['file_exists'] else '❌'}")
    
    if not report['file_exists']:
        print("\n❌ 配置文件不存在，请检查路径")
        sys.exit(1)
    
    # 显示统计信息
    print("\n📊 配置统计:")
    for key, value in report['statistics'].items():
        print(f"  {key.replace('_', ' ').title()}: {value}")
    
    # 显示验证结果
    print(f"\n{'✅' if report['validation_passed'] else '❌'} 验证结果:")
    
    if report['validation_passed']:
        print("🎉 配置文件验证通过！")
    else:
        print("❌ 配置文件存在错误:")
        for error in report['errors']:
            print(f"  - {error}")
    
    # 显示警告信息
    if report['warnings']:
        print("\n⚠️ 警告信息:")
        for warning in report['warnings']:
            print(f"  - {warning}")
    
    print("\n" + "=" * 60)
    
    # 退出码
    sys.exit(0 if report['validation_passed'] else 1)


if __name__ == "__main__":
    main()