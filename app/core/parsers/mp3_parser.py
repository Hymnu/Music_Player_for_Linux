#!/usr/bin/env python3
# MP3 音频文件解析器
# 用于解析 MP3 文件并创建 Song 对象

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TPE2, TCON, TDRC, TRCK, COMM, TXXX, USLT

from app.models.song import (
    Song, FileInfo, SongMetadata, AudioFormat,
    ReplayGain, Artwork, LyricInfo
)

logger = logging.getLogger(__name__)


class MP3Parser:
    """MP3 文件解析器"""
    
    @classmethod
    def can_parse(cls, file_path: Path) -> bool:
        """检查是否能解析该文件"""
        return file_path.suffix.lower() in ['.mp3', '.mp2', '.mp1']
    
    @classmethod
    def parse(cls, file_path: Path) -> Optional[Song]:
        """
        解析 MP3 文件并创建 Song 对象
        
        Args:
            file_path: MP3 文件路径
            
        Returns:
            Song 对象，如果解析失败返回 None
        """
        try:
            if not file_path.exists():
                logger.error(f"文件不存在: {file_path}")
                return None
                
            logger.info(f"开始解析 MP3 文件: {file_path}")
            
            # 使用 mutagen 读取文件
            audio = MP3(file_path)
            
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
            logger.error(f"解析 MP3 文件失败 {file_path}: {e}", exc_info=True)
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
    def _extract_metadata(audio: MP3) -> SongMetadata:
        """提取歌曲元数据"""
        tags = audio.tags or {}
        
        def get_tag(tag_key, default=None):
            """安全获取标签值"""
            if tag_key in tags:
                try:
                    return str(tags[tag_key])
                except:
                    return default
            return default
        
        def get_first_text(tag_key, default=None):
            """获取文本标签的第一个值"""
            if tag_key in tags:
                try:
                    if hasattr(tags[tag_key], 'text') and tags[tag_key].text:
                        return str(tags[tag_key].text[0])
                except:
                    pass
            return default
        
        # 获取音轨号
        track_number = None
        if "TRCK" in tags:
            try:
                track_text = get_first_text("TRCK", "")
                if track_text and "/" in track_text:
                    track_number = int(track_text.split("/")[0])
                elif track_text and track_text.isdigit():
                    track_number = int(track_text)
            except (ValueError, AttributeError):
                pass
        
        # 获取年份
        year = None
        year_str = get_first_text("TDRC", "")
        if year_str and len(year_str) >= 4:
            try:
                year = int(year_str[:4])
            except ValueError:
                pass
        
        # 获取 ISRC
        isrc = None
        if "TSRC" in tags:
            isrc = get_first_text("TSRC")
        elif "TXXX:ISRC" in tags:
            isrc = get_first_text("TXXX:ISRC")
        
        # 获取 BPM
        bpm = None
        if "TBPM" in tags:
            try:
                bpm_text = get_first_text("TBPM", "")
                if bpm_text:
                    bpm = int(float(bpm_text))
            except (ValueError, AttributeError):
                pass
        elif "TXXX:BPM" in tags:
            try:
                bpm_text = get_first_text("TXXX:BPM", "")
                if bpm_text:
                    bpm = int(float(bpm_text))
            except (ValueError, AttributeError):
                pass
        
        return SongMetadata(
            title=get_first_text("TIT2", "").strip(),
            artist=get_first_text("TPE1", "").strip(),
            album=get_first_text("TALB", "").strip(),
            album_artist=get_first_text("TPE2"),
            genre=get_first_text("TCON"),
            year=year,
            track_number=track_number,
            disc_number=None,  # MP3 通常不包含碟号
            composer=get_first_text("TCOM"),
            publisher=get_first_text("TPUB"),
            isrc=isrc,
            comment=get_first_text("COMM"),
            bpm=bpm,
            copyright=get_first_text("TCOP"),
        )
    
    @staticmethod
    def _extract_audio_format(audio: MP3) -> AudioFormat:
        """提取音频格式信息"""
        info = audio.info
        tags = audio.tags or {}
        
        def get_tag(tag_key, default=None):
            """安全获取标签值"""
            if tag_key in tags:
                try:
                    return str(tags[tag_key])
                except:
                    return default
            return default
        
        def get_first_text(tag_key, default=None):
            """获取文本标签的第一个值"""
            if tag_key in tags:
                try:
                    if hasattr(tags[tag_key], 'text') and tags[tag_key].text:
                        return str(tags[tag_key].text[0])
                except:
                    pass
            return default
        
        # 检测 MP3 编码配置
        profile = None
        if info.version == 2:  # MPEG-2
            profile = "MPEG-2"
        elif info.version == 1:  # MPEG-1
            profile = "MPEG-1"
        
        # 检测立体声模式
        mp3_stereo_mode = None
        if hasattr(info, 'mode'):
            mode_map = {
                0: "stereo",
                1: "joint_stereo", 
                2: "dual_channel",
                3: "mono"
            }
            mp3_stereo_mode = mode_map.get(info.mode, f"unknown_{info.mode}")
        
        # 获取编码延迟和填充信息（如果有）
        enc_delay = None
        enc_padding = None
        
        # 尝试从 ID3v2 标签获取编码延迟和填充
        # 这些信息通常在 LAME 编码的 MP3 文件的 Xing/Info 头中
        # 这里我们简单地从自定义标签中查找
        lame_info = get_first_text("TXXX:LAME")
        if lame_info:
            # 简单的 LAME 信息解析（简化版）
            if "enc_delay" in lame_info or "enc_padding" in lame_info:
                # 在实际实现中，可以解析更详细的 LAME 信息
                pass
        
        # 获取编码器信息（TENC - 编码软件/硬件）
        encoder = get_first_text("TENC")
        
        # 获取 FFmpeg 版本信息（TSSE/TXXX:TSSE - FFmpeg 多媒体框架版本标识）
        ffmpeg_version = get_first_text("TSSE")
        if not ffmpeg_version:
            ffmpeg_version = get_first_text("TXXX:TSSE")
        
        return AudioFormat(
            codec="MP3",
            profile=profile,
            encoding="lossy",
            sample_rate=info.sample_rate,
            channels=info.channels,
            bitrate=int(info.bitrate / 1000),  # 转换为 kbps
            bit_depth=None,  # MP3 没有固定的位深度
            mp3_stereo_mode=mp3_stereo_mode,
            enc_delay=enc_delay,
            enc_padding=enc_padding,
            encoder=encoder,
            ffmpeg_version=ffmpeg_version,
        )
    
    @staticmethod
    def _extract_replaygain(audio: MP3) -> ReplayGain:
        """提取 ReplayGain 信息"""
        tags = audio.tags or {}
        
        def get_replaygain_value(tag_key, default=None):
            """获取 ReplayGain 值"""
            if tag_key in tags:
                try:
                    text = str(tags[tag_key])
                    # 提取数值部分 (如 "-6.5 dB" -> -6.5)
                    if "dB" in text:
                        value_str = text.split("dB")[0].strip()
                        return float(value_str)
                except (ValueError, AttributeError):
                    pass
            return default
        
        return ReplayGain(
            track_gain=get_replaygain_value("TXXX:replaygain_track_gain"),
            track_peak=get_replaygain_value("TXXX:replaygain_track_peak"),
            album_gain=get_replaygain_value("TXXX:replaygain_album_gain"),
            album_peak=get_replaygain_value("TXXX:replaygain_album_peak"),
        )
    
    @staticmethod
    def _extract_artwork(file_path: Path, audio: MP3) -> Optional[Artwork]:
        """提取封面图片（可选：解析尺寸）"""
        try:
            tags = audio.tags or {}

            # 查找 APIC 标签（封面）
            for tag_id, tag_value in tags.items():
                if isinstance(tag_value, APIC):
                    image_data = tag_value.data
                    width, height = None, None

                    # 尝试获取尺寸（使用 Pillow，可选）
                    try:
                        import io
                        from PIL import Image
                        with Image.open(io.BytesIO(image_data)) as img:
                            width, height = img.size
                            logger.debug(f"封面尺寸: {width}x{height}")
                    except Exception as e:
                        logger.debug(f"未获取封面尺寸（将懒加载）: {e}")

                    logger.debug(f"找到封面: {tag_id}, MIME: {tag_value.mime}, "
                               f"大小: {len(image_data)} 字节, 尺寸: {width}x{height}")

                    return Artwork.from_embedded(
                        offset=0,  # mutagen 已经解析出数据
                        mime_type=tag_value.mime,
                        source_audio=file_path,
                        size_bytes=len(image_data),
                        width=width,
                        height=height,
                        description=tag_value.desc,
                        hash_checksum=None,
                        image_data=image_data,  # 传入图片数据用于懒加载
                    )

            # 没有找到内嵌封面
            logger.debug(f"未找到内嵌封面: {file_path}")
            return None

        except Exception as e:
            logger.warning(f"提取封面失败 {file_path}: {e}")
            return None
    
    @staticmethod
    def _extract_lyrics(audio: MP3) -> LyricInfo:
        """提取歌词信息

        优先级: TXXX:LYRICS → USLT
        """
        tags = audio.tags or {}
        lyric_text = None

        # 1️⃣ 优先查找 TXXX:LYRICS 标签（自定义歌词）
        if "TXXX:LYRICS" in tags:
            try:
                lyric_text = str(tags["TXXX:LYRICS"])
                logger.debug(f"找到自定义歌词标签 (TXXX:LYRICS)")
            except Exception as e:
                logger.warning(f"解析 TXXX:LYRICS 失败: {e}")

        # 2️⃣ 其次查找 USLT (Unsynchronized lyrics/text transcription) 标签
        if lyric_text is None:
            for tag_id, tag_value in tags.items():
                if isinstance(tag_value, USLT):
                    try:
                        lyric_text = tag_value.text
                        lang = tag_value.lang or "eng"
                        desc = tag_value.desc or ""

                        logger.debug(f"找到歌词 (USLT): {desc} ({lang})")
                        break  # 只取第一个找到的歌词标签

                    except Exception as e:
                        logger.warning(f"解析 USLT 歌词失败: {e}")

        return LyricInfo(
            text=lyric_text,
            source="embedded" if lyric_text else None,
            language=None,
        )
    
    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """获取支持的扩展名"""
        return ['.mp3', '.mp2', '.mp1']


# 便捷函数
def parse_mp3_file(file_path: Path) -> Optional[Song]:
    """
    解析 MP3 文件的便捷函数
    
    Args:
        file_path: MP3 文件路径
        
    Returns:
        Song 对象，如果解析失败返回 None
    """
    return MP3Parser.parse(file_path)


def can_parse_mp3(file_path: Path) -> bool:
    """
    检查是否能解析 MP3 文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        是否能解析
    """
    return MP3Parser.can_parse(file_path)