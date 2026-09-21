#!/usr/bin/env python3
# Lyric package initialization

from .parser import LRCParser
from .finder import LyricFinder
from .manager import LyricManager

__all__ = [
    'LRCParser',
    'LyricFinder',
    'LyricManager',
]
