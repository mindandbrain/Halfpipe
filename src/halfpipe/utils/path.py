# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import logging
import os
import pathlib
import zipfile
from os import path as op
from pathlib import Path
from shutil import copyfile
from typing import Any, Iterator

AnyPath = pathlib.Path | zipfile.Path


def resolve(path: Path | str, fs_root: Path | str) -> Path:
    fs_root = str(fs_root)

    # resolve workdir in fs_root
    abspath = str(Path(path).resolve())

    if not abspath.startswith(fs_root):
        abspath = op.normpath(fs_root + abspath)

    return Path(abspath)


def find_paths(obj: Any) -> list[Path | str]:
    from pathlib import Path

    from nipype.interfaces.base.specs import BaseTraitedSpec
    from nipype.interfaces.base.support import InterfaceResult

    paths: list[Path | str] = []
    stack = [obj]
    while len(stack) > 0:
        obj = stack.pop()
        if isinstance(obj, InterfaceResult):
            stack.append(obj.inputs)
            stack.append(obj.outputs)
        elif isinstance(obj, BaseTraitedSpec):
            stack.append(obj.get_traitsfree())
        elif hasattr(obj, "__dict__"):
            stack.append(obj.__dict__)
        elif isinstance(obj, dict):
            stack.extend(obj.values())
        elif isinstance(obj, str):
            if obj.startswith("def"):
                continue
            path = Path(obj)
            try:
                if path.exists():
                    paths.append(path)
            except OSError:
                pass
        elif isinstance(obj, Path):
            try:
                if obj.exists():
                    paths.append(obj)
            except OSError:
                pass
        else:
            try:  # check if the obj is iterable
                stack.extend(obj)
            except TypeError:
                pass
    return paths


def split_ext(path: str | AnyPath):
    """Splits filename and extension (.gz safe)
    >>> split_ext('some/file.nii.gz')
    ('file', '.nii.gz')
    >>> split_ext('some/other/file.nii')
    ('file', '.nii')
    >>> split_ext('otherext.tar.gz')
    ('otherext', '.tar.gz')
    >>> split_ext('text.txt')
    ('text', '.txt')

    Adapted from niworkflows
    """
    from pathlib import Path

    if isinstance(path, str):
        path = Path(path)

    name = str(path.name)

    safe_name = name
    for compound_extension in [".gz", ".xz"]:
        safe_name = safe_name.removesuffix(compound_extension)

    stem = Path(safe_name).stem
    return stem, name[len(stem) :]


def is_empty(path: Path | str) -> bool:
    from pathlib import Path

    path = Path(path)
    try:
        if next(path.iterdir()) is not None:  # dir is not empty
            return False
    except (FileNotFoundError, StopIteration):
        pass

    return True


def validate_workdir(path: Path | str):
    try:
        return Path(path).is_dir()
    except TypeError:
        return False


def is_hidden(path: Path | str) -> bool:
    """
    adapted from cpython glob
    """
    return Path(path).stem[0] == "."


def iterdir(dirname: str | Path, dironly: bool) -> Iterator[str]:
    """
    adapted from cpython glob
    """
    if not dirname:
        dirname = os.curdir
    try:
        with os.scandir(dirname) as it:
            for entry in it:
                try:
                    if not dironly or entry.is_dir():
                        entry_name = entry.name
                        if entry.is_dir():
                            entry_name = op.join(entry_name, "")
                        if not is_hidden(entry_name):
                            yield entry_name
                except OSError:
                    pass
    except OSError:
        return


def rlistdir(
    dirname: str | Path,
    dironly: bool = False,
    maxdepth: int | None = None,
) -> Iterator[str]:
    """
    adapted from cpython glob
    """
    if maxdepth is not None:
        maxdepth -= 1
    names = list(iterdir(dirname, dironly))
    for x in names:
        path = op.join(dirname, x) if dirname else x
        yield path
        if maxdepth is None or maxdepth > 0:
            yield from rlistdir(path, dironly)


def recursive_list_directory(
    path: str | AnyPath,
    only_directories: bool = False,
    enter_archives: bool = False,
    max_depth: int | None = None,
) -> Iterator[AnyPath]:
    if max_depth is not None:
        max_depth -= 1
    if isinstance(path, str):
        path = Path(path)
    if path.is_dir():
        if max_depth is None or max_depth >= 0:
            for child in path.iterdir():
                if child.is_dir():
                    yield child
                yield from recursive_list_directory(
                    child,
                    only_directories,
                    enter_archives,
                    max_depth,
                )
    else:
        if not only_directories:
            yield path
        if enter_archives:
            with path.open("rb") as file_handle:
                if not zipfile.is_zipfile(file_handle):
                    return
                zip_file = zipfile.ZipFile(file_handle)
                yield from recursive_list_directory(
                    zipfile.Path(zip_file),
                    only_directories,
                    enter_archives,
                    max_depth,
                )


def copy_if_newer(inpath: Path, outpath: Path):
    outpath.parent.mkdir(exist_ok=True, parents=True)
    if outpath.exists():
        if os.stat(inpath).st_mtime <= os.stat(outpath).st_mtime:
            logging.info(f'Not overwriting file "{outpath}"')
            return False
        logging.info(f'Overwriting file "{outpath}"')
    else:
        logging.info(f'Creating file "{outpath}"')
    copyfile(inpath, outpath)
    return True


def exists(path: Path | str) -> bool:
    path = Path(path)
    try:
        return path.exists()
    except PermissionError:
        return False
