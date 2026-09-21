from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePath
from typing import Optional, Dict, Any, List, Union, BinaryIO
import mimetypes

@dataclass
class AudioFormat:
    """音频格式信息"""
    codec: str  # 编码格式 (MP3, FLAC, WAV等)
    profile: Optional[str] = None  # 编码配置 (如 MP3 CBR)
    encoding: str = "lossy"  # 编码类型: lossy(有损)/lossless(无损)/uncompressed(未压缩)
    sample_rate: int = 0  # 采样率 (Hz)
    channels: int = 0  # 声道数
    bitrate: int = 0  # 比特率 (kbps)
    bit_depth: Optional[int] = None  # 位深度 (如16-bit, 24-bit)
    
    # MP3特定字段
    mp3_stereo_mode: Optional[str] = None  # MP3立体声模式
    enc_delay: Optional[int] = None  # 编码延迟
    enc_padding: Optional[int] = None  # 编码填充
    
    # 编码器信息
    encoder: Optional[str] = None  # 编码软件/硬件
    ffmpeg_version: Optional[str] = None  # FFmpeg 多媒体框架版本标识
    
    @property
    def quality_description(self) -> str:
        """获取音质描述"""
        if self.encoding == "lossless":
            return "无损"
        elif self.encoding == "uncompressed":
            return "未压缩"
        else:
            return f"{self.bitrate}kbps"

@dataclass
class ReplayGain:
    """ReplayGain音量平衡信息"""
    track_gain: Optional[float] = None  # 音轨增益 (dB)
    track_peak: Optional[float] = None  # 音轨峰值
    album_gain: Optional[float] = None  # 专辑增益 (dB)
    album_peak: Optional[float] = None  # 专辑峰值
    
    @property
    def has_replaygain(self) -> bool:
        """是否包含ReplayGain信息"""
        return self.track_gain is not None or self.album_gain is not None

@dataclass
class Artwork:
    mime_type: str
    embedded_offset: Optional[int] = None
    source_audio_path: Optional[Path] = None  # 内嵌封面来源
    external_path: Optional[Path] = None
    description: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    size_bytes: Optional[int] = None  # 创建时快照
    hash_checksum: Optional[str] = None

    # 私有缓存字段（不参与序列化）
    _dimensions_loaded: bool = field(default=False, repr=False)
    _cached_image_data: Optional[bytes] = field(default=None, repr=False)

    @classmethod
    def from_embedded(cls, offset: int, mime_type: str,
                      source_audio: Union[str, Path],
                      size_bytes: int,
                      width: Optional[int] = None,
                      height: Optional[int] = None,
                      description: Optional[str] = None,
                      hash_checksum: Optional[str] = None,
                      image_data: Optional[bytes] = None) -> 'Artwork':
        """
        创建内嵌封面对象

        Args:
            image_data: 封面图片的二进制数据（mutagen已解析）
        """
        return cls(
            mime_type=mime_type,
            embedded_offset=offset,
            source_audio_path=Path(source_audio),
            size_bytes=size_bytes,
            width=width,
            height=height,
            description=description,
            hash_checksum=hash_checksum,
            _cached_image_data=image_data,  # 缓存图片数据
        )

    @classmethod
    def from_external(cls, filepath: Union[str, Path],
                      mime_type: Optional[str] = None,
                      description: Optional[str] = None) -> 'Artwork':
        path = Path(filepath)

        if mime_type is None:
            mime_type, _ = mimetypes.guess_type(path)
            mime_type = mime_type or 'application/octet-stream'

        return cls(
            external_path=path,
            mime_type=mime_type,
            size_bytes=path.stat().st_size,
            description=description,
        )

    @property
    def is_embedded(self) -> bool:
        return self.embedded_offset is not None and self.source_audio_path is not None

    @property
    def is_external(self) -> bool:
        return self.external_path is not None

    @property
    def dimensions(self) -> Optional[tuple[int, int]]:
        """真实尺寸（懒加载）"""
        self._ensure_dimensions_loaded()
        return (self.width, self.height) if self.width and self.height else None

    @property
    def pixel_count(self) -> int:
        """像素总数"""
        dims = self.dimensions
        return dims[0] * dims[1] if dims else 0

    def estimate_dimensions(self) -> tuple[int, int]:
        """估算尺寸（用于占位）"""
        if self.width and self.height:
            return (self.width, self.height)
        # 基于文件大小估算...
        return (300, 300)

    @property
    def extension(self) -> str:
        ext = mimetypes.guess_extension(self.mime_type)
        return ext or ".img"

    @property
    def size_kb(self) -> Optional[float]:
        """文件大小（KB）"""
        if self.size_bytes is not None:
            return self.size_bytes / 1024.0
        return None

    @property
    def data_base64(self) -> str:
        """Base64编码的图片数据（暂不实现）"""
        # 这是一个占位实现，如果需要实际实现，可以添加图片读取和base64编码逻辑
        return ""

    def _ensure_dimensions_loaded(self) -> None:
        """确保尺寸已加载（懒加载）"""
        if self._dimensions_loaded or (self.width and self.height):
            return

        try:
            import io
            from PIL import Image
            import logging

            logger = logging.getLogger(__name__)

            # 获取图片数据
            image_data = self._read_image_data()
            if not image_data:
                return

            # 使用 Pillow 获取尺寸
            with Image.open(io.BytesIO(image_data)) as img:
                self.width, self.height = img.size

            self._dimensions_loaded = True
            logger.debug(f"获取封面尺寸: {self.width}x{self.height}")

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"获取封面尺寸失败: {e}")

    def _read_image_data(self) -> Optional[bytes]:
        """读取图片数据（懒加载，一次读取后缓存）"""
        # 如果已有缓存，直接返回
        if self._cached_image_data is not None:
            return self._cached_image_data

        try:
            if self.is_external:
                self._cached_image_data = self.external_path.read_bytes()
                return self._cached_image_data
            # 内嵌封面：依赖 from_embedded 时传入的 image_data
            # 如果没有传入数据，无法读取（因为 offset=0 指向 MP3 文件开头）
            # 实际使用中应该总是传入 image_data
            import logging
            logging.getLogger(__name__).warning("内嵌封面没有缓存的图片数据")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"读取封面数据失败: {e}")
        return None

    def get_display_data(self, config: Optional[Dict[str, Any]] = None) -> tuple[bytes, str]:
        """
        根据配置策略获取显示用的图片数据

        Args:
            config: 封面配置字典，包含:
                - read_strategy: auto/original
                - pixel_threshold: 像素阈值
                - thumbnail_max_size: 缩略图最大尺寸
                - thumbnail_quality: 缩略图质量

        Returns:
            (图片数据, MIME类型)
        """
        import logging
        logger = logging.getLogger(__name__)

        # 默认配置
        if config is None:
            config = {}

        read_strategy = config.get('read_strategy', 'auto')
        pixel_threshold = config.get('pixel_threshold', 500000)
        thumbnail_max_size = config.get('thumbnail_max_size', 300)
        thumbnail_quality = config.get('thumbnail_quality', 85)

        # 读取图片数据
        image_data = self._read_image_data()
        if not image_data:
            return (b'', self.mime_type)

        # 强制使用原图
        if read_strategy == 'original':
            logger.debug("使用原图（策略: original）")
            return (image_data, self.mime_type)

        # 自动策略：基于像素阈值判断
        if read_strategy == 'auto':
            self._ensure_dimensions_loaded()
            pixel_count = self.pixel_count

            # 像素数低于阈值，直接返回原图
            if pixel_count <= pixel_threshold:
                logger.debug(f"使用原图（{pixel_count} <= {pixel_threshold}）")
                return (image_data, self.mime_type)

            # 超过阈值，生成缩略图
            logger.debug(f"生成缩略图（{pixel_count} > {pixel_threshold}）")
            return self._generate_thumbnail(image_data, thumbnail_max_size, thumbnail_quality)

        # 默认返回原图
        return (image_data, self.mime_type)

    def _generate_thumbnail(self, image_data: bytes, max_size: int, quality: int) -> tuple[bytes, str]:
        """生成缩略图"""
        try:
            import io
            from PIL import Image
            import logging

            logger = logging.getLogger(__name__)

            # 输入 BytesIO
            input_io = io.BytesIO(image_data)

            # 打开图片
            img = Image.open(input_io)

            # 在缩放前保存格式信息
            img_format = img.format or 'JPEG'

            # 保持比例缩放
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # 输出为字节
            output = io.BytesIO()
            img.save(output, format=img_format, quality=quality)

            # 关闭图片
            img.close()

            result = output.getvalue()
            logger.debug(f"缩略图生成成功: {img.size}, 格式={img_format}, 质量={quality}, 大小={len(result)} 字节")
            return (result, f'image/{img_format.lower()}')

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"生成缩略图失败，返回原图: {e}")
            return (image_data, self.mime_type)

    def get_cache_key(self) -> str:
        if self.hash_checksum:
            return self.hash_checksum

        if self.is_embedded:
            mtime = self.source_audio_path.stat().st_mtime
            return f"emb_{hash((str(self.source_audio_path), mtime, self.embedded_offset))}"
        elif self.is_external:
            mtime = self.external_path.stat().st_mtime
            return f"ext_{hash((str(self.external_path), mtime))}"
        else:
            raise ValueError("Invalid artwork: no source")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        result = {
            "mime_type": self.mime_type,
            "embedded_offset": self.embedded_offset,
            "source_audio_path": str(self.source_audio_path) if self.source_audio_path else None,
            "external_path": str(self.external_path) if self.external_path else None,
            "description": self.description,
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
            "hash_checksum": self.hash_checksum,
            "size_kb": self.size_kb,
            "is_embedded": self.is_embedded,
            "is_external": self.is_external,
            "extension": self.extension,
        }

        # 如果有尺寸信息，添加 dimensions 字段
        if self.dimensions:
            result["dimensions"] = self.dimensions

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Artwork':
        return cls(
            mime_type=data["mime_type"],
            embedded_offset=data.get("embedded_offset"),
            source_audio_path=Path(data["source_audio_path"]) if data.get("source_audio_path") else None,
            external_path=Path(data["external_path"]) if data.get("external_path") else None,
            description=data.get("description"),
            width=data.get("width"),
            height=data.get("height"),
            size_bytes=data.get("size_bytes"),
            hash_checksum=data.get("hash_checksum"),
        )

    def __repr__(self) -> str:
        src = "embedded" if self.is_embedded else "external" if self.is_external else "invalid"
        dims = f"{self.width}x{self.height}" if self.dimensions else "unknown"
        return f"Artwork({src}, {self.mime_type}, {dims})"

@dataclass
class SongMetadata:
    """歌曲元数据（ID3等标签信息）"""
    # 核心元数据
    title: str = ""  # 歌曲标题
    artist: str = ""  # 艺术家
    album: str = ""  # 专辑名
    album_artist: Optional[str] = None  # 专辑艺术家
    
    # 辅助元数据
    genre: Optional[str] = None  # 流派
    composer: Optional[str] = None  # 作曲者
    performer: Optional[str] = None  # 表演者
    lyricist: Optional[str] = None  # 作词者
    conductor: Optional[str] = None  # 指挥者
    publisher: Optional[str] = None  # 出版商
    
    # 序号信息
    track_number: Optional[int] = None  # 音轨号
    total_tracks: Optional[int] = None  # 总音轨数
    disc_number: Optional[int] = None  # 碟片号
    total_discs: Optional[int] = None  # 总碟片数
    
    # 时间信息
    year: Optional[int] = None  # 年份
    date: Optional[str] = None  # 完整日期字符串
    original_date: Optional[str] = None  # 原始发行日期
    
    # 其他
    comment: Optional[str] = None  # 评论
    lyrics: Optional[str] = None  # 歌词文本（内嵌）
    copyright: Optional[str] = None  # 版权信息
    bpm: Optional[int] = None  # 每分钟节拍数
    isrc: Optional[str] = None  # 国际标准录音代码

@dataclass
class FileInfo:
    """文件系统信息"""
    path: Path  # 完整路径
    size_bytes: int  # 文件大小（字节）
    created_time: datetime  # 创建时间
    modified_time: datetime  # 修改时间
    accessed_time: datetime  # 访问时间
    
    @property
    def filename(self) -> str:
        """文件名（含扩展名）"""
        return self.path.name
    
    @property
    def stem(self) -> str:
        """文件名（不含扩展名）"""
        return self.path.stem
    
    @property
    def suffix(self) -> str:
        """文件扩展名"""
        return self.path.suffix.lower()
    
    @property
    def parent_dir(self) -> str:
        """父目录名"""
        return self.path.parent.name
    
    @property
    def directory(self) -> Path:
        """所在目录路径"""
        return self.path.parent
    
    @property
    def size_mb(self) -> float:
        """文件大小（MB）"""
        return self.size_bytes / (1024 * 1024)
    
    @property
    def size_readable(self) -> str:
        """人类可读的文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.size_bytes < 1024.0:
                return f"{self.size_bytes:.1f} {unit}"
            self.size_bytes /= 1024.0
        return f"{self.size_bytes:.1f} TB"

@dataclass
class LyricLine:
    """歌词行数据结构"""
    time: float  # 时间戳（秒）
    text: str  # 歌词文本
    original_timestamp: Optional[str] = None  # 原始时间戳字符串（用于调试）

    def __lt__(self, other):
        """支持按时间排序"""
        if isinstance(other, LyricLine):
            return self.time < other.time
        return NotImplemented

    def __repr__(self) -> str:
        minutes = int(self.time // 60)
        seconds = int(self.time % 60)
        centiseconds = int((self.time % 1) * 100)
        return f"[{minutes:02d}:{seconds:02d}.{centiseconds:02d}] {self.text}"

@dataclass
class LyricInfo:
    """歌词信息"""
    text: Optional[str] = None  # 歌词文本（LRC格式）
    synced: bool = False  # 是否已同步（有时轴）
    source: str = "embedded"  # 来源: embedded/file/network
    language: Optional[str] = None  # 语言代码

    # 解析后的结构化歌词（懒加载）
    _parsed_lines: Optional[List[LyricLine]] = field(default=None, repr=False)

    @property
    def has_lyrics(self) -> bool:
        """是否有歌词"""
        return self.text is not None and len(self.text.strip()) > 0

    @property
    def lines(self) -> List[LyricLine]:
        """获取解析后的歌词行列表"""
        if self._parsed_lines is None and self.has_lyrics:
            from app.core.lyric.parser import LRCParser
            self._parsed_lines = LRCParser.parse(self.text)
        return self._parsed_lines or []

@dataclass
class Song:
    """
    歌曲数据结构
    包含播放音乐所必需的所有信息，设计为可序列化
    """
    # ========== 必需字段（播放核心）==========
    file_info: FileInfo  # 文件信息
    metadata: SongMetadata  # 元数据
    audio_format: AudioFormat  # 音频格式
    duration: float  # 时长（秒）
    # id: str = field(default_factory=lambda: hashlib.md5().hexdigest()[:12]) # 内部标识符，参考foobar，暂不设置
    
    # ========== 可选字段（增强功能）==========
    replaygain: ReplayGain = field(default_factory=ReplayGain)  # 音量平衡
    artwork: Optional[Artwork] = None  # 封面
    lyrics: LyricInfo = field(default_factory=LyricInfo)  # 歌词
    rating: Optional[int] = None  # 评分 0-5
    play_count: int = 0  # 播放次数
    last_played: Optional[datetime] = None  # 最后播放时间
    
    # ========== 播放状态字段（非持久化）==========
    current_position: float = 0.0  # 当前播放位置（秒）
    lyric_offset: float = 0.0  # 歌词时间偏移（秒，用户设定）
    is_favorite: bool = False  # 是否收藏
    
    # ========== 计算属性 ==========
    @property
    def display_title(self) -> str:
        """显示用的标题（优先使用元数据，否则使用文件名）"""
        if self.metadata.title and self.metadata.title.strip():
            return self.metadata.title.strip()
        return self.file_info.stem
    
    @property
    def display_artist(self) -> str:
        """显示用的艺术家"""
        if self.metadata.artist and self.metadata.artist.strip():
            return self.metadata.artist.strip()
        return "未知艺术家"
    
    @property
    def display_album(self) -> str:
        """显示用的专辑"""
        if self.metadata.album and self.metadata.album.strip():
            return self.metadata.album.strip()
        return "未知专辑"
    
    @property
    def duration_formatted(self) -> str:
        """格式化的时长 (MM:SS)"""
        minutes = int(self.duration // 60)
        seconds = int(self.duration % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    @property
    def has_artwork(self) -> bool:
        """是否有封面"""
        return self.artwork is not None
    
    # 考虑将音质检测做成插件，暂不实现
    # @property
    # def quality_score(self) -> float:
    #     """音质评分（0-10，用于排序）"""
    #     score = 0.0
    #     
    #     # 编码类型权重
    #     if self.audio_format.encoding == "lossless":
    #         score += 3.0
    #     elif self.audio_format.encoding == "uncompressed":
    #         score += 4.0
    #     
    #     # 比特率权重
    #     if self.audio_format.bitrate >= 320:
    #         score += 3.0
    #     elif self.audio_format.bitrate >= 256:
    #         score += 2.0
    #     elif self.audio_format.bitrate >= 192:
    #         score += 1.0
    #     
    #     # 采样率权重
    #     if self.audio_format.sample_rate >= 96000:
    #         score += 2.0
    #     elif self.audio_format.sample_rate >= 48000:
    #         score += 1.0
    #     
    #     # 位深度权重
    #     if self.audio_format.bit_depth and self.audio_format.bit_depth >= 24:
    #         score += 1.0
    #     elif self.audio_format.bit_depth and self.audio_format.bit_depth >= 16:
    #         score += 0.5
    #     
    #     return min(score, 10.0)
    
    @property
    def file_type(self) -> str:
        """文件类型分类"""
        suffix = self.file_info.suffix
        if suffix in ['.mp3', '.mp2', '.mp1']:
            return 'MPEG'
        elif suffix in ['.flac']:
            return 'FLAC'
        elif suffix in ['.wav', '.wave']:
            return 'WAV'
        elif suffix in ['.ogg', '.oga']:
            return 'OGG'
        elif suffix in ['.m4a', '.mp4']:
            return 'AAC'
        elif suffix in ['.opus']:
            return 'Opus'
        else:
            return '其他'
    
    # ========== 序列化方法 ==========
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        result = {
            # 文件信息
            "path": str(self.file_info.path),
            "size_bytes": self.file_info.size_bytes,
            "filename": self.file_info.filename,
            
            # 元数据
            "title": self.metadata.title,
            "artist": self.metadata.artist,
            "album": self.metadata.album,
            "track_number": self.metadata.track_number,
            
            # 音频格式
            "codec": self.audio_format.codec,
            "encoding": self.audio_format.encoding,
            "bitrate": self.audio_format.bitrate,
            "sample_rate": self.audio_format.sample_rate,
            "channels": self.audio_format.channels,
            "duration": self.duration,
            
            # 状态
            "play_count": self.play_count,
            "rating": self.rating,
            "is_favorite": self.is_favorite,
            
            # 计算属性
            "display_title": self.display_title,
            "display_artist": self.display_artist,
            "duration_formatted": self.duration_formatted,
            "has_artwork": self.has_artwork,
            "has_lyrics": self.lyrics.has_lyrics,
        }
        
        # 添加封面（如果存在且较小）
        if self.artwork and self.artwork.size_kb < 100:  # 仅添加小于100KB的封面
            result["artwork_thumbnail"] = self.artwork.data_base64[:500] + "..."
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Song':
        """从字典创建Song对象（反序列化）"""
        # 注意：这是一个简化版本，实际实现需要更完整的字段处理
        file_info = FileInfo(
            path=Path(data["path"]),
            size_bytes=data["size_bytes"],
            created_time=datetime.now(),
            modified_time=datetime.now(),
            accessed_time=datetime.now(),
        )
        
        metadata = SongMetadata(
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            album=data.get("album", ""),
            track_number=data.get("track_number"),
        )
        
        audio_format = AudioFormat(
            codec=data.get("codec", "MP3"),
            bitrate=data.get("bitrate", 0),
            sample_rate=data.get("sample_rate", 44100),
            channels=data.get("channels", 2),
        )
        
        return cls(
            file_info=file_info,
            metadata=metadata,
            audio_format=audio_format,
            duration=data.get("duration", 0.0),
            play_count=data.get("play_count", 0),
            rating=data.get("rating"),
            is_favorite=data.get("is_favorite", False),
        )
