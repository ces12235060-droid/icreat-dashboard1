"""iCReaT 연구데이터 정제 및 기탁 대시보드 (Streamlit)"""
import html
import streamlit as st

st.set_page_config(page_title="iCReaT 연구데이터 정제 및 기탁 대시보드", page_icon="🗄️", layout="wide",
                   initial_sidebar_state="collapsed")

# ──────────────────────────────────────────────────────────────
# 데이터
# ──────────────────────────────────────────────────────────────
PROJECTS = {
    "PRJ-2026-0891": dict(org="홍길동대학교 병원", pi="김연구 교수",
                          title="만성 질환 유전체 기반 바이오헬스 임상데이터 통합 구축",
                          goal="만성 질환자 5,000명의 유전체 및 임상 역학 데이터 표준화 및 저장",
                          clean=85, map=92),
    "PRJ-2026-0912": dict(org="건국대학교 산학협력단", pi="이공학 박사",
                          title="웨어러블 센서 기반 생활습관 데이터 표준화",
                          goal="웨어러블 PGHD 데이터 FHIR R5 매핑 및 기탁",
                          clean=100, map=100),
    "PRJ-2026-0957": dict(org="삼성서울병원", pi="박의학 교수",
                          title="희귀질환 다기관 임상 코호트 데이터 구축",
                          goal="희귀질환 환자 1,200명 임상·영상 데이터 정제 및 기탁",
                          clean=45, map=60),
}

DOCS = [
    ("1. 연구계획서 (Research Proposal)", "연구 목적 및 수행 절차 확인"),
    ("2. 동의서 정보 (IRB Consent Forms)", "인체유래물 및 개인정보 활용 동의"),
    ("3. 공개자원 설명서 (Data Descriptor)", "데이터셋 구성 및 변수 설명서"),
    ("4. 임상 역학 정보 (Clinical / Bio Data)", "임상 지표 및 측정 항목 양식"),
]

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

ss = st.session_state
ss.setdefault("page", "dashboard")
ss.setdefault("rules", [dict(r) for r in DEFAULT_RULES])

# ──────────────────────────────────────────────────────────────
# 아이콘 (lucide 스타일 SVG)
# ──────────────────────────────────────────────────────────────
def icon(name, size=20, color="currentColor", sw=1.8):
    paths = {
        "db": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5"/><path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3"/>',
        "server": '<rect x="3" y="3" width="18" height="8" rx="2"/><rect x="3" y="13" width="18" height="8" rx="2"/><path d="M7 7h.01M7 17h.01"/>',
        "layers": '<path d="m12 2 9 5-9 5-9-5 9-5z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
        "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
        "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
        "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
        "pie": '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
        "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
        "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>',
        "chart": '<path d="M12 20V10M18 20V4M6 20v-4"/>',
    }
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">'
            f'{paths[name]}</svg>')

# ──────────────────────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&family=JetBrains+Mono:wght@400;500&display=swap');
:root{
  --navy:#161b2e; --bg:#f6f8fa; --card:#ffffff; --line:#e5e9ef; --text:#1e2433; --muted:#6b7280;
  --green:#7fb4a1; --green-d:#4e8f78; --green-bg:#eef7f3; --purple:#7a68e6; --purple-d:#5b4bd1;
  --yellow:#e5c25a; --orange:#c98a1e; --blue:#4f6bdc; --gray:#d6dae1;
}
html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, select{
  font-family:'Noto Sans KR','Pretendard',sans-serif !important;
}
.stApp{background:var(--bg);}
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stSidebar"],
[data-testid="stDecoration"], footer{display:none !important;}
.block-container{padding:0 0 3rem 0 !important; max-width:100% !important;}
div[data-testid="stVerticalBlock"]{gap:0.9rem;}

/* ─── 헤더 ─── */
.st-key-topbar{background:var(--navy); padding:18px 5% 18px 5%; margin-bottom:18px;
  box-shadow:0 2px 6px rgba(0,0,0,.12);}
.st-key-topbar [data-testid="stHorizontalBlock"]{align-items:center;}
.brand{display:flex; align-items:center; gap:16px;}
.brand-ic{width:52px;height:52px;border-radius:12px;background:var(--green);display:flex;
  align-items:center;justify-content:center;}
.brand h1{color:#fff;font-size:26px;font-weight:700;margin:0;padding:0;line-height:1.25;letter-spacing:-.3px;}
.brand p{color:#c4c9d4;font-size:15px;margin:2px 0 0 0;}
.st-key-projbox{background:#1f2538;border:1px solid #333b52;border-radius:12px;padding:6px 10px 6px 18px;}
.st-key-projbox [data-testid="stHorizontalBlock"]{align-items:center; gap:6px;}
.projlbl{display:flex;align-items:center;gap:10px;color:#c9ced8;font-size:16px;white-space:nowrap;}
.st-key-projbox [data-testid="stSelectbox"] [role="group"]{background:#151a2b !important;border:none !important;
  border-radius:8px !important;min-height:40px;box-shadow:none !important;}
.st-key-projbox [data-testid="stSelectbox"] input{color:#9fe3c4 !important;-webkit-text-fill-color:#9fe3c4 !important;
  font-weight:700 !important;font-size:15.5px !important;background:transparent !important;}
.st-key-projbox [data-testid="stSelectbox"] button{color:#c9ced8 !important;background:transparent !important;}
[data-testid="stElementContainer"]:has(> div > div > style), [data-testid="stElementContainer"]:has(style){display:none !important;}

/* ─── 레이아웃 래퍼 ─── */
.st-key-body{padding:0 5%;}
.st-key-body > div > [data-testid="stHorizontalBlock"]{gap:36px; align-items:flex-start; flex-wrap:nowrap !important;}

/* ─── 카드 ─── */
.card, .st-key-menucard, .st-key-formcard, .st-key-cbcard{background:var(--card);border:1px solid var(--line);
  border-radius:16px;box-shadow:0 1px 3px rgba(16,24,40,.04);}
.st-key-menucard{padding:22px 22px 24px;}
.menu-title{color:#9aa1ad;font-size:15px;font-weight:500;margin:0 0 4px 10px;}

/* 메뉴 버튼 */
.st-key-menucard .stButton>button{width:100%;justify-content:flex-start;background:transparent;border:1px solid transparent;
  border-radius:12px;padding:14px 18px;color:#3b4252;font-size:19px;font-weight:500;letter-spacing:.5px;
  position:relative;box-shadow:none;}
.st-key-menucard .stButton>button p{font-size:18.5px;white-space:nowrap;}
.st-key-menucard .stButton>button>div{justify-content:flex-start !important;flex:1;}
.st-key-menucard .stButton>button::after{content:"›";position:absolute;right:20px;top:50%;transform:translateY(-55%);
  font-size:26px;color:#8b93a1;}
.st-key-menucard .stButton>button:hover{background:#f6faf8;color:var(--text);border-color:#e6efea;}
.st-key-menucard .stButton>button:focus:not(:active){border-color:#cfe6dc;color:var(--text);}
.st-key-menucard .stButton>button[kind="primary"]{background:var(--green-bg);border-color:#cfe6dc;color:var(--text);}
.st-key-menucard .stButton>button[kind="primary"]:hover{background:#e6f3ed;}
.st-key-menucard div[data-testid="stVerticalBlock"]{gap:6px;}
.st-key-menucard .stButton>button::before{content:"";width:22px;height:22px;margin-right:14px;flex-shrink:0;
  background-repeat:no-repeat;background-size:contain;}
.st-key-nav_dashboard .stButton>button::before{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236b7f78' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M12 20V10M18 20V4M6 20v-4'/%3E%3C/svg%3E");}
.st-key-nav_form .stButton>button::before{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236b7f78' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/%3E%3Cpath d='M14 2v6h6M16 13H8M16 17H8M10 9H8'/%3E%3C/svg%3E");}
.st-key-nav_codebook .stButton>button::before{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236b7f78' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m12 2 9 5-9 5-9-5 9-5z'/%3E%3Cpath d='m3 12 9 5 9-5'/%3E%3Cpath d='m3 17 9 5 9-5'/%3E%3C/svg%3E");}

/* 분포 카드 */
.dist{padding:22px 22px 26px;}
.dist-head{display:flex;justify-content:space-between;align-items:center;padding-bottom:14px;border-bottom:1px solid var(--line);}
.dist-head b{white-space:nowrap;display:flex;align-items:center;gap:8px;font-size:17px;color:var(--text);}
.badge-live{white-space:nowrap;background:var(--green-bg);color:var(--green-d);font-size:13px;padding:3px 10px;border-radius:6px;}
.donut{display:flex;justify-content:center;margin:26px 0 30px;}
.legend-row{display:flex;justify-content:space-between;align-items:center;font-size:16.5px;color:#374151;margin:9px 0;}
.legend-row span{display:flex;align-items:center;gap:10px;}
.legend-row i{width:13px;height:13px;border-radius:50%;display:inline-block;}
.legend-row b{font-weight:700;color:var(--text);}

/* 가이드 배너 */
.guide{margin-bottom:24px;background:#f3f6fe;border:1px solid #d9e1f7;border-radius:16px;padding:24px 28px;display:flex;gap:16px;}
.guide h3{margin:0 0 8px 0;padding:0;font-size:20px;font-weight:700;color:#1f2a55;}
.guide p{margin:0;color:#4b5d93;font-size:16px;line-height:1.75;}
.guide p strong{color:#24337a;}

/* KPI */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:24px;margin-bottom:24px;}
.kpi{padding:22px 24px 20px;}
.kpi-top{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#6b7280;font-size:16px;white-space:nowrap;}
.kpi-val{font-size:34px;font-weight:900;color:var(--text);margin:14px 0 10px;letter-spacing:-.5px;}
.kpi-sub{font-size:15px;display:flex;align-items:center;gap:6px;}

/* 막대 비교 */
.cmp{padding:24px 30px 30px;}
.cmp-head{display:flex;justify-content:space-between;align-items:center;padding-bottom:20px;border-bottom:1px solid var(--line);}
.cmp-head b{display:flex;align-items:center;gap:10px;font-size:20px;color:var(--text);}
.cmp-legend{display:flex;gap:22px;font-size:16px;color:#374151;}
.cmp-legend span{display:flex;align-items:center;gap:7px;}
.cmp-legend i{width:16px;height:16px;border-radius:4px;display:inline-block;}
.bar-item{margin-top:26px;}
.bar-lbl{display:flex;justify-content:space-between;font-size:17px;margin-bottom:10px;}
.bar-lbl b{color:var(--text);} .bar-lbl em{font-style:normal;color:#9aa1ad;font-weight:400;}
.bar-lbl .r{color:#4b5563;font-size:15.5px;} .bar-lbl .r b.g{color:var(--green-d);} .bar-lbl .r b.p{color:var(--purple-d);}
.track{height:9px;background:#eef0f3;border-radius:6px;margin:6px 0;overflow:hidden;}
.fill{height:100%;border-radius:6px;}

/* ─── 입력 폼 ─── */
.st-key-formcard{padding:34px 34px 30px;}
.pg-head{display:flex;align-items:flex-start;gap:12px;}
.pg-head h2{margin:0;padding:0;font-size:24px;font-weight:700;color:var(--text);}
.pg-head p{margin:6px 0 0;color:#6b7280;font-size:15.5px;}
.sect{border-radius:10px;padding:12px 18px;font-size:16.5px;font-weight:700;display:flex;align-items:center;gap:10px;}
.sect.auto{background:#f3f4f6;color:#1f2a55;}
.sect.user{background:#f1faf5;color:#1f2a55;border:1px solid #e0f0e7;}
.hr{border-top:1px solid var(--line);margin:10px 0;}
.subh{font-size:17px;font-weight:700;color:var(--text);margin:4px 0 0;}
.st-key-formcard label p{font-size:16px !important;color:#4b5563 !important;}
.st-key-formcard input, .st-key-formcard textarea{font-size:16px !important;color:var(--text) !important;}
.st-key-formcard [data-testid="stTextInputRootElement"], .st-key-formcard [data-testid="stTextAreaRootElement"]{
  border:1px solid #d5dae2 !important;border-radius:10px !important;background:#fff !important;height:auto !important;}
.st-key-formcard [data-testid="stTextInputRootElement"] input{padding:12px 16px !important;background:transparent !important;height:46px;}
.st-key-formcard [data-testid="stTextAreaRootElement"] textarea{padding:12px 16px !important;background:transparent !important;}
.st-key-formcard input:disabled{background:#f3f4f6 !important;-webkit-text-fill-color:#374151 !important;
  font-family:'JetBrains Mono',monospace !important;font-size:15px !important;}
.st-key-formcard [data-testid="stTextInputRootElement"]:has(input:disabled){background:#f3f4f6 !important;border-color:#e5e7eb !important;}
.st-key-savebtn{display:flex;justify-content:flex-end;}
.st-key-savebtn button{background:#5c937f !important;border:none !important;color:#fff !important;border-radius:10px !important;
  padding:10px 22px !important;font-weight:700 !important;box-shadow:0 2px 4px rgba(0,0,0,.08);}
.st-key-savebtn button p{font-size:16px !important;font-weight:700 !important;}
.st-key-savebtn button:hover{background:#4e8270 !important;}
[class*="st-key-doc_"]{border:1px solid var(--line);border-radius:12px;padding:16px 18px;background:#fff;}
[class*="st-key-doc_"] label p{color:var(--text) !important;font-size:16.5px !important;}
[class*="st-key-doc_"] .doc-desc{color:#8a919d;font-size:15px;margin:-10px 0 0 36px;}
[class*="st-key-doc_"] [data-testid="stCheckbox"] label > div:first-of-type{width:22px !important;height:22px !important;border-radius:5px !important;
  background:#4f6bdc !important;border-color:#4f6bdc !important;margin-right:8px;}
[class*="st-key-doc_"] [data-testid="stCheckbox"][data-selected="false"] label > div:first-of-type{background:#fff !important;border-color:#c3c8d1 !important;}
[class*="st-key-doc_"] [data-testid="stCheckbox"] label{gap:6px;}

/* ─── 코드북 ─── */
.st-key-cbcard{padding:30px 34px 34px;}
.st-key-cbtop{border-bottom:1px solid var(--line);padding-bottom:18px;}
.st-key-cbtop [data-testid="stHorizontalBlock"]{align-items:center;}
.st-key-cbsearch input, .st-key-cbfilter input{font-size:16px !important;background:transparent !important;}
.st-key-cbsearch [data-testid="stTextInputRootElement"]{height:46px !important;border:1px solid #d5dae2 !important;border-radius:10px !important;background:#fff !important;padding-left:34px;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%239aa1ad' stroke-width='2' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cpath d='m20 20-3.5-3.5'/%3E%3C/svg%3E") !important;
  background-repeat:no-repeat !important;background-size:18px !important;background-position:12px center !important;}
.st-key-cbsearch input{background:transparent !important;}
.st-key-cbfilter [role="group"]{min-height:46px;border:1px solid #d5dae2 !important;border-radius:10px !important;background:#fff !important;}
.st-key-cbtable{border:1px solid var(--line);border-radius:14px;overflow:hidden;gap:0 !important;}
.st-key-cbtable > div{gap:0 !important;}
.st-key-cbtable [data-testid="stHorizontalBlock"]{align-items:center;gap:14px;padding:0 18px;}
.st-key-cbhead{background:#f6f7f9;border-bottom:1px solid var(--line);padding:16px 0;}
.st-key-cbhead p{font-weight:700;color:#2a3140;font-size:16.5px;margin:0;}
[class*="st-key-cbrow_"]{border-bottom:1px solid #eef0f3;padding:14px 0;min-height:84px;display:flex;align-items:center;}
[class*="st-key-cbrow_"]:last-child{border-bottom:none;}
.c-id{font-family:'JetBrains Mono',monospace;color:#6b7280;font-size:15px;line-height:1.5;}
.c-src{font-weight:700;color:var(--text);font-size:16.5px;line-height:1.45;}
.c-tgt{font-family:'JetBrains Mono',monospace;color:#4e8f78;font-size:15.5px;}
.c-txt{color:#2f3644;font-size:16px;line-height:1.45;}
.tag{display:inline-block;font-size:14.5px;padding:2px 8px;border-radius:6px;line-height:1.5;max-width:76px;}
.tag.map{background:#eef1fd;color:#4f63c9;border:1px solid #dde3fb;}
.tag.cln{background:#fdf0f6;color:#b24a83;border:1px solid #f7dbe9;}
.st{display:inline-block;font-size:14px;font-weight:700;padding:3px 9px;border-radius:6px;line-height:1.45;max-width:60px;text-align:center;}
.st.done{background:#e7f6ee;color:#2f7d58;}
.st.rev{background:#fde8ea;color:#c0392b;}
.st.ing{background:#fdf5d8;color:#a77a0c;}
[class*="st-key-del_"] button{background:transparent !important;border:none !important;color:#9aa1ad !important;padding:4px 8px !important;min-height:0 !important;}
[class*="st-key-del_"] button span{font-size:21px !important;}
[class*="st-key-del_"] button:hover{color:#d64545 !important;background:#fdf0f0 !important;}
.empty{padding:40px;text-align:center;color:#9aa1ad;}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# 헤더
# ──────────────────────────────────────────────────────────────
with st.container(key="topbar"):
    h1, h2 = st.columns([1.35, 1])
    with h1:
        st.markdown(f"""<div class="brand"><div class="brand-ic">{icon('db', 28, '#1c2a24', 2)}</div>
        <div><h1>iCReaT 연구데이터 정제 및 기탁 대시보드</h1>
        <p>Clinical &amp; Bio-Data Curation &amp; Mapping Support System</p></div></div>""",
                    unsafe_allow_html=True)
    with h2:
        with st.container(key="projbox"):
            p1, p2 = st.columns([0.32, 1])
            p1.markdown(f'<div class="projlbl">{icon("server", 20, "#c9ced8")} 선택 과제:</div>', unsafe_allow_html=True)
            pid = p2.selectbox("과제", list(PROJECTS), label_visibility="collapsed", key="pid",
                               format_func=lambda k: f"[{k}] {PROJECTS[k]['org']} - {PROJECTS[k]['pi']}")
proj = PROJECTS[pid]

# ──────────────────────────────────────────────────────────────
# 좌측 패널
# ──────────────────────────────────────────────────────────────
def donut_svg(segs, center="77%", sub="평균 완성도"):
    r, c = 70, 2 * 3.14159 * 70
    off, arcs = 0, ""
    for pct, col in segs:
        ln = c * pct / 100
        arcs += (f'<circle cx="90" cy="90" r="{r}" fill="none" stroke="{col}" stroke-width="18" '
                 f'stroke-dasharray="{ln:.1f} {c - ln:.1f}" stroke-dashoffset="{-off:.1f}" '
                 f'transform="rotate(150 90 90)"/>')
        off += ln
    return f"""<svg width="180" height="180" viewBox="0 0 180 180">
      <circle cx="90" cy="90" r="{r}" fill="none" stroke="#eef0f3" stroke-width="18"/>{arcs}
      <text x="90" y="92" text-anchor="middle" font-size="27" font-weight="700" fill="#1e2433">{center}</text>
      <text x="90" y="116" text-anchor="middle" font-size="12" fill="#9aa1ad">{sub}</text></svg>"""


def left_panel():
    with st.container(key="menucard"):
        st.markdown('<div class="menu-title">메뉴 관리</div>', unsafe_allow_html=True)
        for key, label in [("dashboard", "대시보드 현황"), ("form", "과제 및 데이터 입력 폼"), ("codebook", "코드북 매핑 & 정제")]:
            with st.container(key=f"nav_{key}"):
                if st.button(label, key=f"btn_{key}", type="primary" if ss.page == key else "secondary",
                             use_container_width=True):
                    ss.page = key
                    st.rerun()
    segs = [(68, "#7fb4a1"), (20, "#e5c25a"), (12, "#eef0f3")]
    legend = "".join(f'<div class="legend-row"><span><i style="background:{c}"></i>{n}</span><b>{v}%</b></div>'
                     for n, v, c in [("정제/매핑 완료", 68, "#7fb4a1"), ("검토/정제 진행중", 20, "#e5c25a"),
                                     ("대기 항목", 12, "#d6dae1")])
    st.markdown(f"""<div class="card dist"><div class="dist-head"><b>{icon('pie', 19, '#4b5563')} 변환/정제 항목 분포</b>
      <span class="badge-live">실시간</span></div><div class="donut">{donut_svg(segs)}</div>{legend}</div>""",
                unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# 페이지: 대시보드
# ──────────────────────────────────────────────────────────────
def page_dashboard():
    st.markdown(f"""<div class="guide"><div style="padding-top:2px">{icon('info', 26, '#4f6bdc')}</div><div>
      <h3>iCReaT 자동 추출 &amp; 연구자 입력 폼 가이드</h3>
      <p>과제명, 과제번호, 수행기관 등 기본 속성은 iCReaT 시스템에서 자동 연동되며,<strong>코드북 항목 매핑, 데이터 정제 규칙, 서류 동의서 항목</strong>은 제공된 폼 양식을 통해 연구자가 직접 채워 넣을 수 있습니다.</p>
      </div></div>""", unsafe_allow_html=True)

    n_clean = sum(1 for r in ss.rules if r["cat"] == "데이터 정제")
    kpis = [
        ("총 기탁 과제 수", "db", "#7fb4a1", f"{len(PROJECTS)}건",
         f'{icon("check", 17, "#4e8f78")}<span style="color:#4e8f78">iCReaT DB 동기화 완료</span>'),
        ("iCReaT 자동 연동 항목", "server", "#4f6bdc", "3 / 6",
         '<span style="color:#4f6bdc">자동 매핑 비율 50%</span>'),
        ("데이터 정제 규칙 수", "layers", "#c98a1e", f"{n_clean}개",
         '<span style="color:#c98a1e">오기·오류 및 결측 정제 포함</span>'),
        ("데이터 리스트 &amp; 변수 개수", "list", "#7a68e6", "65개 변수",
         '<span style="color:#6b7280">임상: 45개 • 유전체: 12개 • 센서: 8개</span>'),
    ]
    st.markdown('<div class="kpis">' + "".join(
        f'<div class="card kpi"><div class="kpi-top">{t}{icon(ic, 22, c)}</div>'
        f'<div class="kpi-val">{v}</div><div class="kpi-sub">{s}</div></div>'
        for t, ic, c, v, s in kpis) + "</div>", unsafe_allow_html=True)

    bars = "".join(f"""<div class="bar-item"><div class="bar-lbl"><b>{p['org']} <em>({p['pi']})</em></b>
        <span class="r">정제율: <b class="g">{p['clean']}%</b>&nbsp;&nbsp;&nbsp;매핑율: <b class="p">{p['map']}%</b></span></div>
        <div class="track"><div class="fill" style="width:{p['clean']}%;background:#7fb4a1"></div></div>
        <div class="track"><div class="fill" style="width:{p['map']}%;background:#7a68e6"></div></div></div>"""
                   for p in PROJECTS.values())
    st.markdown(f"""<div class="card cmp"><div class="cmp-head"><b>{icon('activity', 22, '#4e8f78')} 수행기관별 데이터 정제량 및 매핑량 비교</b>
      <div class="cmp-legend"><span><i style="background:#7fb4a1"></i>정제율(%)</span><span><i style="background:#7a68e6"></i>매핑율(%)</span></div></div>
      {bars}</div>""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# 페이지: 입력 폼
# ──────────────────────────────────────────────────────────────
def page_form():
    with st.container(key="formcard"):
        a, b = st.columns([3, 1])
        a.markdown(f"""<div class="pg-head">{icon('file', 26, '#4b5563')}<div><h2>연구 과제 메타데이터 &amp; 데이터 입력 폼</h2>
          <p>iCReaT 자동 수집 항목과 연구자 추가 입력(없는 데이터 채우기)을 한 곳에서 관리합니다.</p></div></div>""",
                   unsafe_allow_html=True)
        with b:
            with st.container(key="savebtn"):
                if st.button(":material/save: 설정 및 폼 양식 저장", key="save"):
                    st.toast("설정 및 폼 양식이 저장되었습니다.", icon="✅")
        st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sect auto">{icon("server", 19, "#4f6bdc")} [자동 연동] iCReaT 시스템 보유 기본 데이터 (읽기 전용)</div>',
                    unsafe_allow_html=True)
        c1, c2 = st.columns(2, gap="medium")
        c1.text_input("과제 번호 (자동 부여)", value=pid, disabled=True, key=f"f_id_{pid}")
        c2.text_input("수행 기관", value=proj["org"], key=f"f_org_{pid}")
        c1.text_input("과제명", value=proj["title"], key=f"f_title_{pid}")
        c2.text_input("연구 책임자", value=proj["pi"], key=f"f_pi_{pid}")
        st.text_area("수행 및 기탁 목표", value=proj["goal"], height=80, key=f"f_goal_{pid}")
        st.markdown('<div class="hr" style="margin:14px 0"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sect user">{icon("check", 19, "#4e8f78")} [연구자 입력 폼] 없는 데이터 채우기 및 필수 제출 서류 체크</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="subh">필요 첨부 서류 수신/확인 상태</div>', unsafe_allow_html=True)
        cols = st.columns(2, gap="medium")
        for i, (t, d) in enumerate(DOCS):
            with cols[i % 2]:
                with st.container(key=f"doc_{i}"):
                    st.checkbox(t, value=True, key=f"chk_{pid}_{i}")
                    st.markdown(f'<div class="doc-desc">{d}</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# 페이지: 코드북
# ──────────────────────────────────────────────────────────────
STATUS_CLS = {"완료": "done", "검토필요": "rev", "진행중": "ing"}
CAT_CLS = {"항목 매핑": "map", "데이터 정제": "cln"}
WIDTHS = [0.55, 1.9, 1.45, 0.9, 1.1, 2.75, 0.7, 0.35]


def page_codebook():
    with st.container(key="cbcard"):
        with st.container(key="cbtop"):
            a, b, c = st.columns([3.2, 1.05, 0.72], gap="small")
            a.markdown(f"""<div class="pg-head">{icon('layers', 28, '#4e8f78')}<div><h2>코드북 매핑 양식 및 데이터 정제 규칙</h2>
              <p>항목 매핑(코드북 규칙)과 데이터 정제(오기/오류/결측 처리) 규칙을 체계적으로 분류하여 관리합니다.</p></div></div>""",
                       unsafe_allow_html=True)
            with b:
                with st.container(key="cbsearch"):
                    q = st.text_input("검색", placeholder="필드명 또는 규칙 검색...", label_visibility="collapsed")
            with c:
                with st.container(key="cbfilter"):
                    f = st.selectbox("구분", ["전체 구분", "항목 매핑", "데이터 정제"], label_visibility="collapsed")

        rows = [r for r in ss.rules
                if (f == "전체 구분" or r["cat"] == f)
                and (not q or q.lower() in (r["src"] + r["tgt"] + r["rtype"] + r["detail"]).lower())]

        with st.container(key="cbtable"):
            with st.container(key="cbhead"):
                hs = st.columns(WIDTHS)
                for col, h in zip(hs, ["ID", "원본 필드 (iCReaT)", "CoDA 타겟 필드", "구분", "규칙 유형",
                                       "상세 정제/매핑 세부사항", "상태", "삭<br>제"]):
                    col.markdown(f"<p>{h}</p>", unsafe_allow_html=True)
            if not rows:
                st.markdown('<div class="empty">조건에 맞는 규칙이 없습니다.</div>', unsafe_allow_html=True)
            for r in rows:
                with st.container(key=f"cbrow_{r['id']}"):
                    cs = st.columns(WIDTHS)
                    e = html.escape
                    cs[0].markdown(f'<div class="c-id">{r["id"].replace("-", "-<br>")}</div>', unsafe_allow_html=True)
                    cs[1].markdown(f'<div class="c-src">{e(r["src"])}</div>', unsafe_allow_html=True)
                    cs[2].markdown(f'<div class="c-tgt">{e(r["tgt"])}</div>', unsafe_allow_html=True)
                    cs[3].markdown(f'<span class="tag {CAT_CLS[r["cat"]]}">{r["cat"]}</span>', unsafe_allow_html=True)
                    cs[4].markdown(f'<div class="c-txt">{e(r["rtype"])}</div>', unsafe_allow_html=True)
                    cs[5].markdown(f'<div class="c-txt">{e(r["detail"])}</div>', unsafe_allow_html=True)
                    cs[6].markdown(f'<span class="st {STATUS_CLS[r["status"]]}">{r["status"]}</span>', unsafe_allow_html=True)
                    with cs[7]:
                        with st.container(key=f"del_{r['id']}"):
                            if st.button(":material/delete:", key=f"bdel_{r['id']}", help="삭제"):
                                ss.rules = [x for x in ss.rules if x["id"] != r["id"]]
                                st.rerun()

# ──────────────────────────────────────────────────────────────
# 본문
# ──────────────────────────────────────────────────────────────
with st.container(key="body"):
    left, main = st.columns([1, 3.1])
    with left:
        left_panel()
    with main:
        {"dashboard": page_dashboard, "form": page_form, "codebook": page_codebook}[ss.page]()
