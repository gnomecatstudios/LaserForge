"""API 1 plugin metadata and enablement; deliberately never imports plugin code.

Capabilities below describe future broker interfaces. They are not a Python sandbox.
The native migration only reads manifests, so discovery cannot activate hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
from typing import Iterable, Mapping


PLUGIN_API_VERSION = 1
MANIFEST_VERSION = 1
MAX_MANIFEST_BYTES = 64 * 1024
CAPABILITIES = frozenset({"drawing-tools", "import", "export", "materials", "menus", "panels"})
_ID = re.compile(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*\Z")
_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
_FIELDS = frozenset({"manifestVersion", "apiVersion", "id", "name", "version", "entrypoint", "capabilities", "dependencies"})


class PluginError(ValueError):
    """An invalid, incompatible, or unavailable plugin, suitable for a UI error list."""


@dataclass(frozen=True)
class Dependency:
    id: str
    version: str


@dataclass(frozen=True)
class PluginManifest:
    id: str
    name: str
    version: str
    api_version: int
    entrypoint: str
    capabilities: frozenset[str]
    dependencies: tuple[Dependency, ...]
    directory: Path


@dataclass(frozen=True)
class PluginIssue:
    directory: str
    message: str


@dataclass(frozen=True)
class DiscoveryReport:
    plugins: tuple[PluginManifest, ...]
    issues: tuple[PluginIssue, ...]


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or len(value) > 100 or not _ID.fullmatch(value):
        raise PluginError(f"{field} must be a lowercase plugin identifier")
    return value


def _version(value: object, field: str) -> str:
    if not isinstance(value, str) or len(value) > 40 or not _VERSION.fullmatch(value):
        raise PluginError(f"{field} must be an exact major.minor.patch version")
    return value


def _safe_file(package: Path, value: object) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        raise PluginError("entrypoint must be a portable relative file path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {".", ".."} for part in value.split("/")):
        raise PluginError("entrypoint must stay inside its plugin directory")
    if any(not part for part in value.split("/")):
        raise PluginError("entrypoint must not contain empty path components")
    current = package
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise PluginError("plugin entrypoint paths must not contain symbolic links")
    if not current.is_file():
        raise PluginError("plugin entrypoint does not exist or is not a file")
    if not current.resolve().is_relative_to(package.resolve()):
        raise PluginError("plugin entrypoint escapes its plugin directory")
    return current


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PluginError(f"duplicate manifest key: {key}")
        result[key] = value
    return result


def read_manifest(directory: str | Path) -> PluginManifest:
    """Validate one installed package without opening or executing its entrypoint."""
    package = Path(directory)
    if package.is_symlink() or not package.is_dir():
        raise PluginError("plugin package must be a real directory")
    source = package / "plugin.json"
    if source.is_symlink() or not source.is_file():
        raise PluginError("plugin.json must be a regular file")
    with source.open("rb") as handle:
        raw = handle.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise PluginError("plugin manifest exceeds 64 KiB")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PluginError(f"invalid UTF-8 JSON manifest: {exc}") from exc
    if not isinstance(data, dict):
        raise PluginError("plugin manifest must be an object")
    unknown = set(data) - _FIELDS
    if unknown:
        raise PluginError(f"unknown manifest fields: {', '.join(sorted(unknown))}")
    for field, expected in (("manifestVersion", MANIFEST_VERSION), ("apiVersion", PLUGIN_API_VERSION)):
        if type(data.get(field)) is not int or data[field] != expected:
            raise PluginError(f"unsupported {field}; expected {expected}")
    plugin_id = _identifier(data.get("id"), "id")
    if package.name != plugin_id:
        raise PluginError("plugin directory name must match its id")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 200 or any(ord(c) < 32 for c in name):
        raise PluginError("name must be 1–200 printable characters")
    version = _version(data.get("version"), "version")
    entrypoint = data.get("entrypoint")
    _safe_file(package, entrypoint)
    capabilities = data.get("capabilities")
    if not isinstance(capabilities, list) or not all(isinstance(c, str) for c in capabilities):
        raise PluginError("capabilities must be a list of API capability names")
    if len(set(capabilities)) != len(capabilities):
        raise PluginError("duplicate capability names")
    denied = set(capabilities) - CAPABILITIES
    if denied:
        raise PluginError(f"unsupported capabilities: {', '.join(sorted(denied))}")
    dependencies = data.get("dependencies", {})
    if not isinstance(dependencies, dict):
        raise PluginError("dependencies must map plugin ids to exact versions")
    required = tuple(Dependency(_identifier(key, "dependency id"), _version(value, "dependency version"))
                     for key, value in sorted(dependencies.items()))
    if any(dep.id == plugin_id for dep in required):
        raise PluginError("a plugin cannot depend on itself")
    return PluginManifest(plugin_id, name, version, PLUGIN_API_VERSION, entrypoint,
                          frozenset(capabilities), required, package.resolve())


def discover_plugins(root: str | Path) -> DiscoveryReport:
    """Inspect immediate package directories, isolating errors and dependency failures."""
    location = Path(root)
    if not location.exists():
        return DiscoveryReport((), ())
    if location.is_symlink() or not location.is_dir():
        return DiscoveryReport((), (PluginIssue(str(location), "plugin root must be a real directory"),))
    found: dict[str, PluginManifest] = {}
    issues: list[PluginIssue] = []
    try:
        entries = sorted(location.iterdir(), key=lambda item: item.name)
    except OSError as exc:
        return DiscoveryReport((), (PluginIssue(str(location), str(exc)),))
    for package in entries:
        # Hidden directories are used for staging/rollback and must never be discovered.
        if package.name.startswith(".") or (not package.is_dir() and not package.is_symlink()):
            continue
        try:
            manifest = read_manifest(package)
            found[manifest.id] = manifest
        except (PluginError, OSError) as exc:
            issues.append(PluginIssue(package.name, str(exc)))

    invalid: dict[str, str] = {}

    checked: set[str] = set()

    def visit(plugin_id: str) -> None:
        # Iterative DFS prevents a manifest dependency chain exhausting Python's
        # recursion limit; memoization also avoids repeated work in shared graphs.
        stack = [(plugin_id, iter(found[plugin_id].dependencies))]
        active = {plugin_id}
        while stack:
            current, children = stack[-1]
            dependency = next(children, None)
            if dependency is None:
                checked.add(current)
                active.remove(current)
                stack.pop()
                continue
            if dependency.id not in found:
                raise PluginError(f"missing plugin dependency: {dependency.id} {dependency.version}")
            installed = found[dependency.id]
            if installed.version != dependency.version:
                raise PluginError(f"dependency {dependency.id} requires {dependency.version}, found {installed.version}")
            if dependency.id in invalid:
                raise PluginError(f"dependency {dependency.id} is unavailable: {invalid[dependency.id]}")
            if dependency.id in active:
                chain = [item[0] for item in stack] + [dependency.id]
                raise PluginError(f"dependency cycle: {' -> '.join(chain)}")
            if dependency.id not in checked:
                active.add(dependency.id)
                stack.append((dependency.id, iter(installed.dependencies)))

    for plugin_id in found:
        try:
            visit(plugin_id)
        except PluginError as exc:
            invalid[plugin_id] = str(exc)
            issues.append(PluginIssue(plugin_id, str(exc)))
    return DiscoveryReport(tuple(plugin for key, plugin in found.items() if key not in invalid), tuple(issues))


class PluginRegistry:
    """User enable/disable preferences for validated metadata; never an execution host.

    Callers may persist ``preferences()`` in OS user settings. A missing/invalid plugin
    is never restored as enabled. Dependencies must be enabled explicitly first.
    """

    def __init__(self, report: DiscoveryReport, enabled: Iterable[str] = ()) -> None:
        self.plugins: Mapping[str, PluginManifest] = {item.id: item for item in report.plugins}
        self.issues = report.issues
        requested = set(enabled)
        self._enabled: set[str] = set()
        # Multiple passes restore persisted flags in dependency order.
        while True:
            ready = {key for key in requested - self._enabled if key in self.plugins
                     and all(dep.id in self._enabled for dep in self.plugins[key].dependencies)}
            if not ready:
                break
            self._enabled.update(ready)

    def is_enabled(self, plugin_id: str) -> bool:
        return plugin_id in self._enabled

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        if plugin_id not in self.plugins:
            raise PluginError(f"plugin is unavailable: {plugin_id}")
        if enabled:
            missing = [dep.id for dep in self.plugins[plugin_id].dependencies if dep.id not in self._enabled]
            if missing:
                raise PluginError(f"enable required plugins first: {', '.join(missing)}")
            self._enabled.add(plugin_id)
        else:
            self._enabled.discard(plugin_id)
            # Disable transitive dependents rather than leave an invalid active set.
            while True:
                broken = {key for key in self._enabled
                          if any(dep.id not in self._enabled for dep in self.plugins[key].dependencies)}
                if not broken:
                    break
                self._enabled.difference_update(broken)

    def preferences(self) -> dict[str, bool]:
        return {key: key in self._enabled for key in sorted(self.plugins)}
