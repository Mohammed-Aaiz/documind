# Path migration note — historical phase directories

**Status: INFORMATIONAL.** No code change is required; this only translates
paths cited inside historical architecture / decision records.

At some point before 2026-09-30 the phase directories were moved under a
`phases/` parent. Documents written before that move still cite the old
top-level paths, so a path quoted in an older record may not resolve on disk
today.

## Mapping

| Path cited in old documents | Actual path on disk today |
|---|---|
| `backend/phase4f/...` | `backend/phases/phase4f/...` |
| `backend/phase4f_gpu/...` | `backend/phases/phase4f_gpu/...` |
| `backend/phase4d/...` | `backend/phases/phase4d/...` |
| `backend/phase4e/...` | `backend/phases/phase4e/...` |

Everything below the prefix is unchanged — e.g. the frozen benchmark

```
backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl      (as cited, stale)
backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl   (actual)
```

is the **same file**, sha256
`1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`.

## How many documents are affected

As of 2026-09-30, **34 files** under `backend/architecture/` still cite a
stale `backend/phase4*` path (30 of them under `architecture/phase4f_6/`). They
were deliberately **not** mass-edited: they are historical evidence records
whose provenance value depends on being left as written. This single note is
the translation layer (audit finding **D-1**).

## Re-checking

From `backend/`:

```bash
grep -rl "backend/phase4" architecture/ --include="*.md" --include="*.json" \
    --include="*.txt" | grep -v phase4f_6 | wc -l
```

A non-zero count is expected and is not a defect — it means those records still
use the historical prefix. Replace the prefix with `backend/phases/` to resolve
any quoted path.
