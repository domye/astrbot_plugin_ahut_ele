"""
核心常量定义
"""

# 插件名称
PLUGIN_NAME = "ahut_ele"

# 命令前缀
COMMAND_PREFIX = "电费"

# 管理员命令
ADMIN_COMMANDS = {
    "登录": "admin_login",
    "登出": "admin_logout",
}

# 用户命令
USER_COMMANDS = {
    "设置": "user_setup",
    "我的": "user_my",
    "删除": "user_delete",
}

# 查询命令
QUERY_COMMANDS = {
    "查询": "query_all",
}

# 定时任务命令
SCHEDULE_COMMANDS = {
    "定时": {
        "添加": "schedule_add",
        "列表": "schedule_list",
        "删除": "schedule_delete",
        "设置": "schedule_update",
    }
}

# 其他命令
OTHER_COMMANDS = {
    "状态": "status",
    "帮助": "help",
}

# 会话超时（分钟）
SESSION_TIMEOUT_MINUTES = 30

# 请求超时（秒）
REQUEST_TIMEOUT_SECONDS = 10

# 电费查询最大重试次数
MAX_RETRIES = 3

# 宿舍设置最大重试次数
MAX_SETUP_RETRIES = 3

# 数据文件路径
DATA_PATH = "data/plugin_data/ahut_ele"

# 定时任务文件名
SCHEDULE_FILE = "schedule_tasks.json"

# 宿舍注册表文件名
DORM_REGISTRY_FILE = "dorm_registry.json"

# 凭证文件名
CREDENTIALS_FILE = "credentials.json"

# 校区选项
CAMPUS_OPTIONS = {
    "NewS": "新校区",
    "OldS": "老校区",
}

# 缴费系统URL
PAY_SYSTEM_BASE_URL = "https://pay.ahut.edu.cn"
PAY_SYSTEM_LOGIN_URL = f"{PAY_SYSTEM_BASE_URL}/Account/Login"
PAY_SYSTEM_LOGIN_SERVICE_URL = f"{PAY_SYSTEM_BASE_URL}/Account/LoginService"
PAY_SYSTEM_IMS_URL = f"{PAY_SYSTEM_BASE_URL}/Charge/IMS?state=WXSTATEFLAG"
PAY_SYSTEM_IMS_SERVICE_URL = f"{PAY_SYSTEM_BASE_URL}/Charge/GetIMS_AHUTService"
