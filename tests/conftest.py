# -*- coding: utf-8 -*-
"""共享 fixtures。

Linux CI（无 Secret Service/dbus）下 keyring 没有可用后端，
真实调用会抛 NoKeyringError —— 用 null 后端兜底（get_password 返回 None，
与 Windows 上"尚未录入 key"的行为一致）。
"""

import keyring
import pytest
from keyring.errors import NoKeyringError


@pytest.fixture(autouse=True, scope="session")
def _keyring_backend() -> None:
    try:
        keyring.get_password("hatch/session-check", "u")
    except NoKeyringError:
        from keyring.backends.null import Keyring

        keyring.set_keyring(Keyring())
