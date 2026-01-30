"""
Read-Along Module

Provides synchronized audio-text playback with sentence-level highlighting.
Generates timing maps that link audio timestamps to text positions.
"""

from scripts.readalong.sentence_splitter import SentenceSplitter, split_into_sentences
from scripts.readalong.timed_tts import TimedTTSGenerator
from scripts.readalong.timing_map import TimingMap, TimingEntry
from scripts.readalong.book_processor import BookProcessor

__all__ = [
    "SentenceSplitter",
    "split_into_sentences",
    "TimedTTSGenerator",
    "TimingMap",
    "TimingEntry",
    "BookProcessor",
]
