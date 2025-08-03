from __future__ import annotations

import json
from argparse import ArgumentParser
from importlib import import_module
from math import ceil
from pathlib import Path
from sys import stderr, stdout
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from typing import Any


class ScriptWriter:
    def __init__(self, patches: list[tuple[str, Any]], install_path: str, output_path: str | None):
        self.install_path = install_path
        self.lines = []

        if output_path:
            self.output_path = Path(output_path)

            if self.output_path.suffix in {".bat", ".cmd"}:
                self._prepare = self._batch_prepare
                self.comment = self._batch_comment
                self.set_variable = self._batch_set_variable
                self.remove_file = self._batch_remove_file
            else:
                msg = f"Unsupported output file extension {self.output_path.suffix}."
                raise ValueError(msg)
        else:
            self._prepare = self._dummy
            self.comment = self._dummy
            self.set_variable = self._dummy
            self.remove_file = self._dummy

        self._prepare(patches)
        self.set_variable("VSC_PATH", install_path)

    def write(self):
        if self.lines:
            self.output_path.write_text("\n".join(self.lines))

    def _dummy(self, *_, **__):
        pass

    def _batch_prepare(self, patches: list[tuple[str, Any]]):
        self.lines.extend((
            "@echo off",
            f"rem This script was created AUTOMATICALLY using Viesco v{Patcher.VERSION}.",
            "rem",
            "rem GitHub: https://github.com/noahrenes/viesco",
            "rem Codeberg: https://codeberg.org/renesnoah/viesco",
            "rem",
            "rem Viesco is free software; you can redistribute it and/or modify",
            "rem it under the terms of the GNU General Public License version 2",
            "rem as published by the Free Software Foundation.",
            "rem",
            "rem Viesco and this script is distributed in the hope that it will",
            "rem be useful, but WITHOUT ANY WARRANTY; without even the implied",
            "rem warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR ",
            "rem PURPOSE.",
            "rem",
            "rem Applied patches:",
            f"rem   {','.join(name for name, _ in patches)}",
        ))

    def _batch_comment(self, message: str):
        self.lines.append(f"rem {message}")

    def _batch_set_variable(self, name: str, value: str):
        self.lines.append(f'set "{name}={value}"')

    def _batch_remove_file(self, path: Path):
        path = path.relative_to(self.install_path)
        self.lines.append(f"echo :: Deleting {path}...")
        self.lines.append(f"del /F /Q %VSC_PATH%\\{path}")


class Patcher:
    VERSION = "1.0.0"

    EXIT_USER = 1
    EXIT_FATAL = 2

    def __init__(self, install_path: Path, *, dry_run: bool = False):
        self.install_path = install_path
        self.output: ScriptWriter = None  # pyright: ignore[reportAttributeAccessIssue]
        self.dry_run = dry_run

        self._skip_patch = False
        self.current_patch = ""

        with (install_path / "resources/app/product.json").open() as f:
            self.product_info = json.load(f)

        with (install_path / "resources/app/package.json").open() as f:
            self.package_info = json.load(f)

    def _find(self, array: tuple, item: Any) -> int:
        try:
            return array.index(item)
        except ValueError:
            return -1

    def _ask_to_skip_patch(self, *args):
        self.print(*args, level="warning")
        try:
            self._skip_patch = (
                input(f"[{self.current_patch}] Skip the patch? [Y/n]: ").lower() != "n"
            )
        except KeyboardInterrupt:
            exit(Patcher.EXIT_USER)

    def check_patch(self, name: str, check: Callable[[Patcher], None]) -> bool:
        self.current_patch = name
        check(self)
        return not self._skip_patch

    def check_product_name(self, *supported: str):
        if self.product_info["nameShort"] not in supported:
            self._ask_to_skip_patch(
                f"'{self.product_info['nameShort']}' is not supported by the patch."
            )

    def check_version(self, minimal_str: str):
        minimal = tuple(map(int, minimal_str.split(".")))
        current: tuple[int, ...] = tuple(map(int, self.package_info["version"].split(".")))
        if not (
            current[0] >= minimal[0]
            and (len(minimal) < 2 or current[1] >= minimal[1])
            and (len(minimal) < 3 or current[2] >= minimal[2])
        ):
            self._ask_to_skip_patch(
                f"{self.product_info['nameShort']} v{self.package_info['version']}",
                f"is not supported by the patch (minimal: v{minimal_str}).",
            )

    def select_from(self, items: dict[str, Any], prompt: str = "Select") -> list:
        labels = tuple(items.keys())
        values = tuple(items.values())
        max_items_idx = len(items) - 1

        self.print_items_with_index(labels)

        prompt = f"[{self.current_patch}] {prompt} (comma-separated) > "
        while True:
            try:
                selected = input(prompt)
            except KeyboardInterrupt:
                exit(Patcher.EXIT_USER)

            invalid = []
            selected = selected.split(",")
            for sel_idx, sel_item in enumerate(selected):
                label_idx = self._find(labels, sel_item)
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
        self.print(f"Starting '{name}'...")
        self.current_patch = name

        self.output.lines.append("")
        self.output.comment(name)

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

        if self.current_patch:
            print(f"[{self.current_patch}]", level, *args, file=fd, **kwargs)
        else:
            print(level, *args, file=fd, **kwargs)

    def remove(self, path: Path):
        if not self.dry_run:
            path.unlink(missing_ok=True)

        self.output.remove_file(path)
        self.print(f"Removed {path}.", level="info")


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

    patcher = Patcher(install_path=Path(args.install), dry_run=args.dry_run)
    if not patcher.install_path.is_dir():
        patcher.print(f"Unable to access the folder: '{args.install}'.", level="warning")
        exit(Patcher.EXIT_FATAL)

    patcher.print(f"Received args: {args}", level="debug")
    if patcher.dry_run:
        patcher.print("This is a dry run. No changes will be made.", level="warning")

    patches: list[tuple[str, Callable[[Patcher], None]]] = []
    for patch_name in args.patch:
        if not Path(f"patches/{patch_name}.py").is_file():
            patcher.print(
                f"Patch 'patches/{patch_name}.py' not found. Skipping...", level="warning"
            )
            continue

        patch_module = import_module(f"patches.{patch_name}")
        if patcher.check_patch(patch_name, patch_module.check):
            patches.append((patch_name, patch_module.patch))

    try:
        writer = ScriptWriter(patches, args.install, args.output)
        patcher.output = writer
    except ValueError as exc:
        patcher.print(exc, level="warning")
        exit(Patcher.EXIT_USER)

    for name, func in patches:
        patcher.print_patch_name(name)
        func(patcher)

    patcher.output.write()
