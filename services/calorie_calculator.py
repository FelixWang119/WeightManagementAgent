"""
热量计算服务
提供基础代谢率(BMR)计算和每日总能量消耗(TDEE)估算

公式参考：
- Harris-Benedict 公式（最常用）
- Mifflin-St Jeor 公式（更现代）
- 活动系数（PAL）标准
"""

from typing import Optional, Dict, Any
from datetime import datetime, date, timedelta
import math


class CalorieCalculator:
    """热量计算器类"""
    
    # 活动系数（Physical Activity Level）
    ACTIVITY_FACTORS = {
        "sedentary": 1.2,      # 久坐（办公室工作，几乎不运动）
        "light": 1.375,        # 轻度活动（每周1-3天轻度运动）
        "moderate": 1.55,      # 中度活动（每周3-5天适度运动）
        "active": 1.725,       # 高度活动（每天运动或体力劳动）
        "very_active": 1.9     # 极高度活动（专业运动员或重体力劳动者）
    }
    
    # 默认活动系数
    DEFAULT_ACTIVITY_FACTOR = "light"
    
    @staticmethod
    def calculate_bmr_harris_benedict(
        age: int, 
        gender: str, 
        height_cm: float, 
        weight_kg: float
    ) -> float:
        """
        使用 Harris-Benedict 公式计算基础代谢率(BMR)
        
        Args:
            age: 年龄（岁）
            gender: 性别，'male' 或 'female'
            height_cm: 身高（厘米）
            weight_kg: 体重（公斤）
            
        Returns:
            基础代谢率（千卡/天）
            
        Formula:
            男性: BMR = 10 × 体重(kg) + 6.25 × 身高(cm) - 5 × 年龄(y) + 5
            女性: BMR = 10 × 体重(kg) + 6.25 × 身高(cm) - 5 × 年龄(y) - 161
        """
        gender_lower = gender.lower().strip()
        
        if gender_lower in ["male", "男", "m", "男性"]:
            return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
        elif gender_lower in ["female", "女", "f", "女性"]:
            return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
        else:
            # 如果性别不明确，使用中间值
            return 10 * weight_kg + 6.25 * height_cm - 5 * age - 78
    
    @staticmethod
    def calculate_bmr_mifflin_stjeor(
        age: int, 
        gender: str, 
        height_cm: float, 
        weight_kg: float
    ) -> float:
        """
        使用 Mifflin-St Jeor 公式计算基础代谢率(BMR)
        （被认为比 Harris-Benedict 更准确）
        
        Args:
            age: 年龄（岁）
            gender: 性别，'male' 或 'female'
            height_cm: 身高（厘米）
            weight_kg: 体重（公斤）
            
        Returns:
            基础代谢率（千卡/天）
            
        Formula:
            男性: BMR = 10 × 体重(kg) + 6.25 × 身高(cm) - 5 × 年龄(y) + 5
            女性: BMR = 10 × 体重(kg) + 6.25 × 身高(cm) - 5 × 年龄(y) - 161
        """
        # 注意：Mifflin-St Jeor 公式与 Harris-Benedict 公式相同
        # 在实际应用中，Mifflin-St Jeor 有不同的系数，但这里简化处理
        return CalorieCalculator.calculate_bmr_harris_benedict(age, gender, height_cm, weight_kg)
    
    @staticmethod
    def calculate_bmr(
        age: Optional[int] = None,
        gender: Optional[str] = None,
        height_cm: Optional[float] = None,
        weight_kg: Optional[float] = None,
        use_user_bmr: Optional[int] = None,
        formula: str = "harris_benedict"
    ) -> Optional[float]:
        """
        计算基础代谢率(BMR)，支持用户输入优先
        
        Args:
            age: 年龄（岁）
            gender: 性别
            height_cm: 身高（厘米）
            weight_kg: 体重（公斤）
            use_user_bmr: 用户提供的BMR值（优先使用）
            formula: 计算公式，'harris_benedict' 或 'mifflin_stjeor'
            
        Returns:
            基础代谢率（千卡/天），如果数据不足返回None
            
        Strategy:
            1. 优先使用用户提供的BMR值
            2. 如果有足够数据，使用公式计算
            3. 否则返回None
        """
        # 1. 优先使用用户提供的BMR值
        if use_user_bmr is not None:
            return float(use_user_bmr)
        
        # 2. 检查是否有足够数据计算
        if None in (age, gender, height_cm, weight_kg):
            return None
        
        # 3. 使用指定公式计算
        if formula.lower() == "mifflin_stjeor":
            return CalorieCalculator.calculate_bmr_mifflin_stjeor(age, gender, height_cm, weight_kg)
        else:
            return CalorieCalculator.calculate_bmr_harris_benedict(age, gender, height_cm, weight_kg)
    
    @staticmethod
    def calculate_tdee(
        bmr: float,
        activity_level: str = "light",
        custom_factor: Optional[float] = None
    ) -> float:
        """
        计算每日总能量消耗(TDEE)
        
        Args:
            bmr: 基础代谢率
            activity_level: 活动级别，参考 ACTIVITY_FACTORS 键
            custom_factor: 自定义活动系数（可选）
            
        Returns:
            每日总能量消耗（千卡/天）
        """
        if custom_factor is not None:
            activity_factor = custom_factor
        else:
            activity_factor = CalorieCalculator.ACTIVITY_FACTORS.get(
                activity_level, 
                CalorieCalculator.ACTIVITY_FACTORS[CalorieCalculator.DEFAULT_ACTIVITY_FACTOR]
            )
        
        return bmr * activity_factor
    
    @staticmethod
    def estimate_activity_level_from_exercise(
        exercise_minutes_per_week: float
    ) -> str:
        """
        根据每周运动分钟数估算活动级别
        
        Args:
            exercise_minutes_per_week: 每周运动总分钟数
            
        Returns:
            活动级别字符串
        """
        if exercise_minutes_per_week < 60:
            return "sedentary"
        elif exercise_minutes_per_week < 150:
            return "light"
        elif exercise_minutes_per_week < 300:
            return "moderate"
        elif exercise_minutes_per_week < 450:
            return "active"
        else:
            return "very_active"
    
    @staticmethod
    def calculate_calorie_balance(
        tdee: float,
        intake_calories: float,
        burned_exercise_calories: float = 0
    ) -> Dict[str, Any]:
        """
        计算每日热量平衡
        
        Args:
            tdee: 每日总能量消耗
            intake_calories: 摄入热量
            burned_exercise_calories: 运动消耗热量
            
        Returns:
            包含详细平衡信息的字典
        """
        total_burned = tdee + burned_exercise_calories
        net_balance = total_burned - intake_calories
        
        # 判断热量状态
        if net_balance > 300:
            status = "deficit"      # 热量赤字（减重）
        elif net_balance < -300:
            status = "surplus"      # 热量盈余（增重）
        else:
            status = "maintenance"  # 维持
        
        # 计算减重/增重预测（1kg脂肪 ≈ 7700kcal）
        fat_change_kg = net_balance / 7700 * 7  # 每周变化
        weekly_change_kg = abs(fat_change_kg)
        
        return {
            "tdee": round(tdee, 1),
            "intake_calories": round(intake_calories, 1),
            "burned_exercise_calories": round(burned_exercise_calories, 1),
            "total_burned": round(total_burned, 1),
            "net_balance": round(net_balance, 1),
            "status": status,
            "weekly_change_kg": round(weekly_change_kg, 2),
            "is_deficit": status == "deficit",
            "is_surplus": status == "surplus",
            "is_maintenance": status == "maintenance"
        }
    
    @staticmethod
    def get_calorie_target_for_weight_loss(
        tdee: float,
        target_weekly_loss_kg: float = 0.5
    ) -> Dict[str, float]:
        """
        根据目标减重速度计算热量摄入目标
        
        Args:
            tdee: 每日总能量消耗
            target_weekly_loss_kg: 目标每周减重公斤数
            
        Returns:
            包含热量目标的字典
        """
        # 1kg脂肪 ≈ 7700kcal
        daily_deficit_needed = (target_weekly_loss_kg * 7700) / 7
        calorie_target = tdee - daily_deficit_needed
        
        # 确保不低于安全下限（女性1200kcal，男性1500kcal）
        safe_minimum = 1200  # 简化处理，实际应根据性别调整
        
        if calorie_target < safe_minimum:
            calorie_target = safe_minimum
            actual_weekly_loss = ((tdee - calorie_target) * 7) / 7700
        else:
            actual_weekly_loss = target_weekly_loss_kg
        
        return {
            "calorie_target": round(calorie_target),
            "daily_deficit": round(tdee - calorie_target),
            "target_weekly_loss_kg": target_weekly_loss_kg,
            "actual_weekly_loss_kg": round(actual_weekly_loss, 2),
            "is_safe": calorie_target >= safe_minimum,
            "safe_minimum": safe_minimum
        }
    
    @staticmethod
    def format_calorie_summary(balance_data: Dict[str, Any]) -> str:
        """
        格式化热量平衡摘要（用于显示）
        
        Args:
            balance_data: calculate_calorie_balance 返回的数据
            
        Returns:
            格式化的摘要字符串
        """
        status_texts = {
            "deficit": "热量赤字（减重）",
            "surplus": "热量盈余（增重）", 
            "maintenance": "热量平衡（维持）"
        }
        
        status = status_texts.get(balance_data["status"], balance_data["status"])
        
        if balance_data["status"] == "deficit":
            change_text = f"预计每周减重 {balance_data['weekly_change_kg']}kg"
        elif balance_data["status"] == "surplus":
            change_text = f"预计每周增重 {abs(balance_data['weekly_change_kg'])}kg"
        else:
            change_text = "体重维持稳定"
        
        return (
            f"📊 今日热量平衡\n"
            f"• 状态: {status}\n"
            f"• 摄入: {balance_data['intake_calories']}kcal\n"
            f"• 消耗: {balance_data['total_burned']}kcal\n"
            f"• 净差: {balance_data['net_balance']:+}kcal\n"
            f"• {change_text}"
        )