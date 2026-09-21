#!/usr/bin/env python3
# MP3 解析器使用示例
# 演示如何使用新的 MP3 解析器模块和智能歌词查找

import logging
import yaml
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def demonstrate_parser_usage():
    """演示解析器的各种用法"""
    
    print("=" * 60)
    print("MP3 解析器使用示例")
    print("=" * 60)
    
    # 1. 导入解析器模块
    print("\n1. 导入解析器模块")
    print("-" * 40)
    
    try:
        # 方法A: 使用便捷函数
        from app.metadata_extractor import parse_single_file, get_supported_extensions
        
        # 方法B: 使用特定解析器
        from app.core.parsers.mp3_parser import MP3Parser, parse_mp3_file
        
        # 方法C: 使用解析器工厂
        from app.core.parsers import ParserFactory
        
        print("✓ 模块导入成功")
        
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return
    
    # 2. 检查支持的格式
    print("\n2. 支持的音频格式")
    print("-" * 40)
    
    extensions = get_supported_extensions()
    print(f"当前支持的格式: {', '.join(extensions)}")
    
    # 3. 创建测试文件路径
    test_file = Path("/mnt/d/music/其他/Distortion!! - 結束バンド.mp3")
    if not test_file.exists():
        # 使用一个占位符文件路径（实际使用时需要修改）
        test_file = Path("test.mp3")
        print(f"⚠  注意: 测试文件不存在，将使用路径: {test_file}")
        print("   实际使用时请替换为真实的 MP3 文件路径")
    
    # 4. 方法A: 使用便捷函数解析
    print("\n3. 方法A: 使用便捷函数解析单文件")
    print("-" * 40)
    
    if test_file.exists():
        song = parse_single_file(test_file)
        if song:
            print(f"✓ 解析成功!")
            print(f"   标题: {song.display_title}")
            print(f"   艺术家: {song.display_artist}")
            print(f"   专辑: {song.display_album}")
            print(f"   时长: {song.duration_formatted}")
            print(f"   比特率: {song.audio_format.bitrate} kbps")
            print(f"   是否有封面: {'是' if song.has_artwork else '否'}")
            
            if song.artwork:
                print(f"   封面信息: {song.artwork}")
        else:
            print("✗ 解析失败")
    
    # 5. 方法B: 使用 MP3Parser 类
    print("\n4. 方法B: 使用 MP3Parser 类")
    print("-" * 40)
    
    if MP3Parser.can_parse(test_file):
        print("✓ 支持解析此文件")
        
        # 解析文件
        song = MP3Parser.parse(test_file)
        if song:
            print(f"✓ MP3Parser 解析成功!")
            print(f"   标题: {song.display_title}")
            
            # 获取支持的扩展名
            extensions = MP3Parser.get_supported_extensions()
            print(f"   MP3Parser 支持: {', '.join(extensions)}")
    
    # 6. 方法C: 使用 ParserFactory（推荐）
    print("\n5. 方法C: 使用 ParserFactory（自动选择解析器）")
    print("-" * 40)
    
    parser_class = ParserFactory.get_parser(test_file)
    if parser_class:
        print(f"✓ 找到解析器: {parser_class.__name__}")
        
        # 使用工厂解析
        song = ParserFactory.parse_file(test_file)
        if song:
            print(f"✓ 工厂解析成功!")
            print(f"   专辑艺术家: {song.metadata.album_artist or 'N/A'}")
            print(f"   流派: {song.metadata.genre or 'N/A'}")
            print(f"   年份: {song.metadata.year or 'N/A'}")
            print(f"   音轨号: {song.metadata.track_number or 'N/A'}")
    
    # 7. 批量解析示例
    print("\n6. 批量解析示例")
    print("-" * 40)
    
    from metadata_extractor import parse_multiple_files
    
    # 模拟多个文件路径
    test_files = [test_file] if test_file.exists() else []
    
    if test_files:
        songs = parse_multiple_files(test_files)
        print(f"批量解析结果: {len(songs)} 个文件成功")
        
        for i, song in enumerate(songs, 1):
            print(f"  {i}. {song.display_title} - {song.display_artist}")
    
    # 8. 目录解析示例
    print("\n7. 目录解析示例")
    print("-" * 40)
    
    from metadata_extractor import parse_audio_directory
    
    test_dir = Path("/mnt/d/music")
    if test_dir.exists() and test_dir.is_dir():
        print(f"将解析目录: {test_dir}")
        print("（这可能需要一些时间，取决于文件数量）")
        
        song_count = 0
        for song in parse_audio_directory(test_dir, recursive=False):
            song_count += 1
            if song_count <= 3:  # 只显示前3个
                print(f"  {song_count}. {song.display_title}")
        
        print(f"总共找到 {song_count} 个支持的音频文件")
    else:
        print(f"测试目录不存在: {test_dir}")
        print("实际使用时请替换为真实的音乐目录路径")
    
    print("\n" + "=" * 60)
    print("示例结束")
    print("=" * 60)


def create_song_example():
    """演示如何手动创建带 Artwork 的 Song 对象"""
    
    print("\n8. 手动创建 Song 对象示例")
    print("-" * 40)
    
    from app.models.song import Song, FileInfo, SongMetadata, AudioFormat, Artwork
    from datetime import datetime
    
    # 创建带 Artwork 的 Song
    file_info = FileInfo(
        path=Path("example.mp3"),
        size_bytes=1024 * 1024 * 5,  # 5MB
        created_time=datetime.now(),
        modified_time=datetime.now(),
        accessed_time=datetime.now()
    )
    
    metadata = SongMetadata(
        title="示例歌曲",
        artist="示例艺术家",
        album="示例专辑",
        year=2024,
        track_number=1,
        genre="示例流派"
    )
    
    audio_format = AudioFormat(
        codec="MP3",
        sample_rate=44100,
        channels=2,
        bitrate=320,
        encoding="lossy"
    )
    
    # 创建 Artwork（外部文件示例）
    artwork = Artwork.from_external(
        filepath="cover.jpg",
        mime_type="image/jpeg",
        description="专辑封面"
    )
    
    song = Song(
        file_info=file_info,
        metadata=metadata,
        audio_format=audio_format,
        artwork=artwork,
        duration=180.5  # 3分钟0.5秒
    )
    
    print("✓ 创建了带封面的 Song 对象")
    print(f"   标题: {song.display_title}")
    print(f"   艺术家: {song.display_artist}")
    print(f"   是否有封面: {song.has_artwork}")
    print(f"   封面类型: {song.artwork.mime_type if song.artwork else '无'}")
    print(f"   封面描述: {song.artwork.description if song.artwork else '无'}")


def demonstrate_lyric_finder():
    """演示智能歌词查找功能"""
    print("\n9. 智能歌词查找示例")
    print("-" * 40)

    from app.metadata_extractor import parse_audio_file, set_config

    # 加载配置文件
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        print(f"✓ 已加载配置: {config_path}")
        print(f"  歌词优先级: {config['lyrics']['priority']}")
        set_config(config)

    # 测试文件
    test_file = Path("test.mp3")  # 替换为实际文件
    if test_file.exists():
        song = parse_audio_file(test_file)
        if song and song.lyrics:
            print(f"\n✓ 找到歌词:")
            print(f"  来源: {song.lyrics.source}")
            print(f"  是否同步: {song.lyrics.synced}")
            print(f"  格式: {song.lyrics.format}")
            print(f"  前100字符预览: {song.lyrics.text[:100]}...")
        elif song:
            print("\n⚠  未找到歌词（可能需要创建 .lrc 文件）")
            print("  提示: 创建同名 .lrc 文件来测试 LRC 歌词查找")
    else:
        print("\n⚠  测试文件不存在，跳过歌词查找演示")


if __name__ == "__main__":
    demonstrate_parser_usage()
    create_song_example()
    demonstrate_lyric_finder()
