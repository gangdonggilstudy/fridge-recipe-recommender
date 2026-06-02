"""사용자 선호 벡터 (CRUD · cold-start · 갱신)."""

from pathlib import Path

from llm.review_analyzer import REVIEW_KEYWORD_DIMS

from ._base_repo import BaseRepository
from .db_init import ensure_user
from .normalize import STYLE_KEYS, TASTE_KEYS

# 분 단위
COOK_TIME_SHORT_MAX = 20
COOK_TIME_MEDIUM_MAX = 40

COOK_TIME_BUCKETS: tuple[str, ...] = ("short", "medium", "long")

# Cosine similarity 비교 시 동일 순서 유지. 리뷰 키워드는 review_analyzer 단일 소스.
FEATURE_KEYS: list[str] = [
    *STYLE_KEYS,
    *TASTE_KEYS,
    *COOK_TIME_BUCKETS,
    *REVIEW_KEYWORD_DIMS,
]

# update() 시 기존 벡터에 곱하는 비율. 0.95 → 14회 누적 시 절반.
DECAY_RATE = 0.95


def cook_time_bucket(cook_time: int) -> str:
    # 조리시간(분)을 3구간으로: ≤20 short, ≤40 medium, 그 외 long.
    if cook_time <= COOK_TIME_SHORT_MAX:
        return COOK_TIME_BUCKETS[0]
    if cook_time <= COOK_TIME_MEDIUM_MAX:
        return COOK_TIME_BUCKETS[1]
    return COOK_TIME_BUCKETS[2]


class PreferenceManager(BaseRepository):
    def __init__(self, db_path: str | Path | None = None):
        super().__init__(db_path)

    def load(self, user_id: str) -> dict[str, float]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT feature, value FROM preference_vectors WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            return {r["feature"]: r["value"] for r in rows}

    def save(self, user_id: str, vector: dict[str, float]) -> None:
        ensure_user(self.db_path, user_id)
        with self._connect() as con:
            con.execute("DELETE FROM preference_vectors WHERE user_id = ?", (user_id,))
            con.executemany(
                "INSERT INTO preference_vectors (user_id, feature, value) VALUES (?, ?, ?)",
                [(user_id, k, v) for k, v in vector.items()],
            )
            con.commit()

    def init_cold_start(self, answers: dict) -> dict[str, float]:
        """온보딩 음식 카드 → 초기 선호 벡터.

        비대칭 +1.0/-0.5: 싫어요는 약한 신호. 초기 벡터는 max(0) 클리핑
        (음수 허용은 update() 이후).
        """
        # 모든 선호 차원을 0.0 으로 시작.
        vec: dict[str, float] = dict.fromkeys(FEATURE_KEYS, 0.0)

        # 좋아요 카드는 +1.0, 싫어요 카드는 -0.5 (싫어요는 약한 신호 → 비대칭).
        for card in answers.get("cards", []):
            delta = 1.0 if card.get("liked") else -0.5
            for key in (card.get("style"), card.get("taste")):
                if key in vec:
                    # 초기 벡터는 음수로 내려가지 않게 0 에서 바닥 처리.
                    vec[key] = max(0.0, vec[key] + delta)

        return vec

    # 새 차원 추가 시 이 테이블만 수정. cook_time_bucket 은 변환 함수 별도 처리.
    _BUMP_FIELDS: tuple[tuple[str, bool], ...] = (
        ("style", False),
        ("taste", True),
        ("review_keywords", True),
    )

    def _apply_delta(
        self, vec: dict[str, float], recipe: dict, delta: float,
    ) -> None:
        """recipe 학습 차원에 delta 가산. FEATURE_KEYS 외 키는 무시."""
        # 주어진 차원 키에 delta 를 더하는 헬퍼(미등록 키는 무시).
        def bump(key: str | None) -> None:
            if key in FEATURE_KEYS:
                vec[key] = vec.get(key, 0.0) + delta

        # 레시피의 style(단일)·taste/review_keywords(리스트)를 해당 선호 차원에 반영.
        for field, is_list in self._BUMP_FIELDS:
            values = recipe.get(field, []) if is_list else [recipe.get(field)]
            for v in values:
                bump(v)
        # 조리시간 구간 차원도 함께 반영.
        bump(cook_time_bucket(recipe.get("cook_time", 0)))

    def update(self, user_id: str, recipe: dict, selected: bool) -> dict[str, float]:
        """시간 감쇠 + 음수 허용 (preference_score 가 0~1 클리핑)."""
        vec = self.load(user_id)
        # ① 전체 차원에 ×0.95 → 과거 취향을 조금씩 망각(최신 취향 우선).
        vec = {k: v * DECAY_RATE for k, v in vec.items()}
        # ② 이번 레시피 특성에 델타 가산: 선택 +1.0, 미선택 -0.5(비대칭).
        self._apply_delta(vec, recipe, 1.0 if selected else -0.5)
        self.save(user_id, vec)
        return vec

    def revert_then_dislike(
        self, user_id: str, recipe: dict,
    ) -> dict[str, float]:
        """직전 update(selected=True) +1.0 상쇄 + 패널티 -0.5 = -1.5. DECAY 미적용."""
        # '별로에요'는 직전 선택(+1.0)을 되돌리고(-1.0) 추가로 -0.5 패널티 = -1.5.
        # 직전 동작의 거울이므로 감쇠는 적용하지 않는다.
        vec = self.load(user_id)
        self._apply_delta(vec, recipe, -1.5)
        self.save(user_id, vec)
        return vec
