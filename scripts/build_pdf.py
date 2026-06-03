#!/usr/bin/env python3
"""
프로젝트 MD → HTML → PDF 빌드 파이프라인.

KaTeX 수식 + Mermaid 차트 + HTML 중간 산출물 지원.

사용법:
    python scripts/build_pdf.py all                  # 14개 전부 → 개별 PDF
    python scripts/build_pdf.py all --merge          # + 합본 PDF (all_in_one.pdf)
    python scripts/build_pdf.py README.md            # 단일 파일
    python scripts/build_pdf.py docs/시연_시나리오.md
    python scripts/build_pdf.py all --keep-html      # HTML 중간 산출물 유지
    python scripts/build_pdf.py all --out ./custom   # 출력 폴더 변경

의존성 (requirements.txt):
    markdown>=3.5, Pygments>=2.16, pypdf>=4.0 (--merge 시)

외부 자원 (기존 위치 재활용):
    2026-1/_shared/mermaid/mermaid.min.js
    2026-1/ai_math/교재/text_book/main/katex/{katex.min.js, katex.min.css, contrib/auto-render.min.js, fonts/}

PDF 엔진: Chrome/Edge headless (subprocess). 다중 폴백 + shutil.which() 검색.
"""
from __future__ import annotations

import argparse
import html
import io
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path

# Windows 콘솔 cp949 → UTF-8 강제 (한글·이모지 출력)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import markdown as md_lib  # noqa: E402

# ─────────────────────────────────────────
# 경로 상수
# ─────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent      # 프로젝트/
REPO_ROOT = PROJECT_ROOT.parent.parent.parent              # ssu_study/
MERMAID_JS = REPO_ROOT / "2026-1" / "_shared" / "mermaid" / "mermaid.min.js"
KATEX_DIR = REPO_ROOT / "2026-1" / "ai_math" / "교재" / "text_book" / "main" / "katex"
KATEX_CSS = KATEX_DIR / "katex.min.css"
KATEX_JS = KATEX_DIR / "katex.min.js"
KATEX_AUTO = KATEX_DIR / "contrib" / "auto-render.min.js"

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

# 합본 PDF 의 파일 순서 (자연스러운 인계 순서: 요약 → 본문 → 상세)
MERGE_ORDER = [
    "README.md",
    "docs/초기용_설계서.md",
    "분석_구현안.md",
    "docs/초기용_플로우차트.md",
    "docs/개발환경_설정.md",
    "docs/팀_컨벤션.md",
    "docs/데이터_명세.md",
    "docs/구현_진행상황.md",
    "docs/CHANGELOG.md",
    "docs/테스트_계획.md",
    "docs/시연_시나리오.md",
    "docs/시연_검증_보고.md",
    "docs/서버_배포_가이드.md",
    "docs/발표_아웃라인.md",
    "docs/README.md",
]


from _cli_utils import die, info, ok, section, warn  # noqa: E402


# ─────────────────────────────────────────
# 1. 파일 탐색
# ─────────────────────────────────────────
def discover_all_files() -> list[Path]:
    """프로젝트 의 모든 정식 .md 파일 (recipes/ 제외)."""
    files: list[Path] = []
    # 합본 순서대로 정렬해서 반환 — 단일 빌드에선 순서 무관, 합본에선 일치
    for rel in MERGE_ORDER:
        p = PROJECT_ROOT / rel
        if p.exists():
            files.append(p)
        else:
            warn(f"누락: {rel}")
    return files


def resolve_target(target: str) -> list[Path]:
    """CLI 인자를 파일 목록으로 해석.

    "all" → discover_all_files()
    그 외 → 단일 파일 경로 (프로젝트/ 기준)
    """
    if target == "all":
        return discover_all_files()
    p = PROJECT_ROOT / target
    if not p.exists():
        die(f"파일 없음: {target}")
    if p.suffix != ".md":
        die(f"md 파일이 아님: {target}")
    return [p]


# ─────────────────────────────────────────
# 2. Chrome 탐지
# ─────────────────────────────────────────
def find_chrome() -> str:
    """Chrome 또는 Edge 실행 파일 경로 탐색. 못 찾으면 die."""
    for path in CHROME_PATHS:
        if Path(path).exists():
            return path
    for cmd in ("chrome", "chrome.exe", "msedge", "msedge.exe", "google-chrome"):
        which = shutil.which(cmd)
        if which:
            return which
    die(
        "Chrome / Edge 실행 파일을 찾지 못함.\n"
        "  - Windows: Chrome 또는 Edge 설치 확인\n"
        f"  - 또는 CHROME_PATHS 에 경로 추가: {__file__}"
    )
    return ""  # noqa


# ─────────────────────────────────────────
# 3. 자원 사전 점검
# ─────────────────────────────────────────
def check_resources() -> None:
    """KaTeX·Mermaid 자원 존재 확인."""
    missing = []
    for resource in (MERMAID_JS, KATEX_CSS, KATEX_JS, KATEX_AUTO):
        if not resource.exists():
            missing.append(str(resource))
    if missing:
        die("외부 자원 누락:\n" + "\n".join(f"  - {m}" for m in missing))


# ─────────────────────────────────────────
# 4. 수식 placeholder 전·후처리
# ─────────────────────────────────────────
def preprocess_math(md_text: str) -> tuple[str, dict[str, str]]:
    """`$...$`, `$$...$$` 를 placeholder 로 치환 — markdown 파서로부터 보호."""
    placeholders: dict[str, str] = {}
    counter = [0]

    def make_ph(match: re.Match) -> str:
        key = f"%%MATH_{counter[0]}%%"
        counter[0] += 1
        placeholders[key] = match.group(0)
        return key

    # 1. block math (멀티라인 $$...$$ 별도 줄)
    text = re.sub(
        r"^\$\$\s*$(.*?)^\$\$\s*$",
        make_ph,
        md_text,
        flags=re.DOTALL | re.MULTILINE,
    )
    # 2. inline display math ($$...$$)
    text = re.sub(r"\$\$(.+?)\$\$", make_ph, text)
    # 3. inline math ($...$)
    text = re.sub(
        r"(?<!\$)\$(?!\$)((?:[^$\n]|\\\$)+?)(?<!\$)\$(?!\$)",
        make_ph,
        text,
    )
    return text, placeholders


def restore_math(html_text: str, placeholders: dict[str, str]) -> str:
    """HTML 변환 후 placeholder 복원 (escaped 변종 포함)."""
    for key, value in placeholders.items():
        html_text = html_text.replace(key, value)
        escaped = key.replace("%", "&#37;")
        html_text = html_text.replace(escaped, value)
    return html_text


# ─────────────────────────────────────────
# 5. Mermaid 블록 처리
# ─────────────────────────────────────────
MERMAID_BLOCK_RE = re.compile(r"```mermaid\s*\n(.*?)\n```", re.IGNORECASE | re.DOTALL)


def render_mermaid_blocks(md_text: str) -> str:
    """````mermaid``` 블록 → <pre class="mermaid"> 로 변환.

    markdown 파서가 코드블록으로 처리하지 않도록 사전에 raw HTML 로 교체.
    `<br/>` 등 HTML 토큰은 escape 해서 <pre> 안에서 브라우저가 해석하지 않도록 한다
    (mermaid 가 securityLevel: loose + htmlLabels: true 로 자체 디코딩한다).
    """
    def replace(match: re.Match) -> str:
        diagram = match.group(1).strip()
        return (
            '\n<div class="mermaid-diagram">'
            f'<pre class="mermaid">{html.escape(diagram)}</pre>'
            '</div>\n'
        )

    return MERMAID_BLOCK_RE.sub(replace, md_text)


# ─────────────────────────────────────────
# 6. HTML 템플릿
# ─────────────────────────────────────────
def _file_uri(path: Path) -> str:
    """Windows 절대경로 → file:/// URI."""
    return path.resolve().as_uri()


def html_template(title: str, body_html: str) -> str:
    mermaid_uri = _file_uri(MERMAID_JS)
    katex_css_uri = _file_uri(KATEX_CSS)
    katex_js_uri = _file_uri(KATEX_JS)
    katex_auto_uri = _file_uri(KATEX_AUTO)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{katex_css_uri}">
<style>
{CSS}
</style>
</head>
<body>
<article class="doc">
{body_html}
</article>

<script src="{katex_js_uri}"></script>
<script src="{katex_auto_uri}"></script>
<script src="{mermaid_uri}"></script>
<script>
(function () {{
    if (window.renderMathInElement) {{
        renderMathInElement(document.body, {{
            delimiters: [
                {{ left: "$$", right: "$$", display: true }},
                {{ left: "$",  right: "$",  display: false }},
                {{ left: "\\\\(", right: "\\\\)", display: false }},
                {{ left: "\\\\[", right: "\\\\]", display: true }}
            ],
            throwOnError: false
        }});
    }}
    if (!window.mermaid) {{
        document.documentElement.setAttribute("data-mermaid-error", "missing mermaid global");
        return;
    }}
    mermaid.initialize({{
        startOnLoad: false,
        securityLevel: "loose",
        theme: "base",
        flowchart: {{
            htmlLabels: true,
            useMaxWidth: true,
            nodeSpacing: 35,
            rankSpacing: 40,
            padding: 8
        }},
        sequence: {{ useMaxWidth: true }},
        themeVariables: {{
            fontFamily: "Malgun Gothic, Apple SD Gothic Neo, Noto Sans KR, sans-serif",
            primaryColor: "#edf4fb",
            primaryBorderColor: "#9ebbd8",
            primaryTextColor: "#1a1a1a",
            lineColor: "#5b7897"
        }}
    }});
    window.__MERMAID_READY__ = mermaid.run({{ querySelector: ".mermaid" }})
        .then(function () {{
            document.documentElement.setAttribute("data-mermaid-ready", "true");
        }})
        .catch(function (error) {{
            console.error(error);
            document.documentElement.setAttribute("data-mermaid-error", String(error));
        }});
}})();
</script>
</body>
</html>
"""


CSS = """
@page {
    size: A4;
    margin: 18mm 15mm 18mm 15mm;
}

* { box-sizing: border-box; }

body {
    font-family: "Malgun Gothic", "맑은 고딕", "Apple SD Gothic Neo", "Noto Sans CJK KR",
                 -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a1a;
    margin: 0;
}

.doc {
    max-width: 100%;
}

h1 {
    font-size: 22pt;
    border-bottom: 2px solid #1a1a1a;
    padding-bottom: 6pt;
    margin-top: 18pt;
    page-break-after: avoid;
}

h2 {
    font-size: 17pt;
    border-bottom: 1px solid #888;
    padding-bottom: 4pt;
    margin-top: 16pt;
    page-break-after: avoid;
}

h3 {
    font-size: 14pt;
    margin-top: 14pt;
    page-break-after: avoid;
}

h4, h5, h6 {
    font-size: 12pt;
    margin-top: 12pt;
    page-break-after: avoid;
}

p { margin: 6pt 0; }

ul, ol { padding-left: 22pt; }
li { margin: 3pt 0; }

a { color: #0958d9; text-decoration: none; word-break: break-all; }
a:hover { text-decoration: underline; }

code {
    background: #f4f4f4;
    border-radius: 3px;
    padding: 1px 5px;
    font-family: Consolas, "Courier New", monospace;
    font-size: 10pt;
    color: #c7254e;
}

pre {
    background: #f8f8f8;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 8pt 10pt;
    overflow-x: auto;
    font-size: 9.5pt;
    line-height: 1.45;
    page-break-inside: avoid;
}
pre code {
    background: transparent;
    border: 0;
    padding: 0;
    color: inherit;
    font-size: inherit;
}

blockquote {
    border-left: 4px solid #ccc;
    padding-left: 10pt;
    color: #555;
    margin: 6pt 0;
}

table {
    border-collapse: collapse;
    margin: 8pt 0;
    width: 100%;
    page-break-inside: avoid;
}
th, td {
    border: 1px solid #bbb;
    padding: 5pt 8pt;
    font-size: 10.5pt;
    vertical-align: top;
}
th { background: #f0f0f0; text-align: left; }

hr {
    border: 0;
    border-top: 1px solid #ddd;
    margin: 14pt 0;
}

.mermaid-diagram {
    text-align: center;
    margin: 10pt 0;
    page-break-inside: avoid;
}
.mermaid-diagram svg {
    max-width: 100%;
    /* A4 본문 영역(높이 ~26cm)에 다이어그램 + 주변 텍스트가 함께 들어가도록 제한 */
    max-height: 22cm;
    height: auto;
}

.katex { font-size: 1.05em; }
.katex-display { margin: 8pt 0; }

img { max-width: 100%; height: auto; }
"""


# ─────────────────────────────────────────
# 7. HTML 빌드
# ─────────────────────────────────────────
def build_html(md_path: Path) -> str:
    """단일 md → HTML 문자열."""
    md_text = md_path.read_text(encoding="utf-8")
    md_text = render_mermaid_blocks(md_text)
    md_text, placeholders = preprocess_math(md_text)

    body_html = md_lib.markdown(
        md_text,
        extensions=[
            "extra",         # 표·각주·약어 등
            "codehilite",    # Pygments
            "toc",
            "sane_lists",
            "tables",
        ],
        extension_configs={
            "codehilite": {"guess_lang": False, "noclasses": True},
        },
        output_format="html5",
    )
    body_html = restore_math(body_html, placeholders)
    return html_template(md_path.stem, body_html)


# ─────────────────────────────────────────
# 8. Chrome → PDF
# ─────────────────────────────────────────
def html_to_pdf(html_text: str, pdf_path: Path, chrome: str) -> None:
    """HTML 문자열 → PDF (Chrome headless subprocess)."""
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".html", delete=False,
    ) as tmp:
        tmp.write(html_text)
        tmp_path = Path(tmp.name)

    try:
        args = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--allow-file-access-from-files",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=30000",
            f"--print-to-pdf={pdf_path}",
            tmp_path.as_uri(),
        ]
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0 or not pdf_path.exists():
            err = (result.stderr or result.stdout or "").strip()[:500]
            raise RuntimeError(f"Chrome PDF 생성 실패 (rc={result.returncode}): {err}")
    finally:
        with suppress(OSError):
            tmp_path.unlink()


# ─────────────────────────────────────────
# 9. pypdf 합본 + outline
# ─────────────────────────────────────────
def merge_pdfs(pdfs: list[tuple[Path, str]], out_path: Path) -> None:
    """[(pdf_path, bookmark_title), ...] → 단일 PDF + outline."""
    try:
        from pypdf import PdfReader, PdfWriter  # noqa: PLC0415
    except ImportError:
        die("pypdf 미설치 — `pip install pypdf` 후 재시도")

    writer = PdfWriter()
    page_offset = 0
    for pdf_path, title in pdfs:
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            writer.add_page(page)
        writer.add_outline_item(title, page_offset)
        page_offset += len(reader.pages)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        writer.write(f)


# ─────────────────────────────────────────
# 10. main
# ─────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="프로젝트 MD → HTML → PDF 빌더 (KaTeX + Mermaid 지원)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("target", help='"all" 또는 단일 md 경로 (프로젝트 기준 상대경로)')
    p.add_argument("--merge", action="store_true", help="개별 PDF + 합본 PDF (all_in_one.pdf)")
    p.add_argument("--keep-html", action="store_true", help="HTML 중간 산출물 유지")
    p.add_argument("--out", default="pdf_output", help="PDF 출력 디렉토리 (default: pdf_output)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    section("자원 점검")
    check_resources()
    chrome = find_chrome()
    ok(f"Chrome: {chrome}")

    out_dir = (PROJECT_ROOT / args.out).resolve()
    html_dir = (PROJECT_ROOT / "html_output").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.keep_html:
        html_dir.mkdir(parents=True, exist_ok=True)

    files = resolve_target(args.target)
    section(f"빌드 대상 {len(files)}개")
    for f in files:
        info(f.relative_to(PROJECT_ROOT))

    # 빌드 루프
    generated: list[tuple[Path, str]] = []
    for md_path in files:
        rel = md_path.relative_to(PROJECT_ROOT)
        section(f"빌드 — {rel}")
        t_start = time.time()

        html_text = build_html(md_path)

        if args.keep_html:
            html_path = html_dir / f"{md_path.stem}.html"
            html_path.write_text(html_text, encoding="utf-8")
            ok(f"HTML: {html_path.relative_to(PROJECT_ROOT)}")

        # 같은 파일명이 docs/README 와 README 처럼 중복 가능 — 경로 슬러그
        slug = str(rel).replace("\\", "_").replace("/", "_").removesuffix(".md")
        pdf_path = out_dir / f"{slug}.pdf"
        html_to_pdf(html_text, pdf_path, chrome)

        elapsed = time.time() - t_start
        ok(f"PDF: {pdf_path.relative_to(PROJECT_ROOT)} ({elapsed:.1f}s)")
        generated.append((pdf_path, md_path.stem))

    # 합본
    if args.merge and len(generated) > 1:
        section("합본 PDF 생성")
        merged_path = out_dir / "all_in_one.pdf"
        merge_pdfs(generated, merged_path)
        ok(f"합본: {merged_path.relative_to(PROJECT_ROOT)} ({len(generated)}개 통합)")

    print("\n" + "=" * 50)
    print(f"완료 — {len(generated)}개 PDF" + (" + 합본 1개" if args.merge else ""))
    print(f"출력: {out_dir}")
    print("=" * 50)


if __name__ == "__main__":
    main()
