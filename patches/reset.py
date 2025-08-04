from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from viesco import Patcher


def validate(patcher: Patcher):
    patcher.check_product_name("VSCodium")
    patcher.check_version("1.102.35058")


def patch(patcher: Patcher):
    patcher.remove("%USERPROFILE%/.vscode-oss", "Windows")
    patcher.remove("%APPDATA%/VSCodium", "Windows")
