"""定时任务管理器 - 电费查询插件

管理群聊的定时电费查询任务
"""

import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime, time, timedelta
from dataclasses import dataclass, field
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path


@dataclass
class ScheduleTask:
    """群聊的定时任务"""
    group_umo: str  # 群组统一消息来源
    group_name: str = ""  # 群组显示名称
    times: List[str] = field(default_factory=list)  # 时间列表，如 "8:00", "20:00"

    def to_dict(self) -> Dict:
        return {
            "group_umo": self.group_umo,
            "group_name": self.group_name,
            "times": self.times,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ScheduleTask":
        return cls(
            group_umo=data.get("group_umo", ""),
            group_name=data.get("group_name", ""),
            times=data.get("times", []),
        )


@dataclass
class ScheduleRegistry:
    """所有定时任务的注册表"""
    tasks: Dict[str, ScheduleTask] = field(default_factory=dict)  # group_umo -> ScheduleTask

    def to_dict(self) -> Dict:
        return {
            "tasks": {
                umo: task.to_dict()
                for umo, task in self.tasks.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ScheduleRegistry":
        tasks_data = data.get("tasks", {})
        return cls(
            tasks={
                umo: ScheduleTask.from_dict(task_data)
                for umo, task_data in tasks_data.items()
            }
        )

    def add_task(self, group_umo: str, group_name: str, times: List[str]) -> ScheduleTask:
        """添加或更新定时任务"""
        task = ScheduleTask(
            group_umo=group_umo,
            group_name=group_name,
            times=times,
        )
        self.tasks[group_umo] = task
        return task

    def get_task(self, group_umo: str) -> Optional[ScheduleTask]:
        """获取群组的任务"""
        return self.tasks.get(group_umo)

    def remove_task(self, group_umo: str) -> bool:
        """移除群组的任务"""
        if group_umo in self.tasks:
            del self.tasks[group_umo]
            return True
        return False

    def get_all_tasks(self) -> List[ScheduleTask]:
        """获取所有任务"""
        return list(self.tasks.values())


class ScheduleManager:
    """管理定时电费查询任务"""

    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        self._data_path: Optional[Path] = None
        self._registry: Optional[ScheduleRegistry] = None
        self._lock = asyncio.Lock()
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """初始化管理器并加载现有任务"""
        self._data_path = Path(get_astrbot_data_path()) / "plugin_data" / self.plugin_name
        self._data_path.mkdir(parents=True, exist_ok=True)

        await self._load_registry()
        logger.info(f"ScheduleManager 已初始化，包含 {len(self._registry.tasks)} 个任务")

    async def _load_registry(self):
        """从文件加载注册表"""
        registry_file = self._data_path / "schedule_tasks.json"

        async with self._lock:
            if registry_file.exists():
                try:
                    with open(registry_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self._registry = ScheduleRegistry.from_dict(data)
                    logger.info(f"已加载 {len(self._registry.tasks)} 个定时任务")
                except Exception as e:
                    logger.error(f"加载定时任务注册表失败: {e}")
                    self._registry = ScheduleRegistry()
            else:
                self._registry = ScheduleRegistry()

    async def _save_registry(self):
        """保存注册表到文件"""
        if not self._registry:
            return

        registry_file = self._data_path / "schedule_tasks.json"

        async with self._lock:
            try:
                with open(registry_file, 'w', encoding='utf-8') as f:
                    json.dump(self._registry.to_dict(), f, ensure_ascii=False, indent=2)
                logger.debug("定时任务注册表已保存")
            except Exception as e:
                logger.error(f"保存定时任务注册表失败: {e}")

    async def add_task(self, group_umo: str, group_name: str, times: List[str]) -> ScheduleTask:
        """为群组添加定时任务"""
        if not self._registry:
            await self._load_registry()

        task = self._registry.add_task(group_umo, group_name, times)
        await self._save_registry()
        logger.info(f"已为 {group_name} 添加定时任务: {times}")
        return task

    async def get_task(self, group_umo: str) -> Optional[ScheduleTask]:
        """获取群组的定时任务"""
        if not self._registry:
            await self._load_registry()

        return self._registry.get_task(group_umo)

    async def remove_task(self, group_umo: str) -> bool:
        """移除群组的定时任务"""
        if not self._registry:
            await self._load_registry()

        removed = self._registry.remove_task(group_umo)
        if removed:
            await self._save_registry()
            logger.info(f"已移除 {group_umo} 的定时任务")
        return removed

    async def get_all_tasks(self) -> List[ScheduleTask]:
        """获取所有定时任务"""
        if not self._registry:
            await self._load_registry()

        return self._registry.get_all_tasks()

    def parse_times(self, time_str: str) -> List[str]:
        """解析时间字符串如 '8:00,20:00' 为时间列表"""
        times = []
        for t in time_str.split(','):
            t = t.strip()
            # 验证时间格式
            try:
                # 支持格式: "8:00", "08:00", "8", "08"
                if ':' in t:
                    hour, minute = t.split(':')
                    hour = int(hour)
                    minute = int(minute)
                else:
                    hour = int(t)
                    minute = 0

                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    times.append(f"{hour:02d}:{minute:02d}")
            except ValueError:
                continue

        return times

    def start_scheduler(self, send_callback):
        """启动定时任务后台任务

        参数:
            send_callback: 发送消息的异步回调函数
                          签名: async def callback(group_umo: str, message: str)
        """
        if self._running:
            logger.warning("调度器已在运行")
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop(send_callback))
        logger.info("调度器已启动")

    def stop_scheduler(self):
        """停止定时任务后台任务"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            self._scheduler_task = None
        logger.info("调度器已停止")

    async def _scheduler_loop(self, send_callback):
        """定时任务主循环，检查并执行任务"""
        logger.info("调度器循环已启动")

        while self._running:
            try:
                now = datetime.now()
                current_time = now.strftime("%H:%M")
                current_minute = now.minute

                # 每分钟开始时检查
                tasks = await self.get_all_tasks()

                for task in tasks:
                    if current_time in task.times:
                        logger.info(f"在 {current_time} 执行 {task.group_name} 的定时任务")
                        try:
                            await send_callback(task.group_umo)
                        except Exception as e:
                            logger.error(f"发送定时消息到 {task.group_name} 失败: {e}")

                # 休眠到下一分钟
                next_minute = (now.replace(second=0, microsecond=0)
                              + timedelta(minutes=1))
                sleep_seconds = (next_minute - now).total_seconds()
                await asyncio.sleep(sleep_seconds)

            except asyncio.CancelledError:
                logger.info("调度器循环已取消")
                break
            except Exception as e:
                logger.error(f"调度器循环错误: {e}")
                await asyncio.sleep(60)  # 重试前等待