#!/usr/bin/env python3
"""
Add PDF pages to an existing processed Read-Along book.

This script extracts pages from a PDF as images and creates the
pages.json index, enabling the page viewer in the web reader.

Usage:
    python scripts/add_pages.py <pdf_file> <output_folder>

Example:
    python scripts/add_pages.py "input/The Intelligent Investor.pdf" "output/readalong/The-Intelligent-Investor"
"""

import sys
import json
from pathlib import Path

def extract_pages(pdf_path: Path, output_dir: Path, dpi: int = 150) -> bool:
    """Extract PDF pages as JPEG images."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("ERROR: PyMuPDF not installed. Run: pip install PyMuPDF")
        return False

    pages_dir = output_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    print(f"Opening PDF: {pdf_path}")
    doc = fitz.open(str(pdf_path))
    page_count = len(doc)
    print(f"Found {page_count} pages")

    pages_index = []

    for page_num in range(page_count):
        print(f"  Extracting page {page_num + 1}/{page_count}...", end="\r")

        page = doc[page_num]
        # Render at specified DPI
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)

        # Save as JPEG
        img_filename = f"page_{page_num + 1:04d}.jpg"
        img_path = pages_dir / img_filename
        pix.save(str(img_path))

        pages_index.append({
            "number": page_num + 1,
            "file": f"pages/{img_filename}",
            "width": pix.width,
            "height": pix.height
        })

    doc.close()
    print(f"\nExtracted {page_count} pages to {pages_dir}")

    # Save pages index
    pages_json = {
        "totalPages": page_count,
        "dpi": dpi,
        "pages": pages_index
    }

    pages_json_path = output_dir / "pages.json"
    with open(pages_json_path, "w", encoding="utf-8") as f:
        json.dump(pages_json, f, indent=2)

    print(f"Created pages index: {pages_json_path}")

    # Update manifest if it exists
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        manifest["hasOriginalPages"] = True
        manifest["pagesFile"] = "pages.json"
        manifest["version"] = "2.0"

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        print(f"Updated manifest: {manifest_path}")

    return True


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nUsage: python scripts/add_pages.py <pdf_file> <output_folder>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not pdf_path.exists():
        print(f"ERROR: PDF file not found: {pdf_path}")
        sys.exit(1)

    if not output_dir.exists():
        print(f"ERROR: Output folder not found: {output_dir}")
        sys.exit(1)

    print("=" * 50)
    print("Adding PDF Pages to Read-Along Book")
    print("=" * 50)

    success = extract_pages(pdf_path, output_dir)

    if success:
        print("\n" + "=" * 50)
        print("SUCCESS! Page viewer is now available.")
        print("=" * 50)
        print("\nTo use:")
        print("  1. Start the web server: python -m http.server 8000 --directory web")
        print("  2. Open http://localhost:8000 in your browser")
        print("  3. Load your book")
        print("  4. Click the split-view icon (two rectangles) to see pages")
        print("  5. Press 'P' key to toggle page view")
    else:
        print("\nFailed to extract pages.")
        sys.exit(1)


if __name__ == "__main__":
    main()
