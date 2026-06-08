"""app.db 스키마 부트스트랩 — 멱등."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# 동의 버전. 수집 항목 변경 시 증가시켜 재동의 트리거.
CONSENT_VERSION = "v1"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id              TEXT PRIMARY KEY,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    consent_at           TIMESTAMP,
    consent_version      TEXT,
    gender               TEXT,      -- 'M' | 'F' | NULL (선택 안 함)
    age_group            TEXT,      -- '10s' | '20s' | '30s' | '40s' | '50s+' | NULL
    city                 TEXT,      -- 사용자 위치 도시명 (예: 'Seoul')
    lat                  REAL,      -- 위도 (좌표 기반 날씨 조회용)
    lon                  REAL,      -- 경도
    location_source      TEXT,      -- 'browser' | 'ip' | 'manual' | 'default'
    location_updated_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS preference_vectors (
    user_id TEXT,
    feature TEXT,
    value   REAL,
    PRIMARY KEY (user_id, feature)
);

CREATE TABLE IF NOT EXISTS history (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            TEXT,
    recipe_id          TEXT,
    selected           INTEGER,
    ingredient_score   REAL,
    consumption_score  REAL,
    preference_score   REAL,
    context_score      REAL,
    hour               INTEGER,
    weather            TEXT,
    month              TEXT,           -- '1월'~'12월' (계절 4 → 월 12 해상도 확장)
    temporal_fit       REAL,           -- 0.0/0.5/1.0: 시기 적합 서수(월일치=1·계절만=0.5·불일치=0). 블렌더 5번 피처
    model_group        TEXT,           -- 실제 추천 레짐 (rule / blender)
    rec_rank           INTEGER,        -- 추천 리스트 내 위치(1-based). 평가 NDCG/Recall 순서용
    timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recommendation_impressions (
    session_id  TEXT,
    user_id     TEXT,
    recipe_id   TEXT,
    rec_rank    INTEGER,
    selected    INTEGER DEFAULT 0,
    acted       INTEGER DEFAULT 0,
    model_group TEXT,
    total_score REAL,
    hour        INTEGER,
    weather     TEXT,
    month       TEXT,
    -- 블렌더 학습 피처(노출 시점 스냅샷). 약한 미선택(acted=0) 행을 학습 음성으로
    -- 쓰기 위해 history 와 동일한 5피처를 여기에도 보존. history 는 명시적 선택만,
    -- 이 컬럼들은 '노출됐으나 안 고른' 약한 음성 신호의 X 를 공급한다.
    ingredient_score  REAL,
    consumption_score REAL,
    preference_score  REAL,
    context_score     REAL,
    temporal_fit      REAL,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, recipe_id)
);

CREATE TABLE IF NOT EXISTS fridge (
    user_id     TEXT,
    ingredient  TEXT,
    expiry_date DATE,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, ingredient)
);

-- 커스텀 레시피 (사용자 등록)
CREATE TABLE IF NOT EXISTS custom_recipes (
    id               TEXT PRIMARY KEY,
    author_id        TEXT,
    name             TEXT NOT NULL,
    style            TEXT,
    taste            TEXT,
    cook_time        INTEGER,
    difficulty       TEXT,
    suitable_time    TEXT,
    suitable_weather TEXT,
    suitable_month   TEXT,
    is_shared        INTEGER DEFAULT 0,
    review_keywords  TEXT,
    instructions     TEXT DEFAULT '',           -- 조리법 (사용자 입력 자유 텍스트)
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS custom_recipe_ingredients (
    recipe_id  TEXT,
    ingredient TEXT,
    PRIMARY KEY (recipe_id, ingredient)
);

-- Phase 2: 좋아요 (시스템 r001 + 커스텀 c xxx 모두 가능)
-- 별점(1~5)은 좋아요 토글과 신호 의미가 중복되어 통합·삭제됨.
CREATE TABLE IF NOT EXISTS recipe_likes (
    user_id    TEXT,
    recipe_id  TEXT,
    liked      INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, recipe_id)
);

-- 알레르기·기피 재료 (고정 설정, 온보딩 시 입력)
-- 의료 면책: 심한 알레르기·식이 제한은 의료 전문가와 상담 권장
CREATE TABLE IF NOT EXISTS user_restrictions (
    user_id    TEXT,
    ingredient TEXT,                -- 정규화된 재료명 (normalize_ingredient 적용)
    reason     TEXT DEFAULT 'avoid', -- 'allergy' | 'avoid' (선택적 메타)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, ingredient)
);

-- 키워드 피드백 투표 — LLM 초기 라벨을 사용자 응답으로 보정
CREATE TABLE IF NOT EXISTS recipe_keyword_votes (
    recipe_id TEXT,
    keyword   TEXT,
    agree     INTEGER DEFAULT 0,
    disagree  INTEGER DEFAULT 0,
    PRIMARY KEY (recipe_id, keyword)
);

-- user_id 가 PK leading 이 아닌 테이블에만 별도 인덱스.
-- (fridge/recipe_likes/user_restrictions/preference_vectors 는 PK 가 (user_id,...)
--  이라 SQLite 가 자동 인덱스 활용 → 별도 인덱스 불필요.)
CREATE INDEX IF NOT EXISTS idx_history_user
    ON history(user_id);
CREATE INDEX IF NOT EXISTS idx_impressions_user
    ON recommendation_impressions(user_id);
-- 약한 미선택 학습 쿼리(user_id + acted=0) 가속. 재학습마다 사용자 노출을 훑음.
CREATE INDEX IF NOT EXISTS idx_impressions_weak
    ON recommendation_impressions(user_id, acted);
"""


# 추가형(ADD COLUMN) 자동 마이그레이션 원장.
# SQLite 는 ADD COLUMN 만 안전(드롭·리네임·타입변경 불가)하므로 '컬럼 추가' 변경만
# 여기 등록하면 init_db 가 기존 DB 에 누락 컬럼을 자동 보강한다. SCHEMA_SQL 과 함께
# 갱신할 것 — 신규 DB 는 SCHEMA_SQL 이, 기존 DB 는 이 원장이 같은 컬럼을 채운다.
_ADDITIVE_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "recommendation_impressions": (
        ("ingredient_score", "REAL"),
        ("consumption_score", "REAL"),
        ("preference_score", "REAL"),
        ("context_score", "REAL"),
        ("temporal_fit", "REAL"),
    ),
}


def _reconcile_columns(con: sqlite3.Connection) -> None:
    """기존 테이블에 누락된 추가형 컬럼을 ALTER 로 보강(멱등). 구조적 변경은 미지원."""
    for table, columns in _ADDITIVE_COLUMNS.items():
        existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
        if not existing:
            continue  # 테이블 자체가 없으면 위 CREATE TABLE 이 새 스키마로 만듦
        for name, decl_type in columns:
            if name not in existing:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl_type}")


@contextmanager
def _connect(path: str | Path) -> Iterator[sqlite3.Connection]:
    """모듈 함수 공용 연결 컨텍스트. BaseRepository 패턴과 동일한 close 보장.

    Repo 가 아닌 모듈 함수(`ensure_user`/`record_consent`/`has_consent`/
    `get_consent_info`/`delete_user_complete`/`init_db`)들이 같은 try/finally
    보일러플레이트를 중복하지 않도록 한곳에 묶는다.
    """
    con = sqlite3.connect(path)
    try:
        yield con
    finally:
        con.close()


def init_db(db_path: str | Path | None = None) -> Path:
    """app.db 생성 및 스키마 적용. 멱등.

    SCHEMA_SQL 은 모든 컬럼을 정의하는 단일 출처. 신규 DB 는 여기서 완성된다.
    기존 DB 의 **컬럼 추가**(additive)는 `_reconcile_columns` 가 매 기동 시 자동
    보강한다(`_ADDITIVE_COLUMNS` 원장 기반) — 별도 수동 마이그레이션 불필요.
    단, 드롭·리네임·타입변경 같은 **구조적 변경**은 자동화하지 않으므로 그때는
    app.db 재생성이 필요하다(README §6).
    """
    from .db_paths import get_app_db_path  # 순환 import 회피 — _base_repo→db_init→db_paths
    path = Path(db_path) if db_path is not None else Path(get_app_db_path())
    path.parent.mkdir(parents=True, exist_ok=True)

    with _connect(path) as con:
        # WAL: reader/writer 비차단(읽기가 쓰기 뒤에 직렬화되지 않음) + 커밋 가속.
        # DB 파일 헤더에 영속되므로 connect-per-op 후속 연결이 자동 상속 → 단일
        # 출처(init_db)에서 한 번만 단언. 멱등. executescript 보다 먼저 실행.
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(SCHEMA_SQL)
        # 기존 DB 누락 컬럼 자동 보강(추가형 마이그레이션). 신규 DB 는 no-op.
        _reconcile_columns(con)
        con.commit()
    return path


def ensure_user(db_path: str | Path, user_id: str) -> None:
    """users 테이블에 사용자 행이 없으면 생성."""
    with _connect(db_path) as con:
        con.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        con.commit()


# ── 데이터 수집 동의 ──

def record_consent(
    db_path: str | Path,
    user_id: str,
    version: str = CONSENT_VERSION,
) -> None:
    """동의 시점 + 버전 기록. user_id 없으면 자동 생성."""
    if not user_id:
        return
    ensure_user(db_path, user_id)
    with _connect(db_path) as con:
        con.execute(
            "UPDATE users SET consent_at = CURRENT_TIMESTAMP, consent_version = ? "
            "WHERE user_id = ?",
            (version, user_id),
        )
        con.commit()


def has_consent(db_path: str | Path, user_id: str) -> bool:
    """현재 버전(CONSENT_VERSION)으로 동의 완료한 사용자인지."""
    if not user_id:
        return False
    if not Path(db_path).exists():
        return False
    with _connect(db_path) as con:
        row = con.execute(
            "SELECT consent_at, consent_version FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return False
    consent_at, version = row
    return consent_at is not None and version == CONSENT_VERSION


def get_consent_info(db_path: str | Path, user_id: str) -> dict | None:
    """동의 기록 반환. 없으면 None."""
    if not user_id or not Path(db_path).exists():
        return None
    with _connect(db_path) as con:
        row = con.execute(
            "SELECT consent_at, consent_version FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row or row[0] is None:
        return None
    return {"consent_at": row[0], "consent_version": row[1]}


def delete_user_complete(db_path: str | Path, user_id: str) -> None:
    """사용자 데이터 전체 cascade 삭제 (동의 철회 처리).

    FK 의존성 순으로 삭제하여 무결성 위반 없이 처리한다. 커스텀 레시피의
    cascade 정책은 `CustomRecipeRepo.cascade_delete_recipe` 단일 출처를 사용
    (자식 테이블 추가 시 한 곳만 갱신).
    """
    if not user_id:
        return
    from .custom_recipe_repo import CustomRecipeRepo

    with _connect(db_path) as con:
        custom_ids = [
            r[0]
            for r in con.execute(
                "SELECT id FROM custom_recipes WHERE author_id = ?", (user_id,)
            ).fetchall()
        ]
        # 이 사용자가 작성한 커스텀 레시피 각각의 자식 row 정리(고아 row 방지).
        for recipe_id in custom_ids:
            CustomRecipeRepo.cascade_delete_recipe(con, recipe_id)
        con.execute("DELETE FROM recipe_likes WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM recommendation_impressions WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM fridge WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM preference_vectors WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM user_restrictions WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        con.commit()

    try:
        from .model_registry import ModelRegistry

        ModelRegistry().clear_user(user_id)
    except ValueError:
        # 오래된/외부 입력 user_id 가 파일 경로로 안전하지 않으면 DB 삭제만 완료한다.
        pass


if __name__ == "__main__":
    path = init_db()
    print(f"[OK] {path} 초기화 완료")
