#!/usr/bin/env python3
"""
Simple Agent 部署脚本

自动化部署 Simple Agent 到生产环境
"""

import os
import sys
import subprocess
import time
from datetime import datetime
import json
import asyncio

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.langchain.monitoring import get_agent_monitor


class DeploymentManager:
    """部署管理器"""

    def __init__(self):
        self.start_time = datetime.now()
        self.deployment_log = []
        self.success = True

    def log(self, message: str, level: str = "INFO"):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.deployment_log.append(log_entry)
        print(log_entry)

    def run_command(self, command: str, description: str = "") -> bool:
        """运行命令"""
        if description:
            self.log(f"执行: {description}")

        try:
            self.log(f"命令: {command}")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
            )

            if result.returncode == 0:
                self.log(f"成功: {description}")
                if result.stdout:
                    self.log(f"输出: {result.stdout[:200]}...")
                return True
            else:
                self.log(f"失败: {description}", "ERROR")
                self.log(f"错误输出: {result.stderr}", "ERROR")
                return False

        except subprocess.TimeoutExpired:
            self.log(f"超时: {description}", "ERROR")
            return False
        except Exception as e:
            self.log(f"异常: {description} - {e}", "ERROR")
            return False

    async def check_agent_health(self) -> bool:
        """检查 Agent 健康状态"""
        self.log("检查 Agent 健康状态...")

        try:
            from services.langchain.agent_simple import SimpleWeightAgent
            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
            from sqlalchemy.orm import sessionmaker
            from models.database import Base

            # 创建内存数据库测试
            engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            async_session = sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )

            async with async_session() as db:
                # 测试 Agent 创建
                agent = await SimpleWeightAgent.create(user_id=999, db=db)

                # 测试基本聊天
                result = await agent.chat("你好")
                if "response" not in result:
                    self.log("Agent 响应格式错误", "ERROR")
                    return False

                # 测试工具调用
                result = await agent.chat("体重65kg")
                if "response" not in result:
                    self.log("工具调用响应格式错误", "ERROR")
                    return False

                self.log("Agent 健康检查通过")
                return True

        except Exception as e:
            self.log(f"Agent 健康检查失败: {e}", "ERROR")
            return False

    def check_environment(self) -> bool:
        """检查环境变量"""
        self.log("检查环境变量...")

        required_vars = ["AGENT_VERSION"]
        missing_vars = []

        for var in required_vars:
            if var not in os.environ:
                missing_vars.append(var)

        if missing_vars:
            self.log(f"缺少环境变量: {missing_vars}", "ERROR")
            return False

        agent_version = os.environ.get("AGENT_VERSION", "").lower()
        if agent_version != "simple":
            self.log(
                f"AGENT_VERSION 应为 'simple', 当前为 '{agent_version}'", "WARNING"
            )
            # 这不是致命错误，但记录警告

        self.log(f"环境变量检查通过: AGENT_VERSION={agent_version}")
        return True

    def backup_configuration(self) -> bool:
        """备份当前配置"""
        self.log("备份当前配置...")

        backup_dir = "backups"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 创建备份目录
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # 备份 .env 文件
        env_file = ".env"
        if os.path.exists(env_file):
            backup_file = os.path.join(backup_dir, f"env_backup_{timestamp}")
            if self.run_command(f"cp {env_file} {backup_file}", f"备份 {env_file}"):
                self.log(f"配置备份到: {backup_file}")
                return True
            else:
                return False
        else:
            self.log(f"未找到 {env_file} 文件", "WARNING")
            return True  # 不是致命错误

    def update_configuration(self) -> bool:
        """更新配置"""
        self.log("更新配置...")

        env_file = ".env"
        agent_config = "AGENT_VERSION=simple"

        # 检查是否已配置
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                content = f.read()

            if "AGENT_VERSION=" in content:
                # 更新现有配置
                lines = content.split("\n")
                updated_lines = []
                for line in lines:
                    if line.startswith("AGENT_VERSION="):
                        updated_lines.append(agent_config)
                    else:
                        updated_lines.append(line)

                new_content = "\n".join(updated_lines)
            else:
                # 添加新配置
                new_content = content + f"\n{agent_config}\n"

            with open(env_file, "w") as f:
                f.write(new_content)

            self.log(f"更新 {env_file}: {agent_config}")
        else:
            # 创建新文件
            with open(env_file, "w") as f:
                f.write(f"{agent_config}\n")
            self.log(f"创建 {env_file}: {agent_config}")

        return True

    def save_deployment_report(self):
        """保存部署报告"""
        report = {
            "deployment_time": self.start_time.isoformat(),
            "completion_time": datetime.now().isoformat(),
            "success": self.success,
            "log": self.deployment_log,
            "summary": {
                "agent_version": "simple",
                "environment": os.environ.get("AGENT_VERSION", "unknown"),
                "python_version": sys.version,
            },
        }

        report_dir = "deployment_reports"
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(report_dir, f"deployment_{timestamp}.json")

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.log(f"部署报告保存到: {report_file}")
        return report_file

    async def run_deployment(self):
        """运行部署流程"""
        self.log("=" * 60)
        self.log("开始 Simple Agent 部署")
        self.log("=" * 60)

        # 阶段 1: 预部署检查
        self.log("\n阶段 1: 预部署检查")
        self.log("-" * 40)

        if not self.check_environment():
            self.success = False
            return

        # 阶段 2: 备份和配置
        self.log("\n阶段 2: 备份和配置")
        self.log("-" * 40)

        if not self.backup_configuration():
            self.success = False
            return

        if not self.update_configuration():
            self.success = False
            return

        # 阶段 3: 健康检查
        self.log("\n阶段 3: 健康检查")
        self.log("-" * 40)

        if not await self.check_agent_health():
            self.success = False
            return

        # 阶段 4: 完成
        self.log("\n阶段 4: 完成")
        self.log("-" * 40)

        if self.success:
            self.log("✅ 部署成功完成!")
            self.log("\n下一步:")
            self.log("1. 重启你的服务以应用新配置")
            self.log("2. 运行监控检查: python scripts/check_monitoring.py")
            self.log("3. 验证生产环境功能")
        else:
            self.log("❌ 部署失败!")
            self.log("\n请检查以上错误并修复后重试")

        # 保存报告
        report_file = self.save_deployment_report()

        self.log("\n" + "=" * 60)
        self.log(f"部署完成: {'成功' if self.success else '失败'}")
        self.log(f"详细报告: {report_file}")
        self.log("=" * 60)


async def main():
    """主函数"""
    manager = DeploymentManager()

    try:
        await manager.run_deployment()
    except KeyboardInterrupt:
        manager.log("部署被用户中断", "WARNING")
        manager.success = False
    except Exception as e:
        manager.log(f"部署过程中发生未预期错误: {e}", "ERROR")
        manager.success = False

    # 退出码
    sys.exit(0 if manager.success else 1)


if __name__ == "__main__":
    asyncio.run(main())
