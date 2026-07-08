"""凭据管理（keyring + .env 后备）"""

import keyring


class KeyManager:
    """API Key 安全管理器"""

    SERVICE_PREFIX = "hatch"

    def set_key(self, provider: str, key: str) -> None:
        keyring.set_password(f"{self.SERVICE_PREFIX}/{provider}", provider, key)

    def get_key(self, provider: str) -> str | None:
        return keyring.get_password(f"{self.SERVICE_PREFIX}/{provider}", provider)

    def delete_key(self, provider: str) -> None:
        try:
            keyring.delete_password(f"{self.SERVICE_PREFIX}/{provider}", provider)
        except keyring.errors.PasswordDeleteError:
            pass

    def list_providers(self) -> list[str]:
        known = ["deepseek", "glm", "claude"]
        return [p for p in known if self.get_key(p) is not None]

    def mask_key(self, key: str) -> str:
        if len(key) <= 4:
            return "****"
        return "****" + key[-4:]

    def __repr__(self) -> str:
        return f"KeyManager(providers={self.list_providers()})"