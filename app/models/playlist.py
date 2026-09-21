# models/playlist.py
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import json
from .song import Song
import random

@dataclass
class Playlist:
    """播放列表数据模型"""
    name: str
    songs: List[Song] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    description: Optional[str] = None
    cover_path: Optional[Path] = None
    tags: List[str] = field(default_factory=list)
    
    # 播放状态（非持久化）
    current_index: int = 0
    shuffle: bool = False
    repeat_mode: str = "none"  # none, one, all
    
    def add_song(self, song: Song, position: Optional[int] = None):
        """添加歌曲到播放列表"""
        if position is None:
            self.songs.append(song)
        else:
            self.songs.insert(position, song)
        self.updated_at = datetime.now()
    
    def remove_song(self, index: int) -> Song:
        """从播放列表移除歌曲"""
        if 0 <= index < len(self.songs):
            song = self.songs.pop(index)
            self.updated_at = datetime.now()
            return song
        raise IndexError(f"索引 {index} 超出范围")
    
    def move_song(self, from_index: int, to_index: int):
        """移动歌曲位置"""
        if 0 <= from_index < len(self.songs) and 0 <= to_index < len(self.songs):
            song = self.songs.pop(from_index)
            self.songs.insert(to_index, song)
            self.updated_at = datetime.now()
    
    def clear(self):
        """清空播放列表"""
        self.songs.clear()
        self.updated_at = datetime.now()
        self.current_index = 0
    
    def get_current_song(self) -> Optional[Song]:
        """获取当前播放的歌曲"""
        if self.songs and 0 <= self.current_index < len(self.songs):
            return self.songs[self.current_index]
        return None
    
    def next_song(self) -> Optional[Song]:
        """获取下一首歌曲"""
        if not self.songs:
            return None
        
        if self.shuffle:
            self.current_index = random.randrange(len(self.songs))
        else:
            self.current_index = (self.current_index + 1) % len(self.songs)
        
        return self.get_current_song()
    
    def prev_song(self) -> Optional[Song]:
        """获取上一首歌曲"""
        if not self.songs:
            return None
        
        if self.shuffle:
            self.current_index = random.randrange(len(self.songs))
        else:
            self.current_index = (self.current_index - 1) % len(self.songs)
        
        return self.get_current_song()
    
    @property
    def total_duration(self) -> float:
        """播放列表总时长"""
        return sum(song.duration for song in self.songs)
    
    @property
    def total_duration_formatted(self) -> str:
        """格式化的总时长"""
        total = self.total_duration
        hours = int(total // 3600)
        minutes = int((total % 3600) // 60)
        seconds = int(total % 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
    
    @property
    def song_count(self) -> int:
        """歌曲数量"""
        return len(self.songs)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "cover_path": str(self.cover_path) if self.cover_path else None,
            "tags": self.tags,
            "song_paths": [str(song.file_info.path) for song in self.songs]
        }
    
    def save(self, path: Path):
        """保存播放列表到文件"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, path: Path) -> 'Playlist':
        """从文件加载播放列表（需要外部提供歌曲解析）"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        playlist = cls(
            name=data["name"],
            description=data.get("description"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            cover_path=Path(data["cover_path"]) if data.get("cover_path") else None,
            tags=data.get("tags", [])
        )
        
        # 注意：这里只保存了歌曲路径，实际使用时需要外部提供歌曲对象
        # playlist.songs = [Song.from_path(Path(p)) for p in data["song_paths"]]
        
        return playlist

@dataclass
class PlaylistManager:
    """播放列表管理器"""
    playlists: Dict[str, Playlist] = field(default_factory=dict)
    default_playlists_dir: Path = Path.home() / ".config" / "music_player" / "playlists"
    
    def __post_init__(self):
        self.default_playlists_dir.mkdir(parents=True, exist_ok=True)
    
    def create_playlist(self, name: str, description: Optional[str] = None) -> Playlist:
        """创建新播放列表"""
        if name in self.playlists:
            raise ValueError(f"播放列表 '{name}' 已存在")
        
        playlist = Playlist(name=name, description=description)
        self.playlists[name] = playlist
        return playlist
    
    def delete_playlist(self, name: str):
        """删除播放列表"""
        if name in self.playlists:
            del self.playlists[name]
    
    def get_playlist(self, name: str) -> Optional[Playlist]:
        """获取播放列表"""
        return self.playlists.get(name)
    
    def save_all(self):
        """保存所有播放列表"""
        for playlist in self.playlists.values():
            playlist_path = self.default_playlists_dir / f"{playlist.name}.json"
            playlist.save(playlist_path)
    
    def load_all(self):
        """加载所有播放列表"""
        self.playlists.clear()
        for playlist_file in self.default_playlists_dir.glob("*.json"):
            try:
                playlist = Playlist.load(playlist_file)
                self.playlists[playlist.name] = playlist
            except Exception as e:
                print(f"加载播放列表失败 {playlist_file}: {e}")

