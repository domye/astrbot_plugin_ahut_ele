"""宿舍配置管理器

管理用户宿舍配置用于电费查询
"""

import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, List
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from ..models import DormConfig, UserDormRegistry


class DormManager:
    """管理所有用户的宿舍配置"""

    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        self._data_path: Optional[Path] = None
        self._registry: Optional[UserDormRegistry] = None
        self._lock = asyncio.Lock()

    async def initialize(self):
        """初始化管理器并加载现有数据"""
        self._data_path = Path(get_astrbot_data_path()) / "plugin_data" / self.plugin_name
        self._data_path.mkdir(parents=True, exist_ok=True)

        await self._load_registry()

    async def _load_registry(self):
        """从文件加载注册表"""
        registry_file = self._data_path / "dorm_registry.json"

        async with self._lock:
            if registry_file.exists():
                try:
                    with open(registry_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self._registry = UserDormRegistry.from_dict(data)
                    logger.info(f"已加载 {len(self._registry.dorms)} 个宿舍配置")
                except Exception as e:
                    logger.error(f"加载宿舍注册表失败: {e}")
                    self._registry = UserDormRegistry()
            else:
                self._registry = UserDormRegistry()

    async def _save_registry(self):
        """保存注册表到文件"""
        if not self._registry:
            return

        registry_file = self._data_path / "dorm_registry.json"

        async with self._lock:
            try:
                with open(registry_file, 'w', encoding='utf-8') as f:
                    json.dump(self._registry.to_dict(), f, ensure_ascii=False, indent=2)
                logger.debug("宿舍注册表已保存")
            except Exception as e:
                logger.error(f"保存宿舍注册表失败: {e}")

    async def set_dorm(self, sender_id: str, dorm: DormConfig) -> bool:
        """
        设置用户的宿舍配置

        返回: 成功返回 True
        """
        if not self._registry:
            await self._load_registry()

        self._registry.set_dorm(sender_id, dorm)
        await self._save_registry()
        logger.info(f"已为 {sender_id} 设置宿舍: {dorm.get_display_name()}")
        return True

    async def get_dorm(self, sender_id: str) -> Optional[DormConfig]:
        """获取用户的宿舍配置"""
        if not self._registry:
            await self._load_registry()

        return self._registry.get_dorm(sender_id)

    async def remove_dorm(self, sender_id: str) -> bool:
        """
        移除用户的宿舍配置

        返回: 已移除返回 True，未找到返回 False
        """
        if not self._registry:
            await self._load_registry()

        removed = self._registry.remove_dorm(sender_id)
        if removed:
            await self._save_registry()
            logger.info(f"已移除 {sender_id} 的宿舍")
        return removed

    async def get_all_dorms(self) -> List[tuple]:
        """获取所有宿舍配置，返回 (sender_id, DormConfig) 元组列表"""
        if not self._registry:
            await self._load_registry()

        return self._registry.get_all_dorms()

    async def get_dorm_count(self) -> int:
        """获取已注册宿舍的数量"""
        if not self._registry:
            await self._load_registry()

        return len(self._registry.dorms)