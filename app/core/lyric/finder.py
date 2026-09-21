#!/usr/bin/env python3
"""智能歌词查找器"""

import logging
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass

from app.models.song import LyricInfo, Song

logger = logging.getLogger(__name__)


@dataclass
class LyricResult:
    """歌词查找结果"""
    lyrics: Optional[LyricInfo]
    source: Optional[str]  # 实际使用的源: lrc, embedded, None


class LyricFinder:
    """智能歌词查找器"""
    
    # 支持的源类型
    SOURCES = ["lrc", "embedded"]
    
    def __init__(self, config: Optional[Dict] = None):
        """初始化歌词查找器
        
        Args:
            config: 配置字典，格式见 config.yaml
        """
        self.config = config or {}
        self._parse_config()
    
    def _parse_config(self):
        """解析配置"""
        lyrics_config = self.config.get("lyrics", {})
        
        # 获取优先级列表，默认: lrc, embedded
        self.priority = lyrics_config.get("priority", ["lrc", "embedded"])
        
        # 验证优先级列表
        for source in self.priority:
            if source not in self.SOURCES:
                logger.warning(f"未知的歌词源: {source}，已忽略")
        
        # LRC配置
        lrc_config = lyrics_config.get("lrc", {})
        self.lrc_patterns = lrc_config.get(
            "search_patterns",
            ["{filename}.lrc"]
        )
        self.lrc_encodings = lrc_config.get(
            "encoding_priority",
            ["utf-8", "gbk", "gb2312"]
        )
    
    def find(self, song: Song, audio_path: Optional[Path] = None) -> LyricResult:
        """
        智能查找歌词
        
        Args:
            song: Song对象，可能已包含内嵌歌词
            audio_path: 音频文件路径（如果song.file_info.path不可用）
        
        Returns:
            LyricResult: 查找结果
        """
        path = audio_path or (song.file_info.path if song.file_info else None)
        
        # 按优先级依次尝试
        for source in self.priority:
            if source == "lrc":
                result = self._try_lrc(path, song)
                if result.lyrics:
                    logger.debug(f"从LRC文件获取歌词: {result.lyrics.source}")
                    return result
            
            elif source == "embedded":
                result = self._try_embedded(song)
                if result.lyrics:
                    logger.debug(f"从内嵌标签获取歌词: {result.lyrics.source}")
                    return result
        
        # 所有源都失败
        logger.debug("未找到任何歌词")
        return LyricResult(lyrics=None, source=None)
    
    def _try_lrc(self, audio_path: Optional[Path], song: Song) -> LyricResult:
        """尝试从LRC文件获取歌词"""
        if not audio_path:
            return LyricResult(None, None)
        
        # 解析路径模板
        variables = self._get_template_variables(song, audio_path)
        
        # 按配置的查找模式尝试
        for pattern in self.lrc_patterns:
            try:
                pattern_path = pattern.format(**variables)
                lrc_path = audio_path.parent / pattern_path
                
                if lrc_path.exists():
                    lyrics = self._load_lrc_file(lrc_path)
                    if lyrics:
                        return LyricResult(lyrics, "lrc")
            except Exception as e:
                logger.debug(f"LRC查找模式失败 '{pattern}': {e}")
        
        return LyricResult(None, None)
    
    def _try_embedded(self, song: Song) -> LyricResult:
        """尝试从内嵌标签获取歌词"""
        if song.lyrics and song.lyrics.text:
            return LyricResult(song.lyrics, "embedded")
        return LyricResult(None, None)
    
    def _get_template_variables(self, song: Song, audio_path: Path) -> Dict[str, str]:
        """获取路径模板变量"""
        return {
            "filename": audio_path.stem,
            "title": song.metadata.title or "",
            "artist": song.metadata.artist or "",
            "album": song.metadata.album or "",
        }
    
    def _load_lrc_file(self, lrc_path: Path) -> Optional[LyricInfo]:
        """加载LRC文件（智能编码检测）"""
        lrc_config = self.config.get("lyrics", {}).get("lrc", {})
        
        # 1️⃣ 判断是否启用编码检测
        use_detection = lrc_config.get("use_charset_detection", True)
        
        encodings_to_try = []
        
        if use_detection:
            # 先尝试自动检测编码
            detected = self._detect_encoding(lrc_path)
            if detected:
                # 检测到的编码优先（确保不重复）
                normalized_detected = detected.lower().replace("-", "").replace("_", "")
                unique = True
                for enc in self.lrc_encodings:
                    if enc.lower().replace("-", "").replace("_", "") == normalized_detected:
                        unique = False
                        break
                if unique:
                    encodings_to_try.append(detected)
        
        # 2️⃣ 添加用户配置的编码列表
        encodings_to_try.extend(self.lrc_encodings)
        
        # 3️⃣ 按优先级尝试解码
        for encoding in encodings_to_try:
            try:
                text = lrc_path.read_text(encoding=encoding)
                
                # 判断是否为同步歌词（包含时间标签）
                is_synced = "[" in text and "]" in text
                
                logger.debug(f"成功解码LRC文件，使用编码: {encoding}")

                return LyricInfo(
                    text=text,
                    synced=is_synced,
                    source="file",
                )
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"读取LRC文件失败: {e}")
                break
        
        logger.warning(f"无法解码LRC文件: {lrc_path}")
        return None
    
    def _detect_encoding(self, file_path: Path) -> Optional[str]:
        """检测文件编码（使用 charset-normalizer）"""
        try:
            from charset_normalizer import from_path
            
            # 读取前16KB进行检测（足够准确且快速）
            with open(file_path, 'rb') as f:
                raw_data = f.read(16384)
            
            result = from_path(file_path).best()
            if result and result.encoding:
                logger.debug(f"检测到文件编码: {result.encoding} (置信度: {result.accuracy:.2%})")
                return result.encoding
        except ImportError:
            logger.debug("charset-normalizer 未安装，跳过编码检测")
        except Exception as e:
            logger.debug(f"编码检测失败: {e}")
        
        return None
