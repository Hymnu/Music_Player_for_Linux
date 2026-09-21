#!/usr/bin/env python3
# LRC 歌词解析器

import logging
import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from app.models.song import LyricLine

logger = logging.getLogger(__name__)


class LRCParser:
    """LRC 格式歌词解析器"""

    # LRC 时间戳正则表达式: [mm:ss.xx] 或 [mm:ss]
    TIMESTAMP_PATTERN = re.compile(r'\[(\d{2}):(\d{2})(?:\.(\d{2,3}))?\]')

    # 元数据标签正则表达式: [tag:value]
    METADATA_PATTERN = re.compile(r'\[([a-zA-Z]+):([^\]]+)\]')

    @classmethod
    def parse(cls, lrc_text: str) -> List[LyricLine]:
        """
        解析 LRC 格式歌词文本

        Args:
            lrc_text: LRC 格式歌词文本

        Returns:
            LyricLine 对象列表（按时间排序）
        """
        if not lrc_text:
            return []

        lines = lrc_text.split('\n')
        parsed_lines: List[LyricLine] = []
        metadata: Dict[str, str] = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 1. 先检查是否为元数据标签
            meta_match = cls.METADATA_PATTERN.fullmatch(line)
            if meta_match:
                tag_name = meta_match.group(1).lower()
                tag_value = meta_match.group(2).strip()
                metadata[tag_name] = tag_value
                logger.debug(f"解析元数据: [{tag_name}: {tag_value}]")
                continue

            # 2. 解析时间戳和歌词
            lyric_lines = cls._parse_line_with_timestamps(line)
            parsed_lines.extend(lyric_lines)

        # 3. 按时间排序
        parsed_lines.sort(key=lambda x: x.time)

        logger.debug(f"解析完成: {len(parsed_lines)} 行歌词, {len(metadata)} 个元数据标签")
        if metadata:
            logger.debug(f"元数据: {metadata}")

        return parsed_lines

    @classmethod
    def _parse_line_with_timestamps(cls, line: str) -> List[LyricLine]:
        """
        解析带有时间戳的歌词行

        支持格式:
        - [mm:ss.xx]歌词
        - [mm:ss.xx][mm:ss.xx]歌词（同一行多个时间戳）

        Args:
            line: 歌词行

        Returns:
            LyricLine 对象列表
        """
        # 查找所有时间戳
        matches = list(cls.TIMESTAMP_PATTERN.finditer(line))
        if not matches:
            return []

        # 获取歌词文本（去掉所有时间戳）
        text = cls.TIMESTAMP_PATTERN.sub('', line).strip()
        if not text:
            return []

        # 为每个时间戳创建 LyricLine
        result: List[LyricLine] = []
        for match in matches:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            centiseconds_str = match.group(3)

            # 转换为秒
            if centiseconds_str:
                # 处理 2 位或 3 位的毫秒
                if len(centiseconds_str) == 2:
                    centiseconds = int(centiseconds_str) / 100.0  # [mm:ss.xx] -> xx 是百分秒
                else:
                    centiseconds = int(centiseconds_str[:2]) / 100.0  # [mm:ss.xxx] -> 只取前两位
            else:
                centiseconds = 0.0

            time_in_seconds = minutes * 60 + seconds + centiseconds
            original_timestamp = match.group(0)

            result.append(LyricLine(
                time=time_in_seconds,
                text=text,
                original_timestamp=original_timestamp
            ))

        return result

    @classmethod
    def find_line_at_time(cls, lines: List[LyricLine], current_time: float) -> Optional[LyricLine]:
        """
        查找指定时间对应的歌词行

        Args:
            lines: 歌词行列表（必须已排序）
            current_time: 当前播放时间（秒）

        Returns:
            对应的 LyricLine，如果没有则返回 None
        """
        if not lines:
            return None

        # 二分查找
        left, right = 0, len(lines) - 1
        result = None

        while left <= right:
            mid = (left + right) // 2
            if lines[mid].time <= current_time:
                result = lines[mid]
                left = mid + 1
            else:
                right = mid - 1

        return result

    @classmethod
    def get_lines_around_time(
        cls,
        lines: List[LyricLine],
        current_time: float,
        before: int = 2,
        after: int = 2
    ) -> tuple[List[LyricLine], Optional[int]]:
        """
        获取指定时间前后的歌词行

        Args:
            lines: 歌词行列表（必须已排序）
            current_time: 当前播放时间（秒）
            before: 当前行之前的行数
            after: 当前行之后的行数

        Returns:
            (歌词行列表, 当前行索引)
        """
        if not lines:
            return [], None

        # 找到当前行
        current_index = None
        for i, line in enumerate(lines):
            if line.time <= current_time:
                current_index = i
            else:
                break

        if current_index is None:
            # 第一行还没有显示
            return lines[:after + 1], 0

        # 计算范围
        start = max(0, current_index - before)
        end = min(len(lines), current_index + after + 1)

        return lines[start:end], current_index

    @classmethod
    def is_synced_lyrics(cls, lrc_text: str) -> bool:
        """
        检查歌词是否为同步歌词（包含时间戳）

        Args:
            lrc_text: 歌词文本

        Returns:
            是否为同步歌词
        """
        return bool(cls.TIMESTAMP_PATTERN.search(lrc_text))

    @classmethod
    def format_time(cls, time_seconds: float) -> str:
        """
        格式化时间为 [mm:ss.xx] 格式

        Args:
            time_seconds: 时间（秒）

        Returns:
            格式化的时间字符串
        """
        minutes = int(time_seconds // 60)
        seconds = int(time_seconds % 60)
        centiseconds = int((time_seconds % 1) * 100)
        return f"[{minutes:02d}:{seconds:02d}.{centiseconds:02d}]"

    @classmethod
    def serialize(cls, lines: List[LyricLine], metadata: Optional[Dict[str, str]] = None) -> str:
        """
        将歌词行列表序列化为 LRC 格式文本

        Args:
            lines: 歌词行列表
            metadata: 元数据字典（如 {"ti": "歌名", "ar": "歌手"}）

        Returns:
            LRC 格式文本
        """
        if metadata:
            # LRC 标准元数据标签
            lrc_tags = {
                'ti': 'title',  # 歌名
                'ar': 'artist',  # 歌手
                'al': 'album',  # 专辑
                'by': 'editor',  # 编辑者
            }

            result_lines = []
            for tag_key, tag_value in metadata.items():
                # 查找标准的 LRC 标签名
                lrc_key = None
                for lrc_tag, eng_key in lrc_tags.items():
                    if tag_key.lower() == eng_key or tag_key.lower() == lrc_tag:
                        lrc_key = lrc_tag
                        break

                if lrc_key:
                    result_lines.append(f"[{lrc_key}:{tag_value}]")
                else:
                    result_lines.append(f"[{tag_key}:{tag_value}]")

            result_lines.append("")  # 空行分隔元数据和歌词
        else:
            result_lines = []

        # 添加歌词行
        for line in lines:
            result_lines.append(f"{cls.format_time(line.time)}{line.text}")

        return '\n'.join(result_lines)
