"""XAI 분해 — rule: 배점×달성도×100 / blender: LR 계수 wᵢ·xᵢ (충실 분해)."""

from .contracts import ScoreComponents
from .scorer import DEFAULT_WEIGHTS


LABEL_MAP = {
    "ingredient":  "재료 일치도",
    "consumption": "소모 우선순위",
    "preference":  "선호도",
    "context":     "상황 적합도",
    "diversity":   "다양성",
}

# 학습 블렌더의 절편(개인 기본 성향) 표시 라벨
INTERCEPT_LABEL = "기본 성향"


class Explainer:
    """점수 구성 요소 → 기여 비율(%)·분해. 레짐(rule/blender) 자동 분기."""

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or DEFAULT_WEIGHTS

    @staticmethod
    def _is_blender(scores: ScoreComponents) -> bool:
        return scores.get("combine") == "blender"

    def _rule_items(self, scores: ScoreComponents, scale: float) -> dict[str, float]:
        """rule 레짐 항목별 기여 = 배점 × 달성도 × scale.

        explain() 은 scale=1.0(이후 % 정규화), breakdown() 은 scale=100.0.
        """
        return {
            LABEL_MAP[key]: weight * scores.get(key, 0.0) * scale
            for key, weight in self.weights.items()
        }

    def explain(self, scores: ScoreComponents) -> dict[str, float]:
        """각 요소의 기여 비율(%) 반환. 합 ≈ 100 (양수, 막대 표시용).

        blender 레짐은 기여가 음수일 수 있으므로 |기여|/Σ|기여| 로 정규화한다
        (부호·실제 점수는 breakdown 이 보유). rule 레짐은 기존 동작 그대로.
        """
        if self._is_blender(scores):
            magnitudes = {k: abs(float(v)) for k, v in scores.get("contrib", {}).items()}
            total = sum(magnitudes.values())
            if total == 0:
                n = len(magnitudes) or 1
                return {k: round(100 / n, 1) for k in magnitudes}
            return {k: round(v / total * 100, 1) for k, v in magnitudes.items()}

        contributions = self._rule_items(scores, 1.0)
        total = sum(contributions.values())
        if total == 0:
            n = len(contributions) or len(self.weights)
            return {k: round(100 / n, 1) for k in contributions}
        return {k: round(v / total * 100, 1) for k, v in contributions.items()}

    def top_reason(self, scores: ScoreComponents) -> str:
        """가장 큰 기여 요소 라벨 (LLM narrator용). blender 는 |기여| 최대."""
        if self._is_blender(scores):
            contrib = scores.get("contrib", {})
            if not contrib:
                return INTERCEPT_LABEL
            return max(contrib, key=lambda k: abs(contrib[k]))
        contributions = self.explain(scores)
        return max(contributions, key=contributions.get)

    def breakdown(self, scores: ScoreComponents) -> dict:
        """항목별 실제 기여 점수 + 합 반환. `mode` 로 레짐 구분.

        rule:    {"mode":"rule","items":{라벨:배점×달성도×100},"total":합,"intercept":0.0}
                 → items 합 == total == 규칙 종합(보조 제외)
        blender: {"mode":"blender","items":{라벨:wᵢ·xᵢ},"intercept":b,
                  "total":z(=b+Σ),"prob":σ(z)}
                 → intercept + Σ items == z (충실성 불변식). items 는 음수 가능.
        """
        if self._is_blender(scores):
            items = {k: round(float(v), 3) for k, v in scores.get("contrib", {}).items()}
            intercept = round(float(scores.get("intercept", 0.0)), 3)
            z = round(intercept + sum(items.values()), 3)
            # prob 은 분해와 충실한 σ(z) 그대로(=scores["ml"], scorer가 저장한
            # 깨끗한 시그모이드). like_bonus 는 학습 대상이 아닌 가산항이라
            # prob 에 섞지 않고 별도로 노출(σ(z)+bonus 가 1을 넘는 표시 방지).
            return {
                "mode": "blender",
                "items": items,
                "intercept": intercept,
                "total": z,
                "prob": round(float(scores.get("ml", 0.0)), 3),
                "like_bonus": round(float(scores.get("like_bonus", 0.0)), 3),
            }

        items = {k: round(v, 1) for k, v in self._rule_items(scores, 100.0).items()}
        return {
            "mode": "rule",
            "items": items,
            "intercept": 0.0,
            "total": round(sum(items.values()), 1),
        }
