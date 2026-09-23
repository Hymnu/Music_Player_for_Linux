"""
音频播放引擎 - 最小化实现
使用 miniaudio 库实现基本的音频播放功能

架构（常驻设备 + 静音门控）：
- 播放设备与主生成器在首次播放时创建并持续运行，暂停/停止/跳转不再停启设备
- 暂停/停止通过静音门控（_muted）实现：主生成器直接返回静音，不解码数据
- 跳转/恢复只需重开解码器流，无设备操作与线程创建开销
- 自然播放结束由数据流结束信号驱动，尾部音频播完后由常驻监控线程收尾
- 设备格式（采样率/声道数）变化时自动销毁重建，避免变速/变调
"""

import miniaudio
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum, auto
import time
import threading
import array

try:
    import audioop  # 标准库 C 实现，用于音量处理（Python 3.13+ 移除，届时自动降级）
except ImportError:
    audioop = None

try:
    import numpy as _np  # 可选：向量化音量处理加速
except ImportError:
    _np = None


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

    # 数据流结束后，等待设备内已缓冲尾部音频播完的最长时限（秒）
    _TAIL_GRACE = 0.5

    def __init__(self, keep_device: bool = True):
        """
        Args:
            keep_device: True（默认）时设备常驻运行，暂停/停止仅静音门控（恢复延迟最低）；
                         False 时暂停/停止真正停掉设备（省资源，恢复需重启设备）
        """
        self._stream_generator = None                 # 当前活动流（wrapper，随 play/seek/resume 重建）
        self._device: Optional[miniaudio.PlaybackDevice] = None
        self._device_format: Optional[tuple] = None   # (sample_rate, nchannels)，设备复用时的格式校验
        self._device_running = False                  # 设备是否处于运行（回调激活）状态
        self._master_generator = None                 # 常驻主生成器（设备唯一数据源，实现静音门控）
        self._muted = True                            # 静音门控：True 时主生成器返回静音，不解码
        self._current_file: Optional[Path] = None
        self._state = PlaybackState.STOPPED
        self._volume = 1.0
        self._duration = 0.0
        self._monitor_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()      # 引擎关闭信号（常驻监控线程退出）
        self._state_lock = threading.Lock()           # 状态迁移锁（防止自然结束与 stop/pause 竞态双通知）
        self._stream_ended = threading.Event()        # 数据流结束标记（数据驱动的播放结束检测）
        self._stream_ended_epoch = 0                  # 结束信号所属的流代际号（淘汰换流前旧流的迟到信号）
        self._stream_epoch = 0                        # 流代际号：每次 _create_stream 递增
        self._tail_deadline: Optional[float] = None   # 数据流结束后尾部音频播完的截止时刻
        self._state_change_callback: Optional[Callable[[PlaybackState], None]] = None
        self._start_time = 0.0
        self._paused_at = 0.0
        self._file_info = None
        self._keep_device = keep_device

    # ==================== 设备管理 ====================

    def _ensure_device(self, sample_rate, nchannels):
        """确保设备已创建、格式匹配且处于运行状态

        复用设备前校验采样率/声道数：格式不匹配时必须销毁重建，
        否则旧设备按原格式播放新数据会导致变速/变调
        （例如 44.1kHz 歌曲切到 48kHz 歌曲时仍按 44.1kHz 播放）。
        """
        target_format = (sample_rate, nchannels)

        # 已有设备且格式匹配：直接复用（仅确保运行状态，处理 keep_device=False 停过的情形）
        if (self._device is not None and self._keep_device
                and self._device_format == target_format):
            self._start_device()
            return

        # 无设备 / 不复用设备 / 格式不匹配：（重新）创建
        if self._device is not None:
            self._stop_device()
            self._device = None

        self._device = miniaudio.PlaybackDevice(
            sample_rate=sample_rate,
            nchannels=nchannels
        )
        self._device_format = target_format
        self._start_device()
        print(f"[AudioEngine] Device created ({sample_rate}Hz, {nchannels}ch)")

    def _start_device(self):
        """启动设备（常驻主生成器作为唯一数据源，每次启动使用新实例）"""
        if self._device is None or self._device_running:
            return
        self._master_generator = self._create_master_generator()
        self._device.start(self._master_generator)
        self._device_running = True

    def _stop_device(self):
        """停止设备（仅 keep_device=False 的暂停/停止路径及引擎销毁时使用）

        ma_device_stop() 为同步调用，会等待设备音频线程退出后才返回，
        无需额外盲等休眠。
        """
        if self._device is not None and self._device_running:
            self._device.stop()
            self._device_running = False
            self._master_generator = None

    # ==================== 数据流 ====================

    def _create_master_generator(self):
        """创建常驻主生成器：设备唯一数据源，实现静音门控

        - 门控开启（_muted=True）或无活动流：直接返回静音，不解码数据
          → pause/stop 仅置标记即可生效，无设备操作
        - 门控关闭：委托给当前流生成器（wrapper），由其解码并应用音量
        """
        # 静音长度按设备格式计算（创建时捕获，设备重建时随之更新）
        bytes_per_frame = self._device_format[1] * 2  # 设备声道数 × 2 字节（SIGNED16）

        def master_generator():
            required_frames = yield None
            while True:
                # 静音门控：暂停/停止/换流期间返回静音，不解码
                gen = None if self._muted else self._stream_generator
                if gen is None:
                    silence = bytes(required_frames * bytes_per_frame)
                    required_frames = yield silence
                    continue
                try:
                    audio_data = gen.send(required_frames)
                    required_frames = yield audio_data
                except StopIteration:
                    # 流意外终止：仅当仍是当前流时标记结束（旧流的迟到信号被忽略）
                    if gen is self._stream_generator:
                        self._stream_ended_epoch = self._stream_epoch
                        self._stream_ended.set()
                    silence = bytes(required_frames * bytes_per_frame)
                    required_frames = yield silence

        gen = master_generator()
        next(gen)
        return gen

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
        my_epoch = self._stream_epoch  # 捕获本流代际号（_create_stream 已先行递增）

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
                            # 文件结束：标记数据流结束（附代际号，换流后旧信号失效），用静音填充剩余帧
                            self._stream_ended_epoch = my_epoch
                            self._stream_ended.set()
                            silence = bytes(remaining_frames * bytes_per_frame)
                            chunks.append(silence)
                            break

                        # 应用音量 (SIGNED16 格式，优先使用 C 实现避免逐样本 Python 循环)
                        audio_data = self._apply_volume(audio_data)

                        chunks.append(audio_data)
                        remaining_frames -= chunk_frames
                    except StopIteration:
                        # 文件结束：标记数据流结束（附代际号，换流后旧信号失效），用静音填充剩余帧
                        self._stream_ended_epoch = my_epoch
                        self._stream_ended.set()
                        silence = bytes(remaining_frames * bytes_per_frame)
                        chunks.append(silence)
                        break

                # 合并所有块
                combined_data = b''.join(chunks)
                required_frames = yield combined_data

        return wrapper_generator()

    def _apply_volume(self, audio_data: bytes) -> bytes:
        """对 SIGNED16 PCM 数据应用音量（优先 C 实现，避免逐样本 Python 循环）"""
        vol = self._volume
        if vol == 1.0 or not audio_data:
            return audio_data

        # 1) audioop：标准库 C 实现
        if audioop is not None:
            return audioop.mul(audio_data, 2, vol)

        # 2) numpy：向量化运算（若已安装）
        if _np is not None:
            samples = _np.frombuffer(audio_data, dtype=_np.int16)
            scaled = samples.astype(_np.float32) * vol
            scaled = _np.clip(scaled, -32768, 32767)
            return scaled.astype(_np.int16).tobytes()

        # 3) 纯 Python 兜底（带削波，避免音量 >1.0 时 OverflowError）
        samples = array.array('h', audio_data)
        for i in range(len(samples)):
            v = int(samples[i] * vol)
            if v > 32767:
                v = 32767
            elif v < -32768:
                v = -32768
            samples[i] = v
        return samples.tobytes()

    def _create_stream(self, seek_frame: int = 0) -> None:
        """创建音频流生成器（重开解码器；seek/resume 延迟的主要成本所在）"""
        self._stream_epoch += 1     # 递增代际号：使旧流的迟到结束信号失效
        self._stream_ended.clear()
        self._tail_deadline = None
        self._stream_generator = self._create_stream_wrapper(seek_frame)
        next(self._stream_generator)

    # ==================== 播放控制 ====================

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

            self._muted = True  # 换流期间静音
            # 确保设备已创建且格式匹配（首次/格式变化时建设备并启动主生成器）
            self._ensure_device(self._file_info.sample_rate, self._file_info.nchannels)
            # 创建流生成器
            self._create_stream()

            self._start_time = time.time()
            self._paused_at = 0.0
            with self._state_lock:
                self._state = PlaybackState.PLAYING
            self._muted = False  # 开闸

            self._start_monitor()
            print(f"[AudioEngine] Playback started: {file_path.name}")
            self._notify_state_change(PlaybackState.PLAYING)
            return True

        except Exception as e:
            self._muted = True
            with self._state_lock:
                self._state = PlaybackState.STOPPED
            raise RuntimeError(f"播放失败: {e}")

    def pause(self) -> bool:
        """暂停播放（仅置静音门控标记，无设备操作）"""
        with self._state_lock:
            if self._state != PlaybackState.PLAYING:
                return False
            self._paused_at = self.get_position()
            self._muted = True
            self._state = PlaybackState.PAUSED
        if not self._keep_device:
            self._stop_device()
        self._notify_state_change(PlaybackState.PAUSED)
        return True

    def resume(self) -> bool:
        """继续播放（重开解码器流，无设备/线程操作）"""
        if self._state != PlaybackState.PAUSED or not self._current_file:
            return False

        try:
            self._muted = True  # 防御性门控（暂停期间本已静音）
            seek_frame = int(self._paused_at * self._file_info.sample_rate)

            self._ensure_device(self._file_info.sample_rate, self._file_info.nchannels)
            self._create_stream(seek_frame)

            self._start_time = time.time() - self._paused_at
            with self._state_lock:
                self._state = PlaybackState.PLAYING
            self._muted = False  # 开闸

            self._start_monitor()
            self._notify_state_change(PlaybackState.PLAYING)
            return True

        except Exception as e:
            self._muted = True
            with self._state_lock:
                self._state = PlaybackState.STOPPED
            return False

    def stop(self) -> bool:
        """停止播放（仅置静音门控标记，设备保持常驻运行以备快速复用）"""
        with self._state_lock:
            if self._state == PlaybackState.STOPPED:
                return True
            self._muted = True
            self._stream_generator = None
            self._start_time = 0.0
            self._paused_at = 0.0
            self._state = PlaybackState.STOPPED
        if not self._keep_device:
            self._stop_device()
        self._notify_state_change(PlaybackState.STOPPED)
        return True

    def seek(self, position: float) -> bool:
        """跳转到指定位置（秒）（重开解码器流，无设备/线程操作）"""
        if not self._current_file:
            return False

        try:
            position = max(0.0, min(position, self._duration))

            self._muted = True  # 换流期间静音，避免新旧位置音频交叠
            seek_frame = int(position * self._file_info.sample_rate)

            self._ensure_device(self._file_info.sample_rate, self._file_info.nchannels)
            self._create_stream(seek_frame)

            self._start_time = time.time() - position
            self._paused_at = position
            with self._state_lock:
                self._state = PlaybackState.PLAYING
            self._muted = False  # 开闸

            self._start_monitor()
            self._notify_state_change(PlaybackState.PLAYING)
            return True

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._muted = True
            with self._state_lock:
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

    # ==================== 状态查询 ====================

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

    # ==================== 监控线程与自然结束 ====================

    def _start_monitor(self):
        """启动常驻监控线程（引擎生命周期内持续运行，重复调用无副作用）"""
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return
        self._shutdown_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _finish_playback(self):
        """处理自然播放结束（由监控线程调用，与 stop/pause 互斥保证只通知一次）"""
        with self._state_lock:
            if self._state != PlaybackState.PLAYING:
                return
            self._muted = True
            self._state = PlaybackState.STOPPED
            self._stream_generator = None
            self._start_time = 0.0
            self._paused_at = 0.0
        if not self._keep_device:
            self._stop_device()
        self._notify_state_change(PlaybackState.STOPPED)

    def _monitor_loop(self):
        """常驻监控线程：由数据流结束信号驱动，待尾部音频播完后收尾"""
        while not self._shutdown_event.is_set():
            if (self._state == PlaybackState.PLAYING
                    and self._stream_ended.is_set()
                    and self._stream_ended_epoch == self._stream_epoch):
                if self._tail_deadline is None:
                    # 数据流已结束：按设备已缓冲的尾部时长（0.1~0.5 秒）确定截止时刻，
                    # 让设备把已缓冲的结尾音频播完后再收尾
                    remaining = self._duration - self.get_position()
                    wait = max(0.1, min(remaining, self._TAIL_GRACE))
                    self._tail_deadline = time.time() + wait
                if time.time() >= self._tail_deadline:
                    self._finish_playback()
                    self._tail_deadline = None
                    continue
            elif (self._state == PlaybackState.PLAYING
                    and not self._stream_ended.is_set()
                    and self._duration > 0
                    and self.get_position() >= self._duration - 0.05):
                # 兜底：时钟已到末尾但结束信号未到（极端情况下信号丢失时仍能收尾）
                self._finish_playback()
                self._tail_deadline = None
                continue
            self._shutdown_event.wait(timeout=0.05)

    def __del__(self):
        try:
            self._shutdown_event.set()
            self._muted = True
            self._stop_device()
        except Exception:
            pass
