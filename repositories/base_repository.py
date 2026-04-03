"""
仓储基类
"""
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from ..core.exceptions import RepositoryException
from ..core.logger import log_service_call


class BaseRepository(ABC):
    """仓储基类"""

    def __init__(self, data_path: Path, filename: str):
        self.data_path = data_path
        self.file_path = data_path / filename
        self._lock = asyncio.Lock()
        self._cache: Optional[Dict] = None

    async def _ensure_file(self):
        """确保文件存在"""
        self.data_path.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text(json.dumps({}), encoding='utf-8')

    async def _load(self) -> Dict:
        """加载数据"""
        await self._ensure_file()
        try:
            async with self._lock:
                content = self.file_path.read_text(encoding='utf-8')
                return json.loads(content)
        except json.JSONDecodeError as e:
            log_service_call(self.__class__.__name__, "_load", False, f"JSON decode error: {e}")
            return {}
        except Exception as e:
            log_service_call(self.__class__.__name__, "_load", False, str(e))
            raise RepositoryException(f"Failed to load data from {self.file_path}", e)

    async def _save(self, data: Dict):
        """保存数据"""
        try:
            async with self._lock:
                self.file_path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding='utf-8'
                )
            log_service_call(self.__class__.__name__, "_save", True)
        except Exception as e:
            log_service_call(self.__class__.__name__, "_save", False, str(e))
            raise RepositoryException(f"Failed to save data to {self.file_path}", e)

    @abstractmethod
    async def get(self, key: str) -> Any:
        """获取单个实体"""
        pass

    @abstractmethod
    async def save(self, key: str, value: Any):
        """保存单个实体"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除实体"""
        pass

    @abstractmethod
    async def get_all(self) -> Dict[str, Any]:
        """获取所有实体"""
        pass
