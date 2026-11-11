# Plugin manifest v1 (declarative, inert)

The workbench discovers connectors and plugins from one directory. Manifests
are inert JSON: the GUI reads them, validates them and renders them. No manifest
field causes code to be imported or executed.

## Location

| Source | Value |
|---|---|
| Default | `plugins/` (tracked examples) |
| Override | `BINARYREPAIR_PLUGIN_DIR` |
| API | `GET /api/connectors` returns `plugins[]`, `warnings[]`, `plugin_dir_source` |
| Page | `GET /connectors` |

## Shape

```json
{
  "id": "review-hook",
  "name": "Review hook",
  "kind": "connector",
  "description": "Posts a review comment when a bundle is exported.",
  "enabled": true
}
```

| Field | Required | Rule |
|---|---|---|
| `id` | yes | lowercase `[a-z][a-z0-9._-]{1,63}`, unique per directory |
| `name` | yes | non-empty ASCII text |
| `kind` | yes | non-empty ASCII text (`connector`, `hook`, `exporter`, ...) |
| `description` | yes | non-empty ASCII text |
| `enabled` | no | boolean, defaults to `false`; displayed, not executed |
| `docs_url` | no | ASCII `http(s)` link shown on the plugin card |

Invalid JSON, a non-ASCII filename, a bad id or non-ASCII text is skipped and
reported in `warnings[]`. Warnings are page text, never a silent success.

## Why inert

The acceptance model forbids a manifest from changing verdicts, writing jobs or
executing code. A future Python loader would implement the protocol in
`app/services/connectors.py`:

```python
class Plugin(Protocol):
    manifest: Mapping[str, Any]
    def probe(self) -> str: ...
```

Until such a loader exists, `GET /api/connectors` reports the manifests and the
page states that no code was loaded.
