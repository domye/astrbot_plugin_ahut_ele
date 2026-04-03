"""
凭证仓储
"""
from pathlib import Path
from typing import Optional

from .base_repository import BaseRepository
from ..models.entities import PayCredentials


class CredentialRepository(BaseRepository):
    """凭证数据访问"""

    def __init__(self, data_path: Path):
        super().__init__(data_path, "credentials.json")

    async def get(self, key: str = "default") -> Optional[PayCredentials]:
        """获取凭证"""
        data = await self._load()
        creds_data = data.get(key)
        if creds_data:
            return PayCredentials.from_dict(creds_data)
        return None

    async def save(self, key: str, value: PayCredentials):
        """保存凭证"""
        data = await self._load()
        data[key] = value.to_dict()
        await self._save(data)

    async def delete(self, key: str = "default") -> bool:
        """删除凭证"""
        data = await self._load()
        if key in data:
            del data[key]
            await self._save(data)
            return True
        return False

    async def get_all(self):
        """获取所有凭证（凭证通常只有一个）"""
        data = await self._load()
        return {k: PayCredentials.from_dict(v) for k, v in data.items()}

    async def exists(self, key: str = "default") -> bool:
        """检查凭证是否存在"""
        data = await self._load()
        return key in data and data[key].get("username")
