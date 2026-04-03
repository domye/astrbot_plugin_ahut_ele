"""
核心异常定义
"""


class AhutEleException(Exception):
    """插件基础异常"""

    def __init__(self, message: str, code: str = None):
        super().__init__(message)
        self.message = message
        self.code = code

    def __str__(self):
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class ValidationException(AhutEleException):
    """输入验证异常"""

    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class ServiceException(AhutEleException):
    """服务层异常"""

    def __init__(self, message: str, code: str = "SERVICE_ERROR"):
        super().__init__(message, code)


class AuthException(ServiceException):
    """认证相关异常"""

    def __init__(self, message: str):
        super().__init__(message, "AUTH_ERROR")


class PaySystemException(ServiceException):
    """缴费系统相关异常"""

    def __init__(self, message: str, code: str = "PAY_SYSTEM_ERROR"):
        super().__init__(message, code)


class NotConfiguredException(ServiceException):
    """插件未配置异常"""

    def __init__(self, message: str = "插件未配置"):
        super().__init__(message, "NOT_CONFIGURED")


class RepositoryException(AhutEleException):
    """数据访问层异常"""

    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message, "REPOSITORY_ERROR")
        self.original_error = original_error
