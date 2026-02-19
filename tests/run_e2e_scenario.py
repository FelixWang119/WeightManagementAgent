#!/usr/bin/env python3
"""
E2E场景测试运行入口

运行示例:
    # 运行30天减重场景
    python tests/run_e2e_scenario.py --scenario weight_loss --days 30
    
    # 运行连续打卡场景
    python tests/run_e2e_scenario.py --scenario exercise_streak --days 21
    
    # 运行习惯养成场景
    python tests/run_e2e_scenario.py --scenario habit --habit-type morning_exercise
    
    # 使用FastAPI TestClient运行（无需启动服务器）
    python tests/run_e2e_scenario.py --scenario weight_loss --use-test-client
    
    # 批量运行所有场景
    python tests/run_e2e_scenario.py --run-all

支持的场景:
    - weight_loss: 30天减重旅程
    - exercise_streak: 连续运动打卡
    - habit: 习惯养成
    - plateau: 平台期突破
    - mixed: 混合日常
"""

import argparse
import asyncio
import sys
from pathlib import Path
from datetime import date, timedelta

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.e2e import E2ETestEngine
from tests.e2e.scenarios import (
    WeightLossJourneyScenario,
    ExerciseStreakScenario,
    HabitFormationScenario,
    MixedRoutineScenario,
)
from tests.e2e.scenarios.weight_loss_journey import PlateauBreakScenario


async def run_weight_loss_scenario(engine, args) -> None:
    """运行减重场景"""
    scenario = WeightLossJourneyScenario(
        days=args.days,
        start_weight=args.start_weight,
        target_weight=args.target_weight,
        start_date=args.start_date,
        user_code=args.user_code,
        seed=args.seed
    )
    result = await engine.run_scenario(scenario)
    
    if args.save_report:
        engine.save_report(result, output_dir=args.output_dir)
    
    return result


async def run_exercise_streak_scenario(engine, args) -> None:
    """运行连续打卡场景"""
    scenario = ExerciseStreakScenario(
        days=args.days,
        streak_target=args.streak_target,
        interrupt_day=args.interrupt_day,
        exercise_duration=args.duration,
        start_date=args.start_date,
        user_code=args.user_code,
        seed=args.seed
    )
    result = await engine.run_scenario(scenario)
    
    if args.save_report:
        engine.save_report(result, output_dir=args.output_dir)
    
    return result


async def run_habit_scenario(engine, args) -> None:
    """运行习惯养成场景"""
    scenario = HabitFormationScenario(
        days=args.days,
        habit_type=args.habit_type,
        start_date=args.start_date,
        user_code=args.user_code
    )
    result = await engine.run_scenario(scenario)
    
    if args.save_report:
        engine.save_report(result, output_dir=args.output_dir)
    
    return result


async def run_plateau_scenario(engine, args) -> None:
    """运行平台期突破场景"""
    scenario = PlateauBreakScenario(
        days=args.days,
        start_weight=args.start_weight,
        plateau_days=args.plateau_days,
        start_date=args.start_date,
        user_code=args.user_code
    )
    result = await engine.run_scenario(scenario)
    
    if args.save_report:
        engine.save_report(result, output_dir=args.output_dir)
    
    return result


async def run_mixed_scenario(engine, args) -> None:
    """运行混合日常场景"""
    weeks = args.days // 7
    scenario = MixedRoutineScenario(
        weeks=weeks,
        start_date=args.start_date,
        user_code=args.user_code
    )
    result = await engine.run_scenario(scenario)
    
    if args.save_report:
        engine.save_report(result, output_dir=args.output_dir)
    
    return result


async def run_all_scenarios(engine, args) -> list:
    """批量运行所有场景"""
    scenarios = [
        ("减重旅程", WeightLossJourneyScenario(days=14, user_code="weight_loss_test")),
        ("连续打卡", ExerciseStreakScenario(days=14, streak_target=10, user_code="streak_test")),
        ("习惯养成", HabitFormationScenario(days=14, habit_type="water_drinking", user_code="habit_test")),
        ("平台期突破", PlateauBreakScenario(days=21, plateau_days=7, user_code="plateau_test")),
    ]
    
    results = []
    for name, scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"🚀 运行场景: {name}")
        print('='*60)
        result = await engine.run_scenario(scenario)
        results.append((name, result))
        
        if args.save_report:
            engine.save_report(result, output_dir=args.output_dir, 
                             filename=f"e2e_{scenario.name}_{date.today().strftime('%Y%m%d')}.json")
    
    # 打印汇总
    print("\n" + "="*60)
    print("📊 所有场景运行完成")
    print("="*60)
    for name, result in results:
        status = "✅" if result.status.value == "success" else "❌"
        print(f"{status} {name}: {result.success_actions}/{result.total_actions} ({result.success_rate*100:.1f}%)")
    
    return results


def parse_date(date_str: str) -> date:
    """解析日期字符串"""
    if date_str.lower() == "today":
        return date.today()
    return date.fromisoformat(date_str)


def main():
    parser = argparse.ArgumentParser(
        description="E2E场景测试运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行30天减重场景
  python tests/run_e2e_scenario.py --scenario weight_loss --days 30
  
  # 运行14天连续打卡，第7天中断
  python tests/run_e2e_scenario.py --scenario exercise_streak --days 14 --interrupt-day 7
  
  # 使用TestClient运行（无需启动服务器）
  python tests/run_e2e_scenario.py --scenario weight_loss --use-test-client
  
  # 批量运行所有场景
  python tests/run_e2e_scenario.py --run-all
        """
    )
    
    # 场景选择
    parser.add_argument(
        "--scenario",
        choices=["weight_loss", "exercise_streak", "habit", "plateau", "mixed"],
        default="weight_loss",
        help="选择要运行的场景"
    )
    
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="批量运行所有场景"
    )
    
    # 通用参数
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="场景天数（默认30）"
    )
    
    parser.add_argument(
        "--start-date",
        type=parse_date,
        default=None,
        help="开始日期（YYYY-MM-DD或today）"
    )
    
    parser.add_argument(
        "--user-code",
        default="e2e_test_user",
        help="测试用户code"
    )
    
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子（默认42）"
    )
    
    # 连接参数
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API基础URL"
    )
    
    parser.add_argument(
        "--use-test-client",
        action="store_true",
        help="使用FastAPI TestClient（无需启动服务器）"
    )
    
    # 减重场景参数
    parser.add_argument(
        "--start-weight",
        type=float,
        default=72.0,
        help="起始体重（默认72.0）"
    )
    
    parser.add_argument(
        "--target-weight",
        type=float,
        default=67.0,
        help="目标体重（默认67.0）"
    )
    
    # 连续打卡参数
    parser.add_argument(
        "--streak-target",
        type=int,
        default=14,
        help="连续打卡目标天数"
    )
    
    parser.add_argument(
        "--interrupt-day",
        type=int,
        default=None,
        help="中断日索引（可选）"
    )
    
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="每次运动时长（分钟）"
    )
    
    # 习惯养成参数
    parser.add_argument(
        "--habit-type",
        choices=["morning_exercise", "healthy_breakfast", "water_drinking", "early_sleep"],
        default="morning_exercise",
        help="习惯类型"
    )
    
    # 平台期参数
    parser.add_argument(
        "--plateau-days",
        type=int,
        default=10,
        help="平台期天数"
    )
    
    # 输出参数
    parser.add_argument(
        "--save-report",
        action="store_true",
        default=True,
        help="保存测试报告"
    )
    
    parser.add_argument(
        "--output-dir",
        default="test_reports/e2e",
        help="报告输出目录"
    )
    
    args = parser.parse_args()
    
    # 设置默认开始日期
    if args.start_date is None:
        args.start_date = date.today() - timedelta(days=args.days)
    
    # 创建引擎
    if args.use_test_client:
        try:
            from main import app
            engine = E2ETestEngine(use_test_client=True, app=app)
        except ImportError:
            print("❌ 无法导入FastAPI应用，请确保在正确的目录下运行")
            sys.exit(1)
    else:
        engine = E2ETestEngine(base_url=args.base_url)
    
    # 运行场景
    async def run():
        async with engine:
            if args.run_all:
                results = await run_all_scenarios(engine, args)
                # 如果有失败的场景，返回非0退出码
                failed = sum(1 for _, r in results if r.status.value != "success")
                return 1 if failed > 0 else 0
            else:
                scenario_map = {
                    "weight_loss": run_weight_loss_scenario,
                    "exercise_streak": run_exercise_streak_scenario,
                    "habit": run_habit_scenario,
                    "plateau": run_plateau_scenario,
                    "mixed": run_mixed_scenario,
                }
                
                runner = scenario_map.get(args.scenario)
                if runner:
                    result = await runner(engine, args)
                    return 0 if result.status.value == "success" else 1
                else:
                    print(f"❌ 未知场景: {args.scenario}")
                    return 1
    
    try:
        exit_code = asyncio.run(run())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ 测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 测试运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
