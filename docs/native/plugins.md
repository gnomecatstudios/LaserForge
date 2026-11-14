# Native plugin API foundation

The migration provides **manifest discovery and enable/disable preferences only**. It does not
import entrypoints, install dependencies, execute scripts, add live panels or expose hardware.
Enabling a discovered plugin records user intent; it does not execute that plugin in this stage.
No marketplace or automatic installation is included.

`native/laserforge_native/plugins.py` is independent of Qt and the core process. A caller supplies
an OS user-data plugin directory to `discover_plugins(root)`. Packages occupy one immediate
directory per plugin id. Each `plugin.json` is limited to 64 KiB. Errors remain visible in the
discovery report and do not prevent other valid plugins from appearing.

```text
plugins/
  community.shapes/
    plugin.json
    main.py
```

```json
{
  "manifestVersion": 1,
  "apiVersion": 1,
  "id": "community.shapes",
  "name": "Community shape generators",
  "version": "1.0.0",
  "entrypoint": "main.py",
  "capabilities": ["drawing-tools", "menus"],
  "dependencies": {}
}
```

Manifest and API versions are exact integers, currently 1. Package versions are exact
`major.minor.patch` strings. Plugin ids use lowercase letters/numbers separated by dots or
hyphens; the directory must match the id. Entrypoints must be existing relative files, without
absolute paths, Windows drive prefixes, parent traversal, backslashes or symbolic links. Package
directories and manifest files cannot be symbolic links. Unknown fields and duplicate keys are
rejected, so unsupported authority requests do not pass silently.

API 1 reserves these capability names:

| Capability | Intended future broker interface |
| --- | --- |
| `drawing-tools` | Register tools and submit proposed project edits or generated geometry |
| `import` | Parse user-selected content into validated project data |
| `export` | Produce output for a user-selected destination |
| `materials` | Contribute material metadata and suggested settings |
| `menus` | Register action metadata linked to broker commands |
| `panels` | Register constrained native panel descriptions |

Image processing, automation and custom workflows will need explicit future contracts rather
than general Python callbacks. Additional machine integrations need a separately reviewed driver
interface behind the machine service's preflight, state, cancellation and emergency-stop rules.
There is no `hardware`, `serial`, `usb`, `bluetooth`, raw core RPC or arbitrary shell capability.

## Dependencies and enablement

`dependencies` maps other plugin ids to exact versions, for example
`{"community.materials": "2.1.0"}`. API 1 does not install Python/npm packages or execute setup
hooks. Unknown/missing/incompatible dependencies and dependency cycles make a plugin unavailable;
failures propagate to dependents. Dependencies must be enabled explicitly before dependents.
Disabling a plugin also disables its transitive dependents. `PluginRegistry.preferences()` returns
a JSON-compatible id-to-boolean mapping for the native preference store; only validated available
plugins and enabled dependency sets can be restored. The API does not modify settings itself.

## Installation lifecycle

Independent installation/removal/update is a directory lifecycle. A future installer should unpack
to a hidden staging directory on the same filesystem, validate every archive path and manifest,
verify artifact provenance, then rename the complete directory into `<root>/<id>`. Hidden staging
directories are ignored by discovery. Never merge an untrusted archive over an existing package.
On update, stop its worker, retain the previous complete directory for rollback, replace atomically
where the platform permits, rediscover dependencies and require reconsent for new capabilities.
Removal should stop its worker, disable dependents and remove only that package directory; projects,
profiles, materials and preferences remain outside package code. These installer/worker operations
are design requirements and are not implemented by the metadata module.

## Permission boundary

**Manifest validation is not a security sandbox.** Arbitrary Python imported into the GUI or core
could access the filesystem, process APIs and hardware regardless of declared capabilities. This
stage avoids that problem by executing no plugin code. Before execution becomes available, define
a separate worker protocol with validated data-only messages, resource limits, explicit user file
grants and OS-level containment where required. A process boundary alone does not prevent direct
hardware access. Plugin contributions must become ordinary validated commands routed through the
core and machine safety service; plugins must never hold a transport or bypass job preflight.

Tests in `native/tests/test_plugins.py` cover discovery isolation, path/symlink rejection, API and
dependency compatibility, capability denial, enablement and malformed manifests. No test loads
third-party Python or opens a device.
