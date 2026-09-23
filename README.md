# 终端音乐播放器项目

一个功能丰富的终端音乐播放器，支持多种音频格式解析、元数据提取、歌词同步显示和播放列表管理。

## 测试音频路径
- 主要测试音频：`/mnt/d/music/其他/Distortion!! - 結束バンド.mp3`
- 批量测试目录：`/mnt/d/music/其他/` (约300个MP3文件)
- FLAC测试目录：`/mnt/d/music/flac/` (约10个FLAC/WAV文件)

---

## 项目结构

```
dev/
├── app/
│   ├── core/
│   │   ├── parsers/          # 音频文件解析器
│   │   │   ├── __init__.py   # 解析器入口和注册
│   │   │   ├── base.py       # 解析器基类和工厂模式
│   │   │   ├── mp3_parser.py # MP3格式解析器实现
│   │   │   └── flac_parser.py # FLAC格式解析器实现
│   │   ├── lyric/            # 歌词处理
│   │   │   ├── __init__.py   # 歌词模块入口
│   │   │   ├── finder.py     # 歌词查找器（LRC/内嵌）
│   │   │   ├── parser.py     # LRC歌词解析器
│   │   │   └── manager.py    # 歌词同步管理器
│   │   ├── player/           # 音频播放引擎
│   │   │   └── audio_engine.py # 音频播放引擎（支持MP3/FLAC/WAV）
│   │   └── ui/               # 用户界面
│   ├── models/               # 数据模型
│   │   ├── song.py           # Song数据模型
│   │   └── playlist.py       # Playlist数据模型
│   ├── metadata_extractor.py # 元数据提取统一接口
│   ├── example_usage.py      # API使用示例
│   └── main.py               # 主程序入口
├── config/
│   ├── config.py             # 配置管理
│   └── config.yaml           # 配置文件（歌词、封面）
├── test/
│   ├── test_audio.py         # 音频播放测试（统一入口）
│   ├── test_lyric.py         # 歌词解析测试
│   ├── test_lyric_manager.py # 歌词管理器测试
│   ├── test_lyric_offset.py  # 歌词偏移测试
│   ├── test_play_with_lyrics.py # 播放+歌词集成测试
│   └── test.py              # 元数据解析测试工具
└── README.md                 # 项目文档
```

---

## 核心API文档

### 1. 数据模型 (`app/models/`)

#### Song - 歌曲数据模型
**位置**: `app/models/song.py`

**主要属性**:
```python
class Song:
    file_info: FileInfo        # 文件信息（路径、大小、时间）
    metadata: SongMetadata     # 元数据（标题、艺术家、专辑等）
    audio_format: AudioFormat  # 音频格式（编码、采样率、比特率）
    replaygain: ReplayGain     # ReplayGain音量平衡信息
    artwork: Artwork           # 封面信息
    lyrics: LyricInfo          # 歌词信息
    duration: float            # 时长（秒）

    # 播放状态字段（非持久化）
    current_position: float    # 当前播放位置（秒）
    lyric_offset: float        # 歌词时间偏移（秒，用户设定）
    is_favorite: bool          # 是否收藏

    # 便捷属性
    @property
    def display_title(self) -> str:    # 显示用的标题
    @property
    def display_artist(self) -> str:   # 显示用的艺术家
    @property
    def display_album(self) -> str:    # 显示用的专辑
    @property
    def duration_formatted(self) -> str: # 格式化的时长（MM:SS）
    @property
    def has_artwork(self) -> bool:      # 是否有封面
```

#### LyricInfo - 歌词信息
**位置**: `app/models/song.py`

**主要属性**:
```python
class LyricInfo:
    text: str                   # 歌词文本（LRC格式）
    synced: bool               # 是否已同步（有时轴）
    source: str                # 来源: embedded/file/network
    language: str              # 语言代码

    # 解析后的结构化歌词（懒加载）
    @property
    def lines(self) -> List[LyricLine]:  # 歌词行列表

    @property
    def has_lyrics(self) -> bool:         # 是否有歌词
```

#### LyricLine - 歌词行数据结构
**位置**: `app/models/song.py`

**主要属性**:
```python
class LyricLine:
    time: float                    # 时间戳（秒）
    text: str                      # 歌词文本
    original_timestamp: str         # 原始时间戳字符串（用于调试）

    def __lt__(self, other) -> bool: # 支持按时间排序
    def __repr__(self) -> str:       # 格式化为 LRC 时间戳格式
```

#### FileInfo - 文件信息
**位置**: `app/models/song.py`

**主要属性**:
```python
class FileInfo:
    path: Path               # 文件路径
    size_bytes: int          # 文件大小（字节）
    created_time: datetime   # 创建时间
    modified_time: datetime  # 修改时间
    accessed_time: datetime  # 访问时间
```

#### SongMetadata - 歌曲元数据
**位置**: `app/models/song.py`

**主要属性**:
```python
class SongMetadata:
    title: str               # 标题
    artist: str              # 艺术家
    album: str               # 专辑
    year: int                # 年份
    genre: str               # 流派
    track_number: int        # 音轨号
    total_tracks: int        # 总音轨数
    disc_number: int         # 盘号
    total_discs: int         # 总盘数
```

#### AudioFormat - 音频格式信息
**位置**: `app/models/song.py`

**主要属性**:
```python
class AudioFormat:
    codec: str           # 编码格式 (MP3, FLAC, WAV等)
    profile: str         # 编码配置档 (MP3/FLAC)
    encoding: str        # 编码类型: lossy/lossless/uncompressed
    sample_rate: int      # 采样率 (Hz)
    channels: int        # 声道数
    bitrate: int         # 比特率 (kbps)
    bit_depth: int       # 位深度 (16-bit, 24-bit)
```

#### AudioFormat - 音频格式信息
```python
class AudioFormat:
    codec: str           # 编码格式 (MP3, FLAC, WAV等)
    encoding: str        # 编码类型: lossy/lossless/uncompressed
    sample_rate: int    # 采样率 (Hz)
    channels: int       # 声道数
    bitrate: int        # 比特率 (kbps)
    bit_depth: int      # 位深度 (16-bit, 24-bit)
```

---

### 2. 解析器类 (`app/core/parsers/`)

#### ParserFactory - 解析器工厂
**位置**: `app/core/parsers/base.py`

**主要功能**:
```python
# 解析文件（自动调度）
@classmethod
def parse_file(cls, file_path: Path) -> Optional[Song]:
    """解析文件（自动选择解析器）"""

# 获取所有支持格式
@classmethod
def get_supported_extensions(cls) -> List[str]:
    """获取所有已注册解析器支持的格式"""

# 注册新解析器
@classmethod
def register_parser(cls, parser_class: AudioParser):
    """注册新的解析器类"""
```

#### MP3Parser - MP3文件解析器
**位置**: `app/core/parsers/mp3_parser.py`

**主要功能**:
- 支持格式: `.mp3`, `.mp2`, `.mp1`
- 提取信息: ID3标签、音频参数、封面、歌词
- 使用的库: `mutagen`

**核心方法**:
```python
@classmethod
def can_parse(cls, file_path: Path) -> bool:
    """检查是否能解析该文件"""

@classmethod
def parse(cls, file_path: Path) -> Optional[Song]:
    """解析MP3文件并创建Song对象"""

@classmethod
def get_supported_extensions(cls) -> List[str]:
    """获取支持的扩展名列表"""
```

#### AudioParser - 解析器基类
**位置**: `app/core/parsers/base.py`

**抽象方法**:
```python
@classmethod
@abstractmethod
def can_parse(cls, file_path: Path) -> bool:
    """检查是否能解析该文件"""

@classmethod
@abstractmethod
def parse(cls, file_path: Path) -> Optional[Song]:
    """解析音频文件并创建Song对象"""

@classmethod
@abstractmethod
def get_supported_extensions(cls) -> List[str]:
    """获取支持的扩展名"""
```

---

### 6. 歌词模块 (`app/core/lyric/`)

#### LRCParser - LRC歌词解析器
**位置**: `app/core/lyric/parser.py`

**主要功能**:
- 解析LRC格式歌词（标准时间戳格式）
- 支持元数据标签（ti, ar, al, by等）
- 支持一行多时间戳（同一歌词多次出现）
- 支持双语/多语歌词（相同时间戳多行）
- 查找指定时间对应歌词行（二分查找）
- 获取前后歌词行（用于显示上下文）

**核心方法**:
```python
class LRCParser:
    @classmethod
    def parse(cls, lrc_text: str) -> List[LyricLine]:
        """解析LRC格式歌词文本"""

    @classmethod
    def find_line_at_time(cls, lines: List[LyricLine], time: float) -> Optional[LyricLine]:
        """查找指定时间对应的歌词行（返回最后匹配行）"""

    @classmethod
    def get_lines_around_time(cls, lines: List[LyricLine], time: float,
                              before: int = 2, after: int = 2) -> Tuple[List[LyricLine], int]:
        """获取指定时间前后的歌词行和当前索引"""

    @classmethod
    def is_synced_lyrics(cls, lrc_text: str) -> bool:
        """检测是否为同步歌词（包含时间戳）"""

    @classmethod
    def serialize(cls, lines: List[LyricLine],
                  metadata: Optional[Dict[str, str]] = None) -> str:
        """将歌词行列表序列化为LRC格式文本"""

    @staticmethod
    def format_time(seconds: float) -> str:
        """将秒数格式化为LRC时间戳 [mm:ss.xx]"""
```

**使用示例**:
```python
from app.core.lyric import LRCParser

# 解析LRC歌词
lrc_text = """[00:00.00]第一行歌词
[00:05.50]第二行歌词
[00:10.20]第三行歌词"""

lines = LRCParser.parse(lrc_text)
for line in lines:
    print(f"[{line.time:.2f}] {line.text}")
# 输出: [0.00] 第一行歌词
#       [5.50] 第二行歌词
#       [10.20] 第三行歌词

# 查找指定时间的歌词
current_line = LRCParser.find_line_at_time(lines, 6.0)
print(current_line.text)  # 输出: 第二行歌词

# 获取前后歌词行
before, current, after = LRCParser.get_lines_around_time(lines, 6.0, before=1, after=1)
```

#### LyricFinder - 歌词查找器
**位置**: `app/core/lyric/finder.py`

**主要功能**:
- 多源歌词查找（LRC文件 + 内嵌歌词）
- 支持自定义查找路径模板
- 自动编码检测
- 查找优先级配置

**核心方法**:
```python
class LyricFinder:
    @classmethod
    def find_lyrics(cls, song: Song, config: Optional[Dict] = None) -> LyricInfo:
        """查找歌词（按优先级尝试多个来源）"""

    @classmethod
    def _find_lrc_file(cls, song: Song, config: Optional[Dict] = None) -> Optional[str]:
        """查找LRC歌词文件"""

    @classmethod
    def _load_lrc_file(cls, file_path: Path, encoding_priority: List[str]) -> Optional[str]:
        """加载LRC文件内容（处理编码）"""
```

**使用示例**:
```python
from app.core.lyric import LyricFinder
from app.metadata_extractor import parse_audio_file

song = parse_audio_file(Path("song.mp3"))
lyrics = LyricFinder.find_lyrics(song)

if lyrics.has_lyrics:
    print(f"歌词来源: {lyrics.source}")
    print(f"是否同步: {lyrics.synced}")
```

#### LyricManager - 歌词同步管理器
**位置**: `app/core/lyric/manager.py`

**主要功能**:
- 根据播放位置实时追踪当前歌词行
- 支持歌词偏移调整（用户实时设定）
- 支持双语/多语歌词显示
- 歌词切换时触发事件回调
- 获取显示上下文（前后歌词行）

**核心方法**:
```python
class LyricManager:
    def load(self, song: Song) -> bool:
        """加载歌曲的歌词"""

    def update(self, playback_position: float) -> Optional[LyricLine]:
        """根据播放位置更新当前歌词行"""

    def set_offset(self, offset: float):
        """设置歌词偏移量（秒）"""

    def adjust_offset(self, delta: float):
        """调整歌词偏移量（秒）"""

    def set_enabled(self, enabled: bool):
        """启用或禁用歌词显示"""

    def get_concurrent_lines(self) -> List[LyricLine]:
        """获取与当前歌词行时间戳相同的所有行（处理双语歌词）"""

    def get_display_context(self, before: int = 2, after: int = 2):
        """获取用于显示的歌词上下文"""

    def set_line_change_callback(self, callback: Callable):
        """设置歌词行切换回调"""

    def set_offset_change_callback(self, callback: Callable):
        """设置偏移量变化回调"""

    def reset(self):
        """重置管理器状态"""

    @property
    def has_lyrics(self) -> bool:
        """是否有可用的歌词"""

    @property
    def current_line(self) -> Optional[LyricLine]:
        """当前歌词行"""

    @property
    def offset(self) -> float:
        """歌词偏移量（秒）"""
```

**使用示例**:
```python
from app.core.lyric import LyricManager
from app.core.player import AudioEngine
from app.metadata_extractor import parse_audio_file

# 加载歌曲
song = parse_audio_file(Path("song.mp3"))

# 创建歌词管理器
manager = LyricManager()
manager.load(song)

# 设置回调
def on_line_change(line, index):
    print(f"歌词切换: [{line.time:.2f}] {line.text}")

def on_offset_change(offset):
    print(f"偏移调整: {offset:+.1f}秒")

manager.set_line_change_callback(on_line_change)
manager.set_offset_change_callback(on_offset_change)

# 播放时更新歌词
engine = AudioEngine()
engine.play(Path("song.mp3"))

while engine.is_playing:
    pos = engine.get_position()
    manager.update(pos)

    # 获取当前显示的歌词
    current_line = manager.current_line
    if current_line:
        # 获取双语歌词
        concurrent_lines = manager.get_concurrent_lines()
        for line in concurrent_lines:
            print(line.text)

    time.sleep(0.1)

# 用户调整偏移
manager.adjust_offset(0.5)  # 延迟 0.5 秒
manager.adjust_offset(-0.5)  # 提前 0.5 秒
```

---

### 3. 元数据提取器 (`app/metadata_extractor.py`)

#### MetadataExtractor - 元数据提取统一接口
**位置**: `app/metadata_extractor.py`

**主要函数**:
```python
# 解析单个音频文件
def parse_audio_file(file_path: Path, config: Optional[Dict] = None) -> Optional[Song]:
    """解析音频文件（自动选择解析器）"""

# 解析目录中的音频文件
def parse_audio_directory(directory_path: Path, recursive: bool = False) -> Iterator[Song]:
    """解析目录中的音频文件（批量处理）"""

# 获取支持的音频格式
def get_supported_extensions() -> List[str]:
    """获取支持的音频文件扩展名列表"""

# 检查文件是否能被解析
def can_parse_file(file_path: Path) -> bool:
    """检查是否能解析指定文件"""

# 配置管理
def set_config(config: Dict):
    """设置全局配置（用于歌词查找）"""
```

---

### 4. 音频播放引擎 (`app/core/player/`)

#### AudioEngine - 音频播放引擎
**位置**: `app/core/player/audio_engine.py`

**主要功能**:
- 支持格式: MP3, FLAC, WAV, OGG, M4A
- 基础控制: 播放、暂停、继续、停止
- 进度控制: 跳转到指定位置
- 音量控制: 0-100%
- 状态获取: 实时播放状态

**核心方法**:
```python
class AudioEngine:
    def __init__(self, keep_device: bool = True):
        """
        Args:
            keep_device: 是否在暂停时保持设备实例以降低延迟
        """

    def play(self, file_path: Path) -> bool:
        """播放指定文件"""

    def pause(self) -> bool:
        """暂停播放"""

    def resume(self) -> bool:
        """继续播放"""

    def stop(self) -> bool:
        """停止播放"""

    def seek(self, position: float) -> bool:
        """跳转到指定位置（秒）"""

    def set_volume(self, volume: float) -> bool:
        """设置音量 (0.0 - 1.0)"""

    @property
    def status(self) -> PlaybackStatus:
        """获取当前播放状态"""

    @property
    def is_playing(self) -> bool:
        """是否正在播放"""

    def set_state_change_callback(self, callback: Callable[[PlaybackState], None]):
        """设置状态变化回调"""
```

**使用示例**:
```python
from app.core.player.audio_engine import AudioEngine

engine = AudioEngine(keep_device=True)

# 播放
engine.play(Path("song.mp3"))

# 暂停
engine.pause()

# 跳转到 30 秒
engine.seek(30.0)

# 设置音量 70%
engine.set_volume(0.7)

# 停止
engine.stop()
```

---

### 5. 测试类

#### test_lyric.py - 歌词解析测试
**位置**: `test/test_lyric.py`

**主要功能**:
- LRC解析器功能测试
- MP3内嵌歌词提取测试
- 时间戳查找测试
- 歌词偏移测试

**使用方法**:
```bash
python3 test/test_lyric.py
```

#### test_lyric_manager.py - 歌词管理器测试
**位置**: `test/test_lyric_manager.py`

**主要功能**:
- LyricManager基本功能测试
- 加载歌曲歌词
- 播放位置更新
- 偏移调整测试
- 回调机制测试

**使用方法**:
```bash
python3 test/test_lyric_manager.py
```

#### test_lyric_offset.py - 歌词偏移测试
**位置**: `test/test_lyric_offset.py`

**主要功能**:
- 演示歌词偏移功能
- 展示偏移如何在播放时动态应用

**使用方法**:
```bash
python3 test/test_lyric_offset.py
```

#### test_play_with_lyrics.py - 播放+歌词集成测试
**位置**: `test/test_play_with_lyrics.py`

**主要功能**:
- 播放音乐并同步显示歌词
- 支持双语/多语歌词显示
- 实时调整歌词偏移
- 交互式控制（暂停、跳转、偏移调整）

**使用方法**:
```bash
# 默认测试文件
python3 test/test_play_with_lyrics.py

# 指定音乐文件
python3 test/test_play_with_lyrics.py "/path/to/music.mp3"
```

**控制键**:
- 空格 - 暂停/继续播放
- q - 退出
- +/- - 调整歌词偏移（实时生效）
- l - 启用/禁用歌词

#### test_audio.py - 音频播放测试
**位置**: `test/test_audio.py`

**主要功能**:
- 交互式播放测试
- 暂停/继续循环测试
- 跳转操作测试
- 延迟统计报告

**使用方法**:
```bash
# 交互模式（默认）
python3 test/test_audio.py

# 特定测试
python3 test/test_audio.py --test info      # 文件信息
python3 test/test_audio.py --test devices   # 设备枚举
python3 test/test_audio.py --test direct   # 直接播放
python3 test/test_audio.py --test pause    # 暂停/继续测试
python3 test/test_audio.py --test seek     # 跳转测试
python3 test/test_audio.py --test cli      # 交互模式

# 指定文件
python3 test/test_audio.py --file "/path/to/file.flac"

# 播放时长
python3 test/test_audio.py --test direct --duration 10
```

#### test.py - 元数据解析测试
**位置**: `test/test.py`

**主要功能**:
- 支持命令行参数解析
- 单个文件测试和批量目录测试
- 多种输出格式（TXT、JSON、同时输出）
- 生成摘要报告和统计数据

**使用方法**:
```bash
# 显示帮助
python3 test/test.py --help

# 测试单个文件
python3 test/test.py -f "/path/to/file.mp3" -v

# 批量测试目录
python3 test/test.py -d "/path/to/music" --max-files 10 --summary

# 检查歌词文件
python3 test/test.py -d "/path/to/music" --check-lyrics
```

---

## 使用示例

### 数据模型使用示例

```python
from pathlib import Path
from app.models.song import Song
from app.metadata_extractor import parse_audio_file

# 解析音频文件
song = parse_audio_file(Path("song.mp3"))

if song:
    # 访问元数据
    print(f"标题: {song.display_title}")
    print(f"艺术家: {song.display_artist}")
    print(f"专辑: {song.display_album}")
    print(f"时长: {song.duration_formatted}")
    print(f"格式: {song.audio_format.codec}")
    print(f"比特率: {song.audio_format.bitrate}kbps")

    # 访问封面信息
    if song.has_artwork:
        print(f"封面: {song.artwork.mime_type}")
        print(f"尺寸: {song.artwork.dimensions}")

    # 访问歌词
    if song.lyrics.has_lyrics:
        print(f"歌词来源: {song.lyrics.source}")
```

### 解析器使用示例

```python
from pathlib import Path
from app.core.parsers import ParserFactory

# 自动选择解析器
song = ParserFactory.parse_file(Path("song.mp3"))

# 获取支持的格式
formats = ParserFactory.get_supported_extensions()
print(f"支持的格式: {formats}")

# 检查文件是否能解析
can_parse = ParserFactory.get_parser(Path("song.flac"))
```

### 元数据提取器使用示例

```python
from pathlib import Path
from app.metadata_extractor import (
    parse_audio_file,
    parse_audio_directory,
    get_supported_extensions
)

# 解析单个文件
song = parse_audio_file(Path("song.mp3"))

# 批量解析目录
for song in parse_audio_directory(Path("/music"), recursive=True):
    print(f"{song.display_artist} - {song.display_title}")

# 获取支持的格式
formats = get_supported_extensions()
print(f"支持的格式: {', '.join(formats)}")
```

### 音频播放使用示例

```python
from pathlib import Path
from app.core.player.audio_engine import AudioEngine

engine = AudioEngine(keep_device=True)

# 设置状态变化回调
def on_state_change(state):
    state_names = {
        PlaybackState.PLAYING: "播放中",
        PlaybackState.PAUSED: "已暂停",
        PlaybackState.STOPPED: "已停止"
    }
    print(f"状态: {state_names.get(state)}")

engine.set_state_change_callback(on_state_change)

# 播放控制
engine.play(Path("song.mp3"))
engine.pause()
engine.resume()
engine.seek(30.0)
engine.set_volume(0.7)
engine.stop()

# 获取状态
status = engine.status
print(f"位置: {status.position:.1f}/{status.duration:.1f}s")
print(f"音量: {status.volume * 100:.0f}%")
```

---

## 常见问题

### Q1: 支持哪些音频格式？
**A**: 当前支持的格式包括：
- MP3 (`.mp3`, `.mp2`, `.mp1`)
- FLAC (`.flac`)
- WAV (`.wav`, `.wave`)
- OGG (`.ogg`, `.oga`)
- AAC (`.m4a`, `.mp4`)

### Q2: 音频播放延迟高怎么办？
**A**: WSL2 环境下音频延迟是正常现象（200-500ms）。可以尝试：
- 使用 `AudioEngine(keep_device=True)` 保持设备实例
- 确保使用 PulseAudio 后端
- 避免频繁的 seek 操作

### Q3: 如何添加新的音频格式支持？
**A**: 继承 `AudioParser` 基类并实现必要方法：

```python
from app.core.parsers.base import AudioParser
from app.models.song import Song
from pathlib import Path
from typing import Optional, List

class CustomParser(AudioParser):
    @classmethod
    def can_parse(cls, file_path: Path) -> bool:
        return file_path.suffix.lower() == '.custom'

    @classmethod
    def parse(cls, file_path: Path) -> Optional[Song]:
        # 实现解析逻辑
        pass

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        return ['.custom']

# 注册解析器
from app.core.parsers.base import ParserFactory
ParserFactory.register_parser(CustomParser)
```

### Q4: 歌词文件找不到怎么办？
**A**: 检查 `config/config.yaml` 中的歌词配置：
- 确保 `lyrics.lrc.search_patterns` 包含正确的查找模式
- 检查歌词文件编码是否在 `encoding_priority` 列表中
- 启用 `use_charset_detection: true` 自动检测编码

### Q5: 封面显示过大或加载慢？
**A**: 调整 `config/config.yaml` 中的封面配置：
- 设置 `read_strategy: auto` 自动选择
- 降低 `pixel_threshold` 使用原图
- 减小 `thumbnail_max_size` 生成更小的缩略图

---

## 依赖项

### 核心依赖
```python
mutagen        # 音频元数据解析
rich           # 终端UI渲染
pylrc          # LRC歌词解析
numpy          # 数值计算，暂未引入
pillow         # 图像处理（封面处理）
miniaudio      # 音频播放引擎
pyyaml         # 配置文件解析
```

### 开发依赖
- Python 3.8+
- pathlib, typing, datetime (标准库)

---

## 配置文件

### config/config.yaml

配置文件支持以下选项：

**歌词配置** (`lyrics`):
- `priority`: 歌词源优先级 (lrc, embedded)
- `lrc.search_patterns`: LRC文件查找路径模板
- `lrc.use_charset_detection`: 是否启用自动编码检测
- `lrc.encoding_priority`: 编码优先级列表

**封面配置** (`artwork`):
- `read_strategy`: 读取策略 (auto, original)
- `pixel_threshold`: 自动策略的像素阈值
- `thumbnail_max_size`: 缩略图最大尺寸
- `thumbnail_quality`: 缩略图质量 (1-100)

## 项目状态

### 已实现功能

#### 核心模块
- [x] Song/Playlist数据模型（完整字段支持）
- [x] FileInfo/SongMetadata/AudioFormat/Artwork/ReplayGain 数据模型
- [x] LyricInfo/LyricLine 歌词数据模型
- [x] Song 播放状态字段（current_position, lyric_offset, is_favorite）

#### 解析器模块
- [x] AudioParser 解析器基类（抽象接口）
- [x] ParserFactory 解析器工厂模式（支持扩展）
- [x] MP3文件解析器（ID3标签、音频参数、封面、歌词）
- [x] FLAC文件解析器（Vorbis注释、音频参数、封面、歌词）
- [x] register_default_parsers 默认解析器注册

#### 元数据提取
- [x] 元数据提取统一接口（parse_audio_file, parse_audio_directory）
- [x] 集成测试工具（命令行支持）
- [x] JSON/TXT格式测试输出
- [x] 批量处理支持
- [x] 歌词文件查找支持（LyricFinder）

#### 歌词模块
- [x] LRCParser LRC歌词解析器
- [x] 解析LRC格式歌词（标准时间戳）
- [x] 支持元数据标签（ti, ar, al, by等）
- [x] 支持一行多时间戳
- [x] 支持双语/多语歌词（相同时间戳多行）
- [x] 查找指定时间对应歌词行（二分查找）
- [x] 获取前后歌词行（用于显示上下文）
- [x] 序列化为LRC格式
- [x] LyricFinder 歌词查找器（多源查找：LRC文件 + 内嵌）
- [x] LyricManager 歌词同步管理器
- [x] 实时歌词行追踪（根据播放位置）
- [x] 歌词偏移调整（用户实时设定）
- [x] 歌词切换事件回调
- [x] 双语/多语歌词显示支持

#### 音频播放
- [x] AudioEngine 音频播放引擎（基于miniaudio）
- [x] 支持MP3/FLAC/WAV/OGG/M4A格式
- [x] 基础控制：播放、暂停、继续、停止
- [x] 进度控制：跳转到指定位置
- [x] 音量控制：0-100%
- [x] 状态获取：实时播放状态
- [x] 状态变化回调

#### 测试工具
- [x] test_audio.py - 音频播放测试
- [x] test_lyric.py - 歌词解析测试
- [x] test_lyric_manager.py - 歌词管理器测试
- [x] test_lyric_offset.py - 歌词偏移测试
- [x] test_play_with_lyrics.py - 播放+歌词集成测试
- [x] test.py - 元数据解析测试

### 开发中功能
- [ ] 音量增益（自动增益/ReplayGain）
- [ ] TUI界面
    - 弱终端：curses
    - 富终端：Textual
- [ ] 播放列表管理界面
- [ ] 配置文件管理

### 计划功能
- [ ] 音频均衡器（EQ）
- [ ] 频谱图显示
- [ ] 封面图像显示
- [ ] 流媒体播放支持
- [ ] 更多音频格式支持（APE、MPC、WV等）
- [ ] 调试模式
