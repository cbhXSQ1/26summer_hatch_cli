"""T1.5: 凭据管理器 测试"""

from unittest.mock import patch, MagicMock

import pytest
from hatch.security.key_manager import KeyManager


class TestKeyManager:
    """KeyManager"""

    def test_set_and_get_key(self) -> None:
        with patch("hatch.security.key_manager.keyring") as mock_keyring:
            mock_keyring.get_password.return_value = "sk-test-key"
            km = KeyManager()
            km.set_key("deepseek", "sk-test-key")
            mock_keyring.set_password.assert_called_with(
                "hatch/deepseek", "deepseek", "sk-test-key"
            )
            result = km.get_key("deepseek")
            assert result == "sk-test-key"

    def test_get_key_nonexistent(self) -> None:
        with patch("hatch.security.key_manager.keyring") as mock_keyring:
            mock_keyring.get_password.return_value = None
            km = KeyManager()
            result = km.get_key("nonexistent")
            assert result is None

    def test_delete_key(self) -> None:
        with patch("hatch.security.key_manager.keyring") as mock_keyring:
            km = KeyManager()
            km.delete_key("deepseek")
            mock_keyring.delete_password.assert_called_with(
                "hatch/deepseek", "deepseek"
            )

    def test_list_providers(self) -> None:
        with patch("hatch.security.key_manager.keyring") as mock_keyring:
            mock_keyring.get_password.side_effect = lambda service, _: (
                "key1" if service == "hatch/deepseek"
                else "key2" if service == "hatch/glm"
                else None
            )
            km = KeyManager()
            providers = km.list_providers()
            assert "deepseek" in providers
            assert "glm" in providers

    def test_multiple_providers_independent(self) -> None:
        with patch("hatch.security.key_manager.keyring") as mock_keyring:
            stored: dict[str, str] = {}

            def mock_set(service, username, password):
                stored[service] = password

            def mock_get(service, _):
                return stored.get(service)

            mock_keyring.set_password.side_effect = mock_set
            mock_keyring.get_password.side_effect = mock_get

            km = KeyManager()
            km.set_key("deepseek", "ds-key")
            km.set_key("glm", "glm-key")

            mock_keyring.get_password.side_effect = lambda s, _: stored.get(s)
            assert km.get_key("deepseek") == "ds-key"
            assert km.get_key("glm") == "glm-key"

    def test_key_not_in_repr(self) -> None:
        with patch("hatch.security.key_manager.keyring") as mock_keyring:
            mock_keyring.get_password.return_value = "sk-secret-1234"
            km = KeyManager()
            repr_str = repr(km)
            assert "sk-secret-1234" not in repr_str
            assert "secret" not in repr_str

    def test_mask_key_for_display(self) -> None:
        km = KeyManager()
        masked = km.mask_key("sk-1234567890abcdef")
        assert masked == "****cdef"
        assert "1234567890" not in masked

    def test_mask_key_short(self) -> None:
        km = KeyManager()
        masked = km.mask_key("abc")
        assert masked == "****"

    def test_set_and_get_provider_meta(self, tmp_path) -> None:
        km = KeyManager(meta_path=tmp_path / "providers.json")
        km.set_provider_meta("custom-x", "https://api.example.com", models=["x-1"])
        meta = km.get_provider_meta("custom-x")
        assert meta == {"api_base": "https://api.example.com", "models": ["x-1"]}

    def test_provider_meta_persists_across_instances(self, tmp_path) -> None:
        path = tmp_path / "providers.json"
        km1 = KeyManager(meta_path=path)
        km1.set_provider_meta("custom-y", "https://api.example.org")
        km2 = KeyManager(meta_path=path)
        assert km2.get_provider_meta("custom-y") == {"api_base": "https://api.example.org"}

    def test_custom_providers_lists_meta_names(self, tmp_path) -> None:
        km = KeyManager(meta_path=tmp_path / "providers.json")
        km.set_provider_meta("custom-z", "https://api.example.net")
        assert "custom-z" in km.custom_providers()

    def test_list_providers_includes_custom_with_key(self, tmp_path) -> None:
        with patch("hatch.security.key_manager.keyring") as mock_keyring:
            stored: dict[str, str] = {}
            mock_keyring.set_password.side_effect = lambda s, u, p: stored.__setitem__(s, p)
            mock_keyring.get_password.side_effect = lambda s, _: stored.get(s)
            km = KeyManager(meta_path=tmp_path / "providers.json")
            km.set_provider_meta("myllm", "https://api.myllm.example")
            km.set_key("myllm", "sk-custom")
            providers = km.list_providers()
            assert "myllm" in providers