# OpenSprinkler Firmware — Issue Drafts

These issue drafts are ready to copy into GitHub.

---

## 1) Potential buffer overflow in `BufferFiller::emit_p`

**Title**
Potential buffer overflow in `BufferFiller::emit_p` due to unbounded writes

**Body**
`BufferFiller::emit_p` tracks buffer length/position, but several write paths are unbounded:
- direct `*ptr++` writes,
- `strcpy((char*)ptr, ...)` in `$S`,
- looped writes in `$F`.

Only some formatting paths use `snprintf`. This may overflow response buffers when emitted content exceeds remaining space.

**References**
- `opensprinkler_server.h` lines around `BufferFiller::emit_p`.

**Suggested fix**
- Enforce remaining-capacity checks on every write path.
- Replace `strcpy` and raw loop writes with bounded append helpers.
- Keep the buffer null-terminated after each append.

---

## 2) `readlink` result not null-terminated in `get_runtime_path()`

**Title**
`get_runtime_path()` uses `readlink` without guaranteed null-termination

**Body**
In `get_runtime_path()`, `readlink("/proc/self/exe", path, PATH_MAX)` is used, then `strrchr(path, '/')` is called.

`readlink` does not append a trailing `\0`, so subsequent C-string operations may read beyond the valid bytes.

**References**
- `utils.cpp` in `get_runtime_path()`.

**Suggested fix**
- Capture `ssize_t n = readlink(...)`.
- Validate `n > 0 && n < PATH_MAX`.
- Set `path[n] = '\0'` before any C-string operations.

---

## 3) Potential overflow in `get_filename_fullpath()`

**Title**
`get_filename_fullpath()` can overflow static `fullpath` buffer

**Body**
`get_filename_fullpath()` builds `fullpath` using `strcpy`/`strcat` into fixed `PATH_MAX` storage with no bounds checks.

A long `data_dir` + filename can exceed capacity and overflow the buffer.

**References**
- `utils.cpp` in `get_filename_fullpath()`.

**Suggested fix**
- Use `snprintf(fullpath, sizeof(fullpath), "%s/%s", ...)` with separator handling.
- Check truncation return values.
