"""
数据模型模块
"""
from .entities import (
    PayCredentials,
    DormConfig,
    ElectricityData,
    ScheduleTask,
    SessionInfo,
    UserContext,
)
from .dto import (
    LoginResult,
    QueryResult,
    SetupStep,
    BuildingInfo,
    CampusInfo,
)

__all__ = [
    "PayCredentials",
    "DormConfig",
    "ElectricityData",
    "ScheduleTask",
    "SessionInfo",
    "UserContext",
    "LoginResult",
    "QueryResult",
    "SetupStep",
    "BuildingInfo",
    "CampusInfo",
]