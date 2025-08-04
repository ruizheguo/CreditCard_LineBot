# safe_utils.py
import json
import re

def safe_json_parse(content):
    try:
        match = re.search(r"\[[^\]]+\]", content)
        return json.loads(match.group()) if match else []
    except json.JSONDecodeError:
        return []

def calculate_total_score(basic_pt, bonus_pt, type_, ai_score, diver, cooper,
                          penalty_weight=0.25, diversity_weight=0.15):
    # 检查所有输入值是否为None或非数值
    if ai_score is None or basic_pt is None or bonus_pt is None or type_ is None or diver is None or cooper is None:
        return None
        
    # 尝试将所有输入转换为浮点数
    try:
        basic_pt = float(basic_pt) if basic_pt != '' else 0.0
        bonus_pt = float(bonus_pt) if bonus_pt != '' else 0.0
        type_ = float(type_) if type_ != '' else 0.0
        ai_score = float(ai_score) if ai_score != '' else 0.0
        diver = float(diver) if diver != '' else 0.0
        cooper = float(cooper) if cooper != '' else 0.0
    except (ValueError, TypeError):
        return None
        
    # 计算总分
    return (basic_pt + bonus_pt) - penalty_weight * (type_ + ai_score) + diversity_weight * (diver + cooper)

def calculate_total_score_mc(basic_pt,bonus_pt, type_, ai_score,
                          penalty_weight=0.25):
    # 检查所有输入值是否为None或非数值
    if ai_score is None or basic_pt is None or bonus_pt is None or type_ is None:
        return None
        
    # 尝试将所有输入转换为浮点数
    try:
        basic_pt = float(basic_pt) if basic_pt != '' else 0.0
        bonus_pt = float(bonus_pt) if bonus_pt != '' else 0.0
        type_ = float(type_) if type_ != '' else 0.0
        ai_score = float(ai_score) if ai_score != '' else 0.0
    except (ValueError, TypeError):
        return None
        
    # 计算总分
    return (basic_pt +bonus_pt) - penalty_weight * (type_ + ai_score)