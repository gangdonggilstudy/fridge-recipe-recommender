"""STT (faster-whisper) — CPU+int8 기본, 미설치 시 graceful 폴백.

환경변수: `STT_ENABLED` / `STT_MODEL` / `STT_DEVICE` / `STT_COMPUTE_TYPE`.
"""
from __future__ import annotations

import os
from pathlib import Path

from modules.env_flag import env_flag
from modules.logging_setup import get_logger

_logger = get_logger(__name__)


class STTEngine:
    """faster-whisper 모델 래퍼.

    모델 로드는 __init__ 에서 수행 (cache_resource 와 결합되어 한 번만 실행).
    로드 실패 시 _available=False 로 유지되며 transcribe() 는 빈 문자열 반환.
    """

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._available = False
        self._load()

    def _load(self) -> None:
        try:
            from faster_whisper import WhisperModel  # noqa: PLC0415
        except ImportError as e:
            _logger.warning("faster_whisper 미설치 — STT 비활성화: %s", e)
            return

        try:
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            self._available = True
            _logger.info(
                "STT 모델 로드 완료: %s (%s, %s)",
                self.model_size, self.device, self.compute_type,
            )
        except Exception as e:  # noqa: BLE001
            _logger.warning("STT 모델 로드 실패: %s", e)

    def is_available(self) -> bool:
        return self._available

    def transcribe(self, audio_path: str | Path, language: str = "ko") -> str:
        """오디오 파일 → 텍스트. 실패 시 빈 문자열."""
        if not self._available or self._model is None:
            return ""

        try:
            segments, _info = self._model.transcribe(
                str(audio_path),
                language=language,
                vad_filter=True,
            )
            return "".join(seg.text for seg in segments).strip()
        except Exception as e:  # noqa: BLE001
            _logger.warning("STT transcribe 실패: %s", e)
            return ""


def make_stt_engine() -> STTEngine | None:
    """환경변수 기반으로 STT 엔진 생성. 비활성화·실패 시 None."""
    if not env_flag("STT_ENABLED", default=True):
        _logger.debug("STT_ENABLED=false — STT 비활성화")
        return None

    try:
        engine = STTEngine(
            model_size=os.getenv("STT_MODEL", "small"),
            device=os.getenv("STT_DEVICE", "cpu"),
            compute_type=os.getenv("STT_COMPUTE_TYPE", "int8"),
        )
    except Exception as e:  # noqa: BLE001
        _logger.warning("STT 엔진 생성 실패: %s", e)
        return None

    if not engine.is_available():
        return None
    return engine
