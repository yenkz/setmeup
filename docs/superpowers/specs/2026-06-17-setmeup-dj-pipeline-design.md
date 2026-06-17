# setmeup — DJ Music Acquisition & Library Pipeline

**Date:** 2026-06-17
**Status:** Approved design (pre-implementation)

## 1. Purpose

A personal command-line tool for a DJ to acquire music in bulk from Soulseek and
turn the messy results into a clean, deduplicated, consistently named library.

The tool runs an end-to-end pipeline:

1. **Acquire** — search Soulseek (via slskd) and download tracks in parallel from a
   wantlist or imported playlist.
2. **Process** — fingerprint each download, resolve canonical metadata, detect
   duplicates, and compute a clean filename.
3. **Organize** — copy the best copy of each track into a flat `Library/` folder
   using the canonical name.

The output filename format is **`Artist - Track - Version`** (e.g.
`Daft Punk - Around the World - Extended Mix`), falling back to
`Artist - Track` when no version/mix can be determined.

## 2. Goals & Non-Goals

### Goals
- Bulk, parallel acquisition that is **resumable** and survives partial failures.
- Reliable **deduplication** by acoustic fingerprint, keeping the highest-quality copy.
- Consistent, filesystem-safe **canonical naming**.
- **Preserve original downloads** so they keep seeding to the Soulseek community.
- Hands-off operation suitable for large batches, scriptable from the CLI.

### Non-Goals (YAGNI)
- No GUI/TUI/web dashboard (slskd's own web UI covers raw transfer monitoring).
- No audio transcoding or format conversion.
- No genre/BPM/key analysis or crate management (Rekordbox owns that).
- No writing/repairing tags inside files (initial scope — can be added later).
- No speaking the raw Soulseek protocol; we drive **slskd** via its REST API.

## 3. Decisions (locked)

| Area | Decision |
|---|---|
| Language | Python |
| Soulseek integration | **slskd** running in Docker; tool drives it via REST API |
| Input modes | Batch **wantlist file** + **playlist/crate import** |
| Playlist sources | Spotify, Rekordbox, YouTube/YT Music, CSV/plain text (pluggable adapters) |
| Orchestration | Staged pipeline (`fetch`/`process`/`organize` + `run`) backed by SQLite state |
| Metadata source | Hybrid: **AcoustID fingerprint → embedded tags → filename** |
| Version handling | Extracted separately against a mix vocabulary; **omitted** when unknown |
| Dedupe | Chromaprint fingerprint; **keep highest quality**, others not promoted |
| Format priority | **WAV/AIFF → FLAC → MP3-320**; reject below 320 kbps by default |
| Library/Complete relationship | **Copy** into Library; `Complete/` preserved read-only for seeding |
| Library layout | Flat folder, canonical filenames |
| Interface | CLI (`Typer`) with rich progress (`Rich`) |

## 4. Architecture

### 4.1 Pipeline & data flow

```
playlist / wantlist        ──►  fetch     ──►  slskd (Docker)  ──►  Complete/  (preserved,
   (source adapters)                              downloads          read-only, keeps seeding)
                                                                          │  (copy)
Complete/  ──►  process  ──►  fingerprint → resolve metadata → dedupe → canonical name
                                                                          │  (copy)
                              organize  ──►  Library/   (flat, "Artist - Track - Version.ext")
                                         └►  Trash/     (Library evictions only, recoverable)
```

- `Complete/` is **never modified or deleted** by the tool. Originals stay so slskd
  continues sharing them.
- Files are **copied** into `Library/` (copy → checksum-verify). No atomic-move path.
- `Trash/` only ever receives files **evicted from the Library** when a higher-quality
  copy replaces an existing entry; even those are recoverable, and the original still
  lives in `Complete/`.

### 4.2 State store (SQLite)

A single `setmeup.db` is the backbone that makes batches resumable and provides the
dedupe index.

- **`tracks`** — one row per wanted/seen track: source, original query,
  resolved `artist`/`title`/`version`, `status`, slskd transfer id, file path,
  fingerprint, AcoustID id, quality score, timestamps, last error.
  State machine: `wanted → searching → downloading → downloaded → fingerprinted →
  resolved → deduped → organized`, with terminal `failed` / `skipped_duplicate`.
- **`library_index`** — fingerprint → Library file path + quality score, for fast
  "is this already in my Library (and is it better)?" lookups.
- **`runs`** — audit record of each invocation (optional, for `status`/history).

All DB access is confined to the `state/` module; nothing else touches SQLite. Writes
are transactional; every stage is idempotent and keyed on `status`, so re-running is
always safe.

### 4.3 Module layout

Each module has one responsibility and a clean interface.

| Module | Responsibility |
|---|---|
| `config.py` | Load config (paths, slskd URL+key, AcoustID/Spotify keys, format priority, concurrency, thresholds) and secrets from `.env`. |
| `state/` | SQLite schema + repository functions (`tracks`, `library_index`, `runs`). Sole owner of DB access. |
| `sources/` | Playlist adapters behind a `PlaylistSource` interface emitting `WantlistEntry(artist, title, version?, album?, source_ref)`. Impls: `wantlist`, `csv`, `rekordbox`, `spotify`, `youtube`. |
| `slskd/` | Thin async REST client: search, enqueue download, poll transfer status. |
| `acquire/` | `fetch` orchestration: entries → search → select best result → enqueue → record state. |
| `audio/` | Fingerprinting (`fpcalc`/`pyacoustid`), metadata resolution (AcoustID → tags via `mutagen` → filename), version extraction. |
| `dedupe.py` | Quality scoring + duplicate resolution (keep-best). |
| `organize/` | Copy+verify into Library, Library-eviction Trash handling, name collisions. |
| `cli.py` | `fetch` / `process` / `organize` / `run` / `status` / `retry` / `init` with Rich progress. |

## 5. Stage detail

### 5.1 Acquisition (`fetch`)

**Sources → normalized wantlist.** Every adapter implements `PlaylistSource` and emits
`WantlistEntry`, so downstream code is source-agnostic. Phasing by difficulty:
- Offline (first): `wantlist` (plain `Artist - Track` lines, `#` comments), `csv`,
  `rekordbox` (collection/playlist XML).
- Auth/network (later): `spotify` (OAuth client-credentials + playlist API),
  `youtube` (playlist via `yt-dlp` metadata).

**Search + result selection.** For each entry, issue slskd searches, collect file
responses from all peers, score every candidate, and pick the best while keeping a
ranked fallback list:

1. **Format/quality tier** — configurable priority. Default
   `WAV/AIFF > FLAC > MP3-320 > (reject below 320 kbps)`.
2. **Match confidence** — fuzzy token match of filename/path vs `artist + title`;
   reject below a threshold so we don't grab the wrong track or an unwanted remix.
3. **Peer health** — prefer free upload slot, higher speed, shorter queue.
4. **Sanity** — file size vs expected duration to skip previews/corrupt stubs.

**Parallelism & resilience.** Searches and download-enqueues run under bounded
concurrency (asyncio semaphores); slskd manages the actual transfers. Each enqueue
stores the transfer id + expected Complete path in SQLite; status is polled. On
stall/timeout/no-slot/failure, fall back to the next-best candidate; if all fail, mark
`failed` for a later `retry` run. Entries already `downloaded`/in-Library (matched by
normalized artist+title) are skipped before searching, so re-running a wantlist is cheap.

### 5.2 Processing (`process`)

**Fingerprint once.** Each download gets a Chromaprint fingerprint
(`fpcalc`/`pyacoustid`, decoding WAV/AIFF/FLAC/MP3 via ffmpeg), stored in SQLite and
reused for both lookup and dedupe.

**Resolve metadata (hybrid, in priority order):**
1. **AcoustID** — fingerprint+duration → MusicBrainz recording → authoritative
   `artist` + `title`. Rate-limited, cached by fingerprint.
2. **Embedded tags** (`mutagen`) — fallback when AcoustID isn't confident. (Weak for
   WAV/AIFF, which carry poor/no tags — those lean on fingerprint + filename.)
3. **Filename parsing** — last resort; split on ` - ` with heuristics.

**Version extraction (special-cased).** Detected separately from title
parentheticals/brackets and tag fields, matched against a known mix vocabulary
(*Original Mix, Extended Mix, Radio Edit, Club Mix, Dub, Instrumental, Acapella, VIP,
Edit, Re-Edit, Bootleg, "<X> Remix"*, …). The version token is stripped from the title
(keeping the title clean) and placed in the Version slot. **When no version is
detected, it is omitted** and the name is `Artist - Track`.

**Dedupe (keep-best).** Files with matching fingerprints are grouped within the
incoming batch *and* against `library_index`. Each gets a quality score
(format tier → bitrate → sample rate → completeness/duration). The highest score wins.
Because genuinely different versions have different fingerprints, Extended vs Original
are never falsely merged. See §6 for the copy-model behavior of "losers".

**Canonical name.** `Artist - Track - Version` (or `Artist - Track`), sanitized for the
filesystem (strip illegal characters, collapse whitespace). Distinct tracks that would
collide get a small discriminator suffix.

### 5.3 Organize (`organize`)

Copies dedupe winners from `Complete/` into the flat `Library/` under the canonical
filename (copy → checksum-verify). Updates `library_index`. Behavior follows the
copy model in §6.

## 6. Copy model & dedupe semantics

The tool **copies** and never moves/deletes originals:

- `Complete/` is preserved read-only — originals keep seeding to Soulseek.
- **Among newly downloaded files** with the same fingerprint: only the best is
  **promoted** (copied) into `Library/`; inferior copies are **not deleted**, just not
  promoted, and recorded as `skipped_duplicate`.
- **A new file beats an existing `Library/` entry**: copy the better one in and move the
  now-inferior *previously-promoted Library file* to `Trash/` (recoverable). The
  original in `Complete/` is untouched.
- `Trash/` therefore only ever holds Library evictions; nothing in it is irreplaceable.

Disk usage roughly doubles for promoted tracks (Complete copy + Library copy); this is
an accepted trade-off.

## 7. CLI & configuration

- **Commands:** `fetch [source]`, `process`, `organize`, `run` (chains the three),
  `status` (counts by state), `retry` (re-run `failed` tracks), `init` (scaffold config).
- **Config:** a TOML file for paths (`Complete/`, `Library/`, `Trash/`, staging),
  format priority, concurrency limits, match/dedupe thresholds; a `.env` for secrets
  (slskd API key, AcoustID key, Spotify credentials).
- **slskd:** documented `docker-compose` snippet with a shared volume so the container's
  Complete directory maps to the path the tool reads.

## 8. Safety & error handling

- **No hard deletion of originals.** Drops/evictions go to `Trash/` and are recoverable.
- **Copy + checksum-verify** for every file written into the Library.
- **External calls** (slskd, AcoustID, Spotify) get timeouts + retry/backoff; a failure
  is recorded per-track and never aborts the whole batch.
- **Idempotent, resumable stages** keyed on SQLite `status`; transactional writes.
- **AcoustID** rate-limited and cached by fingerprint.
- **Structured logging** to a file plus the Rich console.

## 9. Testing strategy (TDD)

- **Unit (pure logic):** source parsers (Rekordbox XML / CSV fixtures),
  filename + version parser (table of messy → expected), result-selection scorer,
  quality/dedupe scorer, canonical-name sanitizer.
- **Clients:** slskd / AcoustID / Spotify tested against mocked/recorded HTTP responses.
- **State:** repository functions against a temporary SQLite database.
- **Integration:** sample audio files flow through `process → organize`, asserting
  Library layout, Trash contents, and DB state — including the copy-not-move invariant
  (originals remain in `Complete/`).

## 10. Recommended build order

Each phase is independently useful.

1. **Skeleton** — `config` + SQLite `state` + CLI scaffold.
2. **`process` + `organize`** over a folder of existing files — delivers
   fingerprint/dedupe/rename value on the current Complete folder before slskd is wired.
3. **slskd client + `fetch`** with `wantlist`, `csv`, `rekordbox`.
4. **`run` chaining** + `status` / `retry`.
5. **`spotify` + `youtube`** sources.

## 11. Key external dependencies

- **slskd** (Dockerized Soulseek daemon, REST API).
- **Chromaprint / `fpcalc`** + `pyacoustid` (fingerprinting).
- **AcoustID API** (+ MusicBrainz) for metadata resolution (free API key).
- **`mutagen`** (tag reading).
- **`ffmpeg`** (audio decoding for fingerprinting).
- **`Typer`** + **`Rich`** (CLI + progress).
- **`yt-dlp`** (YouTube playlist metadata) and **Spotify Web API** (later phases).
