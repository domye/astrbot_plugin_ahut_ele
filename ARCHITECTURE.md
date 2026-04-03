# AHUT电费查询插件架构说明 (v2.0.0)

## 架构概览

```
astrbot_plugin_ahut_ele/
├── main.py                    # 插件入口（精简，只负责协调）
├── metadata.yaml              # 插件元数据
├── _conf_schema.json          # 配置模式（可选）
├── README.md                  # 使用说明
│
├── core/                      # 核心模块
│   ├── __init__.py
│   ├── constants.py           # 常量定义
│   ├── exceptions.py          # 自定义异常体系
│   └── logger.py              # 日志工具
│
├── models/                    # 数据模型层
│   ├── __init__.py
│   ├── entities.py            # 业务实体（PayCredentials, DormConfig等）
│   └── dto.py                 # 数据传输对象
│
├── repositories/              # 数据访问层（Repository模式）
│   ├── __init__.py
│   ├── base_repository.py     # 仓储基类
│   ├── credential_repository.py  # 凭证存储
│   ├── dorm_repository.py     # 宿舍配置存储
│   └── schedule_repository.py # 定时任务存储
│
├── services/                  # 业务逻辑层
│   ├── __init__.py
│   ├── pay_service.py         # 缴费系统服务
│   ├── building_service.py    # 楼栋数据服务
│   └── scheduler_service.py   # 定时任务服务
│
├── handlers/                  # 命令处理器层
│   ├── __init__.py
│   ├── base_handler.py        # 处理器基类
│   ├── admin_handler.py       # 管理员命令
│   ├── user_handler.py        # 用户命令
│   ├── query_handler.py       # 查询命令
│   └── schedule_handler.py    # 定时任务命令
│
└── utils/                     # 工具模块
    ├── __init__.py
    └── rsa_utils.py           # RSA加密工具
```

## 架构特点

### 1. 分层架构
- **Core层**: 提供基础功能（常量、异常、日志）
- **Models层**: 定义数据结构和DTO
- **Repositories层**: 统一数据访问，便于切换存储后端
- **Services层**: 业务逻辑实现
- **Handlers层**: 处理用户命令和交互

### 2. Repository模式
数据访问统一通过Repository层，当前使用JSON文件存储，未来可轻松切换为数据库：
- `CredentialRepository`: 凭证存储
- `DormRepository`: 宿舍配置存储
- `ScheduleRepository`: 定时任务存储

### 3. 异常体系
```
AhutEleException
├── ValidationException
├── ServiceException
│   ├── AuthException
│   ├── PaySystemException
│   └── NotConfiguredException
└── RepositoryException
```

### 4. 新命令设计

| 命令 | 功能 |
|------|------|
| `/电费 登录` | 管理员登录 |
| `/电费 登出` | 管理员登出 |
| `/电费 设置` | 用户设置宿舍 |
| `/电费 我的` | 查看我的宿舍 |
| `/电费 删除` | 删除宿舍设置 |
| `/电费 查询` | 查询所有宿舍 |
| `/电费 查询 [房间]` | 查询指定房间 |
| `/电费 定时 添加` | 添加定时任务 |
| `/电费 定时 列表` | 查看定时任务 |
| `/电费 定时 删除` | 删除定时任务 |
| `/电费 定时 设置` | 修改定时任务 |
| `/电费 状态` | 查看插件状态 |
| `/电费 帮助` | 查看帮助 |

### 5. 代码规范
- 文件行数 < 400 行
- 函数行数 < 50 行
- 单一职责原则
- 依赖注入

## 迁移说明

### 从 v1.x 迁移到 v2.0.0

**命令变化:**
- `/ele_login` → `/电费 登录`
- `/ele_logout` → `/电费 登出`
- `/ele_set` → `/电费 设置`
- `/ele_my` → `/电费 我的`
- `/ele_del` → `/电费 删除`
- `/ele` → `/电费 查询`
- `/ele_one` → `/电费 查询 [房间]`
- `/ele_schedule_add` → `/电费 定时 添加`
- `/ele_schedule_list` → `/电费 定时 列表`
- `/ele_schedule_del` → `/电费 定时 删除`
- `/ele_schedule_edit` → `/电费 定时 设置`
- `/ele_status` → `/电费 状态`
- `/ele_help` → `/电费 帮助`

**数据兼容性:**
- v1.x 的数据文件可自动迁移到 v2.0.0
- 凭证、宿舍配置、定时任务数据格式保持一致

## 开发规范

### 添加新命令
1. 在 handlers/ 目录创建或修改对应的 handler
2. 在 main.py 的 handle_command 方法中添加命令路由
3. 更新帮助文档

### 修改数据模型
1. 修改 models/entities.py 或 models/dto.py
2. 如需修改存储格式，更新对应 repository
3. 确保向后兼容或提供数据迁移方案

### 错误处理
- 服务层抛出具体的 ServiceException
- 处理器层捕获并转换为用户友好消息
- 所有异常使用 handle_error 方法处理
