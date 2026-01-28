"""
Metadata and Cover Art Handler

Handles audiobook metadata extraction, cover art processing, and management.
"""

import json
import re
import shutil
from pathlib import Path
from typing import Optional

from PIL import Image

from scripts.utils.config import config
from scripts.utils import logger


class MetadataExtractor:
    """Extract metadata from various sources."""

    def __init__(self):
        self.config = config

    def extract_from_pdf(self, pdf_path: Path) -> dict:
        """
        Extract metadata from PDF file.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict with title, author, and other metadata
        """
        import fitz

        pdf_path = Path(pdf_path)
        doc = fitz.open(pdf_path)

        metadata = doc.metadata or {}
        doc.close()

        return {
            "title": metadata.get("title", "") or self._title_from_filename(pdf_path),
            "author": metadata.get("author", "") or "Unknown Author",
            "subject": metadata.get("subject", ""),
            "keywords": metadata.get("keywords", ""),
            "creator": metadata.get("creator", ""),
            "creation_date": metadata.get("creationDate", ""),
        }

    def extract_from_text(self, text: str, filename: str = "") -> dict:
        """
        Extract metadata from text content.

        Attempts to find title and author from common patterns.
        """
        lines = text.strip().split("\n")[:50]  # Look in first 50 lines

        title = ""
        author = ""

        for line in lines:
            line = line.strip()

            # Look for "by Author Name" patterns
            author_match = re.search(
                r"(?:by|written by|author:?)\s+(.+)",
                line,
                re.IGNORECASE,
            )
            if author_match and not author:
                author = author_match.group(1).strip()

            # First substantial line might be title
            if not title and len(line) > 5 and len(line) < 200:
                # Skip if it looks like a chapter marker
                if not re.match(r"^(chapter|part|section)\s+", line, re.IGNORECASE):
                    title = line

        return {
            "title": title or self._title_from_filename(Path(filename)),
            "author": author or "Unknown Author",
        }

    def _title_from_filename(self, path: Path) -> str:
        """Generate title from filename."""
        name = path.stem

        # Remove common patterns
        name = re.sub(r"[-_]", " ", name)
        name = re.sub(r"\s+", " ", name)

        # Title case
        return name.title()

    def create_metadata_file(
        self,
        metadata: dict,
        output_path: Path,
    ) -> Path:
        """Save metadata to JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return output_path

    def load_metadata_file(self, path: Path) -> dict:
        """Load metadata from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


class CoverArtHandler:
    """Handle cover art for audiobooks."""

    # Standard audiobook cover dimensions
    DEFAULT_SIZE = (500, 500)
    MAX_SIZE = (1400, 1400)

    def __init__(self):
        self.covers_dir = config.get_path("covers")
        self.covers_dir.mkdir(parents=True, exist_ok=True)

    def extract_from_pdf(self, pdf_path: Path, output_path: Optional[Path] = None) -> Optional[Path]:
        """
        Extract cover image from first page of PDF.

        Args:
            pdf_path: Path to PDF file
            output_path: Optional path for output image

        Returns:
            Path to extracted cover or None
        """
        import fitz

        pdf_path = Path(pdf_path)
        doc = fitz.open(pdf_path)

        if len(doc) == 0:
            doc.close()
            return None

        # Get first page
        page = doc[0]

        # Extract images from first page
        images = page.get_images(full=True)

        if images:
            # Get the largest image
            largest = None
            largest_size = 0

            for img in images:
                xref = img[0]
                base_image = doc.extract_image(xref)

                if base_image:
                    size = len(base_image["image"])
                    if size > largest_size:
                        largest_size = size
                        largest = base_image

            if largest:
                # Save image
                if output_path is None:
                    output_path = self.covers_dir / f"{pdf_path.stem}_cover.jpg"

                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                with open(output_path, "wb") as f:
                    f.write(largest["image"])

                doc.close()
                logger.success(f"Extracted cover from PDF: {output_path}")
                return output_path

        # If no images, render first page as cover
        output_path = output_path or self.covers_dir / f"{pdf_path.stem}_cover.jpg"
        output_path = Path(output_path)

        # Render at high DPI
        mat = fitz.Matrix(2, 2)  # 2x zoom
        pix = page.get_pixmap(matrix=mat)

        # Save as JPEG
        pix.save(str(output_path))
        doc.close()

        logger.success(f"Generated cover from first page: {output_path}")
        return output_path

    def process_cover(
        self,
        image_path: Path,
        output_path: Optional[Path] = None,
        size: tuple = DEFAULT_SIZE,
    ) -> Path:
        """
        Process and optimize cover image.

        Args:
            image_path: Path to source image
            output_path: Optional output path
            size: Target size (width, height)

        Returns:
            Path to processed cover
        """
        image_path = Path(image_path)

        if output_path is None:
            output_path = self.covers_dir / f"{image_path.stem}_processed.jpg"
        output_path = Path(output_path)

        with Image.open(image_path) as img:
            # Convert to RGB if necessary
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Calculate aspect ratio preserving resize
            img_ratio = img.width / img.height
            target_ratio = size[0] / size[1]

            if img_ratio > target_ratio:
                # Image is wider, fit to height
                new_height = size[1]
                new_width = int(new_height * img_ratio)
            else:
                # Image is taller, fit to width
                new_width = size[0]
                new_height = int(new_width / img_ratio)

            # Resize
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Center crop to exact size
            left = (new_width - size[0]) // 2
            top = (new_height - size[1]) // 2
            img = img.crop((left, top, left + size[0], top + size[1]))

            # Save optimized
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "JPEG", quality=90, optimize=True)

        logger.success(f"Processed cover: {output_path}")
        return output_path

    def create_placeholder_cover(
        self,
        title: str,
        author: str,
        output_path: Optional[Path] = None,
        size: tuple = DEFAULT_SIZE,
    ) -> Path:
        """
        Create a simple placeholder cover with title and author.

        Args:
            title: Book title
            author: Author name
            output_path: Output path
            size: Image size

        Returns:
            Path to created cover
        """
        from PIL import ImageDraw, ImageFont

        if output_path is None:
            safe_title = re.sub(r"[^\w\s-]", "", title)[:50]
            output_path = self.covers_dir / f"{safe_title}_cover.jpg"
        output_path = Path(output_path)

        # Create image with gradient background
        img = Image.new("RGB", size, color=(45, 55, 72))

        draw = ImageDraw.Draw(img)

        # Try to use a system font, fall back to default
        try:
            title_font = ImageFont.truetype("arial.ttf", 36)
            author_font = ImageFont.truetype("arial.ttf", 24)
        except OSError:
            title_font = ImageFont.load_default()
            author_font = title_font

        # Draw title (wrapped)
        title_lines = self._wrap_text(title, 20)
        y_offset = size[1] // 3

        for line in title_lines[:3]:  # Max 3 lines
            bbox = draw.textbbox((0, 0), line, font=title_font)
            text_width = bbox[2] - bbox[0]
            x = (size[0] - text_width) // 2
            draw.text((x, y_offset), line, fill=(255, 255, 255), font=title_font)
            y_offset += 50

        # Draw author
        y_offset = size[1] * 2 // 3
        bbox = draw.textbbox((0, 0), author, font=author_font)
        text_width = bbox[2] - bbox[0]
        x = (size[0] - text_width) // 2
        draw.text((x, y_offset), author, fill=(200, 200, 200), font=author_font)

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "JPEG", quality=90)

        logger.success(f"Created placeholder cover: {output_path}")
        return output_path

    def _wrap_text(self, text: str, max_chars: int) -> list:
        """Wrap text to specified character width."""
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            if sum(len(w) for w in current_line) + len(word) + len(current_line) <= max_chars:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        return lines

    def copy_cover(self, source: Path, dest: Path) -> Path:
        """Copy a cover file to destination."""
        source = Path(source)
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        return dest


def extract_metadata(source_path: Path) -> dict:
    """
    Extract metadata from source file.

    Args:
        source_path: Path to PDF or text file

    Returns:
        Metadata dictionary
    """
    extractor = MetadataExtractor()

    if source_path.suffix.lower() == ".pdf":
        return extractor.extract_from_pdf(source_path)
    else:
        text = source_path.read_text(encoding="utf-8")
        return extractor.extract_from_text(text, str(source_path))


def get_cover(
    source_path: Path,
    output_path: Optional[Path] = None,
    fallback_title: str = "Audiobook",
    fallback_author: str = "Unknown",
) -> Path:
    """
    Get or create cover art for an audiobook.

    Args:
        source_path: Path to source PDF or existing cover image
        output_path: Optional output path
        fallback_title: Title for placeholder cover
        fallback_author: Author for placeholder cover

    Returns:
        Path to cover image
    """
    handler = CoverArtHandler()
    source_path = Path(source_path)

    # If source is an image, process it
    if source_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
        return handler.process_cover(source_path, output_path)

    # If source is PDF, extract cover
    if source_path.suffix.lower() == ".pdf":
        cover = handler.extract_from_pdf(source_path, output_path)
        if cover:
            return handler.process_cover(cover, output_path)

    # Create placeholder cover
    return handler.create_placeholder_cover(
        fallback_title,
        fallback_author,
        output_path,
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python metadata.py <source_file>")
        sys.exit(1)

    source = Path(sys.argv[1])
    metadata = extract_metadata(source)
    print(json.dumps(metadata, indent=2))
