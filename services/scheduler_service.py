"""
定时任务服务
"""
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Optional, List

from ..models.entities import ScheduleTask
from ..repositories.schedule_repository import ScheduleRepository
from ..core.logger import log_service_call


class SchedulerService:
    """定时任务服务"""

    def __init__(self, repository: ScheduleRepository):
        self.repository = repository
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._callback: Optional[Callable] = None

    def start(self, callback: Callable[[str], None]):
        """启动调度器"""
        if self._running:
            return

        self._running = True
        self._callback = callback
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        log_service_call("SchedulerService", "start", True)

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            self._scheduler_task = None
        log_service_call("SchedulerService", "stop", True)

    async def _scheduler_loop(self):
        """调度器主循环"""
        while self._running:
            try:
                now = datetime.now()
                current_time = now.strftime("%H:%M")

                # 检查所有任务
                tasks = await self.repository.get_all_as_list()
                for task in tasks:
                    if current_time in task.times and self._callback:
                        try:
                            await self._callback(task.group_umo)
                        except Exception as e:
                            log_service_call("SchedulerService", "execute_task", False, str(e))

                # 休眠到下一分钟
                next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
                sleep_seconds = (next_minute - now).total_seconds()
                await asyncio.sleep(sleep_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log_service_call("SchedulerService", "loop", False, str(e))
                await asyncio.sleep(60)

    async def add_task(self, group_umo: str, group_name: str, times: List[str]) -> ScheduleTask:
        """添加任务"""
        task = ScheduleTask(group_umo=group_umo, group_name=group_name, times=times)
        await self.repository.save(group_umo, task)
        log_service_call("SchedulerService", "add_task", True)
        return task

    async def get_task(self, group_umo: str) -> Optional[ScheduleTask]:
        """获取任务"""
        return await self.repository.get(group_umo)

    async def remove_task(self, group_umo: str) -> bool:
        """删除任务"""
        result = await self.repository.delete(group_umo)
        log_service_call("SchedulerService", "remove_task", result)
        return result

    async def get_all_tasks(self) -> List[ScheduleTask]:
        """获取所有任务"""
        return await self.repository.get_all_as_list()

    @staticmethod
    def parse_times(time_str: str) -> List[str]:
        """解析时间字符串"""
        times = []
        for t in time_str.split(','):
            t = t.strip()
            try:
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

    @staticmethod
    def validate_time(time_str: str) -> bool:
        """验证时间格式"""
        try:
            parts = time_str.split(':')
            if len(parts) != 2:
                return False
            hour = int(parts[0])
            minute = int(parts[1])
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except ValueError:
            return False
