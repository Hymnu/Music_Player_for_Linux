# 音频文件解析器模块

这是一个可扩展的音频文件解析器系统，用于解析各种音频文件格式并创建 `Song` 对象。

## 目录结构

```
app/core/parsers/
├── __init__.py     # 模块接口
├── base.py         # 解析器基类和工厂
├── mp3_parser.py   # MP3 文件解析器
└── README.md       # 本文档
```

## 使用方法

### 1. 基本使用（推荐）

```python
from app.metadata_extractor import parse_single_file

# 解析单个文件
file_path = Path("song.mp3")
song = parse_single_file(file_path)

if song:
    print(f"标题: {song.display_title}")
    print(f"艺术家: {song.display_artist}")
    print(f"专辑: {song.display_album}")
    print(f"时长: {song.duration_formatted}")
    print(f"是否有封面: {song.has_artwork}")
```

### 2. 批量解析

```python
from app.metadata_extractor import parse_multiple_files

files = [Path("song1.mp3"), Path("song2.mp3")]
songs = parse_multiple_files(files)

for song in songs:
    print(f"找到: {song.display_title}")
```

### 3. 目录解析

```python
from app.metadata_extractor import parse_audio_directory

music_dir = Path("/path/to/music")
for song in parse_audio_directory(music_dir, recursive=True):
    print(f"处理: {song.display_title}")
```

### 4. 直接使用 MP3 解析器

```python
from app.core.parsers.mp3_parser import MP3Parser

# 检查是否能解析
if MP3Parser.can_parse(file_path):
    # 解析文件
    song = MP3Parser.parse(file_path)
```

### 5. 使用解析器工厂（支持自动选择）

```python
from app.core.parsers import ParserFactory

# 自动选择适合的解析器
parser_class = ParserFactory.get_parser(file_path)
if parser_class:
    song = parser_class.parse(file_path)
```

## 支持的属性

### 封面提取
- 支持内嵌封面（ID3 APIC 标签）
- 支持外部封面文件
- 自动检测 MIME 类型
- 缓存键生成

### 元数据提取
- 标题、艺术家、专辑
- 专辑艺术家、流派、年份
- 音轨号、碟号
- ISRC、BPM、编码器信息
- 注释、版权信息

### 音频格式信息
- 编码格式（MP3/FLAC 等）
- 比特率、采样率、声道数
- 编码类型（有损/无损）
- MP3 立体声模式
- 位深度（如果可用）

### 增强功能
- ReplayGain 音量平衡信息
- 歌词提取（USLT 标签）
- 播放统计和评分

## 扩展新格式

要添加对新音频格式的支持：

1. 创建新的解析器类（继承 `AudioParser`）
2. 实现抽象方法：
   - `can_parse()` - 检查是否能解析
   - `parse()` - 解析文件逻辑
   - `get_supported_extensions()` - 支持的扩展名

3. 注册到工厂：
```python
from app.core.parsers import ParserFactory

ParserFactory.register_parser(YourParser)
```

## 示例

完整的示例请查看：
- `app/example_usage.py` - 详细使用示例
- `test.py` - 集成测试示例

## 注意事项

1. **依赖**：需要 `mutagen` 库
   ```bash
   pip install mutagen
   ```

2. **错误处理**：所有解析器都包含详细的错误处理

3. **性能**：大文件或目录解析可能需要较长时间

4. **扩展性**：设计为插件式架构，便于添加新格式