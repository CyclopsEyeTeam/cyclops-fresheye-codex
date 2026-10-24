"""Portable state discovery and read-only validation before any setup."""
from dataclasses import dataclass
import os
from pathlib import Path
from itertools import combinations


class UserError(Exception):
    pass


def absolute(path):
    return Path(path).expanduser().resolve()


def default_data_dir():
    explicit = os.environ.get('CYCLOPS_FRESHEYE_DATA_DIR')
    if explicit:
        return absolute(explicit)
    xdg = os.environ.get('XDG_STATE_HOME')
    if xdg and Path(xdg).is_absolute():
        return absolute(Path(xdg)/'cyclops-fresheye-codex')
    return absolute(Path.home()/'.local/state/cyclops-fresheye-codex')


def contains(parent, child):
    """Compare physical ancestors, retaining suffixes that do not exist yet.

    resolve() handles symlinks but not bind mounts. Existing ancestor identities
    also match two mount names for the same directory, without a disk-specific
    mount table or privileged filesystem operations.
    """
    anchor = parent
    missing = []
    while not anchor.exists():
        missing.insert(0, anchor.name)
        anchor = anchor.parent
    stat = anchor.stat()
    identity = (stat.st_dev, stat.st_ino)
    for candidate in (child, *child.parents):
        if not candidate.exists():
            continue
        current = candidate.stat()
        if (current.st_dev, current.st_ino) == identity:
            suffix = child.relative_to(candidate).parts
            return suffix[:len(missing)] == tuple(missing)
    return False


def overlaps(a, b):
    return contains(a, b) or contains(b, a)


@dataclass(frozen=True)
class Layout:
    home: Path
    receipts: Path
    bindings: Path
    temporary: Path


def validate_layout(cwd, data_dir, home=None, receipts=None):
    cwd, data_dir = absolute(cwd), absolute(data_dir)
    if not cwd.is_dir():
        raise UserError(f'Project directory does not exist: {cwd}')
    layout = Layout(absolute(home or data_dir/'launcher-home'),
                    absolute(receipts or data_dir/'launcher-receipts'),
                    absolute(data_dir/'launcher-bindings'),
                    absolute(data_dir/'runtime-tmp'))
    protected = {absolute(Path.home()/'.codex')}
    if os.environ.get('CODEX_HOME'):
        protected.add(absolute(os.environ['CODEX_HOME']))
    locations = (layout.home, layout.receipts, layout.bindings, layout.temporary)
    for path in locations:
        if overlaps(path, cwd):
            raise UserError('FreshEye settings and records must be outside the project')
        if any(overlaps(path, other) for other in protected):
            raise UserError('FreshEye state must be separate from the main Codex home')
        ancestor = path
        while not ancestor.exists() and ancestor != ancestor.parent:
            ancestor = ancestor.parent
        if not ancestor.is_dir():
            raise UserError(f'A state path crosses a non-directory: {path}')
        if path.exists() and not path.is_dir():
            raise UserError(f'State path is not a directory: {path}')
    if any(overlaps(a, b) for a, b in combinations(locations, 2)):
        raise UserError('Settings, receipt and binding directories must be separate')
    return layout
