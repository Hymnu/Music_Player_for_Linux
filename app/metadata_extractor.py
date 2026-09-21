#!/usr/bin/env python3
# 元数据提取器主模块
# 提供统一的音频文件解析接口

import logging
from pathlib import Path
from typing import Optional, List, Iterator, Dict

from app.models.song import Song
from app.core.parsers import ParserFactory
from app.core.lyric.finder import LyricFinder

logger = logging.getLogger(__name__)

# 全局歌词查找器实例
_lyric_finder: Optional[LyricFinder] = None


def set_config(config: Dict):
    """设置全局配置（用于歌词查找）"""
    global _lyric_finder
    _lyric_finder = LyricFinder(config)
    logger.info("已更新全局配置")


def parse_audio_file(file_path: Path, config: Optional[Dict] = None) -> Optional[Song]:
    """
    解析音频文件（自动选择解析器）
    
    Args:
        file_path: 音频文件路径
        
    Returns:
        Song 对象，如果解析失败返回 None
        
    Examples:
        >>> song = parse_audio_file(Path("song.mp3"))
        >>> if song:
        >>>     print(f"标题: {song.display_title}")
    """
    try:
        logger.info(f"解析音频文件: {file_path}")
        song = ParserFactory.parse_file(file_path)
        if not song:
            return None
        
        # 使用歌词查找器选择最佳歌词
        finder = LyricFinder(config) if config else _lyric_finder
        if finder:
            result = finder.find(song, file_path)
            if result.lyrics:
                song.lyrics = result.lyrics
        
        return song
    except Exception as e:
        logger.error(f"解析音频文件失败 {file_path}: {e}", exc_info=True)
        return None


def parse_audio_directory(directory_path: Path, 
                          recursive: bool = False) -> Iterator[Song]:
    """
    解析目录中的音频文件
    
    Args:
        directory_path: 目录路径
        recursive: 是否递归搜索子目录
        
    Yields:
        Song 对象
        
    Examples:
        >>> for song in parse_audio_directory(Path("music/")):
        >>>     print(f"找到: {song.display_title}")
    """
    if not directory_path.is_dir():
        logger.error(f"不是有效的目录: {directory_path}")
        return
    
    pattern = "**/*" if recursive else "*"
    total_files = 0
    parsed_files = 0
    
    for file_path in directory_path.glob(pattern):
        if file_path.is_file():
            total_files += 1
            
            # 检查文件是否被支持
            if ParserFactory.get_parser(file_path):
                parsed_files += 1
                logger.debug(f"处理文件 ({parsed_files}/{total_files}): {file_path.name}")
                
                song = parse_audio_file(file_path)
                if song:
                    yield song
            else:
                logger.debug(f"跳过不支持的文件: {file_path.suffix}")
    
    logger.info(f"目录解析完成: 总共 {total_files} 个文件，成功解析 {parsed_files} 个")


def get_supported_extensions() -> List[str]:
    """
    获取支持的音频文件扩展名
    
    Returns:
        支持的扩展名列表
        
    Examples:
        >>> extensions = get_supported_extensions()
        >>> print(f"支持格式: {', '.join(extensions)}")
    """
    return ParserFactory.get_supported_extensions()


def can_parse_file(file_path: Path) -> bool:
    """
    检查是否能解析指定文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        是否能解析
        
    Examples:
        >>> if can_parse_file(Path("song.mp3")):
        >>>     print("可以解析此文件")
    """
    return ParserFactory.get_parser(file_path) is not None


# 便捷的单文件解析函数
def parse_single_file(file_path: Path) -> Optional[Song]:
    """解析单个音频文件（简化版本）"""
    return parse_audio_file(file_path)


# 批量解析函数
def parse_multiple_files(file_paths: List[Path]) -> List[Song]:
    """
    解析多个音频文件
    
    Args:
        file_paths: 文件路径列表
        
    Returns:
        Song 对象列表
    """
    results = []
    for i, file_path in enumerate(file_paths, 1):
        logger.info(f"处理文件 {i}/{len(file_paths)}: {file_path.name}")
        song = parse_audio_file(file_path)
        if song:
            results.append(song)
    
    logger.info(f"批量解析完成: {len(results)}/{len(file_paths)} 个文件成功")
    return results