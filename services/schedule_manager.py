"""Scheduled task manager for electricity query plugin.

Manages scheduled electricity query tasks for group chats.
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
    """Scheduled task for a group chat."""
    group_umo: str  # Unified Message Origin for the group
    group_name: str = ""  # Display name for the group
    times: List[str] = field(default_factory=list)  # List of times like "8:00", "20:00"

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
    """Registry of all scheduled tasks."""
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
        """Add or update a scheduled task."""
        task = ScheduleTask(
            group_umo=group_umo,
            group_name=group_name,
            times=times,
        )
        self.tasks[group_umo] = task
        return task

    def get_task(self, group_umo: str) -> Optional[ScheduleTask]:
        """Get task for a group."""
        return self.tasks.get(group_umo)

    def remove_task(self, group_umo: str) -> bool:
        """Remove task for a group."""
        if group_umo in self.tasks:
            del self.tasks[group_umo]
            return True
        return False

    def get_all_tasks(self) -> List[ScheduleTask]:
        """Get all tasks."""
        return list(self.tasks.values())


class ScheduleManager:
    """Manages scheduled electricity query tasks."""

    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        self._data_path: Optional[Path] = None
        self._registry: Optional[ScheduleRegistry] = None
        self._lock = asyncio.Lock()
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize the manager and load existing tasks."""
        self._data_path = Path(get_astrbot_data_path()) / "plugin_data" / self.plugin_name
        self._data_path.mkdir(parents=True, exist_ok=True)

        await self._load_registry()
        logger.info(f"ScheduleManager initialized with {len(self._registry.tasks)} tasks")

    async def _load_registry(self):
        """Load registry from file."""
        registry_file = self._data_path / "schedule_tasks.json"

        async with self._lock:
            if registry_file.exists():
                try:
                    with open(registry_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self._registry = ScheduleRegistry.from_dict(data)
                    logger.info(f"Loaded {len(self._registry.tasks)} scheduled tasks")
                except Exception as e:
                    logger.error(f"Failed to load schedule registry: {e}")
                    self._registry = ScheduleRegistry()
            else:
                self._registry = ScheduleRegistry()

    async def _save_registry(self):
        """Save registry to file."""
        if not self._registry:
            return

        registry_file = self._data_path / "schedule_tasks.json"

        async with self._lock:
            try:
                with open(registry_file, 'w', encoding='utf-8') as f:
                    json.dump(self._registry.to_dict(), f, ensure_ascii=False, indent=2)
                logger.debug("Schedule registry saved")
            except Exception as e:
                logger.error(f"Failed to save schedule registry: {e}")

    async def add_task(self, group_umo: str, group_name: str, times: List[str]) -> ScheduleTask:
        """Add a scheduled task for a group."""
        if not self._registry:
            await self._load_registry()

        task = self._registry.add_task(group_umo, group_name, times)
        await self._save_registry()
        logger.info(f"Added scheduled task for {group_name}: {times}")
        return task

    async def get_task(self, group_umo: str) -> Optional[ScheduleTask]:
        """Get scheduled task for a group."""
        if not self._registry:
            await self._load_registry()

        return self._registry.get_task(group_umo)

    async def remove_task(self, group_umo: str) -> bool:
        """Remove scheduled task for a group."""
        if not self._registry:
            await self._load_registry()

        removed = self._registry.remove_task(group_umo)
        if removed:
            await self._save_registry()
            logger.info(f"Removed scheduled task for {group_umo}")
        return removed

    async def get_all_tasks(self) -> List[ScheduleTask]:
        """Get all scheduled tasks."""
        if not self._registry:
            await self._load_registry()

        return self._registry.get_all_tasks()

    def parse_times(self, time_str: str) -> List[str]:
        """Parse time string like '8:00,20:00' into list of times."""
        times = []
        for t in time_str.split(','):
            t = t.strip()
            # Validate time format
            try:
                # Support formats: "8:00", "08:00", "8", "08"
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
        """Start the scheduler background task.

        Args:
            send_callback: Async function to call for sending messages.
                           Signature: async def callback(group_umo: str, message: str)
        """
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop(send_callback))
        logger.info("Scheduler started")

    def stop_scheduler(self):
        """Stop the scheduler background task."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            self._scheduler_task = None
        logger.info("Scheduler stopped")

    async def _scheduler_loop(self, send_callback):
        """Main scheduler loop that checks and executes tasks."""
        logger.info("Scheduler loop started")

        while self._running:
            try:
                now = datetime.now()
                current_time = now.strftime("%H:%M")
                current_minute = now.minute

                # Check every minute at the start of the minute
                tasks = await self.get_all_tasks()

                for task in tasks:
                    if current_time in task.times:
                        logger.info(f"Executing scheduled task for {task.group_name} at {current_time}")
                        try:
                            await send_callback(task.group_umo)
                        except Exception as e:
                            logger.error(f"Failed to send scheduled message to {task.group_name}: {e}")

                # Sleep until next minute
                next_minute = (now.replace(second=0, microsecond=0)
                              + timedelta(minutes=1))
                sleep_seconds = (next_minute - now).total_seconds()
                await asyncio.sleep(sleep_seconds)

            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(60)  # Wait before retrying