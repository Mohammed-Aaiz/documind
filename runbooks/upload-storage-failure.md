# Incident: Upload storage failure (documents cannot be saved)

## Purpose
Recover when uploads fail because the local upload directory is missing,
unwritable, full, or files vanish after upload.

## Impact
New uploads fail or are stored without readable files; existing documents
whose files disappear can be listed but not re-extracted. Database records may
still be created for failed uploads, so `GET /api/documents` can show entries
in `error` state. Retrieval for affected documents degrades.

## Symptoms
- `POST /api/documents/upload` returns 500 (exception during save/extraction).
- Upload returns 201 but the document ends with `status: "error"`,
  `chunk_count: 0` (`backend/documents/routes.py` sets this on extraction
  failure).
- Uvicorn log shows `OSError`/`PermissionError` on write, or PyMuPDF errors
  opening the stored file.
- 413 responses mean the file exceeded `MAX_UPLOAD_SIZE_MB` (default 50 MB) —
  that is policy, not an incident.

## Severity
P2

## Immediate Actions
1. Identify the configured directory: `UPLOAD_DIR` in `backend/config.py`
   (default `./uploads`, relative to the backend working directory →
   `backend/uploads/`). The directory is auto-created at startup
   (`main.py` lifespan).
2. Check disk space and permissions on that directory.
3. Stop uploading (do not retry-spam) until the cause is known.

## Diagnosis
1. **Directory exists/writable?** As the user running uvicorn, verify write
   access to `UPLOAD_DIR`. The lifespan hook creates it with
   `mkdir(parents=True, exist_ok=True)`, but permissions can still be wrong.
2. **Disk full?** A full volume makes `save_upload`
   (`backend/storage/file_store.py`) raise on `write_bytes`.
3. **Status `error` with the file present?** Extraction failed, not storage:
   check `backend/documents/processing.py` extractors (PDF via PyMuPDF,
   DOCX via python-docx, TXT as UTF-8). Corrupt/empty files produce
   `status: "error"` rows by design.
4. **Empty upload (400 "Uploaded file is empty")** or unsupported extension
   (400 listing allowed `pdf/docx/txt`) are validation responses, not
   incidents.
5. **Files missing after restarts?** `uploads/` is gitignored and not backed
   up by anything in the repo — files only exist on this host's disk.

## Recovery
1. Fix the filesystem cause (free space, correct permissions/ownership,
   remount volume).
2. Restart the backend if the directory had to be recreated (startup hook
   ensures it exists).
3. For documents left in `status: "error"`: there is **no re-upload endpoint**
   — the user must re-upload the file once storage is healthy. Verify with one
   small test upload first.

## Validation
- A small TXT upload returns 201 with `status: "ready"` and
  `embeddingStatus: "ready"`.
- The stored file exists under `UPLOAD_DIR` with a UUID filename
  (extension preserved).
- `GET /api/documents` lists the new document.

## Rollback
No verified rollback mechanism found. Storage changes are host-level
(permissions/space); revert whatever filesystem change was made.

## Escalation
- If the volume is failing or files are lost on a persistent basis, escalate
  to whoever manages the host. **REQUIRES HUMAN APPROVAL** for any restore of
  uploaded files — the repo contains no backup tooling.

## Do Not
- Do not delete `uploads/` contents to "clean up" — DB rows reference those
  files by path (`documents.stored_path`); deleting breaks existing documents
  and `DELETE` flows.
- Do not raise `MAX_UPLOAD_SIZE_MB` as a fix for failures.
- Do not switch to a different storage backend during an incident.

## Root Cause Follow-Up
- Local-disk storage has no redundancy or backup in this repo; decide whether
  that is acceptable for production (see `DOCUMIND_PROJECT_CONTEXT.md` §9 —
  local storage is the stated MVP choice).
- Orphaned rows (DB record with missing file) currently surface only as
  extraction errors; a reconciliation check would prevent repeat confusion.
