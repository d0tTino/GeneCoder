# GeneCoder

## 1. Vision & Core Concept

Create an open, educational software toolkit that **encodes arbitrary text or binary files into simulated DNA sequences** and decodes them back, illustrating the promises and challenges of DNA data storage without touching real wet‑lab biology.

*Why it matters*: DNA offers theoretical densities far beyond magnetic or silicon media (\~10^18 bytes per gram). By simulating the pipeline, learners grasp compression, channel coding, bioinformatics file formats, and the error‑prone reality of molecular data.

---

## 2. Naming – Alternate Title Ideas

| Rank | Candidate     | Rationale                                          |
| ---- | ------------- | -------------------------------------------------- |
| ⭐    | **DNA‑Forge** | Evokes crafting & transformation of data into DNA. |
| 2    | HelixVault    | Focus on archival/storage angle.                   |
| 3    | GeneCoder     | Straightforward, classroom‑friendly.               |
| 4    | CodonCache    | Playful, hints at caching data in codons.          |
| 5    | HelixHub      | Short, brandable, community vibe.                  |

---

## 3. Feature Breakdown (Phase 1 → Phase 3)

### 3.1 Input Handling

* **Text (UTF‑8)** via CLI arg or drag‑and‑drop (later GUI).
* **Binary files** ≤ 5 MB for MVP (scales later).
* Auto‑detect mime‑type & display summary (size, entropy).

### 3.2 Encoding Engine

| Scheme                  | Educational Value                                                      | Status  |
| ----------------------- | ---------------------------------------------------------------------- | ------- |
| **Huffman‑4** (primary) | Introduces variable‑length coding & optimality; maps bits → {A,T,C,G}. | MVP     |
| Base‑4 direct           | Shows naïve 2 bits/nt mapping, baseline.                               | MVP     |
| Ternary + parity        | Demonstrates trade‑offs in alphabet size vs. density.                  | Phase 2 |
| GC‑balanced mapping     | Shows biochemical constraints (avoid homopolymers).                    | Phase 3 |

**Huffman‑4 Mapping Sketch**

1. Build classic binary Huffman tree.
2. Re‑encode resulting codewords in base‑4 (00→A, 01→C, 10→G, 11→T).
3. Concatenate; optionally pad with terminal symbol to reach full codon.

### 3.3 Output

* Raw DNA string (stdout or clipboard).
* **FASTA** file export: `>filename|scheme=HUF4|len=1234|date=2025‑05‑20`.

### 3.4 Decoding Engine

* Reverse mapping table persisted in FASTA header or sidecar json.
* Detect illegal bases; raise descriptive error.

### 3.5 Error‑Resilience (Simulated)

| Technique                                       | Difficulty | Pedagogical Point       |
| ----------------------------------------------- | ---------- | ----------------------- |
| Parity nucleotide every *k* nts                 | Easy       | Error detection.        |
| Triple‑repeat voting                            | Medium     | Redundancy vs. density. |
| (Phase 3) Simplified Hamming(7,4) in quaternary | Hard       | Forward‑error‑corr.     |

### 3.6 Analysis & Metrics

* **Compression ratio** = original\_bytes / encoded\_nts·0.25.
* **Bits per nt** achieved.
* Histogram of codeword lengths (optional matplotlib).

---

## 4. UI / UX Recommendation

| Option                            | Library          | Effort | Pros                                | Cons                              |
| --------------------------------- | ---------------- | ------ | ----------------------------------- | --------------------------------- |
| **CLI First (argparse / click)**  | Built‑in / click | ⭐ Low  | Fast to ship, scriptable, testable. | Less friendly for non‑tech users. |
| Minimal GUI (Tkinter or **Flet**) | Std / pip        | Medium | Cross‑platform, drag‑and‑drop.      | UI polish time.                   |

📌 **Recommendation**: Ship CLI MVP. Add Flet‑based GUI in Phase 2 (browser‑rendered, Python‑only).

---

## 5. Technical Stack

* **Language**: Python ≥ 3.10 — ample libraries, your fluency.
* **Core Libs**

  * `heapq` for Huffman tree.
  * `bitarray` for bit‑level packing.
  * `pathlib`, `argparse`/`click` for I/O.
* **Optional**

  * `numpy` & `matplotlib` for metric plots.
  * `rich` for colourful CLI progress.
* **Dev Tools**: `pytest`, `black`, `ruff`, GitHub Actions CI.

Your rig (7800X3D | 32 GB RAM | NVMe) easily handles multi‑GB in memory; cap demo files to highlight speed.

---

## 6. Efficiency Analysis

| Aspect                 | Insight                                                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Theoretical limit**  | 2 bits/nt with 4‑base alphabet (Shannon).                                                                                    |
| **Huffman efficiency** | Approaches entropy of input; overhead from variable‑length coding & padding; expect 1.6–1.9 bits/nt on typical English text. |
| **Complexity**         | Building Huffman tree O(n log σ); encoding/decoding O(n).                                                                    |
| **Perf factors**       | File size, entropy (affects tree depth), Python interpreter overhead.                                                        |
| **Optimizations**      |                                                                                                                              |

* Cache frequency table with `collections.Counter`.
* Use `bitarray` instead of Python strings for interim bitstream.
* Stream encode large files in chunks to bound memory.
* Parallel decode with `concurrent.futures` (file sections). |

---

## 7. Monetization Paths

1. **Freemium**: CLI & 2 schemes free; GUI, GC‑balancing, batch mode in "DNA‑Forge Pro" (\$10‑15).
2. **Educational Site License**: bundle lesson plans + instructor dashboard.
3. **Paid Workshops / Consulting**: demo biotech‑adjacent startups.
4. **Patreon/GitHub Sponsors**: behind‑the‑scenes dev diaries, vote on new features.
5. **Niche verticals**: puzzle designers, ARG creators, digital art embeds.

---

## 8. Development Roadmap

### MVP (Weeks 1‑2)

* ☐ Text + binary input via CLI.
* ☐ Base‑4 & Huffman‑4 encode/decode.
* ☐ FASTA export.
* ☐ Basic metrics printout.

### Phase 2 (Weeks 3‑4)

* ☐ Parity error detection.
* ☐ Flet GUI prototype (drag‑drop).
* ☐ Plotting dashboard.

### Phase 3 (Month 2)

* ☐ GC‑balanced encoder.
* ☐ Simplified Hamming ECC.
* ☐ Batch processing & multithreading.

### Phase 4 (Stretch)

* ☐ Plug‑in API for community schemes.
* ☐ Cloud notebook demo (Binder / Codespaces).

---

## 9. Modular Architecture

```
/ dna_forge
├── cli.py          # entry‑point
├── core/
│   ├── encode.py   # strategy pattern for schemes
│   ├── decode.py
│   ├── schemes/
│   │   ├── base4.py
│   │   └── huff4.py
│   └── errors.py   # parity, ecc
├── io/
│   ├── fasta.py
│   └── detect.py   # mime & helpers
├── metrics.py      # compression stats
├── gui/            # added later
└── tests/
```

---

## 10. Documentation & QA

* Docstring every public function (Google style).
* `README.md` with quick‑start, examples, GIF.
* Unit tests ≥ 80 % coverage (pytest‑cov).
* GitHub Actions: lint, test on ubuntu‑latest & windows‑latest.

---

## 11. Next Steps for You

1. Scaffold repo structure (`cookiecutter` recommended).
2. Implement frequency counter + Huffman tree.
3. Write CLI encode/decode commands.
4. Add metrics and FASTA writer.
5. Push to GitHub → share link for review!

> **Tip**: Start tiny ("hello world" string), validate round‑trip before handling files.

---

*Crafted for George Pike, May 20 2025. Happy forging!*
