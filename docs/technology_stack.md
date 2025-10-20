# Technology Stack

* **Language:** Python 3.11–3.12
* **CLI:** `argparse`
* **Encoding Algorithms:** Base-4 Direct, Huffman-4, GC-Balanced
* **Error Correction:** Triple-Repeat, Hamming(7,4), Reed-Solomon
* **GUI Framework:** `Flet`
* **Plotting:** `Matplotlib`

## Optional Dependencies

GeneCoder supports several additional FEC back-ends that are loaded only when
installed:

- **LDPC** via `pyldpc` – experimental low-density parity-check codes.
- **Fountain** via `pyfinite` – simple rateless encoding with parity chunks.
- **RaptorQ** via `raptorq` – high-throughput fountain-style repair symbols.

Install these with Poetry extras. The former FrameD integration has been
removed because the upstream project is unmaintained on modern platforms; the
LDPC, Fountain and RaptorQ extras cover the advanced FEC use cases previously
served by FrameD.

## Web Components

The toolkit bundles a lightweight FastAPI server and a React/Three.js helix
viewer built with **Vite**. The frontend lives under `web/helix-ui` and is served
by the FastAPI app or embedded in the Flet GUI. Node.js and npm are required to
build the React app.

## Continuous Integration

GitHub Actions run linting, tests and security scans. Workflows use a merge queue
so each pull request must pass the `python-ci` job before merging. Documentation
or comment-only changes skip heavy jobs with `scripts/only_comments_changed.py`.
A CycloneDX SBOM is produced after successful builds.
