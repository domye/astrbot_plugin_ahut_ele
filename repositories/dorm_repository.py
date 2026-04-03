"""
宿舍配置仓储
"""
from pathlib import Path
from typing import Optional, Dict, List

from .base_repository import BaseRepository
from ..models.entities import DormConfig


class DormRepository(BaseRepository):
    """宿舍配置数据访问"""

    def __init__(self, data_path: Path):
        super().__init__(data_path, "dorm_registry.json")

    async def get(self, user_id: str) -> Optional[DormConfig]:
        """获取用户宿舍配置"""
        data = await self._load()
        dorm_data = data.get("dorms", {}).get(user_id)
        if dorm_data:
            return DormConfig.from_dict(dorm_data)
        return None

    async def save(self, user_id: str, dorm: DormConfig):
        """保存用户宿舍配置"""
        data = await self._load()
        if "dorms" not in data:
            data["dorms"] = {}
        data["dorms"][user_id] = dorm.to_dict()
        await self._save(data)

    async def delete(self, user_id: str) -> bool:
        """删除用户宿舍配置"""
        data = await self._load()
        dorms = data.get("dorms", {})
        if user_id in dorms:
            del dorms[user_id]
            await self._save(data)
            return True
        return False

    async def get_all(self) -> Dict[str, DormConfig]:
        """获取所有宿舍配置"""
        data = await self._load()
        dorms_data = data.get("dorms", {})
        return {k: DormConfig.from_dict(v) for k, v in dorms_data.items()}

    async def get_all_as_list(self) -> List[tuple]:
        """获取所有宿舍配置为列表"""
        dorms = await self.get_all()
        return list(dorms.items())

    async def count(self) -> int:
        """获取宿舍数量"""
        data = await self._load()
        return len(data.get("dorms", {}))
