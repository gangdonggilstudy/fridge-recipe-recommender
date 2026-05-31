"""추천 세션 범위 set — session_id 변경 시 자연 초기화 (`picked` / `disliked` 공통)."""
from __future__ import annotations

import streamlit as st


class SessionScopedSet:
    """`(session_id, set[recipe_id])` 튜플로 st.session_state 에 저장되는 집합."""

    def __init__(self, key: str, session_id: str | None):
        self.key = key
        self.session_id = session_id

    def _load(self) -> set[str]:
        state = st.session_state.get(self.key)
        if isinstance(state, tuple) and state[0] == self.session_id:
            return state[1]
        return set()

    def _save(self, items: set[str]) -> None:
        st.session_state[self.key] = (self.session_id, items)

    def add(self, item: str) -> bool:
        """추가하고 처음 추가됐는지 반환. 이미 있으면 False (no-op)."""
        items = self._load()
        if item in items:
            return False
        items.add(item)
        self._save(items)
        return True

    def discard(self, item: str) -> None:
        """있으면 제거, 없으면 no-op."""
        items = self._load()
        if item not in items:
            return
        items.discard(item)
        self._save(items)

    def __contains__(self, item: str) -> bool:
        return item in self._load()
