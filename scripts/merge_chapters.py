import json
import shutil
from pathlib import Path
from scripts.utils import logger

def merge_chapters(ch1_dir: Path, main_dir: Path):
    """
    Merge Chapter 1 data into the main audiobook dataset.
    """
    logger.header("Merging Chapter 1 into Main Book")

    # Load Main Data
    with open(main_dir / "manifest.json", "r", encoding="utf-8") as f:
        main_manifest = json.load(f)
    with open(main_dir / "text.json", "r", encoding="utf-8") as f:
        main_text = json.load(f)
    with open(main_dir / "timing.json", "r", encoding="utf-8") as f:
        main_timing = json.load(f)

    # Load Ch1 Data
    with open(ch1_dir / "manifest.json", "r", encoding="utf-8") as f:
        ch1_manifest = json.load(f)
    with open(ch1_dir / "text.json", "r", encoding="utf-8") as f:
        ch1_text = json.load(f)
    with open(ch1_dir / "timing.json", "r", encoding="utf-8") as f:
        ch1_timing = json.load(f)

    # 1. Merge Manifest
    logger.step("Merging Manifest", 1, 4)
    # Validate structure
    if not ch1_manifest["chapters"] or not main_manifest["chapters"]:
        raise ValueError("Empty chapters list in manifest")
    
    ch1_info = ch1_manifest["chapters"][0] # Should be only one
    main_manifest["chapters"].insert(0, ch1_info)
    main_manifest["totalDuration"] += ch1_info["duration"]
    main_manifest["chapterCount"] += 1
    
    # Save Manifest
    with open(main_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(main_manifest, f, indent=2, ensure_ascii=False)

    # 2. Merge Text
    logger.step("Merging Text", 2, 4)
    ch1_text_chapter = ch1_text["chapters"][0]
    main_text["chapters"].insert(0, ch1_text_chapter)
    
    with open(main_dir / "text.json", "w", encoding="utf-8") as f:
        json.dump(main_text, f, indent=2, ensure_ascii=False)

    # 3. Merge Timing
    logger.step("Merging Timing Map", 3, 4)
    
    # Merge Chapters List
    # In JSON, chapters is a list of objects, not a dict
    if "chapters" in ch1_timing and isinstance(ch1_timing["chapters"], list):
        ch1_timing_chapter = ch1_timing["chapters"][0]
        main_timing["chapters"].insert(0, ch1_timing_chapter)
    
    # Merge Entries List
    if "entries" in main_timing and "entries" in ch1_timing:
         main_timing["entries"] = ch1_timing["entries"] + main_timing["entries"]
         
    main_timing["totalDuration"] += ch1_timing["totalDuration"]

    with open(main_dir / "timing.json", "w", encoding="utf-8") as f:
        json.dump(main_timing, f, indent=2, ensure_ascii=False)

    # 4. Move Files
    logger.step("Moving Audio Files", 4, 4)
    src_audio = ch1_dir / "audio" / "ch01.wav"
    dst_audio = main_dir / "audio" / "ch01.wav"
    
    if src_audio.exists():
        shutil.copy2(src_audio, dst_audio)
        logger.info(f"Copied {src_audio.name}")
    else:
        logger.error(f"Source audio not found: {src_audio}")

    logger.success("Merge Complete!")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python merge_chapters.py <ch1_dir> <main_dir>")
        sys.exit(1)
        
    ch1_path = Path(sys.argv[1])
    main_path = Path(sys.argv[2])
    
    merge_chapters(ch1_path, main_path)
