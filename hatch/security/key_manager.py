"""凭据管理（keyring + .env 后备）"""

import json
import keyring
from pathlib import Path


class KeyManager:
    """API Key 安全管理器"""

    SERVICE_PREFIX = "hatch"
    KNOWN_PROVIDERS = ["deepseek", "glm", "claude"]
    DEFAULT_META_PATH = Path.home() / ".hatch" / "providers.json"

    def __init__(self, meta_path: str | Path | None = None) -> None:
        self.meta_path = Path(meta_path) if meta_path else self.DEFAULT_META_PATH

    def set_key(self, provider: str, key: str) -> None:
        keyring.set_password(f"{self.SERVICE_PREFIX}/{provider}", provider, key)

    def get_key(self, provider: str) -> str | None:
        return keyring.get_password(f"{self.SERVICE_PREFIX}/{provider}", provider)

    def delete_key(self, provider: str) -> None:
        try:
            keyring.delete_password(f"{self.SERVICE_PREFIX}/{provider}", provider)
        except keyring.errors.PasswordDeleteError:
            pass

    # ---- 自定义 provider 元信息（名称 → api_base / models）----

    def _read_meta(self) -> dict[str, dict]:
        if not self.meta_path.exists():
            return {}
        try:
            return json.loads(self.meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_meta(self, data: dict[str, dict]) -> None:
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
        )

    def set_provider_meta(self, name: str, api_base: str = "", models: list[str] | None = None) -> None:
        data = self._read_meta()
        entry = data.get(name, {})
        if api_base:
            entry["api_base"] = api_base
        if models:
            entry["models"] = models
        data[name] = entry
        self._write_meta(data)

    def get_provider_meta(self, name: str) -> dict | None:
        return self._read_meta().get(name)

    def delete_provider_meta(self, name: str) -> None:
        data = self._read_meta()
        if name in data:
            del data[name]
            self._write_meta(data)

    def custom_providers(self) -> list[str]:
        return list(self._read_meta().keys())

    def list_providers(self) -> list[str]:
        providers = [p for p in self.KNOWN_PROVIDERS if self.get_key(p) is not None]
        for p in self.custom_providers():
            if self.get_key(p) is not None:
                providers.append(p)
        return providers

    def mask_key(self, key: str) -> str:
        if len(key) <= 4:
            return "****"
        return "****" + key[-4:]

    def __repr__(self) -> str:
        return f"KeyManager(providers={self.list_providers()})"
