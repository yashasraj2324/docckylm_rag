"""Download the two reference papers used by the eval suite from arXiv.

    python -m evals.fetch_reference_pdfs

The PDFs are not committed (arXiv papers carry their own licenses and *.pdf is
gitignored). Downloads are verified against the SHA-256 of the exact versions
the golden dataset's page numbers were written for.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent

PAPERS = {
    "1512.03385v1.pdf": (
        "https://arxiv.org/pdf/1512.03385v1",
        "1e0651b6810ecba34a3dbc5b5b0209226f889004607c1f203540a48d64e5a93a",
    ),
    "1706.03762v7.pdf": (
        "https://arxiv.org/pdf/1706.03762v7",
        "bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697",
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(dest: Path = EVAL_DIR) -> int:
    status = 0
    for name, (url, digest) in PAPERS.items():
        path = dest / name
        if path.exists() and _sha256(path.read_bytes()) == digest:
            print(f"ok      {name} (already present, hash verified)")
            continue
        print(f"fetch   {name} <- {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "ai-notebooks-evals/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        if _sha256(data) != digest:
            print(f"ERROR   {name}: SHA-256 mismatch (got {_sha256(data)}). "
                  "arXiv may have re-rendered the PDF; page numbers in the dataset may shift.",
                  file=sys.stderr)
            status = 1
            continue
        path.write_bytes(data)
        print(f"ok      {name}")
    return status


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else EVAL_DIR))
