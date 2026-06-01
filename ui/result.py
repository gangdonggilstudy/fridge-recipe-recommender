"""추천 결과 — 행 클릭 = 선택 액션 + 모달. 별로에요는 모달 안 버튼."""
from __future__ import annotations

from uuid import uuid4

import streamlit as st

from llm.narrator import Narrator
from modules.explainer import Explainer
from modules.ingredient_matcher import missing_ingredients
from modules.like_repo import LikeRepo
from modules.recommendation_impression import RecommendationImpressionRepo
from modules.recommender import Recommender
from ui._defaults import DISPLAY_N, OVERFETCH_N
from ui._session_scoped import SessionScopedSet
from ui.result_cards import (
    render_card_ai,
    render_card_explanation,
    render_card_instructions,
    render_like,
)
from ui.session_keys import SessionKeys


class ResultPageController:
    """추천 결과 페이지의 상태 + 부수효과 라우팅.

    매 rerun 마다 새 인스턴스 (생성 비용 거의 0 — 의존성 보유만).
    """

    def __init__(
        self,
        user_id: str,
        recommender: Recommender,
        context: dict,
        *,
        narrator: Narrator | None = None,
        like_repo: LikeRepo | None = None,
        impression_repo: RecommendationImpressionRepo | None = None,
    ):
        self.user_id = user_id
        self.recommender = recommender
        self.context = context
        self.narrator = narrator or Narrator()
        self.like_repo = like_repo
        self.impression_repo = impression_repo
        self.explainer = Explainer()

    # ── 진입점 ──

    def run(self) -> None:
        """페이지 전체 렌더 — 헤더·메트릭 → 추천 버튼 → 리스트 → 선택 시 팝업."""
        self._render_header()
        self._maybe_refresh_results()
        results = self._visible_results()
        if not results:
            return

        owned_names = {i["name"] for i in self.recommender.fridge.load(self.user_id)}
        impression_session_id = self._ensure_impression_session(results)

        st.subheader(f"📋 추천 결과 ({len(results)}개)")
        for idx, recipe in enumerate(results, start=1):
            self._render_list_item(idx, recipe, owned_names, impression_session_id)

        # 선택된 음식이 있으면 모달 팝업으로 상세 표시.
        opened_id = st.session_state.get(SessionKeys.detail_open_for(self.user_id))
        if opened_id:
            opened_with_rank = next(
                ((r, i) for i, r in enumerate(results, start=1) if r["id"] == opened_id),
                None,
            )
            if opened_with_rank is not None:
                opened, opened_rank = opened_with_rank
                _show_detail_dialog(
                    user_id=self.user_id,
                    recipe=opened,
                    explainer=self.explainer,
                    narrator=self.narrator,
                    like_repo=self.like_repo,
                    recommender=self.recommender,
                    context=self.context,
                    rank=opened_rank,
                    impression_repo=self.impression_repo,
                    impression_session_id=impression_session_id,
                )

    # ── 페이지 헤더 ──

    def _render_header(self) -> None:
        st.header("🍽️ 추천 메뉴")
        cols = st.columns(3)
        cols[0].metric("시간대", self.context["time"])
        cols[1].metric("날씨", self.context["weather"])
        cols[2].metric("계절", self.context["season"])
        st.divider()

    # ── 추천 fetch + 세션 캐시 ──

    def _maybe_refresh_results(self) -> None:
        if st.button("🔄 추천 받기", type="primary", use_container_width=True):
            with st.spinner("추천 계산 중..."):
                results = self.recommender.recommend(
                    self.user_id, self.context, top_n=OVERFETCH_N,
                )
                st.session_state[SessionKeys.last_results_for(self.user_id)] = results
                st.session_state[SessionKeys.last_ctx_for(self.user_id)] = self.context
                # 새 결과를 받으면 열려있던 팝업도 정리 (다른 recipe 일 가능성).
                st.session_state.pop(SessionKeys.detail_open_for(self.user_id), None)

    def _visible_results(self) -> list[dict]:
        """저장된 결과를 DISPLAY_N 개까지 노출. 빈 상태 안내 동반."""
        results_key = SessionKeys.last_results_for(self.user_id)
        ctx_key = SessionKeys.last_ctx_for(self.user_id)
        raw_results = st.session_state.get(results_key, [])
        if raw_results and st.session_state.get(ctx_key) != self.context:
            st.session_state.pop(results_key, None)
            st.session_state.pop(ctx_key, None)
            st.session_state.pop(SessionKeys.detail_open_for(self.user_id), None)
            st.session_state.pop(SessionKeys.LAST_IMPRESSION_SIGNATURE, None)
            st.session_state.pop(SessionKeys.LAST_IMPRESSION_SESSION_ID, None)
            raw_results = []
        results = raw_results[:DISPLAY_N]
        if not results:
            st.info(
                "위 '추천 받기' 버튼을 눌러주세요. "
                "냉장고에 재료가 있어야 추천이 가능합니다."
            )
        return results

    # ── 노출 세션 ──

    def _ensure_impression_session(self, recipes: list[dict]) -> str | None:
        """표시 세트가 바뀌면 새 노출 세션을 만들고, rerun 중복은 막는다."""
        if self.impression_repo is None:
            return None
        recipe_sig = tuple(
            (
                r["id"],
                r.get("scores", {}).get("combine", "rule"),
                round(float(r.get("scores", {}).get("total", 0.0)), 6),
            )
            for r in recipes
        )
        signature = (
            self.user_id, recipe_sig,
            self.context.get("hour"), self.context.get("weather"), self.context.get("season"),
        )
        if st.session_state.get(SessionKeys.LAST_IMPRESSION_SIGNATURE) != signature:
            session_id = uuid4().hex
            self.impression_repo.log_view(
                self.user_id, session_id, recipes, self.context,
            )
            st.session_state[SessionKeys.LAST_IMPRESSION_SIGNATURE] = signature
            st.session_state[SessionKeys.LAST_IMPRESSION_SESSION_ID] = session_id
        return st.session_state.get(SessionKeys.LAST_IMPRESSION_SESSION_ID)

    # ── 리스트 항목 ──

    def _render_list_item(
        self,
        rank: int,
        recipe: dict,
        owned_names: set[str],
        impression_session_id: str | None,
    ) -> None:
        """음식 행 = 큰 버튼. 클릭하면 선택 학습 신호 기록 + 다이얼로그 팝업."""
        badge = " 📝" if recipe.get("is_custom") else ""
        meta = (
            f"{recipe['style']} · {', '.join(recipe['taste'])} · "
            f"{recipe['cook_time']}분 · {recipe['difficulty']}"
        )
        score = recipe["scores"]["total"]
        label = f"{rank}. {recipe['name']}{badge}  ·  {meta}  ·  ⭐ {score:.2f}"

        if st.button(
            label,
            key=f"pick_{recipe['id']}",
            use_container_width=True,
        ):
            self._handle_pick(recipe, rank, impression_session_id)

        missing = missing_ingredients(owned_names, recipe["ingredients"])
        if missing:
            st.caption(f"⚠ 추가 필요: {', '.join(missing)}")

    # ── 선택 액션 ──

    def _handle_pick(
        self,
        recipe: dict,
        rank: int,
        impression_session_id: str | None,
    ) -> None:
        """행 클릭 = 선택 + 팝업.

        같은 추천 세션(impression_session_id) 안에서는 같은 recipe 가 이미 선택
        학습 신호를 받았으면 record_choice 호출을 생략한다 — 사용자가 같은 음식을
        여러 번 눌러도 history 에 중복 row 가 쌓이지 않도록. 새 추천을 받으면
        세션 ID 가 바뀌어 자동으로 카운터가 초기화된다.
        """
        picked = SessionScopedSet(
            SessionKeys.picked_in_session_for(self.user_id),
            impression_session_id,
        )
        if picked.add(recipe["id"]):
            trained = self.recommender.record_choice(
                self.user_id, recipe, True, self.context, rank=rank,
                impression_repo=self.impression_repo,
                impression_session_id=impression_session_id,
            )
            if trained:
                st.toast("🤖 내 추천 모델 학습 완료")
        st.session_state[SessionKeys.detail_open_for(self.user_id)] = recipe["id"]
        st.rerun()


@st.dialog("🍽️ 레시피")
def _show_detail_dialog(
    *,
    user_id: str,
    recipe: dict,
    explainer: Explainer,
    narrator: Narrator,
    like_repo: LikeRepo | None,
    recommender: Recommender,
    context: dict,
    rank: int,
    impression_repo: RecommendationImpressionRepo | None,
    impression_session_id: str | None,
) -> None:
    """선택한 음식의 상세 정보 모달. 닫기 버튼으로 명시적 종료 — 그래야
    다음 rerun 에 다이얼로그가 재오픈되지 않는다 (Streamlit dialog 의 X 닫기는
    session_state 와 별도라 잔류 키 정리가 필요).

    하단 액션: [👎 별로에요] [닫기]
      - 별로에요는 같은 추천 화면에서 메뉴당 1회 (disliked_in_session 가드).
      - 별로에요 시 picked_in_session 에서 제거 → 마음 바꿔 다시 클릭하면
        새 좋아요 신호로 처리.
    """
    st.subheader(recipe["name"])
    st.caption(
        f"{recipe['style']} · {', '.join(recipe['taste'])} · "
        f"{recipe['cook_time']}분 · {recipe['difficulty']}"
    )

    render_card_instructions(recipe)
    render_card_explanation(recipe, explainer)
    render_card_ai(recipe, narrator, explainer)
    if like_repo is not None:
        render_like(like_repo, user_id, recipe["id"])

    st.divider()
    picked = SessionScopedSet(
        SessionKeys.picked_in_session_for(user_id), impression_session_id,
    )
    disliked = SessionScopedSet(
        SessionKeys.disliked_in_session_for(user_id), impression_session_id,
    )
    col_dislike, col_close = st.columns(2)
    if col_dislike.button(
        "👎 별로에요",
        use_container_width=True,
        key=f"dislike_{recipe['id']}",
        disabled=recipe["id"] in disliked,
        help="이 추천이 별로였다고 알려주세요 (학습 신호 -1.5)",
    ):
        recommender.record_dislike(
            user_id, recipe, context, rank=rank,
            impression_repo=impression_repo,
            impression_session_id=impression_session_id,
        )
        picked.discard(recipe["id"])     # 재선택 허용
        disliked.add(recipe["id"])       # 사이클 1회 가드
        st.session_state.pop(SessionKeys.detail_open_for(user_id), None)
        st.toast(f"👎 '{recipe['name']}' 별로에요로 기록", icon="👎")
        st.rerun()
    if col_close.button(
        "닫기", use_container_width=True, key=f"close_detail_{recipe['id']}",
    ):
        st.session_state.pop(SessionKeys.detail_open_for(user_id), None)
        st.rerun()


# ── 진입점 (호환 시그니처 보존) ──

def render(
    user_id: str,
    recommender: Recommender,
    context: dict,
    narrator: Narrator | None = None,
    like_repo: LikeRepo | None = None,
    impression_repo: RecommendationImpressionRepo | None = None,
) -> None:
    """추천 결과 화면 렌더링 — `app.py` 호환 진입점."""
    ResultPageController(
        user_id, recommender, context,
        narrator=narrator,
        like_repo=like_repo,
        impression_repo=impression_repo,
    ).run()
