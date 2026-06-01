"""A/B 그룹 할당 — user_id 해시 결정적 배정. (보존된 미사용 모듈)"""

import hashlib

GROUPS = ("rule_based", "ml_based", "hybrid")


def assign_group(user_id: str, groups: tuple[str, ...] = GROUPS) -> str:
    """사용자 ID 의 MD5 해시를 그룹 수로 모듈로 → 결정론적 배정.

    주의: 배정은 `h % len(groups)` 라 GROUPS 의 **개수·순서**에 묶여 있다.
    GROUPS 를 재정렬·증감하면 기존 사용자의 그룹이 통째로 바뀌어
    진행 중인 A/B 실험 데이터가 오염된다. 실험 중에는 GROUPS 고정.
    """
    if not user_id:
        return groups[0]
    h = int(hashlib.md5(user_id.encode("utf-8")).hexdigest(), 16)
    return groups[h % len(groups)]


class ABTestManager:
    """그룹 배정 + 그룹 정보 조회 헬퍼."""

    def __init__(self, groups: tuple[str, ...] = GROUPS):
        self.groups = groups

    def group_of(self, user_id: str) -> str:
        return assign_group(user_id, self.groups)

    def all_groups(self) -> tuple[str, ...]:
        return self.groups

    def stats_summary(self, group_counts: dict[str, int]) -> dict[str, float]:
        """그룹별 비율."""
        total = sum(group_counts.values())
        if total == 0:
            return dict.fromkeys(self.groups, 0.0)
        return {g: round(group_counts.get(g, 0) / total, 3) for g in self.groups}
