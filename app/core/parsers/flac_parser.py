#!/usr/bin/env python3
# FLAC 音频文件解析器
# 用于解析 FLAC 文件并创建 Song 对象

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from mutagen.flac import FLAC, Picture

from app.models.song import (
    Song, FileInfo, SongMetadata, AudioFormat,
    ReplayGain, Artwork, LyricInfo
)

logger = logging.getLogger(__name__)


class FLACParser:
    """FLAC 文件解析器"""
    
    @classmethod
    def can_parse(cls, file_path: Path) -> bool:
        """检查是否能解析该文件"""
        return file_path.suffix.lower() == '.flac'
    
    @classmethod
    def parse(cls, file_path: Path) -> Optional[Song]:
        """
        解析 FLAC 文件并创建 Song 对象
        
        Args:
            file_path: FLAC 文件路径
            
        Returns:
            Song 对象，如果解析失败返回 None
        """
        try:
            if not file_path.exists():
                logger.error(f"文件不存在: {file_path}")
                return None
                
            logger.info(f"开始解析 FLAC 文件: {file_path}")
            
            # 使用 mutagen 读取文件
            audio = FLAC(file_path)
            
            # 获取文件信息
            file_info = cls._extract_file_info(file_path)
            
            # 获取元数据
            metadata = cls._extract_metadata(audio)
            
            # 获取音频格式信息
            audio_format = cls._extract_audio_format(audio)
            
            # 获取 ReplayGain 信息
            replaygain = cls._extract_replaygain(audio)
            
            # 提取封面
            artwork = cls._extract_artwork(file_path, audio)
            
            # 提取歌词
            lyrics = cls._extract_lyrics(audio)
            
            # 创建 Song 对象
            song = Song(
                file_info=file_info,
                metadata=metadata,
                audio_format=audio_format,
                replaygain=replaygain,
                artwork=artwork,
                lyrics=lyrics,
                duration=audio.info.length,
            )
            
            logger.info(f"成功解析: {song.display_title} - {song.display_artist}")
            return song
            
        except Exception as e:
            logger.error(f"解析 FLAC 文件失败 {file_path}: {e}", exc_info=True)
            return None
    
    @staticmethod
    def _extract_file_info(file_path: Path) -> FileInfo:
        """提取文件基本信息"""
        stat = file_path.stat()
        return FileInfo(
            path=file_path,
            size_bytes=stat.st_size,
            created_time=datetime.fromtimestamp(stat.st_ctime),
            modified_time=datetime.fromtimestamp(stat.st_mtime),
            accessed_time=datetime.fromtimestamp(stat.st_atime)
        )
    
    @staticmethod
    def _extract_metadata(audio: FLAC) -> SongMetadata:
        """提取歌曲元数据"""
        
        def get_tag(tag_key: str, default: str = "") -> str:
            """安全获取标签值"""
            values = audio.get(tag_key, [])
            if values:
                try:
                    return str(values[0])
                except:
                    return default
            return default
        
        # 获取音轨号
        track_number = None
        track_str = get_tag("TRACKNUMBER", "")
        if track_str and "/" in track_str:
            try:
                track_number = int(track_str.split("/")[0])
            except ValueError:
                pass
        elif track_str and track_str.isdigit():
            track_number = int(track_str)
        
        # 获取碟号
        disc_number = None
        disc_str = get_tag("DISCNUMBER", "")
        if disc_str and "/" in disc_str:
            try:
                disc_number = int(disc_str.split("/")[0])
            except ValueError:
                pass
        elif disc_str and disc_str.isdigit():
            disc_number = int(disc_str)
        
        # 获取年份
        year = None
        year_str = get_tag("DATE", "")
        if year_str:
            # DATE 可能是 "2023" 或 "2023-05-15" 等格式
            year_match = year_str[:4] if len(year_str) >= 4 else year_str
            try:
                year = int(year_match)
            except ValueError:
                pass
        
        # 获取 BPM
        bpm = None
        bpm_str = get_tag("BPM", "")
        if bpm_str:
            try:
                bpm = int(float(bpm_str))
            except ValueError:
                pass
        
        return SongMetadata(
            title=get_tag("TITLE", "").strip(),
            artist=get_tag("ARTIST", "").strip(),
            album=get_tag("ALBUM", "").strip(),
            album_artist=get_tag("ALBUMARTIST") or get_tag("ALBUM ARTIST"),
            genre=get_tag("GENRE"),
            year=year,
            track_number=track_number,
            disc_number=disc_number,
            composer=get_tag("COMPOSER"),
            publisher=get_tag("PUBLISHER") or get_tag("ORGANIZATION"),
            isrc=get_tag("ISRC"),
            comment=get_tag("DESCRIPTION") or get_tag("COMMENT"),
            bpm=bpm,
            copyright=get_tag("COPYRIGHT"),
        )
    
    @staticmethod
    def _extract_audio_format(audio: FLAC) -> AudioFormat:
        """提取音频格式信息"""
        info = audio.info
        
        def get_tag(tag_key: str, default: str = "") -> str:
            """安全获取标签值"""
            values = audio.get(tag_key, [])
            if values:
                try:
                    return str(values[0])
                except:
                    return default
            return default
        
        return AudioFormat(
            codec="FLAC",
            profile="FLAC",
            encoding="lossless",
            sample_rate=info.sample_rate,
            channels=info.channels,
            bitrate=int(info.bitrate / 1000) if info.bitrate else None,  # FLAC 是可变比特率
            bit_depth=info.bits_per_sample,
            mp3_stereo_mode=None,
            enc_delay=None,
            enc_padding=None,
            encoder=get_tag("ENCODER"),
            ffmpeg_version=None,
        )
    
    @staticmethod
    def _extract_replaygain(audio: FLAC) -> ReplayGain:
        """提取 ReplayGain 信息"""
        
        def get_replaygain_value(tag_key: str, default=None):
            """获取 ReplayGain 值"""
            values = audio.get(tag_key, [])
            if values:
                try:
                    text = str(values[0])
                    # 提取数值部分 (如 "-6.5 dB" -> -6.5)
                    if "dB" in text:
                        value_str = text.split("dB")[0].strip()
                        return float(value_str)
                    else:
                        return float(text)
                except (ValueError, AttributeError):
                    pass
            return default
        
        # FLAC ReplayGain 标签命名
        return ReplayGain(
            track_gain=get_replaygain_value("REPLAYGAIN_TRACK_GAIN"),
            track_peak=get_replaygain_value("REPLAYGAIN_TRACK_PEAK"),
            album_gain=get_replaygain_value("REPLAYGAIN_ALBUM_GAIN"),
            album_peak=get_replaygain_value("REPLAYGAIN_ALBUM_PEAK"),
        )
    
    @staticmethod
    def _extract_artwork(file_path: Path, audio: FLAC) -> Optional[Artwork]:
        """提取封面图片（可选：解析尺寸）"""
        try:
            # FLAC 使用 Picture 对象存储封面
            pictures = audio.pictures
            if not pictures:
                logger.debug(f"未找到内嵌封面: {file_path}")
                return None
            
            # 取第一个封面（通常是封面）
            picture = pictures[0]
            image_data = picture.data
            width, height = picture.width, picture.height
            
            # 根据 MIME 类型推断文件扩展名
            mime_to_ext = {
                'image/jpeg': 'jpg',
                'image/png': 'png',
                'image/gif': 'gif',
                'image/webp': 'webp',
            }
            ext = mime_to_ext.get(picture.mime, 'jpg')
            
            logger.debug(f"找到封面: MIME={picture.mime}, "
                        f"大小={len(image_data)} 字节, "
                        f"尺寸={width}x{height}, "
                        f"类型={picture.type}")
            
            return Artwork.from_embedded(
                offset=0,
                mime_type=picture.mime,
                source_audio=file_path,
                size_bytes=len(image_data),
                width=width,
                height=height,
                description=picture.desc,
                hash_checksum=None,
                image_data=image_data,
            )
            
        except Exception as e:
            logger.warning(f"提取封面失败 {file_path}: {e}")
            return None
    
    @staticmethod
    def _extract_lyrics(audio: FLAC) -> LyricInfo:
        """提取歌词信息
        
        优先级: LYRICS → UNSYNCEDLYRICS → DESCRIPTION(如果是歌词)
        """
        lyric_text = None
        
        # 1️⃣ 查找 LYRICS 标签
        if "LYRICS" in audio:
            try:
                lyric_text = audio["LYRICS"][0]
                logger.debug(f"找到歌词 (LYRICS)")
            except Exception as e:
                logger.warning(f"解析 LYRICS 失败: {e}")
        
        # 2️⃣ 查找 UNSYNCEDLYRICS 标签
        if not lyric_text and "UNSYNCEDLYRICS" in audio:
            try:
                lyric_text = audio["UNSYNCEDLYRICS"][0]
                logger.debug(f"找到歌词 (UNSYNCEDLYRICS)")
            except Exception as e:
                logger.warning(f"解析 UNSYNCEDLYRICS 失败: {e}")
        
        return LyricInfo(
            text=lyric_text,
            source="embedded" if lyric_text else None,
            language=None,
        )
    
    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """获取支持的扩展名"""
        return ['.flac']


# 便捷函数
def parse_flac_file(file_path: Path) -> Optional[Song]:
    """
    解析 FLAC 文件的便捷函数
    
    Args:
        file_path: FLAC 文件路径
        
    Returns:
        Song 对象，如果解析失败返回 None
    """
    return FLACParser.parse(file_path)


def can_parse_flac(file_path: Path) -> bool:
    """
    检查是否能解析 FLAC 文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        是否能解析
    """
    return FLACParser.can_parse(file_path)
