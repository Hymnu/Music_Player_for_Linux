"""
音频播放引擎 - 最小化实现
使用 miniaudio 库实现基本的音频播放功能
"""

import miniaudio
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum, auto
import time
import threading


class PlaybackState(Enum):
    """播放状态枚举"""
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


@dataclass
class PlaybackStatus:
    """播放状态信息"""
    state: PlaybackState
    position: float      # 当前位置（秒）
    duration: float      # 总时长（秒）
    volume: float        # 音量 0.0-1.0


class AudioEngine:
    """最小音频播放引擎

    支持功能：
    - 播放、暂停、继续、停止
    - 音量控制
    - 进度控制（跳转）
    - 获取播放状态
    """

    def __init__(self, keep_device: bool = True):
        """
        Args:
            keep_device: 是否在暂停时保持设备实例以降低延迟
        """
        self._stream_generator = None
        self._device: Optional[miniaudio.PlaybackDevice] = None
        self._current_file: Optional[Path] = None
        self._state = PlaybackState.STOPPED
        self._volume = 1.0
        self._duration = 0.0
        self._playback_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._state_change_callback: Optional[Callable[[PlaybackState], None]] = None
        self._start_time = 0.0
        self._paused_at = 0.0
        self._file_info = None
        self._keep_device = keep_device

    def _ensure_device(self, sample_rate, nchannels):
        """确保设备已创建（保持设备实例优化）"""
        if self._device is None or not self._keep_device:
            if self._device is not None:
                self._device.stop()
                self._device = None

            self._device = miniaudio.PlaybackDevice(
                sample_rate=sample_rate,
                nchannels=nchannels
            )
            print(f"[AudioEngine] Device created")

    def _stop_device(self):
        """停止设备（复用前必须调用）"""
        if self._device:
            self._device.stop()
            # 短暂等待确保设备完全停止
            time.sleep(0.05)

    def _create_stream_wrapper(self, seek_frame: int = 0):
        """创建包装生成器，处理帧数不匹配问题"""
        # 创建内部流生成器
        internal_stream = miniaudio.stream_file(
            str(self._current_file),
            nchannels=self._file_info.nchannels,
            sample_rate=self._file_info.sample_rate,
            seek_frame=seek_frame
        )
        next(internal_stream)

        # 包装生成器：分批读取数据满足设备请求，并应用音量
        def wrapper_generator():
            required_frames = yield None
            while True:
                # 计算每帧字节数 (样本数 * 声道数 * 字节/样本)
                bytes_per_frame = self._file_info.nchannels * 2  # SIGNED16 = 2 bytes

                # 分批读取，每次最多8192帧
                chunks = []

                remaining_frames = required_frames
                while remaining_frames > 0:
                    try:
                        chunk_frames = min(remaining_frames, 8192)
                        audio_data = internal_stream.send(chunk_frames)
                        if not audio_data or len(audio_data) == 0:
                            # 文件结束，用静音填充剩余帧
                            silence = bytes(remaining_frames * bytes_per_frame)
                            chunks.append(silence)
                            break

                        # 应用音量 (SIGNED16 格式)
                        if self._volume != 1.0:
                            import array
                            # 将字节数组转换为16位整数数组
                            samples = array.array('h', audio_data)
                            # 应用音量
                            for i in range(len(samples)):
                                samples[i] = int(samples[i] * self._volume)
                            # 转回字节数组
                            audio_data = samples.tobytes()

                        chunks.append(audio_data)
                        remaining_frames -= chunk_frames
                    except StopIteration:
                        # 文件结束，用静音填充剩余帧
                        silence = bytes(remaining_frames * bytes_per_frame)
                        chunks.append(silence)
                        break

                # 合并所有块
                combined_data = b''.join(chunks)
                required_frames = yield combined_data

        return wrapper_generator()

    def _create_stream(self, seek_frame: int = 0) -> None:
        """创建音频流生成器"""
        self._stream_generator = self._create_stream_wrapper(seek_frame)
        next(self._stream_generator)

    def play(self, file_path: Path) -> bool:
        """播放指定文件"""
        if self._state != PlaybackState.STOPPED:
            self.stop()

        if not file_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {file_path}")

        try:
            self._file_info = miniaudio.get_file_info(str(file_path))
            self._duration = self._file_info.duration
            self._current_file = file_path

            # 确保设备已创建（保持设备实例）
            self._ensure_device(self._file_info.sample_rate, self._file_info.nchannels)

            # 创建流生成器
            self._create_stream()

            print(f"[AudioEngine] Starting playback...")
            self._device.start(self._stream_generator)
            print(f"[AudioEngine] Playback started")

            # 启动监控线程
            self._stop_event.clear()
            self._playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
            self._playback_thread.start()

            self._start_time = time.time()
            self._state = PlaybackState.PLAYING
            self._notify_state_change(PlaybackState.PLAYING)
            return True

        except Exception as e:
            self._state = PlaybackState.STOPPED
            raise RuntimeError(f"播放失败: {e}")

    def pause(self) -> bool:
        """暂停播放"""
        if self._state != PlaybackState.PLAYING:
            return False

        try:
            self._stop_event.set()
            self._paused_at = self.get_position()

            self._stop_device()  # 确保设备完全停止

            if self._playback_thread and self._playback_thread.is_alive():
                self._playback_thread.join(timeout=1.0)

            self._state = PlaybackState.PAUSED
            self._notify_state_change(PlaybackState.PAUSED)
            return True

        except Exception as e:
            return False

    def resume(self) -> bool:
        """继续播放"""
        if self._state != PlaybackState.PAUSED or not self._current_file:
            return False

        try:
            seek_frame = int(self._paused_at * self._file_info.sample_rate)

            # 复用设备实例
            self._ensure_device(self._file_info.sample_rate, self._file_info.nchannels)

            # 创建新的流生成器从暂停位置开始
            self._create_stream(seek_frame)

            self._device.start(self._stream_generator)

            self._stop_event.clear()
            self._playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
            self._playback_thread.start()

            self._start_time = time.time() - self._paused_at
            self._state = PlaybackState.PLAYING
            self._notify_state_change(PlaybackState.PLAYING)
            return True

        except Exception as e:
            self._state = PlaybackState.STOPPED
            return False

    def stop(self) -> bool:
        """停止播放"""
        if self._state == PlaybackState.STOPPED:
            return True

        try:
            self._stop_event.set()

            self._stop_device()  # 确保设备完全停止

            if not self._keep_device:
                self._device = None

            if self._playback_thread and self._playback_thread.is_alive():
                self._playback_thread.join(timeout=2.0)

            self._stream_generator = None
            self._start_time = 0.0
            self._paused_at = 0.0
            self._state = PlaybackState.STOPPED
            self._notify_state_change(PlaybackState.STOPPED)
            return True

        except Exception as e:
            return False

    def seek(self, position: float) -> bool:
        """跳转到指定位置（秒）"""
        if not self._current_file:
            return False

        try:
            position = max(0.0, min(position, self._duration))

            was_paused = self._state == PlaybackState.PAUSED
            self._stop_event.set()

            if self._playback_thread and self._playback_thread.is_alive():
                self._playback_thread.join(timeout=1.0)

            # 确保设备完全停止
            self._stop_device()

            seek_frame = int(position * self._file_info.sample_rate)

            self._ensure_device(self._file_info.sample_rate, self._file_info.nchannels)
            self._create_stream(seek_frame)
            self._device.start(self._stream_generator)

            self._stop_event.clear()
            self._playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
            self._playback_thread.start()

            self._start_time = time.time() - position
            self._paused_at = position
            self._state = PlaybackState.PLAYING
            self._notify_state_change(PlaybackState.PLAYING)
            return True

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._state = PlaybackState.STOPPED
            return False

    def set_volume(self, volume: float) -> bool:
        """设置音量 (0.0 - 1.0)"""
        volume = max(0.0, min(1.0, volume))
        self._volume = volume
        return True

    def get_position(self) -> float:
        """获取当前播放位置（秒）"""
        if self._state == PlaybackState.STOPPED:
            return 0.0
        if self._state == PlaybackState.PAUSED:
            return self._paused_at
        try:
            elapsed = time.time() - self._start_time
            return max(0.0, min(elapsed, self._duration))
        except:
            return 0.0

    @property
    def status(self) -> PlaybackStatus:
        """获取当前播放状态"""
        return PlaybackStatus(
            state=self._state,
            position=self.get_position(),
            duration=self._duration,
            volume=self._volume
        )

    @property
    def is_playing(self) -> bool:
        return self._state == PlaybackState.PLAYING

    @property
    def is_paused(self) -> bool:
        return self._state == PlaybackState.PAUSED

    @property
    def is_stopped(self) -> bool:
        return self._state == PlaybackState.STOPPED

    @property
    def current_file(self) -> Optional[Path]:
        return self._current_file

    def set_state_change_callback(self, callback: Callable[[PlaybackState], None]):
        self._state_change_callback = callback

    def _notify_state_change(self, new_state: PlaybackState):
        if self._state_change_callback:
            self._state_change_callback(new_state)

    def _playback_loop(self):
        while not self._stop_event.is_set() and self._state != PlaybackState.STOPPED:
            if self._state == PlaybackState.PLAYING:
                pos = self.get_position()
                if pos >= self._duration - 0.1:
                    self._stop_event.set()
                    break
            time.sleep(0.1)

    def __del__(self):
        self.stop()
