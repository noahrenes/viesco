from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from viesco import Patcher


def validate(patcher: Patcher):
    patcher.check_product_name("VSCodium")
    patcher.check_version("1.102.35058")


def patch(patcher: Patcher):
    locales: dict[str, Path] = {}
    locales_paths = tuple((patcher.install_path / "locales").glob("*.pak"))

    for pak_path in locales_paths:
        locale_name = pak_path.stem.lower()
        locales[locale_name] = pak_path

    preserved: list[Path] = patcher.select_from(locales, prompt="Locales to preserve")
    patcher.output.comment(f"Preserved locales: {','.join(path.stem for path in preserved)}")

    for pak_path in locales_paths:
        if pak_path in preserved:
            continue
        patcher.remove(pak_path)
