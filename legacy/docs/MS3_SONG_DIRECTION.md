# MS3 — song-first source direction

Catalog `ms3-song-12d32fcdc64c14ff`. All 465 original MIDI stems supply 48 arrangements in eight blocks. The 40 looping song edits use 216 delivery chunks, plus eight short fanfares. There are 181,635 continuous score notes and 182,091 exported chunk entries (sustains crossing storage boundaries occur in both portable MIDI chunks).

## Musical policy

Follow each source composition in order. Keep all source sections that pass the documented driving-beat proxy. Preserve an isolated four-bar break between driving sections; remove longer non-driving runs and non-driving intros/outros in the maze. Staging retains the full calm composition, including beatless sections. No ranked motif snippets, invented melody, per-chunk lead reassignment, added fill, or competing-voice thinning is applied. Canonical D-Dorian cleanup, nine-instrument routing, duplicate cleanup and polyphony constraints remain.

Each arrangement is rendered once, including held voices and filter motion across internal boundaries. The resulting PCM is split for bounded delivery. This distinction is essential: a storage chunk is not a new performance. Portable per-chunk MIDI ties are inspection/export data; the renderer uses the intact full-song score.

Beat classification is an auditable percussion heuristic, not a listening certificate. “Source retained” measures time after canonical note routing, not the percentage of every original MIDI event or a claim of artistic quality. All detected driving cells are retained; long non-driving sections may account for a substantial share of a source song.

| Arrangement | Song seconds | Delivery chunks | Source time retained |
| --- | ---: | ---: | ---: |
| a-boss | 81.2 | 3 | 50.4% |
| a-t0 | 155.1 | 6 | 100.0% |
| a-t1 | 155.1 | 6 | 77.6% |
| a-t2 | 118.2 | 4 | 78.8% |
| a-t3 | 103.4 | 4 | 69.6% |
| b-boss | 155.1 | 6 | 64.9% |
| b-t0 | 142.2 | 5 | 100.0% |
| b-t1 | 169.8 | 6 | 84.0% |
| b-t2 | 217.8 | 8 | 97.0% |
| b-t3 | 199.4 | 7 | 89.2% |
| c-boss | 81.2 | 3 | 56.6% |
| c-t0 | 142.2 | 5 | 100.0% |
| c-t1 | 162.5 | 6 | 71.5% |
| c-t2 | 110.8 | 4 | 77.2% |
| c-t3 | 147.7 | 5 | 64.0% |
| d-boss | 112.6 | 4 | 75.3% |
| d-t0 | 151.4 | 6 | 100.0% |
| d-t1 | 132.9 | 5 | 90.3% |
| d-t2 | 132.9 | 5 | 81.4% |
| d-t3 | 120.0 | 5 | 80.7% |
| e-boss | 132.9 | 5 | 86.2% |
| e-t0 | 153.2 | 6 | 100.0% |
| e-t1 | 140.3 | 5 | 91.0% |
| e-t2 | 140.3 | 5 | 91.1% |
| e-t3 | 132.9 | 5 | 80.9% |
| f-boss | 132.9 | 5 | 85.4% |
| f-t0 | 201.2 | 7 | 100.0% |
| f-t1 | 103.4 | 4 | 67.7% |
| f-t2 | 118.2 | 4 | 76.6% |
| f-t3 | 101.5 | 4 | 66.5% |
| g-boss | 103.4 | 4 | 67.1% |
| g-t0 | 153.2 | 6 | 100.0% |
| g-t1 | 120.0 | 5 | 80.2% |
| g-t2 | 123.7 | 5 | 81.0% |
| g-t3 | 125.5 | 5 | 81.4% |
| h-boss | 214.2 | 8 | 96.6% |
| h-t0 | 238.2 | 9 | 100.0% |
| h-t1 | 192.0 | 7 | 90.9% |
| h-t2 | 199.4 | 7 | 93.9% |
| h-t3 | 206.8 | 7 | 92.2% |

Exact source windows, omissions, per-cell beat evidence, original file hashes and full-score fingerprints are in `MS3_SONG_AUDIT.json`; intact note timelines are in `MS3_SONG_SCORE.json`. The requested YouTube video remains inaccessible; no video-specific arrangement method is claimed.
