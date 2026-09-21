#!/usr/bin/env python3
# 解析器基类
# 定义音频文件解析器的统一接口

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List

from app.models.song import Song

logger = logging.getLogger(__name__)


class AudioParser(ABC):
    """音频文件解析器基类"""
    
    @classmethod
    @abstractmethod
    def can_parse(cls, file_path: Path) -> bool:
        """
        检查是否能解析该文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否能解析
        """
        pass
    
    @classmethod
    @abstractmethod
    def parse(cls, file_path: Path) -> Optional[Song]:
        """
        解析音频文件并创建 Song 对象
        
        Args:
            file_path: 文件路径
            
        Returns:
            Song 对象，如果解析失败返回 None
        """
        pass
    
    @classmethod
    @abstractmethod
    def get_supported_extensions(cls) -> List[str]:
        """
        获取支持的扩展名
        
        Returns:
            支持的扩展名列表
        """
        pass


class ParserFactory:
    """解析器工厂"""
    
    _parsers: List[AudioParser] = []
    
    @classmethod
    def register_parser(cls, parser_class: AudioParser):
        """
        注册解析器
        
        Args:
            parser_class: 解析器类
        """
        if parser_class not in cls._parsers:
            cls._parsers.append(parser_class)
            logger.info(f"注册解析器: {parser_class.__name__}")
    
    @classmethod
    def get_parser(cls, file_path: Path) -> Optional[AudioParser]:
        """
        获取适合解析指定文件的解析器
        
        Args:
            file_path: 文件路径
            
        Returns:
            解析器类，如果不支持返回 None
        """
        for parser_class in cls._parsers:
            if parser_class.can_parse(file_path):
                return parser_class
        return None
    
    @classmethod
    def parse_file(cls, file_path: Path) -> Optional[Song]:
        """
        解析文件（自动选择解析器）
        
        Args:
            file_path: 文件路径
            
        Returns:
            Song 对象，如果解析失败返回 None
        """
        parser_class = cls.get_parser(file_path)
        if parser_class:
            logger.info(f"使用解析器 {parser_class.__name__} 解析文件: {file_path}")
            return parser_class.parse(file_path)
        else:
            logger.warning(f"没有找到支持 {file_path.suffix} 格式的解析器")
            return None
    
    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """
        获取所有支持的扩展名
        
        Returns:
            支持的扩展名列表
        """
        extensions = []
        for parser_class in cls._parsers:
            extensions.extend(parser_class.get_supported_extensions())
        return sorted(set(extensions))
    
    @classmethod
    def get_all_parsers(cls) -> List[AudioParser]:
        """
        获取所有已注册的解析器
        
        Returns:
            解析器类列表
        """
        return cls._parsers.copy()


def register_default_parsers():
    """注册默认的解析器"""
    try:
        from .mp3_parser import MP3Parser
        ParserFactory.register_parser(MP3Parser)
    except ImportError as e:
        logger.warning(f"无法导入 MP3Parser: {e}")
    
    try:
        from .flac_parser import FLACParser
        ParserFactory.register_parser(FLACParser)
    except ImportError as e:
        logger.warning(f"无法导入 FLACParser: {e}")
    
    # 未来可以添加更多格式的解析器
    # from .flac_parser import FLACParser
    # ParserFactory.register_parser(FLACParser)
    # ...