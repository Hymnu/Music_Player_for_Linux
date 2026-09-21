#!/usr/bin/env python3
# 音频文件解析器模块
# 提供统一的音频文件解析接口

from .base import AudioParser, ParserFactory, register_default_parsers
from .mp3_parser import MP3Parser, parse_mp3_file, can_parse_mp3
from .flac_parser import FLACParser, parse_flac_file, can_parse_flac

__all__ = [
    'AudioParser',
    'ParserFactory', 
    'register_default_parsers',
    'MP3Parser',
    'parse_mp3_file',
    'can_parse_mp3',
    'FLACParser',
    'parse_flac_file',
    'can_parse_flac',
]

# 自动注册默认解析器
try:
    register_default_parsers()
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"注册默认解析器失败: {e}")