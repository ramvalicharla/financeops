#!/usr/bin/env python3
"""
WeasyPrint smoke test - run in the Linux deployment container.
Exits 0 if PDF generation works, 1 if it fails.
Usage: python scripts/smoke_pdf.py
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    print("WeasyPrint smoke test starting...")
    try:
        import weasyprint
    except ImportError:
        print("FAIL: weasyprint not installed")
        return 1

    html_content = """
    <!DOCTYPE html>
    <html>
    <head><style>
        body { font-family: sans-serif; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; }
        td, th { border: 1px solid #ccc; padding: 8px; }
    </style></head>
    <body>
        <h1>FinanceOps Board Pack</h1>
        <p>Smoke test - generated at runtime</p>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Revenue</td><td>1,000,000</td></tr>
            <tr><td>EBITDA</td><td>250,000</td></tr>
        </table>
    </body>
    </html>
    """

    try:
        pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
    except OSError as exc:
        print(f"FAIL: WeasyPrint OSError (missing system libs): {exc}")
        print("Install: libgobject-2.0-0 libpango-1.0-0 libcairo2")
        return 1
    except Exception as exc:  # pragma: no cover - defensive smoke path
        print(f"FAIL: WeasyPrint unexpected error: {exc}")
        return 1

    if not pdf_bytes:
        print("FAIL: write_pdf() returned empty bytes")
        return 1

    if not pdf_bytes.startswith(b"%PDF"):
        print(f"FAIL: output does not look like a PDF (first 8 bytes: {pdf_bytes[:8]!r})")
        return 1

    size_kb = len(pdf_bytes) / 1024
    print(f"OK: PDF generated successfully ({size_kb:.1f} KB)")
    print(f"OK: PDF header: {pdf_bytes[:8]!r}")

    out_path = os.environ.get("SMOKE_PDF_OUTPUT", "")
    if out_path:
        with open(out_path, "wb") as file_obj:
            file_obj.write(pdf_bytes)
        print(f"OK: PDF written to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
