"""
Regenerate text.json and timing.json from the DOCX source file.

This script properly extracts text from the DOCX preserving:
- Paragraph boundaries exactly as they appear
- Heading styles (Heading 1, Heading 2, etc.)
- Proper sentence splitting within each paragraph

It generates:
- text.json: with paragraphs, sentences, and heading metadata
- timing.json: with matching sentence IDs (zero timestamps for word-count estimation)
"""

import json
import re
import sys
import unicodedata
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SentenceInfo:
    id: str
    text: str
    paragraph_id: int


# ── Abbreviation-aware sentence splitter (same logic as sentence_splitter.py) ──

ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "ltd", "inc",
    "vs", "etc", "al", "eg", "ie", "cf", "no", "vol", "pp", "ed",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    "fig", "figs", "eq", "eqs", "sec", "ch", "pt", "para",
}


def protect_special_cases(text: str) -> str:
    protected = text
    for abbr in ABBREVIATIONS:
        pattern = rf'\b({abbr})\.'
        protected = re.sub(pattern, r'\1<PERIOD>', protected, flags=re.IGNORECASE)
    protected = re.sub(r'\b([A-Z])\.\s*(?=[A-Z]\.)', r'\1<PERIOD> ', protected)
    protected = re.sub(r'(\d)\.(\d)', r'\1<DECIMAL>\2', protected)
    protected = re.sub(r'\.{3,}', '<ELLIPSIS>', protected)
    protected = re.sub(r'(\d{1,2})\.(\d{2})\s*(?=[ap]\.?m\.?)', r'\1<TIME>\2', protected, flags=re.IGNORECASE)
    return protected


def restore_special_cases(text: str) -> str:
    text = text.replace('<PERIOD>', '.')
    text = text.replace('<DECIMAL>', '.')
    text = text.replace('<ELLIPSIS>', '...')
    text = text.replace('<TIME>', '.')
    return text


def split_paragraph_into_sentences(paragraph_text: str) -> List[str]:
    """Split a single paragraph into sentences."""
    text = re.sub(r'\s+', ' ', paragraph_text).strip()
    if not text:
        return []
    
    protected_text = protect_special_cases(text)
    pattern = r'([.!?]+)(?=\s+(?:[A-Z"\'\u201c\u201d]|$))'
    parts = re.split(pattern, protected_text)
    
    sentences = []
    i = 0
    while i < len(parts):
        text_part = parts[i]
        if i + 1 < len(parts) and re.match(r'^[.!?]+$', parts[i + 1]):
            text_part += parts[i + 1]
            i += 2
        else:
            i += 1
        
        text_part = restore_special_cases(text_part).strip()
        text_part = unicodedata.normalize("NFKC", text_part)
        if text_part:
            sentences.append(text_part)
    
    return sentences


def extract_chapters_from_docx(docx_path: str) -> list:
    """
    Extract chapters from DOCX preserving paragraph structure and styles.
    
    Returns a list of chapters, each with:
    - title: chapter title
    - paragraphs: list of {text, is_heading, style} dicts
    """
    from docx import Document
    
    doc = Document(docx_path)
    
    # Group paragraphs by chapter (split on Heading 1 or Heading 2)
    chapters = []
    current_chapter = None
    
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        
        style_name = para.style.name if para.style else 'Normal'
        is_heading = style_name.startswith('Heading')
        
        # Detect bold text (for headings without explicit heading style)
        has_bold = False
        for run in para.runs:
            if run.bold:
                has_bold = True
                break
        
        # Start new chapter on Heading 2 (main chapter headings in this book)
        if style_name == 'Heading 2' or (style_name == 'Heading 1' and ('chapter' in text.lower() or 'preface' in text.lower() or 'introduction' in text.lower() or 'appendix' in text.lower())):
            if current_chapter is not None:
                chapters.append(current_chapter)
            current_chapter = {
                'title': text,
                'paragraphs': []
            }
            # Add the heading itself as a paragraph
            current_chapter['paragraphs'].append({
                'text': text,
                'is_heading': True,
                'style': style_name,
            })
            continue
        
        # If no chapter started yet, create a default one
        if current_chapter is None:
            current_chapter = {
                'title': 'Introduction',
                'paragraphs': []
            }
        
        # Determine if this is a sub-heading
        is_subheading = (
            style_name in ('Heading 3', 'Heading 4', 'Heading 5') or
            (has_bold and len(text) < 100 and not text.endswith('.'))
        )
        
        current_chapter['paragraphs'].append({
            'text': text,
            'is_heading': is_heading or is_subheading,
            'style': style_name,
        })
    
    # Add final chapter
    if current_chapter is not None:
        chapters.append(current_chapter)
    
    return chapters


def generate_text_and_timing(docx_path: str, output_dir: str, max_chapters: int = 46):
    """Generate text.json and timing.json from DOCX."""
    
    print(f"Reading DOCX: {docx_path}")
    chapters = extract_chapters_from_docx(docx_path)
    print(f"Found {len(chapters)} chapters in DOCX")
    
    # Cap at max_chapters to match available audio files
    if len(chapters) > max_chapters:
        print(f"Capping at {max_chapters} chapters (matching audio files)")
        chapters = chapters[:max_chapters]
    
    text_data = {"chapters": []}
    timing_data = {"chapters": []}
    
    for ch_idx, chapter in enumerate(chapters):
        chapter_id = f"ch{ch_idx:02d}"
        print(f"  {chapter_id}: {chapter['title'][:60]}")
        
        text_chapter = {
            "id": chapter_id,
            "title": chapter['title'],
            "paragraphs": [],
        }
        
        timing_entries = []
        sentence_counter = 0
        
        for para_idx, para in enumerate(chapter['paragraphs']):
            para_id = f"{chapter_id}_p{para_idx:03d}"
            
            # Split paragraph into sentences
            sentences = split_paragraph_into_sentences(para['text'])
            if not sentences:
                continue
            
            para_sentences = []
            for sent_text in sentences:
                sent_id = f"{chapter_id}_s{sentence_counter:04d}"
                sentence_counter += 1
                
                para_sentences.append({
                    "id": sent_id,
                    "text": sent_text,
                })
                
                timing_entries.append({
                    "id": sent_id,
                    "text": sent_text,
                    "start": 0.0,
                    "end": 0.0,
                })
            
            text_chapter["paragraphs"].append({
                "id": para_id,
                "sentences": para_sentences,
                "isHeading": para['is_heading'],
                "style": para['style'],
            })
        
        text_data["chapters"].append(text_chapter)
        
        # Audio file uses 1-based indexing (ch00 -> ch01.mp3)
        audio_file = f"audio/ch{ch_idx + 1:02d}.mp3"
        
        timing_data["chapters"].append({
            "title": chapter['title'],
            "audioFile": audio_file,
            "entries": timing_entries,
        })
        
        print(f"    {len(text_chapter['paragraphs'])} paragraphs, {sentence_counter} sentences")
    
    # Write text.json
    text_path = Path(output_dir) / "text.json"
    with open(text_path, 'w', encoding='utf-8') as f:
        json.dump(text_data, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {text_path}")
    
    # Write timing.json
    timing_path = Path(output_dir) / "timing.json"
    with open(timing_path, 'w', encoding='utf-8') as f:
        json.dump(timing_data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {timing_path}")
    
    # Update manifest.json
    manifest_path = Path(output_dir) / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        manifest['chapterCount'] = len(chapters)
        manifest['chapters'] = []
        for ch_idx, chapter in enumerate(chapters):
            ch_id = f"ch{ch_idx:02d}"
            text_ch = text_data['chapters'][ch_idx]
            total_sentences = sum(len(p['sentences']) for p in text_ch['paragraphs'])
            manifest['chapters'].append({
                "id": ch_id,
                "title": chapter['title'],
                "audioFile": f"audio/ch{ch_idx + 1:02d}.mp3",
                "duration": 0,
                "sentenceCount": total_sentences,
            })
        
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"Updated {manifest_path}")
    
    return len(chapters)


if __name__ == '__main__':
    docx_path = r'C:\Users\merty\Desktop\Audiobook\input\DOCXs\The_Intelligent_Investor_TTSCleaned.docx'
    output_dir = r'C:\Users\merty\Desktop\Audiobook\output\readalong\The_Intelligent_Investor'
    
    num_chapters = generate_text_and_timing(docx_path, output_dir)
    print(f"\nDone! Generated data for {num_chapters} chapters.")
