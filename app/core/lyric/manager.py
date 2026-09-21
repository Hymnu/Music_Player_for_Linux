#!/usr/bin/env python3
"""
歌词同步管理器

负责根据播放进度追踪当前歌词行，处理偏移调整，并在歌词切换时触发事件。
"""

import logging
from typing import Callable, List, Optional, Tuple

from app.models.song import Song
from app.core.lyric.parser import LRCParser

logger = logging.getLogger(__name__)


class LyricManager:
    """歌词同步管理器"""

    def __init__(self):
        self._lyrics: List["LyricLine"] = []
        self._lyric_offset: float = 0.0
        self._current_line: Optional["LyricLine"] = None
        self._current_index: Optional[int] = None
        self._on_line_change: Optional[Callable] = None
        self._on_offset_change: Optional[Callable] = None
        self._enabled: bool = True

    @property
    def has_lyrics(self) -> bool:
        """是否有可用的歌词"""
        return len(self._lyrics) > 0

    @property
    def current_line(self) -> Optional["LyricLine"]:
        """当前歌词行"""
        return self._current_line

    @property
    def current_index(self) -> Optional[int]:
        """当前歌词行索引"""
        return self._current_index

    @property
    def offset(self) -> float:
        """歌词偏移量（秒）"""
        return self._lyric_offset

    def load(self, song: Song) -> bool:
        """
        加载歌曲的歌词

        Args:
            song: 歌曲对象

        Returns:
            是否成功加载歌词
        """
        if not song.lyrics or not song.lyrics.has_lyrics:
            logger.debug("歌曲没有歌词")
            self._lyrics = []
            self._current_line = None
            self._current_index = None
            return False

        self._lyrics = song.lyrics.lines
        self._lyric_offset = song.lyric_offset
        logger.debug(f"加载歌词: {len(self._lyrics)} 行")
        return True

    def reset(self):
        """重置管理器状态"""
        self._current_line = None
        self._current_index = None
        self._lyrics = []
        self._lyric_offset = 0.0

    def update(self, playback_position: float) -> Optional["LyricLine"]:
        """
        根据播放位置更新当前歌词行

        Args:
            playback_position: 当前播放位置（秒）

        Returns:
            当前歌词行，如果没有歌词或未变化则返回 None
        """
        if not self._enabled or not self._lyrics:
            return None

        # 应用偏移量
        effective_position = playback_position + self._lyric_offset

        # 查找对应歌词行
        new_line = LRCParser.find_line_at_time(self._lyrics, effective_position)
        new_index = self._lyrics.index(new_line) if new_line else None

        if new_index != self._current_index:
            self._current_index = new_index
            self._current_line = new_line

            # 触发行切换回调
            if self._on_line_change:
                self._on_line_change(self._current_line, self._current_index)

        return self._current_line

    def set_offset(self, offset: float):
        """
        设置歌词偏移量

        Args:
            offset: 偏移量（秒），正数表示延迟，负数表示提前
        """
        if self._lyric_offset != offset:
            self._lyric_offset = offset
            logger.debug(f"歌词偏移设置为: {offset:.2f}秒")

            # 触发偏移变化回调
            if self._on_offset_change:
                self._on_offset_change(offset)

    def adjust_offset(self, delta: float):
        """
        调整歌词偏移量

        Args:
            delta: 偏移量变化值（秒）
        """
        new_offset = self._lyric_offset + delta
        self.set_offset(new_offset)

    def get_concurrent_lines(self) -> List["LyricLine"]:
        """
        获取与当前歌词行时间戳相同的所有行
        用于处理双语/多语歌词

        Returns:
            与当前行时间戳相同的所有歌词行列表
        """
        if not self._current_line or not self._lyrics:
            return []

        # 查找所有时间戳相同的行
        concurrent_lines = [line for line in self._lyrics 
                           if abs(line.time - self._current_line.time) < 0.001]
        return concurrent_lines

    def set_enabled(self, enabled: bool):
        """
        启用或禁用歌词显示

        Args:
            enabled: 是否启用
        """
        self._enabled = enabled
        logger.debug(f"歌词显示: {'启用' if enabled else '禁用'}")

    def set_line_change_callback(self, callback: Callable):
        """
        设置歌词行切换回调

        Args:
            callback: 回调函数，签名为 callback(line: Optional[LyricLine], index: Optional[int])
        """
        self._on_line_change = callback

    def set_offset_change_callback(self, callback: Callable):
        """
        设置偏移量变化回调

        Args:
            callback: 回调函数，签名为 callback(offset: float)
        """
        self._on_offset_change = callback

    def get_display_context(self, before: int = 2, after: int = 2) -> Tuple[List["LyricLine"], Optional["LyricLine"], List["LyricLine"]]:
        """
        获取用于显示的歌词上下文

        Args:
            before: 前面的歌词行数
            after: 后面的歌词行数

        Returns:
            (前面的行, 当前行, 后面的行)
        """
        if not self._lyrics:
            return ([], None, [])

        if self._current_index is None:
            return ([], None, self._lyrics[:after])

        # 使用 get_lines_around_time 获取前后行
        context_lines, current_index = LRCParser.get_lines_around_time(
            self._lyrics, self._current_line.time if self._current_line else 0, before, after
        )

        # 分离前、中、后
        current_line = None
        before_lines = []
        after_lines = []

        if current_index is not None and 0 <= current_index < len(context_lines):
            current_line = context_lines[current_index]
            before_lines = context_lines[:current_index]
            after_lines = context_lines[current_index + 1:]

        return (before_lines, current_line, after_lines)

    def __repr__(self) -> str:
        return f"LyricManager(lyrics={len(self._lyrics)}, offset={self._lyric_offset:.2f}s, current_index={self._current_index})"
