"""사용자별 모델 버전 — `models/<user_id>/v{ts}.{pkl,json}` + `latest.txt`."""

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

import joblib

DEFAULT_MODEL_REGISTRY_DIR = "models"
# v<날짜8>-<시각6>[-<마이크로초6>] — 같은 초 안 충돌 방지를 위해 마이크로초 부분 허용.
_VERSION_PATTERN = re.compile(r"^v\d{8}-\d{6}(-\d{6})?$")


class ModelRegistry:
    """사용자별 모델 + 메타데이터 저장."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir or os.getenv("MODEL_REGISTRY_DIR", DEFAULT_MODEL_REGISTRY_DIR))

    def _user_dir(self, user_id: str) -> Path:
        """user_id 별 디렉토리. base_dir 를 벗어나는 경로는 거부 (심층 방어).

        UI 경계(`is_valid_user_id`)에서 이미 걸러지지만, 직접 호출·테스트·
        스크립트 경로까지 막기 위해 resolve 후 base 포함 여부를 재확인한다.
        """
        candidate = self.base_dir / user_id
        base = self.base_dir.resolve()
        if not candidate.resolve().is_relative_to(base):
            raise ValueError(f"unsafe user_id for registry path: {user_id!r}")
        return candidate

    @staticmethod
    def _new_version() -> str:
        # 마이크로초 포함 — 같은 초 안 연속 save() 가 서로 덮어쓰지 않도록.
        return "v" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")

    # ── 저장 ──

    def save(
        self,
        user_id: str,
        model,
        metadata: dict | None = None,
    ) -> str:
        """모델 + 메타 저장. 새 버전 문자열 반환."""
        user_dir = self._user_dir(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        version = self._new_version()
        pkl_path = user_dir / f"{version}.pkl"
        meta_path = user_dir / f"{version}.json"
        latest_path = user_dir / "latest.txt"

        joblib.dump(model, pkl_path)

        meta = {
            "version":    version,
            "user_id":    user_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            **(metadata or {}),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        latest_path.write_text(version, encoding="utf-8")
        return version

    # ── 로드 ──

    def load_latest(self, user_id: str) -> tuple[object, dict] | None:
        user_dir = self._user_dir(user_id)
        latest_path = user_dir / "latest.txt"
        if not latest_path.exists():
            return None
        version = latest_path.read_text(encoding="utf-8").strip()
        return self.load_version(user_id, version)

    def load_version(self, user_id: str, version: str) -> tuple[object, dict] | None:
        # 버전 문자열 포맷 검증 — `..`, `/` 등 경로 우회 + 손상된 latest.txt 방어.
        if not _VERSION_PATTERN.match(version):
            raise ValueError(f"invalid version format: {version!r}")
        user_dir = self._user_dir(user_id)
        pkl_path = user_dir / f"{version}.pkl"
        meta_path = user_dir / f"{version}.json"
        if not pkl_path.exists():
            return None
        model = joblib.load(pkl_path)
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        return model, meta

    def list_versions(self, user_id: str) -> list[dict]:
        """사용자의 모든 버전 메타 (최신 우선 정렬)."""
        user_dir = self._user_dir(user_id)
        if not user_dir.exists():
            return []
        metas = []
        for meta_path in sorted(user_dir.glob("v*.json"), reverse=True):
            metas.append(json.loads(meta_path.read_text(encoding="utf-8")))
        return metas

    def delete_version(self, user_id: str, version: str) -> None:
        user_dir = self._user_dir(user_id)
        for ext in (".pkl", ".json"):
            path = user_dir / f"{version}{ext}"
            if path.exists():
                path.unlink()
        # latest 가리키던 버전이 삭제됐으면 latest.txt 도 정리
        latest_path = user_dir / "latest.txt"
        if latest_path.exists() and latest_path.read_text(encoding="utf-8").strip() == version:
            latest_path.unlink()

    def clear_user(self, user_id: str) -> None:
        """사용자의 모든 모델 제거 (테스트·초기화용)."""
        user_dir = self._user_dir(user_id)
        if user_dir.exists():
            shutil.rmtree(user_dir)
