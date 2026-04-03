"""
定时任务仓储
"""
from pathlib import Path
from typing import Optional, Dict, List

from .base_repository import BaseRepository
from ..models.entities import ScheduleTask


class ScheduleRepository(BaseRepository):
    """定时任务数据访问"""

    def __init__(self, data_path: Path):
        super().__init__(data_path, "schedule_tasks.json")

    async def get(self, group_umo: str) -> Optional[ScheduleTask]:
        """获取群组定时任务"""
        data = await self._load()
        task_data = data.get("tasks", {}).get(group_umo)
        if task_data:
            return ScheduleTask.from_dict(task_data)
        return None

    async def save(self, group_umo: str, task: ScheduleTask):
        """保存群组定时任务"""
        data = await self._load()
        if "tasks" not in data:
            data["tasks"] = {}
        data["tasks"][group_umo] = task.to_dict()
        await self._save(data)

    async def delete(self, group_umo: str) -> bool:
        """删除群组定时任务"""
        data = await self._load()
        tasks = data.get("tasks", {})
        if group_umo in tasks:
            del tasks[group_umo]
            await self._save(data)
            return True
        return False

    async def get_all(self) -> Dict[str, ScheduleTask]:
        """获取所有定时任务"""
        data = await self._load()
        tasks_data = data.get("tasks", {})
        return {k: ScheduleTask.from_dict(v) for k, v in tasks_data.items()}

    async def get_all_as_list(self) -> List[ScheduleTask]:
        """获取所有定时任务为列表"""
        tasks = await self.get_all()
        return list(tasks.values())
