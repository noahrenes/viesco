from __future__ import annotations

import json
from argparse import ArgumentParser
from importlib import import_module
from math import ceil
from pathlib import Path
from platform import system as get_system_name
from sys import stderr, stdout
from typing import Any, Callable


class ScriptWriter:
    def __init__(self, patcher: Patcher, patches: list[tuple[str, Any]], output_path: str | None):
        self.patcher = patcher
        patcher.output = self

        self.platform = ""
        self.lines = []

        if not output_path:
            self._prepare = self._dummy
            self.comment = self._dummy
            self.set_variable = self._dummy
            self.remove_file = self._dummy
            return

        self.output_path = Path(output_path)
        if self.output_path.suffix in {".bat", ".cmd"}:
            self.platform = "Windows"
            self._prepare = self._batch_prepare
            self.comment = self._batch_comment
            self.set_variable = self._batch_set_variable
            self.remove_file = self._batch_remove_file
        else:
            msg = f"Unsupported output file extension {self.output_path.suffix}."
            raise ValueError(msg)

        self._prepare()
        self.comment(
            f"This script was created AUTOMATICALLY using Viesco v{Patcher.VERSION}",
            f"for {patcher.host_product} v{patcher.host_version} on {patcher.host_platform}.",
            "",
            "Applied patches:",
            f"  {','.join(name for name, _ in patches)}",
            "",
            "GitHub: https://github.com/noahrenes/viesco",
            "Codeberg: https://codeberg.org/renesnoah/viesco",
            "",
            "Viesco is free software; you can redistribute it and/or modify",
            "it under the terms of the GNU General Public License version 2",
            "as published by the Free Software Foundation.",
            "",
            "Viesco and this script is distributed in the hope that it will",
            "be useful, but WITHOUT ANY WARRANTY; without even the implied",
            "warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR ",
            "PURPOSE.",
        )
        self.set_variable("VSC_PATH", patcher.install_path)

    def write(self):
        if self.lines:
            self.output_path.write_text("\n".join(self.lines))

    def _dummy(self, *_, **__):
        pass

    def _batch_prepare(self):
        self.lines.append("@echo off")

    def _batch_comment(self, *lines: str):
        self.lines.extend(f"rem {line}" for line in lines)

    def _batch_set_variable(self, name: str, value: Any):
        self.lines.append(f'set "{name}={value}"')

    def _batch_remove_file(self, path: Path):
        if self.patcher.install_path in path.parents:
            path = Path("%VSC_PATH%") / path.relative_to(self.patcher.install_path)

        self.lines.append(f"echo :: Deleting {path}...")
        self.lines.append(f"del /F /Q {path}")


class Patcher:
    VERSION = "1.0.0"

    def __init__(self, *, dry_run: bool = False):
        self.dry_run = dry_run
        self.output: ScriptWriter = None
        self.install_path: Path = None

        self._skip_patch = False
        self._current_patch = ""

        self._product_info: dict = None
        self._package_info: dict = None

        self.host_platform = get_system_name()
        self.host_product = ""
        self.host_version = ""

    def _ask_to_skip_patch(self, *args):
        self.print(*args, level="warning")
        try:
            self._skip_patch = (
                input(f"[{self._current_patch}] Skip the patch? [Y/n]: ").lower() != "n"
            )
        except KeyboardInterrupt:
            exit(1)

    def load_install_path(self, install_path: Path) -> bool:
        product_path = install_path / "resources/app/product.json"
        package_path = install_path / "resources/app/package.json"

        if not product_path.is_file() or not package_path.is_file():
            return False

        with product_path.open() as f:
            self._product_info = json.load(f)
        with package_path.open() as f:
            self._package_info = json.load(f)

        self.host_product = self._product_info["nameShort"]
        self.host_version = self._package_info["version"]

        self.install_path = install_path
        return True

    def validate_patch(self, name: str, validator: Callable[[Patcher], None]) -> bool:
        self._current_patch = name
        validator(self)
        return not self._skip_patch

    def check_product_name(self, *supported: str):
        if self.host_product not in supported:
            self._ask_to_skip_patch(f"'{self.host_product}' is not supported by the patch.")

    def check_version(self, minimal_str: str):
        minimal = tuple(map(int, minimal_str.split(".")))
        current: tuple[int, ...] = tuple(map(int, self.host_version.split(".")))
        if not (
            current[0] >= minimal[0]
            and (len(minimal) < 2 or current[1] >= minimal[1])
            and (len(minimal) < 3 or current[2] >= minimal[2])
        ):
            self._ask_to_skip_patch(
                f"{self.host_product} v{self.host_version}",
                f"is not supported by the patch (minimal: v{minimal_str}).",
            )

    def select_from(self, items: dict[str, Any], prompt: str = "Select") -> list:
        labels = tuple(items.keys())
        values = tuple(items.values())
        max_items_idx = len(items) - 1

        self.print_items_with_index(labels)

        prompt = f"[{self._current_patch}] {prompt} (comma-separated) > "
        while True:
            try:
                selected = input(prompt)
            except KeyboardInterrupt:
                exit(1)

            invalid = []
            selected = selected.split(",")
            for sel_idx, sel_item in enumerate(selected):
                try:
                    label_idx = labels.index(sel_item)
                except ValueError:
                    label_idx = -1

                if label_idx < 0:
                    try:
                        label_idx = int(sel_item) - 1
                    except ValueError:
                        invalid.append(sel_item)
                        continue

                    if label_idx < 0 or max_items_idx < label_idx:
                        invalid.append(sel_item)
                        continue

                selected[sel_idx] = values[label_idx]

            if invalid:
                self.print(
                    f"Invalid input '{','.join(invalid)}'. Input a valid value or number.",
                    level="warning",
                )
            else:
                return selected

    def print_items_with_index(self, items: list[str] | tuple[str, ...]):
        items_len = len(items)
        columns_n = round(items_len**0.4)  # 0.4 results in a more square-ish output
        rows_n = ceil(items_len / columns_n)

        rows: list[list[tuple[str, str]]] = []
        label_max_lengths = [0] * columns_n
        prefix_max_lengths = [0] * columns_n

        for offset in range(rows_n):
            rows.append([])

            for item_idx in range(offset, items_len, rows_n):
                item = (str(item_idx + 1), str(items[item_idx]))
                rows[-1].append(item)

                col = item_idx // rows_n
                prefix_max_lengths[col] = max(len(item[0]), prefix_max_lengths[col])
                label_max_lengths[col] = max(len(item[1]), label_max_lengths[col])

        for row in rows:
            print(
                "  ".join(
                    (
                        f"{item[0].rjust(prefix_max_lengths[col])}) "
                        f"{item[1].ljust(label_max_lengths[col])}"
                    )
                    for col, item in enumerate(row)
                ),
            )

    def print_patch_name(self, name: str):
        self._current_patch = ""
        self.print(f"Starting '{name}'...")
        self._current_patch = name

        # Maybe it should be available as a ScriptWriter method.
        # Though it is needed only here, so hardcoding it is fine for now.
        sep = "-" * 70
        self.output.comment(sep, name, sep)

    def print(self, *args, level: str = "", **kwargs):
        fd = stdout
        if level in {"warning", "error"}:
            level = "[!]"
            fd = stderr
        elif level == "debug":
            level = ".."
            fd = stderr
        elif level == "info":
            level = "[+]"
        else:
            level = "::"

        if self._current_patch:
            print(f"[{self._current_patch}]", level, *args, file=fd, **kwargs)
        else:
            print(level, *args, file=fd, **kwargs)

    def remove(self, path_str: Path | str, platform: str = ""):
        path = Path(path_str)
        if path.is_relative_to(self.install_path):
            path_str = path.relative_to(self.install_path)

        is_targeting_host = not self.dry_run and (not platform or platform == self.host_platform)
        is_targeting_output = self.output.lines and (
            not platform or platform == self.output.platform
        )

        if is_targeting_host:
            path.unlink(missing_ok=True)
            self.print(f"Removed {path_str}.", level="info")

        if is_targeting_output:
            self.output.remove_file(path)
            if not is_targeting_host:
                self.print(f"The script will remove {path_str}.", level="info")
        elif not is_targeting_host:
            self.print(
                f"Ignored {path_str}.",
                f"(expected: {platform or '<any>'},",
                f"host: {self.host_platform or '<unknown>'},",
                f"target: {self.output.platform or '<none>'})",
                level="debug",
            )


if __name__ == "__main__":
    parser = ArgumentParser(
        prog="viesco",
        description="An utility for configuring VSCodium before first run.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="write the automatic script to OUTPUT (.bat)",
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="perform a run without making any changes",
    )

    parser.add_argument("install", help="installation/extraction path of VSCodium")
    parser.add_argument("patch", nargs="+", help="patch files to apply")

    args = parser.parse_args()

    patcher = Patcher(dry_run=args.dry_run)
    patcher.print(f"Received arguments: {args}", level="debug")

    if patcher.dry_run:
        patcher.print(
            "This is a dry run. No changes will be made to the existing installation.",
            level="warning",
        )
    if not patcher.load_install_path(Path(args.install)):
        patcher.print(f"'{args.install}' is not a valid path to VSCodium.", level="warning")
        exit(1)

    patches: list[tuple[str, Callable[[Patcher], None]]] = []
    for patch_name in args.patch:
        if not Path(f"patches/{patch_name}.py").is_file():
            patcher.print(
                f"Patch 'patches/{patch_name}.py' not found. Skipping...", level="warning"
            )
            continue

        patch_module = import_module(f"patches.{patch_name}")
        if patcher.validate_patch(patch_name, patch_module.validate):
            patches.append((patch_name, patch_module.patch))

    try:
        ScriptWriter(patcher, patches, args.output)
    except ValueError as exc:
        patcher.print(exc, level="warning")
        exit(1)

    for name, func in patches:
        patcher.print_patch_name(name)
        func(patcher)

    if patches:
        patcher.output.write()
