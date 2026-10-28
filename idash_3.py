"""iCReaT 연구데이터 정제 및 기탁 대시보드 (Streamlit)

구성
- 대시보드 현황      : KPI + iCReaT eCRF(C170005) → CODA 코드북 매핑 미리보기
- 과제 및 데이터 입력 폼 : iCReaT 자동 연동(읽기 전용) + 연구자 입력(CODA '과제정보' 시트 항목)
- 코드북 매핑 & 정제   : 입력 폼(과제정보) + 매핑 결과(코드북)를 한 화면에 통합, CODA 기탁 양식 Excel 생성

파일
- data/C170005_ecrf_codebook.xlsx           : iCReaT eCRF 코드북 (eCRF명, 항목명, 변수명, 항목유형, 데이터유형, 길이, 단위, 코드리스트)
- data/CODA_clinical_codebook_template.xlsx : CODA 기탁_임상정보 코드북 양식 (과제정보 / 코드북 시트를 채워서 내려받음)
- style.css                                  : 화면 디자인
"""
import datetime as dt
import html
import io
from collections import Counter
from pathlib import Path

import openpyxl
import pandas as pd
import streamlit as st
from openpyxl.styles import Alignment

st.set_page_config(page_title="iCReaT 연구데이터 정제 및 기탁 대시보드", page_icon="🗄️", layout="wide",
                   initial_sidebar_state="collapsed")
E = html.escape
BASE = Path(__file__).parent
DATA = BASE / "data"
ECRF_FILE = DATA / "C170005_ecrf_codebook.xlsx"
TEMPLATE_FILE = DATA / "CODA_clinical_codebook_template.xlsx"

# ══════════════════════════════════════════════════════════════
# 1. 규칙 / 설정  (실제 CODA 규칙 확정 시 여기만 수정)
# ══════════════════════════════════════════════════════════════
# eCRF명 → CODA 테이블명(국문). 영문 테이블명은 eCRF명을 그대로 사용
ECRF_KO = {
    "BaseLineInfo": "기본정보(이식)", "Baseline Information": "기본정보", "Baseline Information_": "기본정보(추가)",
    "BaseLine": "기본정보(BaseLine)", "Laboratory Values": "검사 결과", "Demographics": "인구학적 정보",
    "Drinking and Past-Medical History": "음주 및 과거 병력",
    "dringking and past-medical history_COPY": "음주 및 과거 병력(사본)",
    "Study Drug": "연구 약물", "AE": "이상반응", "그리드 반복": "그리드 반복",
    # 목업 과제용
    "DM": "인구학적 정보", "VS": "활력징후", "LB": "임상검사",
}


def coda_type(dtype, codelist):
    """iCReaT 데이터 유형 → CODA 변수 타입"""
    if codelist:
        return "범주형"
    return {"Integer": "연속형", "Float": "연속형", "String": "문자형", "Date": "날짜형"}.get(dtype, "검토 필요")


def coda_codes(codelist):
    """'1=Normal|2=Abnormal' → '1=Normal,\\n2=Abnormal' (CODA 양식 표기)"""
    if not codelist:
        return ""
    parts = [p.strip() for p in codelist.replace(";", "|").split("|") if p.strip()]
    return ",\n".join(parts)


# CODA 큐레이션 키 변수 (No.0, 00_EXAMINEE)
KEY_TABLE = ("00_EXAMINEE", "기본 정보")
KEY_VARS = [("ID", "아이디", "아이디"), ("FAMILY_ID", "가족 아이디", "아이디"), ("PNTTM", "시점", "연속형")]

# CODA '과제정보' 시트 항목 (행 번호, 항목명, 출처 key)
INFO_ROWS = [
    (4, "과제명", "title", "auto"), (5, "과제 번호", "pid", "auto"),
    (6, "과제 수행기관(데이터 기탁기관)", "org", "auto"), (7, "과제 책임자", "pi", "auto"),
    (8, "과제 수행기간", "period", "auto"), (9, "과제 목표", "goal", "auto"),
    (10, "과제 주요내용", "content", "auto"), (11, "연구 질환명", "disease", "auto"),
    (12, "임상변수 리스트", "var_list", "user"), (13, "임상변수 개수", "var_count", "calc"),
    (14, "대상자수(샘플수)", "n_subjects", "user"), (15, "데이터 기탁 담당자/연락처", "mgr", "user"),
    (16, "데이터 기탁일", "date", "user"), (17, "데이터 설명(특이사항)", "desc", "user"),
    (18, "CODA 데이터 기탁 신청자/아이디/연락처(기탁담당자와 다른 경우)", "coda", "user"),
]
N_AUTO = sum(1 for r in INFO_ROWS if r[3] == "auto")

# ══════════════════════════════════════════════════════════════
# 2. 데이터
# ══════════════════════════════════════════════════════════════
ECRF_COLS = ["eCRF", "항목명", "변수명", "항목 유형", "데이터 유형", "길이", "단위", "코드리스트"]


@st.cache_data
def load_ecrf_xlsx(path):
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r or not any(v not in (None, "") for v in r[:8]):
            continue
        rows.append({c: ("" if v is None else str(v).strip()) for c, v in zip(ECRF_COLS, r[:8])})
    return rows


MOCK_ECRF = [dict(zip(ECRF_COLS, r)) for r in [
    ("DM", "성별", "SEX", "Radio Button", "Integer", "", "", "1=남성|2=여성"),
    ("DM", "연령", "AGE", "TextBox", "Integer", "3", "세", ""),
    ("DM", "생년월일", "BRTHDT", "Date", "Date", "", "", ""),
    ("VS", "수축기 혈압", "SBP", "TextBox", "Integer", "3", "mmHg", ""),
    ("VS", "이완기 혈압", "DBP", "TextBox", "Integer", "3", "mmHg", ""),
    ("VS", "신장", "HEIGHT", "TextBox", "Float", "3.1", "cm", ""),
    ("LB", "공복혈당", "GLU", "TextBox", "Float", "4.1", "mg/dL", ""),
    ("LB", "흡연 여부", "SMOKE", "Radio Button", "Integer", "", "", "1=Current|2=Former|3=Never"),
]]

PROJECTS = {
    "C170005": dict(org="홍길동대학교 병원", pi="김연구 교수", title="신장 이식 환자 임상정보 기반 바이오헬스 데이터 구축",
                    period="2024-03-01 ~ 2026-12-31", goal="신장 이식 환자의 기본·검사·병력 정보를 표준화하여 CODA 기탁",
                    content="iCReaT eCRF로 수집한 기본정보, 검사 결과, 음주·과거 병력, 이상반응 데이터 정제 및 코드북 작성",
                    disease="만성 신장질환(신장 이식)", ecrf="file"),
    "PRJ-2026-0912": dict(org="건국대학교 산학협력단", pi="이공학 박사", title="웨어러블 센서 기반 생활습관 데이터 표준화",
                          period="2025-01-01 ~ 2026-12-31", goal="웨어러블 PGHD 데이터 표준화 및 CODA 기탁",
                          content="생활습관·활력징후 데이터 수집 및 정제", disease="대사증후군", ecrf="mock"),
    "PRJ-2026-0957": dict(org="삼성서울병원", pi="박의학 교수", title="희귀질환 다기관 임상 코호트 데이터 구축",
                          period="2025-06-01 ~ 2027-05-31", goal="희귀질환 환자 1,200명 임상 데이터 정제 및 기탁",
                          content="다기관 희귀질환 코호트 임상정보 표준화", disease="희귀 신경근육질환", ecrf="mock"),
}


def get_ecrf(pid):
    if PROJECTS[pid]["ecrf"] == "file" and ECRF_FILE.exists():
        return load_ecrf_xlsx(str(ECRF_FILE))
    return MOCK_ECRF


def default_form(pid):
    ecrf = get_ecrf(pid)
    if pid == "C170005":  # AE·그리드 반복은 미입력으로 두어 '검토 필요' 예시
        vars_ = {i: not (r["변수명"].startswith(("BIRTHD", "CRCRA")) or r["항목명"] == "생년월일")
                 for i, r in enumerate(ecrf) if r["eCRF"] not in ("AE", "그리드 반복")}
        return dict(vars=vars_, n_subjects=320, mgr="김연구", mgr_tel="02-1234-5678", date=dt.date(2026, 11, 30),
                    desc="신장 이식 후 1년 추적 자료 포함. 결측은 99999로 코딩.", same=True,
                    coda_name="", coda_id="kimresearch01", coda_tel="")
    return dict(vars={i: True for i in range(len(ecrf) - 2)}, n_subjects=800, mgr="", mgr_tel="",
                date=dt.date(2026, 12, 15), desc="", same=False, coda_name="", coda_id="", coda_tel="")


ss = st.session_state
ss.setdefault("page", "dashboard")
ss.setdefault("forms", {})
ss.setdefault("saved", {})
ss.setdefault("ever", {})
ss.setdefault("dels", {})


# ══════════════════════════════════════════════════════════════
# 3. eCRF → CODA 변환 (매핑 + 큐레이션)
# ══════════════════════════════════════════════════════════════
def build_coda(ecrf, public_map):
    dup = {k for k, v in Counter(r["변수명"] for r in ecrf if r["변수명"]).items() if v > 1}
    rows = [{"No.": 0, "공개여부": "공개", "테이블명(영문)": KEY_TABLE[0], "테이블명(국문)": KEY_TABLE[1],
             "변수명(영문)": k, "변수 설명": d, "변수값(코드) 설명": "", "변수 타입": t,
             "_src": "큐레이션", "_status": "key", "_issues": []} for k, d, t in KEY_VARS]
    for no, (i, r) in enumerate(enumerate(ecrf), 1):
        issues = []
        if not r["변수명"]:
            issues.append("변수명 누락")
        elif r["변수명"] in dup:
            issues.append("변수명 중복")
        pub = public_map.get(i)
        if pub is None:
            issues.append("공개여부 미입력")
        typ = coda_type(r["데이터 유형"], r["코드리스트"])
        if typ == "검토 필요":
            issues.append("타입 미정")
        codes = coda_codes(r["코드리스트"])
        status = "rev" if issues else ("cln" if codes else "map")
        rows.append({"No.": no, "공개여부": "" if pub is None else ("공개" if pub else "비공개"),
                     "테이블명(영문)": r["eCRF"], "테이블명(국문)": ECRF_KO.get(r["eCRF"], ""),
                     "변수명(영문)": r["변수명"], "변수 설명": r["항목명"], "변수값(코드) 설명": codes, "변수 타입": typ,
                     "_src": f'{r["eCRF"]}.{r["변수명"] or "?"}', "_status": status, "_issues": issues})
    return rows


def dist(rows):
    v = [r for r in rows if r["_status"] != "key"]
    n = max(len(v), 1)
    c = Counter(r["_status"] for r in v)
    pct = {k: round(c[k] * 100 / n) for k in ("map", "cln", "rev")}
    return pct, round((c["map"] + c["cln"]) * 100 / n), c


CODA_COLS = ["No.", "공개여부", "테이블명(영문)", "테이블명(국문)", "변수명(영문)", "변수 설명", "변수값(코드) 설명", "변수 타입"]
CODA_SRC = {"No.": "큐레이션", "공개여부": "← 연구자 입력", "테이블명(영문)": "← eCRF명", "테이블명(국문)": "← eCRF명",
            "변수명(영문)": "← 변수명", "변수 설명": "← 항목명", "변수값(코드) 설명": "← 코드리스트", "변수 타입": "← 데이터 유형"}


# ══════════════════════════════════════════════════════════════
# 4. 아이콘 / 공통
# ══════════════════════════════════════════════════════════════
def icon(name, size=20, color="currentColor", sw=1.8):
    p = {
        "db": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5"/><path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3"/>',
        "server": '<rect x="3" y="3" width="18" height="8" rx="2"/><rect x="3" y="13" width="18" height="8" rx="2"/><path d="M7 7h.01M7 17h.01"/>',
        "layers": '<path d="m12 2 9 5-9 5-9-5 9-5z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
        "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
        "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
        "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
        "alert": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
        "pie": '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
        "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>',
        "lock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
        "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
        "table": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18"/>',
        "send": '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/>',
        "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
        "clip": '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
    }[name]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" '
            f'style="flex-shrink:0;vertical-align:middle">{p}</svg>')


def md(s):
    st.markdown(s, unsafe_allow_html=True)


md("<style>" + (BASE / "style.css").read_text(encoding="utf-8") + "</style>")

# ══════════════════════════════════════════════════════════════
# 5. 헤더
# ══════════════════════════════════════════════════════════════
with st.container(key="topbar"):
    h1, h2 = st.columns([1.35, 1], vertical_alignment="center")
    with h1:
        md(f'<div class="brand"><div class="brand-ic">{icon("db", 28, "#1c2a24", 2)}</div><div class="brand-t">'
           f'<div class="t1">iCReaT 연구데이터 정제 및 기탁 대시보드</div>'
           f'<div class="t2">Clinical &amp; Bio-Data Curation &amp; Mapping Support System</div></div></div>')
    with h2:
        with st.container(key="projbox"):
            p1, p2 = st.columns([0.32, 1], vertical_alignment="center")
            with p1:
                md(f'<div class="projlbl">{icon("server", 20, "#c9ced8")} 선택 과제:</div>')
            with p2:
                pid = st.selectbox("과제", list(PROJECTS), label_visibility="collapsed", key="pid",
                                   format_func=lambda k: f"[{k}] {PROJECTS[k]['org']} - {PROJECTS[k]['pi']}")

proj = PROJECTS[pid]
ECRF = get_ecrf(pid)
if pid not in ss.forms:
    ss.forms[pid] = default_form(pid)
form = ss.forms[pid]
CODA = build_coda(ECRF, form["vars"])
PCT, DONE, CNT = dist(CODA)


# ══════════════════════════════════════════════════════════════
# 6. 좌측 패널
# ══════════════════════════════════════════════════════════════
def donut_svg(segs, center, sub="평균 완성도"):
    r, c, off, arcs = 70, 2 * 3.14159 * 70, 0, ""
    for pct, col in segs:
        ln = c * pct / 100
        arcs += (f'<circle cx="90" cy="90" r="{r}" fill="none" stroke="{col}" stroke-width="18" '
                 f'stroke-dasharray="{ln:.1f} {c - ln:.1f}" stroke-dashoffset="{-off:.1f}" transform="rotate(150 90 90)"/>')
        off += ln
    return (f'<svg width="180" height="180" viewBox="0 0 180 180"><circle cx="90" cy="90" r="{r}" fill="none" '
            f'stroke="#eef0f3" stroke-width="18"/>{arcs}<text x="90" y="92" text-anchor="middle" font-size="27" '
            f'font-weight="700" fill="#1e2433">{center}</text><text x="90" y="116" text-anchor="middle" '
            f'font-size="12" fill="#9aa1ad">{sub}</text></svg>')


def left_panel():
    with st.container(key="menucard"):
        md('<div class="menu-title">메뉴 관리</div>')
        for key, label in [("dashboard", "대시보드 현황"), ("form", "과제 및 데이터 입력 폼"), ("codebook", "코드북 매핑 & 정제")]:
            with st.container(key=f"nav_{key}"):
                if st.button(label, key=f"btn_{key}", type="primary" if ss.page == key else "secondary",
                             use_container_width=True):
                    ss.page = key
                    st.rerun()
    items = [("매핑 완료", PCT["map"], "#7fb4a1"), ("정제 완료", PCT["cln"], "#e5c25a"), ("검토 필요 항목", PCT["rev"], "#d6dae1")]
    legend = "".join(f'<div class="legend-row"><span><i style="background:{c}"></i>{n}</span><b>{v}%</b></div>'
                     for n, v, c in items)
    md(f'<div class="card dist"><div class="dist-head"><b>{icon("pie", 19, "#4b5563")} 변환/정제 항목 분포</b>'
       f'<span class="badge-live">실시간</span></div><div class="donut">'
       f'{donut_svg([(PCT["map"], "#7fb4a1"), (PCT["cln"], "#e5c25a"), (PCT["rev"], "#eef0f3")], f"{DONE}%")}</div>{legend}</div>')


# ══════════════════════════════════════════════════════════════
# 7. 공통 렌더러
# ══════════════════════════════════════════════════════════════
def var_counts():
    v = form["vars"]
    pub = sum(1 for x in v.values() if x)
    return len(v), pub, len(v) - pub


STATUS_BADGE = {"map": ("map", "매핑 완료"), "cln": ("cln", "정제 완료"), "rev": ("rev", "검토 필요"), "key": ("key", "큐레이션")}


def coda_table_html(rows, with_status=True):
    head = "".join(
        f'<th>{c}<small class="{"c" if CODA_SRC[c] in ("큐레이션", "← 연구자 입력") else ""}">{CODA_SRC[c]}</small></th>'
        for c in CODA_COLS)
    if with_status:
        head += '<th>정제 상태<small>자동 점검</small></th><th>원본<small>iCReaT eCRF</small></th>'
    body = ""
    for r in rows:
        pub = r["공개여부"]
        pb = {"공개": "pub", "비공개": "pri", "": "none"}[pub]
        pub_html = f'<span class="pb {pb}">{pub or "미입력"}</span>'
        codes = E(r["변수값(코드) 설명"]).replace("\n", "<br>") or "-"
        body += (f'<tr class="{"key" if r["_status"] == "key" else "var"}"><td class="no">{r["No."]}</td><td>{pub_html}</td>'
                 f'<td class="mono">{E(r["테이블명(영문)"])}</td><td>{E(r["테이블명(국문)"]) or "-"}</td>'
                 f'<td class="v">{E(r["변수명(영문)"]) or "<span class=pb style=background:#fde8ea;color:#c0392b>누락</span>"}</td>'
                 f'<td class="item">{E(r["변수 설명"])}</td><td class="wrap">{codes}</td><td>{E(r["변수 타입"])}</td>')
        if with_status:
            cls, txt = STATUS_BADGE[r["_status"]]
            iss = "".join(f'<span class="issue">· {E(x)}</span>' for x in r["_issues"])
            src = '<span class="pb cur">큐레이션</span>' if r["_status"] == "key" else E(r["_src"])
            body += f'<td><span class="ps {cls}">{txt}</span>{iss}</td><td class="src">{src}</td>'
        body += "</tr>"
    return f'<div class="tbl-wrap"><table class="pv"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def ecrf_table_html(rows):
    head = "".join(f"<th>{c}</th>" for c in ECRF_COLS)
    body = "".join(
        f'<tr><td class="mono">{E(r["eCRF"])}</td><td class="item">{E(r["항목명"])}</td><td class="v">{E(r["변수명"]) or "-"}</td>'
        f'<td>{E(r["항목 유형"])}</td><td class="mono">{E(r["데이터 유형"])}</td><td class="no">{E(r["길이"]) or "-"}</td>'
        f'<td>{E(r["단위"]) or "-"}</td><td class="wrap">{E(r["코드리스트"]).replace("|", "<br>") or "-"}</td></tr>'
        for r in rows)
    return f'<div class="tbl-wrap"><table class="pv"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def ecrf_names():
    return list(dict.fromkeys(r["eCRF"] for r in ECRF))


def filter_by_ecrf(sel):
    if sel.startswith("전체"):
        return CODA, ECRF
    return ([r for r in CODA if r["_status"] == "key" or r["테이블명(영문)"] == sel], [r for r in ECRF if r["eCRF"] == sel])


# ══════════════════════════════════════════════════════════════
# 8. 대시보드
# ══════════════════════════════════════════════════════════════
def page_dashboard():
    md(f"""<div class="guide"><div style="padding-top:2px">{icon('info', 26, '#4f6bdc')}</div><div>
      <h3>iCReaT 자동 연동 &amp; 연구자 직접 제출 안내</h3>
      <div class="g-row"><span class="g-badge auto">iCReaT 제공</span><div><strong>자동 연동 가능한 기본 속성 불러오기</strong>,
        <strong>코드북 항목 매핑</strong>, <strong>데이터 입력 폼 작성 항목</strong>까지는 자동으로 CODA 형식에 매핑됩니다.</div></div>
      <div class="g-row"><span class="g-badge self">직접 제출</span><div>제출을 위한 <strong>동의서</strong>는
        기탁 사이트(CODA)의 양식을 통해 연구자가 직접 제출해야 합니다.</div></div></div></div>""")

    n_var, n_pub, n_pri = var_counts()
    n_unset = len(ECRF) - n_var
    kpis = [
        ("총 기탁 과제 수", "db", "#7fb4a1", f"{len(PROJECTS)}건",
         f'{icon("check", 17, "#4e8f78")}<span style="color:#4e8f78">iCReaT DB 동기화 완료</span>'),
        ("iCReaT 자동 연동 항목", "server", "#4f6bdc", f"{N_AUTO} / {len(INFO_ROWS)}",
         f'<span style="color:#4f6bdc">과제정보 자동 연동 비율 {round(N_AUTO * 100 / len(INFO_ROWS))}%</span>'),
        ("eCRF 변수 (정제 대상)", "layers", "#c98a1e", f"{len(ECRF)}개",
         f'<span style="color:#c98a1e">eCRF {len(ecrf_names())}종 • 검토 필요 {CNT["rev"]}건</span>'),
        ("임상 변수 리스트", "list", "#7a68e6", f"{n_var}개 변수",
         f'<span style="color:#6b7280">공개 {n_pub} • 비공개 {n_pri} • 미입력 {n_unset}</span>'),
    ]
    md('<div class="kpis">' + "".join(
        f'<div class="card kpi"><div class="kpi-top">{t}{icon(ic, 22, c)}</div><div class="kpi-val">{v}</div>'
        f'<div class="kpi-sub">{s}</div></div>' for t, ic, c, v, s in kpis) + "</div>")

    with st.container(key="preview"):
        with st.container(key="prevtop"):
            a, b = st.columns([3, 1.1], vertical_alignment="center")
            with a:
                md(f'<div class="pv-title">{icon("table", 22, "#4e8f78")} iCReaT eCRF → CODA 코드북 매핑 미리보기</div>'
                   f'<div class="pv-sub">[{E(pid)}] eCRF 코드북을 정제하여 CODA 기탁 코드북(임상정보) 형식으로 변환한 결과입니다.</div>')
            with b:
                with st.container(key="pvfilter"):
                    sel = st.selectbox("eCRF", [f"전체 eCRF ({len(ecrf_names())}종)"] + ecrf_names(),
                                       label_visibility="collapsed", key=f"pv_sel_{pid}")
        chips = [("eCRF명", "테이블명(영문·국문)"), ("변수명", "변수명(영문)"), ("항목명", "변수 설명"),
                 ("데이터 유형", "변수 타입"), ("코드리스트", "변수값(코드) 설명")]
        ar = icon("arrow", 13, "#9aa1ad", 2)
        md('<div class="rules">' + "".join(f'<span class="rchip"><b>{s}</b>{ar}{t}</span>' for s, t in chips)
           + '<span class="rchip cur"><b>큐레이션</b> No. (ID·FAMILY_ID·PNTTM=0, 이후 1부터)</span>'
             '<span class="rchip cur"><b>연구자 입력</b> 공개여부</span></div>')
        coda_v, ecrf_v = filter_by_ecrf(sel)
        t1, t2 = st.tabs([f"CODA 코드북 미리보기 ({len(coda_v)})", f"iCReaT eCRF 원본 ({len(ecrf_v)})"])
        with t1:
            md(coda_table_html(coda_v))
        with t2:
            md(ecrf_table_html(ecrf_v))


# ══════════════════════════════════════════════════════════════
# 9. 과제 및 데이터 입력 폼
# ══════════════════════════════════════════════════════════════
def ro_field(label, value, full=False, mono=False):
    return (f'<div class="{"full" if full else ""}"><div class="ro-lbl">{label}</div>'
            f'<div class="ro-val{" mono" if mono else ""}"><span>{E(value)}</span>{icon("lock", 16, "#9aa1ad")}</div></div>')


def bump(p):
    ss.ever[p] = ss.ever.get(p, 0) + 1


def cb_add(p, ms_key, pub_key):
    for uid in ss.get(ms_key, []):
        ss.forms[p]["vars"][uid] = ss.get(pub_key, "공개") == "공개"
    ss[ms_key] = []
    bump(p)


def cb_add_ecrf(p, uids, pub_key):
    for uid in uids:
        ss.forms[p]["vars"][uid] = ss.get(pub_key, "공개") == "공개"
    bump(p)


def cb_edit(p, ed_key, uids):
    st_ = ss.get(ed_key, {})
    dels = ss.dels.setdefault(p, set())
    for i, ch in st_.get("edited_rows", {}).items():
        uid = uids[int(i)]
        if "공개여부" in ch:
            ss.forms[p]["vars"][uid] = ch["공개여부"] == "공개"
        if "선택" in ch:
            (dels.add if ch["선택"] else dels.discard)(uid)
    bump(p)


def cb_bulk(p, mode):
    v, dels = ss.forms[p]["vars"], ss.dels.setdefault(p, set())
    if mode == "del":
        for uid in list(dels):
            v.pop(uid, None)
        dels.clear()
    else:
        for uid in v:
            v[uid] = mode == "pub"
    bump(p)


def page_form():
    with st.container(key="formcard"):
        a, b = st.columns([3, 1], vertical_alignment="center")
        with a:
            md(f'<div class="pg-head">{icon("file", 26, "#4b5563")}<div><div class="h">연구 과제 메타데이터 &amp; 데이터 입력 폼</div>'
               f'<div class="s">CODA 기탁 \'과제정보\' 항목 중 iCReaT 자동 연동 항목과 연구자 입력 항목을 한 곳에서 관리합니다.</div></div></div>')
        with b:
            with st.container(key="savebtn"):
                if st.button(":material/save: 설정 및 폼 양식 저장", key="save"):
                    ss.saved[pid] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
                    st.toast("연구자 입력 폼이 저장되었습니다.", icon="✅")
                if pid in ss.saved:
                    md(f'<div class="saved">마지막 저장: {ss.saved[pid]}</div>')
        md('<div class="hr"></div>')

        # ── 자동 연동 (수정 불가) ──
        md(f'<div class="sect auto">{icon("server", 19, "#4f6bdc")} [자동 연동] iCReaT 시스템 보유 기본 데이터'
           f'<span class="note">{icon("lock", 14, "#6b7280")} iCReaT 사이트에서 자동 수집 · 수정 불가</span></div>')
        md('<div class="ro-grid">' + ro_field("과제 번호", pid, mono=True) + ro_field("과제 수행기관(데이터 기탁기관)", proj["org"])
           + ro_field("과제명", proj["title"]) + ro_field("과제 책임자", proj["pi"])
           + ro_field("과제 수행기간", proj["period"]) + ro_field("연구 질환명", proj["disease"])
           + ro_field("과제 목표", proj["goal"], full=True) + ro_field("과제 주요내용", proj["content"], full=True) + '</div>')
        md('<div class="hr" style="margin:14px 0 6px"></div>')

        # ── 연구자 입력 ──
        md(f'<div class="sect user">{icon("check", 19, "#4e8f78")} [연구자 입력 폼] 없는 데이터 채우기 · 기탁 정보 입력</div>')
        md(f'<div class="subh">{icon("send", 18, "#4b5563")} 데이터 기탁 정보</div>')
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            form["n_subjects"] = st.number_input("대상자 수 (샘플 수)", min_value=0, step=1,
                                                 value=int(form["n_subjects"]), key=f"w_n_{pid}")
        with c2:
            form["date"] = st.date_input("데이터 기탁일", value=form["date"], key=f"w_date_{pid}", format="YYYY-MM-DD")
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            form["mgr"] = st.text_input("데이터 기탁 담당자", value=form["mgr"], key=f"w_mgr_{pid}", placeholder="성명")
        with c2:
            form["mgr_tel"] = st.text_input("기탁 담당자 연락처", value=form["mgr_tel"], key=f"w_mtel_{pid}",
                                            placeholder="010-0000-0000 / 이메일")
        form["desc"] = st.text_area("데이터 설명 (특이사항)", value=form["desc"], key=f"w_desc_{pid}", height=80,
                                    placeholder="결측 코딩 방식, 추적 기간, 데이터 수집 시 특이사항 등")

        md(f'<div class="subh">{icon("user", 18, "#4b5563")} CODA 데이터 기탁 신청자 <small>기탁 담당자와 다른 경우 입력</small></div>')
        with st.container(key="coda"):
            form["same"] = st.checkbox("데이터 기탁 담당자와 동일", value=form["same"], key=f"w_same_{pid}")
            c1, c2, c3 = st.columns(3, gap="medium")
            if form["same"]:
                with c1:
                    st.text_input("신청자 성명", value=form["mgr"], disabled=True, key=f"w_cn_same_{pid}")
                with c3:
                    st.text_input("신청자 연락처", value=form["mgr_tel"], disabled=True, key=f"w_ct_same_{pid}")
            else:
                with c1:
                    form["coda_name"] = st.text_input("신청자 성명", value=form["coda_name"], key=f"w_cn_{pid}")
                with c3:
                    form["coda_tel"] = st.text_input("신청자 연락처", value=form["coda_tel"], key=f"w_ct_{pid}")
            with c2:
                form["coda_id"] = st.text_input("CODA 아이디", value=form["coda_id"], key=f"w_cid_{pid}")

        # ── 임상 변수 리스트 ──
        md(f'<div class="subh">{icon("list", 18, "#4b5563")} 임상 변수 리스트 및 공개 여부 '
           f'<small>추가한 변수의 공개 여부가 CODA 코드북 \'공개여부\'에 반영됩니다</small></div>')
        ver = ss.ever.get(pid, 0)
        with st.container(key="varadd"):
            c1, c2, c3, c4, c5 = st.columns([1.3, 2.6, 1.2, 0.75, 1.25], vertical_alignment="bottom")
            with c1:
                ef = st.selectbox("eCRF", ecrf_names(), key=f"w_ef_{pid}")
            rem = [i for i, r in enumerate(ECRF) if r["eCRF"] == ef and i not in form["vars"]]
            ms_key, pub_key = f"w_ms_{pid}", f"w_pubnew_{pid}"
            with c2:
                st.multiselect("추가할 변수", rem, key=ms_key, placeholder=f"{len(rem)}개 선택 가능",
                               format_func=lambda i: f'{ECRF[i]["변수명"] or "(변수명 없음)"} · {ECRF[i]["항목명"]}')
            with c3:
                st.radio("공개 여부", ["공개", "비공개"], horizontal=True, key=pub_key)
            with c4:
                with st.container(key="addbtn"):
                    st.button(":material/add: 추가", use_container_width=True, on_click=cb_add,
                              args=(pid, ms_key, pub_key))
            with c5:
                st.button(f":material/playlist_add: {ef[:10]} 전체", use_container_width=True, disabled=not rem,
                          on_click=cb_add_ecrf, args=(pid, rem, pub_key), help=f"{ef}의 미추가 변수 {len(rem)}개를 모두 추가")

        n_var, n_pub, n_pri = var_counts()
        md(f'<div class="cnt">임상 변수 개수 <span class="n">{n_var}개</span> = 공개 <b>{n_pub}</b> + 비공개 <b>{n_pri}</b>'
           f'<span class="f">= SUM(추가된 변수)</span><span style="margin-left:auto">미추가 eCRF 변수 '
           f'<b>{len(ECRF) - n_var}</b>개 → CODA 코드북에서 \'검토 필요\'</span></div>')

        uids = list(form["vars"].keys())
        dels = ss.dels.setdefault(pid, set())
        df = pd.DataFrame([{"선택": u in dels, "No.": n, "eCRF": ECRF[u]["eCRF"], "변수명": ECRF[u]["변수명"] or "(없음)",
                            "항목명": ECRF[u]["항목명"], "공개여부": "공개" if form["vars"][u] else "비공개"}
                           for n, u in enumerate(uids, 1)],
                          columns=["선택", "No.", "eCRF", "변수명", "항목명", "공개여부"])
        ed_key = f"w_ed_{pid}_{ver}"
        with st.container(key="vared"):
            st.data_editor(df, key=ed_key, hide_index=True, use_container_width=True, num_rows="fixed",
                           height=min(38 + 35 * max(len(df), 1), 420), on_change=cb_edit, args=(pid, ed_key, uids),
                           disabled=["No.", "eCRF", "변수명", "항목명"],
                           column_config={"선택": st.column_config.CheckboxColumn("선택", width="small"),
                                          "No.": st.column_config.NumberColumn("No.", width="small"),
                                          "공개여부": st.column_config.SelectboxColumn("공개여부", options=["공개", "비공개"],
                                                                                   required=True, width="small")})
        with st.container(key="varbulk"):
            c1, c2, c3, _ = st.columns([1.1, 1, 1, 2.5])
            with c1:
                with st.container(key="delbtn"):
                    st.button(f":material/delete: 선택 삭제 ({len(dels)})", use_container_width=True, disabled=not dels,
                              on_click=cb_bulk, args=(pid, "del"))
            with c2:
                st.button("전체 공개", use_container_width=True, on_click=cb_bulk, args=(pid, "pub"))
            with c3:
                st.button("전체 비공개", use_container_width=True, on_click=cb_bulk, args=(pid, "pri"))


# ══════════════════════════════════════════════════════════════
# 10. 코드북 매핑 & 정제 = 과제정보 + 코드북 통합 결과
# ══════════════════════════════════════════════════════════════
def info_values():
    """CODA '과제정보' 시트 값 (화면용 html, 엑셀용 text, 출처, 입력 여부)"""
    n_var, n_pub, n_pri = var_counts()
    names = [ECRF[u]["변수명"] or f'({ECRF[u]["항목명"]})' for u in form["vars"]]
    coda_txt = ("기탁 담당자와 동일" + (f" / {form['coda_id']}" if form["coda_id"] else "")) if form["same"] else \
        " / ".join(x for x in (form["coda_name"], form["coda_id"], form["coda_tel"]) if x)
    mgr_txt = " / ".join(x for x in (form["mgr"], form["mgr_tel"]) if x)
    text = {**{k: proj.get(k, "") for k in ("title", "org", "pi", "period", "goal", "content", "disease")},
            "pid": pid, "var_list": ", ".join(names), "var_count": f"{n_var}개 (공개 {n_pub}, 비공개 {n_pri})" if n_var else "",
            "n_subjects": f"{form['n_subjects']:,}명" if form["n_subjects"] else "", "mgr": mgr_txt,
            "date": form["date"].strftime("%Y-%m-%d") if form["date"] else "", "desc": form["desc"],
            "coda": coda_txt if (form["same"] and form["coda_id"]) or not form["same"] else ""}
    chips = "".join(f'<span class="{"" if form["vars"][u] else "pri"}">{E(ECRF[u]["변수명"] or "(없음)")}</span>'
                    for u in list(form["vars"])[:60])
    more = f'<span class="muted">… 외 {n_var - 60}개</span>' if n_var > 60 else ""
    html_ = dict(text)
    html_["var_list"] = (f'<div class="vchips">{chips}{more}</div><div class="muted" style="margin-top:4px">'
                         f'취소선 = 비공개 변수 · Excel에는 전체 목록 입력</div>') if n_var else ""
    return text, html_


def build_xlsx(text):
    """CODA 기탁_임상정보 코드북 양식에 과제정보 + 코드북을 채워 bytes 반환"""
    if TEMPLATE_FILE.exists():
        wb = openpyxl.load_workbook(TEMPLATE_FILE)
    else:
        wb = openpyxl.Workbook()
        wb.active.title = "과제정보"
        wb.create_sheet("CODA 기탁 데이터 코드북 양식_임상정보")
    ws = wb["과제정보"]
    for row, label, key, _ in INFO_ROWS:
        ws.cell(row, 1).value = ws.cell(row, 1).value or label
        c = ws.cell(row, 2)
        c.value = text[key]
        c.alignment = Alignment(wrap_text=True, vertical="center")
        if ws.cell(row, 11).value == 0:  # 양식에 남아 있던 0 값 정리
            ws.cell(row, 11).value = None
    wc = wb["CODA 기탁 데이터 코드북 양식_임상정보"]
    for r in range(4, max(wc.max_row, 4) + 1):
        for col in range(1, 11):
            wc.cell(r, col).value = None
    for n, rr in enumerate(CODA):
        vals = [rr["No."], rr["공개여부"], rr["테이블명(영문)"], rr["테이블명(국문)"], rr["변수명(영문)"], rr["변수 설명"],
                rr["변수값(코드) 설명"], rr["변수 타입"], None, ", ".join(rr["_issues"]) or None]
        for col, v in enumerate(vals, 1):
            c = wc.cell(4 + n, col)
            c.value = v
            c.alignment = Alignment(wrap_text=True, vertical="center")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


SRC_BADGE = {"auto": ('auto', "iCReaT 자동"), "user": ("user", "연구자 입력"), "calc": ("calc", "자동 계산")}


def page_codebook():
    text, html_ = info_values()
    filled = sum(1 for _, _, k, _ in INFO_ROWS if text[k] or k == "desc")
    with st.container(key="resultcard"):
        with st.container(key="restop"):
            a, b = st.columns([3, 1.15], vertical_alignment="center")
            with a:
                md(f'<div class="pg-head">{icon("layers", 28, "#4e8f78")}<div><div class="h">CODA 기탁 결과 — 과제정보 &amp; 코드북 매핑</div>'
                   f'<div class="s">과제 및 데이터 입력 폼의 입력값과 eCRF → CODA 코드북 매핑 결과를 CODA 기탁 양식 그대로 한 화면에 보여줍니다.</div></div></div>')
            with b:
                with st.container(key="xlsxbtn"):
                    st.download_button(":material/download: CODA 기탁 양식 Excel", build_xlsx(text),
                                       file_name=f"{pid}_기탁_임상정보_코드북_{dt.date.today():%Y%m%d}.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                       use_container_width=True)
        md('<div class="hr"></div>')

        # ① 과제정보
        pct = round(filled * 100 / len(INFO_ROWS))
        md(f'<div class="res-sect"><span style="display:flex;align-items:center;gap:8px">{icon("clip", 20, "#4b5563")} ① CODA 데이터 기탁 과제 정보 '
           f'<small>엑셀 \'과제정보\' 시트</small></span><span class="prog">입력 {filled}/{len(INFO_ROWS)}'
           f'<span class="bar"><i style="width:{pct}%"></i></span></span></div>')
        trs = ""
        for _, label, key, src in INFO_ROWS:
            v = html_[key] if key == "var_list" else E(str(html_[key]))
            if not text[key]:
                v = '<span class="miss">미입력</span>' if key != "desc" else '<span class="muted">(선택 항목)</span>'
            cls, t = SRC_BADGE[src]
            trs += f'<tr><th>{E(label)}</th><td class="val">{v}</td><td class="src"><span class="sb {cls}">{t}</span></td></tr>'
        md(f'<div class="tbl-wrap" style="max-height:none"><table class="info"><tbody>{trs}</tbody></table></div>')

        # ② 코드북
        md(f'<div class="res-sect" style="margin-top:16px"><span style="display:flex;align-items:center;gap:8px">{icon("table", 20, "#4b5563")} '
           f'② CODA 기탁 데이터 코드북 (임상정보) <small>엑셀 코드북 시트 · 검토 사항은 비고 열 기재</small></span>'
           f'<span class="prog">매핑 완료 {CNT["map"]} · 정제 완료 {CNT["cln"]} · 검토 필요 {CNT["rev"]}</span></div>')
        c1, c2, _ = st.columns([1.2, 1.3, 2.5], vertical_alignment="center")
        with c1:
            sel = st.selectbox("eCRF", [f"전체 eCRF ({len(ecrf_names())}종)"] + ecrf_names(),
                               label_visibility="collapsed", key=f"res_sel_{pid}")
        with c2:
            only = st.radio("보기", ["전체", "검토 필요만"], horizontal=True, label_visibility="collapsed", key=f"res_only_{pid}")
        rows, _ = filter_by_ecrf(sel)
        if only == "검토 필요만":
            rows = [r for r in rows if r["_status"] == "rev"]
        md(coda_table_html(rows))


# ══════════════════════════════════════════════════════════════
# 11. 본문
# ══════════════════════════════════════════════════════════════
with st.container(key="body"):
    left, main = st.columns([1, 3.1])
    with left:
        left_panel()
    with main:
        {"dashboard": page_dashboard, "form": page_form, "codebook": page_codebook}[ss.page]()
