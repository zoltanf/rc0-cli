# Output formats

Every `rc0` command supports `--output` / `-o`. Because it is a **global flag**,
it must appear **before** the subcommand name:

```bash
rc0 -o json zone list --all   # correct
rc0 zone list --all -o json   # WRONG — will error
```

| `-o` value | When to use |
|------------|-------------|
| `table`    | Interactive terminal use (default on a TTY). Rich-rendered. |
| `json`     | Machine input. Always valid JSON. Compact with `--compact` (coming). |
| `yaml`     | Human-readable structured input for apply-style workflows. |
| `csv`      | Spreadsheet import. Quoted per RFC 4180. |
| `tsv`      | Column-friendly pipes. No quoting. |
| `plain`    | `grep`-friendly. One record per line, space-separated. |

## TTY fallback

If `-o` is omitted and stdout is **not** a TTY, `rc0` renders `plain` instead
of `table`. This means `rc0 zone list | cut -f1` works without `-o plain`.

## Rules for agents

1. **Machine output never writes to stderr** unless it's an error.
2. **No ANSI codes in non-table formats**, ever.
3. **Errors in `-o json`** are JSON on stderr (see `rc0 help exit-codes`).
4. **Exit codes are authoritative**. A command never exits 0 on failure.
5. **Deterministic ordering.** JSON arrays are ordered by a documented key
   (usually `domain` or `id`).
