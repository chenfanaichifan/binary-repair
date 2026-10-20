# agent

Per-branch archive of the member workstreams, created with `git subtree add`.
Each subfolder keeps the history of its source branch; the original branch is
not rewritten.

| Folder | Source branch | Contents |
|---|---|---|
| `member-1-interface-reply/` | `member-1-interface-reply` | §4.1 interface reply plus the verification slice it was based on |
| `member-3-route-a/` | `member-3-route-a` | Route A isolated analysis docs and scripts |
| `member-4-verification/` | `member-4-verification` | Acceptance engine, verification design, handoffs, tests |
| `member-5-deepseek-schema/` | `member-5-deepseek-schema` | Route B / AI candidate provider, schemas, SQLite schema |

Each folder is a full branch tree. To run a workstream, `cd` into its folder and
follow that folder's own README; Each workstream lives only on its branch.
