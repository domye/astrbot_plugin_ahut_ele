"""
RSA加密工具 - 用于密码加密

参考: ahut-tool/backend/utils/RSA.go
"""
import base64
from typing import Optional


# 安工大缴费系统的RSA公钥
RSA_PUBLIC_KEY = """MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCCCUg7rT5UBlDcqoISt9PR/p1qaf2Tj+qZgzV/J764hBJAinMcOGWlcTkGlcL69P8waHti4HsOYYo4Tk5Fx9dqHzEtJha/BtcFUysD/BKiyeJfMyWNMNlgggghG5BuY2M3AYY8qII1Q7xCN6XuQb4pAYJ8qVmIqqAqRvyFA0y4vQIDAQAB"""


def encrypt_password_with_rsa(password: str) -> Optional[str]:
    """
    使用RSA公钥加密密码

    流程:
    1. Base64编码密码
    2. 使用RSA公钥加密 (PKCS1v15)
    3. Base64编码加密后的字节

    返回: Base64编码的加密密码，失败返回 None
    """
    try:
        # 导入加密库
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.backends import default_backend

        # 解码公钥
        pub_bytes = base64.b64decode(RSA_PUBLIC_KEY)

        # 加载公钥
        public_key = serialization.load_der_public_key(
            pub_bytes,
            backend=default_backend()
        )

        # 首先Base64编码密码
        password_b64 = base64.b64encode(password.encode('utf-8'))

        # 使用RSA PKCS1v15加密
        encrypted = public_key.encrypt(
            password_b64,
            padding.PKCS1v15()
        )

        # Base64编码结果
        return base64.b64encode(encrypted).decode('utf-8')

    except ImportError:
        # 回退：如果cryptography不可用，尝试rsa库
        try:
            import rsa

            # 解码公钥
            pub_bytes = base64.b64decode(RSA_PUBLIC_KEY)
            public_key = rsa.PublicKey.load_pkcs1_openssl_der(pub_bytes)

            # Base64编码密码
            password_b64 = base64.b64encode(password.encode('utf-8'))

            # 加密
            encrypted = rsa.encrypt(password_b64, public_key)

            # Base64编码结果
            return base64.b64encode(encrypted).decode('utf-8')

        except ImportError:
            raise RuntimeError(
                "RSA加密需要 'cryptography' 或 'rsa' 库。"
                "安装命令: pip install cryptography"
            )

    except Exception as e:
        raise RuntimeError(f"RSA加密失败: {e}")