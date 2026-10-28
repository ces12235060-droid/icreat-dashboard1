"""iCReaT 연구데이터 정제 및 기탁 대시보드 (Streamlit)

※ eCRF / CODA 코드북은 내부망 반출 불가로 목업 데이터 사용.
  실제 데이터 적용 시 ECRF_ROWS, ECRF_TABLE_MAP, DTYPE_MAP 만 교체하면 됨.
"""
import csv
import datetime as dt
import html
import io

import streamlit as st

st.set_page_config(page_title="iCReaT 연구데이터 정제 및 기탁 대시보드", page_icon="🗄️", layout="wide",
                   initial_sidebar_state="collapsed")
E = html.escape

# ══════════════════════════════════════════════════════════════
# 1. 목업 데이터
# ══════════════════════════════════════════════════════════════
PROJECTS = {
    "PRJ-2026-0891": dict(org="홍길동대학교 병원", pi="김연구 교수",
                          title="만성 질환 유전체 기반 바이오헬스 임상데이터 통합 구축",
                          goal="만성 질환자 5,000명의 유전체 및 임상 역학 데이터 표준화 및 저장"),
    "PRJ-2026-0912": dict(org="건국대학교 산학협력단", pi="이공학 박사",
                          title="웨어러블 센서 기반 생활습관 데이터 표준화",
                          goal="웨어러블 PGHD 데이터 표준화 및 CODA 기탁"),
    "PRJ-2026-0957": dict(org="삼성서울병원", pi="박의학 교수",
                          title="희귀질환 다기관 임상 코호트 데이터 구축",
                          goal="희귀질환 환자 1,200명 임상·영상 데이터 정제 및 기탁"),
}

# iCReaT 코드북: eCRF, 항목명, 변수명, 항목 유형, 데이터 유형, 길이, 단위, 코드리스트
ECRF_COLS = ["eCRF", "항목명", "변수명", "항목 유형", "데이터 유형", "길이", "단위", "코드리스트"]
ECRF_ROWS = [
    ("DM", "생년월", "BRTHYM", "Date picker", "Date", 7, "", ""),
    ("DM", "성별", "SEX", "Radio button", "Character", 1, "", "1=남성;2=여성"),
    ("DM", "연령", "AGE", "Text box", "Numeric", 3, "세", ""),
    ("DM", "교육수준", "EDU", "Dropdown", "Character", 1, "", "1=초졸 이하;2=중졸;3=고졸;4=대졸 이상"),
    ("VS", "측정일", "VSDT", "Date picker", "Date", 10, "", ""),
    ("VS", "신장", "HEIGHT", "Text box", "Numeric", 5, "cm", ""),
    ("VS", "체중", "WEIGHT", "Text box", "Numeric", 5, "kg", ""),
    ("VS", "수축기 혈압", "SBP", "Text box", "Numeric", 3, "mmHg", ""),
    ("VS", "이완기 혈압", "DBP", "Text box", "Numeric", 3, "mmHg", ""),
    ("LB", "공복혈당", "GLU", "Text box", "Numeric", 5, "mg/dL", ""),
    ("LB", "당화혈색소", "HBA1C", "Text box", "Numeric", 4, "%", ""),
    ("LB", "총콜레스테롤", "TCHOL", "Text box", "Numeric", 5, "mg/dL", ""),
    ("SU", "흡연 여부", "SMOKE", "Radio button", "Character", 1, "", "1=현재 흡연;2=과거 흡연;3=비흡연"),
    ("SU", "음주 빈도", "DRINK", "Dropdown", "Character", 1, "", "1=안 마심;2=월 1회 이하;3=주 1~2회;4=주 3회 이상"),
    ("SU", "비고", "SUCOMM", "Text area", "Character", 200, "", ""),
]
ECRF = [dict(zip(ECRF_COLS, r)) for r in ECRF_ROWS]
ECRF_BY_VAR = {r["변수명"]: r for r in ECRF}

# eCRF → CODA 테이블명(영문, 국문)
ECRF_TABLE_MAP = {
    "DM": ("DEMOGRAPHICS", "인구학적 정보"),
    "VS": ("VITAL_SIGNS", "활력징후"),
    "LB": ("LABORATORY", "임상검사"),
    "SU": ("SUBSTANCE_USE", "흡연·음주"),
}
# 데이터 유형 → CODA 변수 타입
DTYPE_MAP = {"Character": "String", "Numeric": "Number", "Date": "Date"}
# CODA 큐레이션 키 변수 (No. 0)
KEY_VARS = [("ID", "연구대상자 고유 ID", "String"),
            ("FAMILY_ID", "가족 ID", "String"),
            ("PNTTM", "측정 시점(차수)", "String")]
NO_RESET_PER_TABLE = True  # True: 테이블마다 No. 1부터 재시작 / False: 전체 연번

DEFAULT_RULES = [
    dict(id="CB-001", src="SUBJECT_ID (환자식별번호)", tgt="subject_anon_id", cat="항목 매핑",
         rtype="익명화 맵핑", detail="SHA-256 단방향 암호화 적용 후 12자리 영문숫자 변환", status="완료"),
    dict(id="CB-002", src="GENDER (성별)", tgt="gender_cd", cat="항목 매핑",
         rtype="코드 매핑", detail="1: 남성(M), 2: 여성(F), 9: 미상(U)", status="완료"),
    dict(id="CB-003", src="AGE_YEARS (연령)", tgt="age", cat="데이터 정제",
         rtype="이상치/범위 검증", detail="0 ~ 120 범위 이외 데이터 Null 처리 및 오기 기록 보고서 생성", status="완료"),
    dict(id="CB-004", src="SYSTOLIC_BP (수축기 혈압)", tgt="sys_bp", cat="데이터 정제",
         rtype="결측치 정제 규칙", detail="999 또는 -1 입력값은 결측(NaN)으로 정제", status="검토필요"),
    dict(id="CB-005", src="DIAGNOSIS_DATE (진단일자)", tgt="dx_date", cat="항목 매핑",
         rtype="포맷 변환", detail="YYYY-MM-DD ISO 표준 형식 포맷팅", status="완료"),
    dict(id="CB-006", src="SMOKING_STAT (흡연여부)", tgt="tobacco_use_status", cat="데이터 정제",
         rtype="오기 정제 규칙", detail="'유'->'Current', '무'->'Never', '과거'->'Former' 텍스트 정규화", status="진행중"),
]

# 연구자 입력 폼 기본값 (vars: 변수명 → True 공개 / False 비공개)
DEFAULT_FORMS = {
    "PRJ-2026-0891": dict(
        vars={v: v not in ("BRTHYM",) for v in
              ["BRTHYM", "SEX", "AGE", "EDU", "VSDT", "HEIGHT", "WEIGHT", "SBP", "DBP", "GLU", "TCHOL", "SMOKE"]},
        n_subjects=5000, mgr="김연구", mgr_tel="02-1234-5678", date=dt.date(2026, 11, 30),
        same=True, coda_name="", coda_id="kimresearch01", coda_tel=""),
    "PRJ-2026-0912": dict(vars={v: True for v in [r["변수명"] for r in ECRF]}, n_subjects=800,
                          mgr="이공학", mgr_tel="02-450-0000", date=dt.date(2026, 12, 15),
                          same=False, coda_name="최기탁", coda_id="konkuk_coda", coda_tel="02-450-1111"),
    "PRJ-2026-0957": dict(vars={"SEX": True, "AGE": True, "SBP": False}, n_subjects=1200,
                          mgr="박의학", mgr_tel="02-3410-0000", date=dt.date(2027, 1, 20),
                          same=True, coda_name="", coda_id="", coda_tel=""),
}

ss = st.session_state
ss.setdefault("page", "dashboard")
ss.setdefault("rules", [dict(r) for r in DEFAULT_RULES])
ss.setdefault("forms", {k: {**v, "vars": dict(v["vars"])} for k, v in DEFAULT_FORMS.items()})
ss.setdefault("saved", {})


# ══════════════════════════════════════════════════════════════
# 2. eCRF → CODA 변환 (매핑 + 큐레이션)
# ══════════════════════════════════════════════════════════════
def fmt_codelist(s):
    """'1=남성;2=여성' → '1: 남성, 2: 여성'"""
    if not s:
        return ""
    return ", ".join(f"{k.strip()}: {v.strip()}" for k, v in (p.split("=", 1) for p in s.split(";") if "=" in p))


def build_coda(public_map):
    rows, no = [], 0
    for code, (t_en, t_ko) in ECRF_TABLE_MAP.items():
        vars_ = [r for r in ECRF if r["eCRF"] == code]
        if not vars_:
            continue
        for k, desc, typ in KEY_VARS:  # 큐레이션: 키 변수 No.0
            rows.append({"No.": 0, "테이블명(영문)": t_en, "테이블명(국문)": t_ko, "변수명(영문)": k,
                         "변수 설명": desc, "변수 타입": typ, "변수값(코드) 설명": "", "공개 여부": "필수 키",
                         "_src": "큐레이션", "_kind": "key"})
        if NO_RESET_PER_TABLE:
            no = 0
        for r in vars_:
            no += 1
            pub = public_map.get(r["변수명"])
            rows.append({"No.": no, "테이블명(영문)": t_en, "테이블명(국문)": t_ko, "변수명(영문)": r["변수명"],
                         "변수 설명": r["항목명"], "변수 타입": DTYPE_MAP.get(r["데이터 유형"], "검토 필요"),
                         "변수값(코드) 설명": fmt_codelist(r["코드리스트"]),
                         "공개 여부": "미입력" if pub is None else ("공개" if pub else "비공개"),
                         "_src": f'{code}.{r["변수명"]}', "_kind": "var"})
    return rows


CODA_COLS = ["No.", "테이블명(영문)", "테이블명(국문)", "변수명(영문)", "변수 설명", "변수 타입", "변수값(코드) 설명", "공개 여부"]
CODA_SRC = {"No.": "큐레이션", "테이블명(영문)": "← eCRF", "테이블명(국문)": "← eCRF", "변수명(영문)": "← 변수명",
            "변수 설명": "← 항목명", "변수 타입": "← 데이터 유형", "변수값(코드) 설명": "← 코드리스트", "공개 여부": "← 연구자 입력"}


# ══════════════════════════════════════════════════════════════
# 3. 아이콘
# ══════════════════════════════════════════════════════════════
def icon(name, size=20, color="currentColor", sw=1.8):
    p = {
        "db": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5"/><path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3"/>',
        "server": '<rect x="3" y="3" width="18" height="8" rx="2"/><rect x="3" y="13" width="18" height="8" rx="2"/><path d="M7 7h.01M7 17h.01"/>',
        "layers": '<path d="m12 2 9 5-9 5-9-5 9-5z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
        "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
        "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
        "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
        "pie": '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
        "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>',
        "lock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
        "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
        "table": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18"/>',
        "send": '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/>',
        "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    }[name]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" '
            f'style="flex-shrink:0;vertical-align:middle">{p}</svg>')


def md(s):
    st.markdown(s, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# 4. CSS  (Streamlit 1.4x baseweb / 1.5x+ react-aria 위젯 모두 대응)
# ══════════════════════════════════════════════════════════════
md("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--navy:#161b2e;--bg:#f6f8fa;--card:#fff;--line:#e5e9ef;--text:#1e2433;--muted:#6b7280;
  --green:#7fb4a1;--green-d:#4e8f78;--green-bg:#eef7f3;--purple:#7a68e6;--purple-d:#5b4bd1;--blue:#4f6bdc;}
html,body,.stApp,.stMarkdown,button,input,textarea,select,[data-testid="stWidgetLabel"] p{
  font-family:'Noto Sans KR','Pretendard',sans-serif !important;}
.stApp{background:var(--bg);}
header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stSidebar"],[data-testid="stDecoration"],
[data-testid="stSidebarCollapsedControl"],footer{display:none !important;}
.block-container,[data-testid="stMainBlockContainer"]{padding:0 0 3rem 0 !important;max-width:100% !important;}
[data-testid="stElementContainer"]:has(style),.element-container:has(style){display:none !important;}
.stMarkdown p{margin-bottom:0;}
[data-testid="stMarkdownContainer"]{margin-bottom:0 !important;}

/* ─── 헤더 ─── */
.st-key-topbar{background:var(--navy);padding:16px 5%;margin-bottom:18px;box-shadow:0 2px 6px rgba(0,0,0,.12);}
.st-key-topbar [data-testid="stHorizontalBlock"]{align-items:center !important;}
.st-key-topbar [data-testid="stColumn"],.st-key-topbar [data-testid="column"]{display:flex;flex-direction:column;justify-content:center;}
.st-key-topbar [data-testid="stColumn"] > div,.st-key-topbar [data-testid="column"] > div{width:100%;}
.st-key-topbar [data-testid="stVerticalBlock"]{gap:0 !important;justify-content:center;}
.st-key-topbar .stMarkdown,.st-key-topbar [data-testid="stMarkdownContainer"],
.st-key-topbar [data-testid="stElementContainer"],.st-key-topbar .element-container{margin:0 !important;padding:0 !important;}
.brand{display:flex;align-items:center;gap:16px;height:56px;}
.brand-ic{width:52px;height:52px;border-radius:12px;background:var(--green);display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.brand-t{display:flex;flex-direction:column;justify-content:center;}
.brand-t .t1{color:#fff;font-size:25px;font-weight:700;line-height:1.25;letter-spacing:-.3px;}
.brand-t .t2{color:#c4c9d4;font-size:14.5px;line-height:1.3;margin-top:3px;}
.st-key-projbox{background:#1f2538;border:1px solid #333b52;border-radius:12px;padding:7px 8px 7px 18px;}
.st-key-projbox [data-testid="stHorizontalBlock"]{align-items:center !important;gap:8px;}
.projlbl{display:flex;align-items:center;gap:10px;color:#c9ced8;font-size:16px;white-space:nowrap;height:40px;}
.st-key-projbox [role="group"],.st-key-projbox div[data-baseweb="select"] > div{background:#151a2b !important;
  border:none !important;border-radius:8px !important;min-height:40px !important;box-shadow:none !important;}
.st-key-projbox input,.st-key-projbox div[data-baseweb="select"] div{color:#9fe3c4 !important;-webkit-text-fill-color:#9fe3c4 !important;
  font-weight:700 !important;font-size:15.5px !important;background:transparent !important;}
.st-key-projbox button,.st-key-projbox svg{color:#c9ced8 !important;fill:#c9ced8 !important;background:transparent !important;}

/* ─── 레이아웃 ─── */
.st-key-body{padding:0 5%;}
.st-key-body > div > [data-testid="stHorizontalBlock"],.st-key-body > [data-testid="stHorizontalBlock"]{
  gap:36px;align-items:flex-start;flex-wrap:nowrap !important;}
.card,.st-key-menucard,.st-key-formcard,.st-key-cbcard,.st-key-preview{background:var(--card);border:1px solid var(--line);
  border-radius:16px;box-shadow:0 1px 3px rgba(16,24,40,.04);}

/* ─── 메뉴 ─── */
.st-key-menucard{padding:22px 22px 24px;}
.st-key-menucard [data-testid="stVerticalBlock"]{gap:6px;}
.menu-title{color:#9aa1ad;font-size:15px;font-weight:500;margin:0 0 4px 10px;}
.st-key-menucard .stButton > button{width:100%;justify-content:flex-start;background:transparent;border:1px solid transparent;
  border-radius:12px;padding:14px 18px;color:#3b4252;position:relative;box-shadow:none;min-height:54px;}
.st-key-menucard .stButton > button > div{justify-content:flex-start !important;flex:1;text-align:left;}
.st-key-menucard .stButton > button [data-testid="stMarkdownContainer"]{text-align:left;width:100%;}
.st-key-menucard .stButton > button p{font-size:18.5px;font-weight:500;letter-spacing:.3px;white-space:nowrap;}
.st-key-menucard .stButton > button::after{content:"›";position:absolute;right:20px;top:50%;transform:translateY(-55%);font-size:26px;color:#8b93a1;}
.st-key-menucard .stButton > button:hover{background:#f6faf8;color:var(--text);border-color:#e6efea;}
.st-key-menucard .stButton > button:focus:not(:active){border-color:#cfe6dc;color:var(--text);box-shadow:none;}
.st-key-menucard .stButton > button[kind="primary"]{background:var(--green-bg);border-color:#cfe6dc;color:var(--text);}
.st-key-menucard .stButton > button::before{content:"";width:22px;height:22px;margin-right:14px;flex-shrink:0;background-repeat:no-repeat;background-size:contain;}
.st-key-nav_dashboard .stButton > button::before{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236b7f78' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M12 20V10M18 20V4M6 20v-4'/%3E%3C/svg%3E");}
.st-key-nav_form .stButton > button::before{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236b7f78' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/%3E%3Cpath d='M14 2v6h6M16 13H8M16 17H8M10 9H8'/%3E%3C/svg%3E");}
.st-key-nav_codebook .stButton > button::before{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236b7f78' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m12 2 9 5-9 5-9-5 9-5z'/%3E%3Cpath d='m3 12 9 5 9-5'/%3E%3Cpath d='m3 17 9 5 9-5'/%3E%3C/svg%3E");}

/* ─── 분포 카드 ─── */
.dist{padding:22px 22px 26px;}
.dist-head{display:flex;justify-content:space-between;align-items:center;padding-bottom:14px;border-bottom:1px solid var(--line);}
.dist-head b{display:flex;align-items:center;gap:8px;font-size:17px;color:var(--text);white-space:nowrap;}
.badge-live{background:var(--green-bg);color:var(--green-d);font-size:13px;padding:3px 10px;border-radius:6px;white-space:nowrap;}
.donut{display:flex;justify-content:center;margin:26px 0 30px;}
.legend-row{display:flex;justify-content:space-between;align-items:center;font-size:16.5px;color:#374151;margin:9px 0;}
.legend-row span{display:flex;align-items:center;gap:10px;}
.legend-row i{width:13px;height:13px;border-radius:50%;display:inline-block;}
.legend-row b{font-weight:700;color:var(--text);}

/* ─── 가이드 ─── */
.guide{margin-bottom:24px;background:#f3f6fe;border:1px solid #d9e1f7;border-radius:16px;padding:22px 28px;display:flex;gap:16px;}
.guide h3{margin:0 0 12px 0;padding:0;font-size:20px;font-weight:700;color:#1f2a55;}
.g-row{display:flex;align-items:flex-start;gap:12px;color:#4b5d93;font-size:15.5px;line-height:1.7;margin-top:6px;}
.g-row strong{color:#24337a;}
.g-badge{flex-shrink:0;font-size:13px;font-weight:700;padding:2px 10px;border-radius:6px;margin-top:2px;white-space:nowrap;}
.g-badge.auto{background:#e3e9fb;color:#3550c4;}
.g-badge.self{background:#fdeee0;color:#b0601a;}

/* ─── KPI ─── */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:24px;margin-bottom:24px;}
.kpi{padding:22px 24px 20px;}
.kpi-top{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#6b7280;font-size:16px;white-space:nowrap;}
.kpi-val{font-size:34px;font-weight:900;color:var(--text);margin:14px 0 10px;letter-spacing:-.5px;}
.kpi-sub{font-size:15px;display:flex;align-items:center;gap:6px;}

/* ─── 매핑 미리보기 ─── */
.st-key-preview{padding:24px 30px 28px;}
.st-key-prevtop [data-testid="stHorizontalBlock"]{align-items:center !important;}
.pv-title{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:700;color:var(--text);}
.pv-sub{color:#6b7280;font-size:14.5px;margin:4px 0 0 32px;}
.rules{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 2px;}
.rchip{display:inline-flex;align-items:center;gap:6px;font-size:13.5px;border-radius:8px;padding:5px 10px;
  background:#f5f6f8;border:1px solid #e7e9ee;color:#374151;}
.rchip b{font-weight:700;color:#1e2433;}
.rchip.cur{background:#eef7f3;border-color:#d4ebe0;color:#2f6e58;}
.rchip.cur b{color:#2f6e58;}
.tbl-wrap{border:1px solid var(--line);border-radius:12px;overflow:auto;max-height:470px;}
table.pv{border-collapse:separate;border-spacing:0;width:100%;font-size:14px;}
table.pv th{position:sticky;top:0;background:#f6f7f9;color:#2a3140;font-weight:700;text-align:left;padding:11px 12px;
  border-bottom:1px solid var(--line);white-space:nowrap;z-index:1;}
table.pv th small{display:block;font-weight:500;font-size:11.5px;color:#7a8394;margin-top:2px;}
table.pv th small.c{color:#2f8a68;}
table.pv{margin:0 !important;}
table.pv th,table.pv td{border-top:none !important;border-left:none !important;border-right:none !important;}
table.pv td{padding:9px 12px !important;border-bottom:1px solid #eef0f3 !important;color:#2f3644;vertical-align:middle;white-space:nowrap;}
table.pv th{padding:10px 12px !important;}
table.pv tr:last-child td{border-bottom:none;}
table.pv tr.key td{background:#f7fbf9;}
table.pv td.mono{font-family:'JetBrains Mono',monospace;font-size:13.5px;}
table.pv td.v{font-family:'JetBrains Mono',monospace;font-size:13.5px;color:#4e8f78;font-weight:500;}
table.pv td.no{text-align:center;font-weight:700;color:#4b5563;}
table.pv td.wrap{white-space:normal;min-width:180px;max-width:260px;}
table.pv td.src{font-family:'JetBrains Mono',monospace;font-size:12.5px;color:#8a919d;}
.pb{display:inline-block;font-size:12.5px;font-weight:700;padding:2px 9px;border-radius:6px;white-space:nowrap;}
.pb.pub{background:#e7f6ee;color:#2f7d58;} .pb.pri{background:#eceef2;color:#4b5563;}
.pb.none{background:#fde8ea;color:#c0392b;} .pb.key{background:#e8eefc;color:#3a55c4;}
.pb.cur{background:#eef7f3;color:#2f6e58;}
.st-key-preview [role="tab"] p,.st-key-preview button[data-baseweb="tab"] p{font-size:15.5px;font-weight:600;}
.st-key-dlbtn button{border-radius:10px !important;border:1px solid #cfe0d8 !important;color:#2f6e58 !important;background:#fff !important;}
.st-key-pvfilter [role="group"],.st-key-pvfilter div[data-baseweb="select"] > div{border-radius:10px !important;}

/* ─── 입력 폼 ─── */
.st-key-formcard{padding:34px 34px 30px;}
.pg-head{display:flex;align-items:flex-start;gap:12px;}
.pg-head .h{font-size:24px;font-weight:700;color:var(--text);line-height:1.3;}
.pg-head .s{margin:6px 0 0;color:#6b7280;font-size:15.5px;}
.sect{border-radius:10px;padding:12px 18px;font-size:16.5px;font-weight:700;display:flex;align-items:center;gap:10px;}
.sect.auto{background:#f3f4f6;color:#1f2a55;}
.sect.user{background:#f1faf5;color:#1f2a55;border:1px solid #e0f0e7;}
.sect .note{margin-left:auto;font-size:13.5px;font-weight:500;color:#6b7280;display:flex;align-items:center;gap:6px;}
.hr{border-top:1px solid var(--line);margin:8px 0;}
.subh{display:flex;align-items:center;gap:8px;font-size:17px;font-weight:700;color:var(--text);margin-top:6px;}
.subh small{font-size:13.5px;color:#8a919d;font-weight:500;}
.ro-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px 24px;}
.ro-grid .full{grid-column:1 / -1;}
.ro-lbl{font-size:15.5px;color:#4b5563;margin-bottom:6px;}
.ro-val{background:#f3f4f6;border:1px solid #e5e7eb;border-radius:10px;padding:12px 16px;font-size:16px;color:#374151;
  display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:48px;cursor:not-allowed;user-select:text;}
.ro-val.mono{font-family:'JetBrains Mono',monospace;font-size:15px;}
.st-key-formcard [data-testid="stWidgetLabel"] p{font-size:15.5px !important;color:#4b5563 !important;}
.st-key-formcard [data-testid="stTextInputRootElement"],.st-key-formcard [data-testid="stNumberInputContainer"],
.st-key-formcard [data-testid="stDateInput"] [data-baseweb="input"],
.st-key-formcard [data-testid="stTextInput"] [data-baseweb="input"],.st-key-formcard [data-testid="stNumberInput"] [data-baseweb="input"]{
  border:1px solid #d5dae2 !important;border-radius:10px !important;background:#fff !important;}
.st-key-formcard input{background:#fff !important;font-size:15.5px !important;color:var(--text) !important;}
.st-key-formcard input:disabled{background:#f3f4f6 !important;-webkit-text-fill-color:#6b7280 !important;}
.st-key-savebtn{display:flex;justify-content:flex-end;align-items:flex-end;}
.st-key-savebtn button{background:#5c937f !important;border:none !important;color:#fff !important;border-radius:10px !important;
  padding:10px 22px !important;box-shadow:0 2px 4px rgba(0,0,0,.08);}
.st-key-savebtn button p{font-size:16px !important;font-weight:700 !important;color:#fff !important;}
.st-key-savebtn button:hover{background:#4e8270 !important;}
.saved{font-size:12.5px;color:#8a919d;text-align:right;margin-top:4px;}
.st-key-coda{border:1px dashed #d5dae2;border-radius:12px;padding:16px 18px 6px;background:#fcfcfd;}
.st-key-varadd{background:#f8fafb;border:1px solid var(--line);border-radius:12px;padding:14px 18px;}
.st-key-varadd [data-testid="stHorizontalBlock"]{align-items:flex-end !important;}
.st-key-varadd button{border-radius:10px !important;min-height:42px;}
.st-key-addbtn button{background:#4f6bdc !important;color:#fff !important;border:none !important;}
.st-key-addbtn button p{color:#fff !important;font-weight:700;}
.cnt{display:flex;align-items:center;gap:14px;flex-wrap:wrap;background:#f3f6fe;border:1px solid #d9e1f7;border-radius:12px;
  padding:12px 18px;font-size:15px;color:#4b5d93;}
.cnt .n{font-size:22px;font-weight:900;color:#1f2a55;}
.cnt .f{font-family:'JetBrains Mono',monospace;font-size:13px;background:#fff;border:1px solid #dfe5f6;border-radius:6px;padding:2px 8px;color:#3a55c4;}
.st-key-vartable{border:1px solid var(--line);border-radius:12px;overflow:hidden;}
.st-key-vartable > div,.st-key-vartable [data-testid="stVerticalBlock"]{gap:0 !important;}
.st-key-vartable [data-testid="stHorizontalBlock"]{align-items:center !important;gap:12px;padding:0 16px;}
.st-key-vhead{background:#f6f7f9;border-bottom:1px solid var(--line);padding:11px 0;}
.st-key-vhead p{font-weight:700;color:#2a3140;font-size:15px;margin:0;}
[class*="st-key-vrow_"]{border-bottom:1px solid #eef0f3;padding:2px 0;}
[class*="st-key-vrow_"] [role="radiogroup"]{min-height:0 !important;height:auto !important;padding:6px 0 !important;}
[class*="st-key-vrow_"] .stMarkdown,[class*="st-key-vrow_"] [data-testid="stElementContainer"],[class*="st-key-vrow_"] .element-container,
[class*="st-key-vrow_"] [data-testid="stRadio"],[class*="st-key-cbrow_"] .stMarkdown,[class*="st-key-cbrow_"] .element-container{margin:0 !important;}
[class*="st-key-vrow_"] [data-testid="stColumn"] > div,[class*="st-key-vrow_"] [data-testid="column"] > div{justify-content:center;}
[class*="st-key-vrow_"] [data-testid="stRadio"] > label{display:none;}
[class*="st-key-vrow_"] [role="radiogroup"]{gap:14px;flex-wrap:nowrap;}
.v-no{font-weight:700;color:#6b7280;font-size:14.5px;}
.v-var{font-family:'JetBrains Mono',monospace;color:#4e8f78;font-size:14.5px;font-weight:500;}
.v-txt{color:#2f3644;font-size:15px;}
.tag{display:inline-block;font-size:13.5px;padding:2px 8px;border-radius:6px;line-height:1.5;white-space:nowrap;}
.tag.map{background:#eef1fd;color:#4f63c9;border:1px solid #dde3fb;}
.tag.cln{background:#fdf0f6;color:#b24a83;border:1px solid #f7dbe9;}
[class*="st-key-vdel_"] button,[class*="st-key-del_"] button{background:transparent !important;border:none !important;
  color:#9aa1ad !important;padding:4px 8px !important;min-height:0 !important;box-shadow:none !important;}
[class*="st-key-vdel_"] button:hover,[class*="st-key-del_"] button:hover{color:#d64545 !important;background:#fdf0f0 !important;}
[class*="st-key-vdel_"] button span,[class*="st-key-del_"] button span{font-size:21px !important;}
.empty{padding:28px;text-align:center;color:#9aa1ad;font-size:15px;}

/* ─── 코드북 규칙 ─── */
.st-key-cbcard{padding:30px 34px 34px;}
.st-key-cbtop{border-bottom:1px solid var(--line);padding-bottom:18px;}
.st-key-cbtop [data-testid="stHorizontalBlock"]{align-items:center !important;}
.st-key-cbtable{border:1px solid var(--line);border-radius:14px;overflow:hidden;}
.st-key-cbtable > div,.st-key-cbtable [data-testid="stVerticalBlock"]{gap:0 !important;}
.st-key-cbtable [data-testid="stHorizontalBlock"]{align-items:center !important;gap:14px;padding:0 18px;}
.st-key-cbhead{background:#f6f7f9;border-bottom:1px solid var(--line);padding:16px 0;}
.st-key-cbhead p{font-weight:700;color:#2a3140;font-size:16px;margin:0;}
[class*="st-key-cbrow_"]{border-bottom:1px solid #eef0f3;padding:14px 0;}
.c-id{font-family:'JetBrains Mono',monospace;color:#6b7280;font-size:14.5px;line-height:1.5;}
.c-src{font-weight:700;color:var(--text);font-size:16px;line-height:1.45;}
.c-tgt{font-family:'JetBrains Mono',monospace;color:#4e8f78;font-size:15px;word-break:break-all;}
.c-txt{color:#2f3644;font-size:15.5px;line-height:1.45;}
.stt{display:inline-block;font-size:13.5px;font-weight:700;padding:3px 9px;border-radius:6px;white-space:nowrap;}
.stt.done{background:#e7f6ee;color:#2f7d58;} .stt.rev{background:#fde8ea;color:#c0392b;} .stt.ing{background:#fdf5d8;color:#a77a0c;}
</style>
""")


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
proj, form = PROJECTS[pid], ss.forms[pid]


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
    items = [("매핑 완료", 68, "#7fb4a1"), ("정제 완료", 20, "#e5c25a"), ("검토 필요 항목", 12, "#d6dae1")]
    legend = "".join(f'<div class="legend-row"><span><i style="background:{c}"></i>{n}</span><b>{v}%</b></div>'
                     for n, v, c in items)
    md(f'<div class="card dist"><div class="dist-head"><b>{icon("pie", 19, "#4b5563")} 변환/정제 항목 분포</b>'
       f'<span class="badge-live">실시간</span></div><div class="donut">'
       f'{donut_svg([(68, "#7fb4a1"), (20, "#e5c25a"), (12, "#eef0f3")], "77%")}</div>{legend}</div>')


# ══════════════════════════════════════════════════════════════
# 7. 대시보드
# ══════════════════════════════════════════════════════════════
def var_counts():
    v = form["vars"]
    pub = sum(1 for x in v.values() if x)
    return len(v), pub, len(v) - pub


def coda_table_html(rows):
    head = "".join(
        f'<th>{c}<small class="{"c" if CODA_SRC[c] in ("큐레이션", "← 연구자 입력") else ""}">{CODA_SRC[c]}</small></th>'
        for c in CODA_COLS) + '<th>원본<small>iCReaT eCRF</small></th>'
    body = ""
    for r in rows:
        pb = {"공개": "pub", "비공개": "pri", "미입력": "none", "필수 키": "key"}[r["공개 여부"]]
        pub_txt = "미입력 · 검토 필요" if r["공개 여부"] == "미입력" else r["공개 여부"]
        src = '<span class="pb cur">큐레이션</span>' if r["_kind"] == "key" else E(r["_src"])
        body += (f'<tr class="{r["_kind"]}"><td class="no">{r["No."]}</td><td class="mono">{E(r["테이블명(영문)"])}</td>'
                 f'<td>{E(r["테이블명(국문)"])}</td><td class="v">{E(r["변수명(영문)"])}</td><td>{E(r["변수 설명"])}</td>'
                 f'<td class="mono">{E(r["변수 타입"])}</td><td class="wrap">{E(r["변수값(코드) 설명"]) or "-"}</td>'
                 f'<td><span class="pb {pb}">{pub_txt}</span></td><td class="src">{src}</td></tr>')
    return f'<div class="tbl-wrap"><table class="pv"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def ecrf_table_html(rows):
    head = "".join(f"<th>{c}</th>" for c in ECRF_COLS)
    body = "".join(
        f'<tr><td class="mono">{E(r["eCRF"])}</td><td>{E(r["항목명"])}</td><td class="v">{E(r["변수명"])}</td>'
        f'<td>{E(r["항목 유형"])}</td><td class="mono">{E(r["데이터 유형"])}</td><td class="no">{r["길이"]}</td>'
        f'<td>{E(r["단위"]) or "-"}</td><td>{E(r["코드리스트"]) or "-"}</td></tr>' for r in rows)
    return f'<div class="tbl-wrap"><table class="pv"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def to_csv(rows, cols):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def page_dashboard():
    md(f"""<div class="guide"><div style="padding-top:2px">{icon('info', 26, '#4f6bdc')}</div><div>
      <h3>iCReaT 자동 연동 &amp; 연구자 직접 제출 안내</h3>
      <div class="g-row"><span class="g-badge auto">iCReaT 제공</span><div><strong>자동 연동 가능한 기본 속성 불러오기</strong>,
        <strong>코드북 항목 매핑</strong>, <strong>데이터 입력 폼 작성 항목</strong>까지는 자동으로 CODA 형식에 매핑됩니다.</div></div>
      <div class="g-row"><span class="g-badge self">직접 제출</span><div>제출을 위한 <strong>동의서</strong>는
        기탁 사이트(CODA)의 양식을 통해 연구자가 직접 제출해야 합니다.</div></div></div></div>""")

    n_var, n_pub, n_pri = var_counts()
    n_unset = len(ECRF) - sum(1 for v in form["vars"] if v in ECRF_BY_VAR)
    n_clean = sum(1 for r in ss.rules if r["cat"] == "데이터 정제")
    kpis = [
        ("총 기탁 과제 수", "db", "#7fb4a1", f"{len(PROJECTS)}건",
         f'{icon("check", 17, "#4e8f78")}<span style="color:#4e8f78">iCReaT DB 동기화 완료</span>'),
        ("iCReaT 자동 연동 항목", "server", "#4f6bdc", "3 / 6", '<span style="color:#4f6bdc">자동 매핑 비율 50%</span>'),
        ("데이터 정제 규칙 수", "layers", "#c98a1e", f"{n_clean}개", '<span style="color:#c98a1e">오기·오류 및 결측 정제 포함</span>'),
        ("임상 변수 리스트", "list", "#7a68e6", f"{n_var}개 변수",
         f'<span style="color:#6b7280">공개 {n_pub} • 비공개 {n_pri} • 미입력 {n_unset}</span>'),
    ]
    md('<div class="kpis">' + "".join(
        f'<div class="card kpi"><div class="kpi-top">{t}{icon(ic, 22, c)}</div><div class="kpi-val">{v}</div>'
        f'<div class="kpi-sub">{s}</div></div>' for t, ic, c, v, s in kpis) + "</div>")

    coda = build_coda(form["vars"])
    with st.container(key="preview"):
        with st.container(key="prevtop"):
            a, b, c = st.columns([3.1, 0.9, 0.75], vertical_alignment="center")
            with a:
                md(f'<div class="pv-title">{icon("table", 22, "#4e8f78")} eCRF → CODA 코드북 매핑 미리보기</div>'
                   f'<div class="pv-sub">iCReaT eCRF 코드북을 정제하여 CODA 코드북 형식으로 변환한 결과입니다. (목업 데이터)</div>')
            with b:
                with st.container(key="pvfilter"):
                    opts = ["전체 테이블"] + [f"{k} · {v[1]}" for k, v in ECRF_TABLE_MAP.items()]
                    sel = st.selectbox("테이블", opts, label_visibility="collapsed", key="pv_sel")
            with c:
                with st.container(key="dlbtn"):
                    st.download_button(":material/download: CSV 다운로드", to_csv(coda, CODA_COLS),
                                       file_name=f"CODA_codebook_{pid}.csv", mime="text/csv", use_container_width=True)
        chips = [("eCRF", "테이블명(영문·국문)"), ("변수명", "변수명(영문)"), ("항목명", "변수 설명"),
                 ("데이터 유형", "변수 타입"), ("코드리스트", "변수값(코드) 설명")]
        ar = icon("arrow", 13, "#9aa1ad", 2)
        md('<div class="rules">' + "".join(f'<span class="rchip"><b>{s}</b>{ar}{t}</span>' for s, t in chips)
           + f'<span class="rchip cur"><b>큐레이션</b> No. (ID·FAMILY_ID·PNTTM=0, 이후 1부터)</span>'
             f'<span class="rchip cur"><b>연구자 입력</b> 공개 여부</span></div>')

        if sel != "전체 테이블":
            code = sel.split(" · ")[0]
            coda_v = [r for r in coda if r["테이블명(영문)"] == ECRF_TABLE_MAP[code][0]]
            ecrf_v = [r for r in ECRF if r["eCRF"] == code]
        else:
            coda_v, ecrf_v = coda, ECRF
        t1, t2 = st.tabs([f"CODA 코드북 미리보기 ({len(coda_v)})", f"iCReaT eCRF 원본 ({len(ecrf_v)})"])
        with t1:
            md(coda_table_html(coda_v))
        with t2:
            md(ecrf_table_html(ecrf_v))


# ══════════════════════════════════════════════════════════════
# 8. 과제 및 데이터 입력 폼
# ══════════════════════════════════════════════════════════════
def ro_field(label, value, full=False, mono=False):
    return (f'<div class="{"full" if full else ""}"><div class="ro-lbl">{label}</div>'
            f'<div class="ro-val{" mono" if mono else ""}"><span>{E(value)}</span>{icon("lock", 16, "#9aa1ad")}</div></div>')


def add_var(var, pub):
    if var:
        ss.forms[pid]["vars"][var] = pub


def page_form():
    with st.container(key="formcard"):
        a, b = st.columns([3, 1], vertical_alignment="center")
        with a:
            md(f'<div class="pg-head">{icon("file", 26, "#4b5563")}<div><div class="h">연구 과제 메타데이터 &amp; 데이터 입력 폼</div>'
               f'<div class="s">iCReaT 자동 수집 항목과 연구자 추가 입력(없는 데이터 채우기)을 한 곳에서 관리합니다.</div></div></div>')
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
        md('<div class="ro-grid">' + ro_field("과제 번호 (자동 부여)", pid, mono=True) + ro_field("수행 기관", proj["org"])
           + ro_field("과제명", proj["title"]) + ro_field("연구 책임자", proj["pi"])
           + ro_field("수행 및 기탁 목표", proj["goal"], full=True) + '</div>')
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
           f'<small>추가한 변수의 공개 여부가 CODA 코드북 \'공개 여부\'에 반영됩니다</small></div>')
        remaining = [r for r in ECRF if r["변수명"] not in form["vars"]]
        with st.container(key="varadd"):
            c1, c2, c3, c4 = st.columns([2.6, 1.3, 0.8, 1.2], vertical_alignment="bottom")
            with c1:
                pick = st.selectbox("eCRF 변수 선택", remaining, key=f"w_pick_{pid}", disabled=not remaining,
                                    format_func=lambda r: f'{r["eCRF"]} · {r["변수명"]} ({r["항목명"]})',
                                    placeholder="추가할 변수가 없습니다")
            with c2:
                pub_new = st.radio("공개 여부", ["공개", "비공개"], horizontal=True, key=f"w_pubnew_{pid}")
            with c3:
                with st.container(key="addbtn"):
                    st.button(":material/add: 추가", use_container_width=True, disabled=not remaining,
                              on_click=add_var, args=(pick["변수명"] if pick else "", pub_new == "공개"))
            with c4:
                if st.button(":material/playlist_add: eCRF 전체 추가", use_container_width=True, disabled=not remaining):
                    for r in remaining:
                        form["vars"][r["변수명"]] = True
                    st.rerun()

        n_var, n_pub, n_pri = var_counts()
        md(f'<div class="cnt">임상 변수 개수 <span class="n">{n_var}개</span> = 공개 <b>{n_pub}</b> + 비공개 <b>{n_pri}</b>'
           f'<span class="f">= SUM(추가된 변수)</span><span style="margin-left:auto">미입력 eCRF 변수 '
           f'<b>{len(remaining)}</b>개 → CODA 미리보기에서 \'검토 필요\' 표시</span></div>')

        widths = [0.45, 0.8, 1.3, 1.6, 1.5, 0.4]
        with st.container(key="vartable"):
            with st.container(key="vhead"):
                for col, h in zip(st.columns(widths), ["No.", "eCRF", "변수명", "항목명", "공개 여부", ""]):
                    with col:
                        md(f"<p>{h}</p>")
            if not form["vars"]:
                md('<div class="empty">추가된 임상 변수가 없습니다. 위에서 eCRF 변수를 선택해 추가하세요.</div>')
            for i, (var, pub) in enumerate(list(form["vars"].items()), 1):
                r = ECRF_BY_VAR.get(var, {"eCRF": "-", "항목명": "-"})
                with st.container(key=f"vrow_{var}"):
                    cs = st.columns(widths, vertical_alignment="center")
                    with cs[0]:
                        md(f'<div class="v-no">{i}</div>')
                    with cs[1]:
                        md(f'<span class="tag map">{E(r["eCRF"])}</span>')
                    with cs[2]:
                        md(f'<div class="v-var">{E(var)}</div>')
                    with cs[3]:
                        md(f'<div class="v-txt">{E(r["항목명"])}</div>')
                    with cs[4]:
                        ch = st.radio("공개 여부", ["공개", "비공개"], index=0 if pub else 1, horizontal=True,
                                      key=f"w_pub_{pid}_{var}", label_visibility="collapsed")
                        form["vars"][var] = ch == "공개"
                    with cs[5]:
                        with st.container(key=f"vdel_{var}"):
                            if st.button(":material/delete:", key=f"bvdel_{pid}_{var}", help="삭제"):
                                del form["vars"][var]
                                st.rerun()


# ══════════════════════════════════════════════════════════════
# 9. 코드북 매핑 & 정제 규칙
# ══════════════════════════════════════════════════════════════
STATUS_CLS = {"완료": "done", "검토필요": "rev", "진행중": "ing"}
CAT_CLS = {"항목 매핑": "map", "데이터 정제": "cln"}
WIDTHS = [0.55, 1.9, 1.45, 0.95, 1.1, 2.7, 0.75, 0.35]


def page_codebook():
    with st.container(key="cbcard"):
        with st.container(key="cbtop"):
            a, b, c = st.columns([3.2, 1.05, 0.72], gap="small", vertical_alignment="center")
            with a:
                md(f'<div class="pg-head">{icon("layers", 28, "#4e8f78")}<div><div class="h">코드북 매핑 양식 및 데이터 정제 규칙</div>'
                   f'<div class="s">항목 매핑(코드북 규칙)과 데이터 정제(오기/오류/결측 처리) 규칙을 체계적으로 분류하여 관리합니다.</div></div></div>')
            with b:
                q = st.text_input("검색", placeholder="필드명 또는 규칙 검색...", label_visibility="collapsed")
            with c:
                f = st.selectbox("구분", ["전체 구분", "항목 매핑", "데이터 정제"], label_visibility="collapsed")
        rows = [r for r in ss.rules if (f == "전체 구분" or r["cat"] == f)
                and (not q or q.lower() in (r["src"] + r["tgt"] + r["rtype"] + r["detail"]).lower())]
        with st.container(key="cbtable"):
            with st.container(key="cbhead"):
                for col, h in zip(st.columns(WIDTHS), ["ID", "원본 필드 (iCReaT)", "CoDA 타겟 필드", "구분", "규칙 유형",
                                                       "상세 정제/매핑 세부사항", "상태", "삭제"]):
                    with col:
                        md(f"<p>{h}</p>")
            if not rows:
                md('<div class="empty">조건에 맞는 규칙이 없습니다.</div>')
            for r in rows:
                with st.container(key=f"cbrow_{r['id']}"):
                    cs = st.columns(WIDTHS, vertical_alignment="center")
                    cells = [f'<div class="c-id">{r["id"]}</div>', f'<div class="c-src">{E(r["src"])}</div>',
                             f'<div class="c-tgt">{E(r["tgt"])}</div>', f'<span class="tag {CAT_CLS[r["cat"]]}">{r["cat"]}</span>',
                             f'<div class="c-txt">{E(r["rtype"])}</div>', f'<div class="c-txt">{E(r["detail"])}</div>',
                             f'<span class="stt {STATUS_CLS[r["status"]]}">{r["status"]}</span>']
                    for col, cell in zip(cs, cells):
                        with col:
                            md(cell)
                    with cs[7]:
                        with st.container(key=f"del_{r['id']}"):
                            if st.button(":material/delete:", key=f"bdel_{r['id']}", help="삭제"):
                                ss.rules = [x for x in ss.rules if x["id"] != r["id"]]
                                st.rerun()


# ══════════════════════════════════════════════════════════════
# 10. 본문
# ══════════════════════════════════════════════════════════════
with st.container(key="body"):
    left, main = st.columns([1, 3.1])
    with left:
        left_panel()
    with main:
        {"dashboard": page_dashboard, "form": page_form, "codebook": page_codebook}[ss.page]()
