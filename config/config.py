# 用于从yaml中加载配置
import yaml
from pathlib import Path
from typing import Any, Dict

CONFIG_FILE = Path(__file__).parent / "config.yaml"


def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


# 全局配置实例
_config = load_config()


def reload_config() -> None:
    """重新加载配置文件"""
    global _config
    _config = load_config()


def get_config() -> Dict[str, Any]:
    """获取当前配置"""
    return _config


def get_artwork_config() -> Dict[str, Any]:
    """获取封面配置"""
    return _config.get('artwork', {})


def get_lyrics_config() -> Dict[str, Any]:
    """获取歌词配置"""
    return _config.get('lyrics', {})
