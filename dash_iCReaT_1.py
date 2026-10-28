import streamlit as st
import pandas as pd

# 1. 페이지 설정
st.set_page_config(
    page_title="iCReaT 기탁 대시보드",
    page_icon="📊",
    layout="wide"
)

# 2. 커스텀 CSS (디자인 스타일 반영 & 에러 수정)
st.markdown("""
<style>
    /* 전체 배경색 및 폰트 */
    .stApp {
        background-color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    /* 사이드바 스타일 */
    [data-testid="stSidebar"] {
        background-color: #0f172a !important;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] * {
        color: #cbd5e1 !important;
    }
    
    /* 상단 헤더 스타일 */
    .top-header {
        background-color: #111827;
        padding: 14px 24px;
        border-radius: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        color: white;
    }
    
    /* 지표 카드 스타일 */
    .dash-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px 20px;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03);
    }
    
    /* 가이드 박스 스타일 */
    .guide-box {
        background-color: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 10px;
        padding: 12px 16px;
        color: #1e3a8a;
        font-size: 12.5px;
        line-height: 1.5;
        margin-bottom: 20px;
    }

    /* Streamlit 여백 정리 */
    header[data-testid="stHeader"] {
        background-color: transparent;
    }
</style>
""", unsafe_allow_html=True) # ✅ html 인자로 정상 적용

# --- 샘플 데이터 ---
task_list = [
    {
        'id': 'PRJ-2026-0891',
        'name': '만성 질환 유전체 기반 바이오헬스 임상데이터 통합\n(만성 질환자 5,000명의 유전체 및 임상 의학 데이터 표준화)',
        'institution': '홍길동대학교 병원',
        'pi': '김연구 교수',
        'cleaningRate': 85,
        'mappingRate': 90
    },
    {
        'id': 'PRJ-2026-0412',
        'name': '식품안전 및 HACCP 공정 모니터링 센서 데이터셋\n(식품 제조 공정 실시간 품질 및 안전성 검증 데이터 큐레이션)',
        'institution': '건국대학교 산학협력단',
        'pi': '이공학 박사',
        'cleaningRate': 100,
        'mappingRate': 95
    },
    {
        'id': 'PRJ-2026-1182',
        'name': '삼성서울병원 심뇌혈관 데이터 기반 코호트 기탁 연구\n(심뇌혈관질환 장기 추적 데이터의 코다(CoDA) 이관 표준화)',
        'institution': '삼성서울병원',
        'pi': '박의학 교수',
        'cleaningRate': 42,
        'mappingRate': 60
    }
]

# --- 1. 상단 타이틀 헤더 ---
st.markdown("""
<div class="top-header">
    <div style="display: flex; align-items: center;">
        <span style="background-color: #10b981; padding: 6px 10px; border-radius: 6px; font-weight: bold; font-size: 14px; margin-right: 12px; color: white;">🟢 iCReaT</span>
        <div>
            <div style="font-weight: bold; font-size: 16px;">iCReaT 기탁 대시보드</div>
            <div style="font-size: 11px; color: #94a3b8;">Clinical Research Data Curation & Repository Management</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 2. 사이드바 영역 ---
with st.sidebar:
    st.markdown("<p style='font-size: 12px; color: #94a3b8; margin-bottom: 8px;'>메뉴 관리</p>", unsafe_allow_html=True)
    
    # GitHub 연동 메뉴 삭제됨
    menu = st.radio(
        "메뉴 관리",
        ["대시보드 현황", "과제 및 데이터 입력 폼", "코드북 매핑 & 정제"],
        label_visibility="collapsed"
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 선택 과제 요약 대신 들어간 '전체 기탁 변환 상태' 파이차트 요약 위젯
    st.markdown("""
        <div style="background-color: #1e293b; border-radius: 10px; padding: 14px; border: 1px solid #334155;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 12px; font-weight: bold; color: #f8fafc !important;">전체 기탁 변환 상태</span>
                <span style="font-size: 10px; color: #60a5fa !important;">실시간</span>
            </div>
            <div style="font-size: 11.5px; line-height: 1.8; color: #cbd5e1 !important;">
                <div>🟢 정제/매핑 완료: <b>65%</b></div>
                <div>🔵 진행 중: <b>25%</b></div>
                <div>🔴 미완료/오류: <b>10%</b></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- 3. 메인 선택바 ---
col_head1, col_head2 = st.columns([2, 2])
with col_head1:
    task_options = [f"[{t['id']}] {t['institution']} - {t['pi']}" for t in task_list]
    selected_task = st.selectbox("선택 과제", task_options, label_visibility="collapsed")

# --- 4. 메인 콘텐츠 ---
if menu == "대시보드 현황":
    
    # 가이드 박스
    st.markdown("""
        <div class="guide-box">
            <b>ⓘ iCReaT 자동 추출 & 연구자 입력 폼 가이드</b><br>
            과제명, 과제번호, 수행기관, 목표 등 기본 속성은 iCReaT 시스템에서 자동 연동되며, <b>코드북 항목 매핑, 데이터 정제 규칙, 서류 동의서 항목</b>은 제공된 폼 양식을 통해 사용자가 직접 채워 넣을 수 있습니다.
        </div>
    """, unsafe_allow_html=True)

    # 4개의 지표 카드 (GitHub 카드 -> 변수 유형 요약 카드로 교체)
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.markdown("""
            <div class="dash-card">
                <div style="font-size: 11.5px; color: #64748b; display: flex; justify-content: space-between;"><span>총 기탁 과제 수</span><span>🗂️</span></div>
                <div style="font-size: 20px; font-weight: bold; color: #1e293b; margin: 4px 0;">3건</div>
                <div style="font-size: 11px; color: #10b981;">✓ iCReaT DB 동기화 완료</div>
            </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown("""
            <div class="dash-card">
                <div style="font-size: 11.5px; color: #64748b; display: flex; justify-content: space-between;"><span>iCReaT 자동 연동 항목</span><span>📋</span></div>
                <div style="font-size: 20px; font-weight: bold; color: #1e293b; margin: 4px 0;">3 / 6</div>
                <div style="font-size: 11px; color: #3b82f6;">자동 매칭 비율 50%</div>
            </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown("""
            <div class="dash-card">
                <div style="font-size: 11.5px; color: #64748b; display: flex; justify-content: space-between;"><span>데이터 정제 규칙 수</span><span>⚙️</span></div>
                <div style="font-size: 20px; font-weight: bold; color: #1e293b; margin: 4px 0;">3개</div>
                <div style="font-size: 11px; color: #d97706;">오기·오류 및 결측 정제 포함</div>
            </div>
        """, unsafe_allow_html=True)
        
    with c4:
        st.markdown("""
            <div class="dash-card">
                <div style="font-size: 11.5px; color: #64748b; display: flex; justify-content: space-between;"><span>변수 유형 및 총 개수 요약</span><span>📊</span></div>
                <div style="font-size: 20px; font-weight: bold; color: #1e293b; margin: 4px 0;">총 65개</div>
                <div style="font-size: 11px; color: #64748b;">임상 45 | 유전 12 | 센서 8</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 수행기관별 시각화 바 차트
    st.markdown("#### 📊 수행기관별 연구 과제 및 기탁 준비 현황")
    chart_df = pd.DataFrame([
        {'수행기관': t['institution'].split(' ')[0], '정제율(%)': t['cleaningRate'], '매핑율(%)': t['mappingRate']}
        for t in task_list
    ]).set_index('수행기관')
    
    st.bar_chart(chart_df, height=220)

    st.markdown("<br>", unsafe_allow_html=True)

    # 과제 현황 테이블 (GitHub 소스/선택 제거 -> 정제율/매핑율로 컬럼 분리)
    st.markdown("#### 📋 기탁 과제 데이터 변환 상세 현황")
    
    table_data = []
    for t in task_list:
        table_data.append({
            "과제 번호": t['id'],
            "과제명 및 목표": t['name'],
            "수행 기관 / 책임자": f"{t['institution']} ({t['pi']})",
            "정제율 (%)": f"{t['cleaningRate']}%",
            "매핑율 (%)": f"{t['mappingRate']}%"
        })
    
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

elif menu == "과제 및 데이터 입력 폼":
    st.subheader("📝 과제 및 데이터 입력 폼")
    st.info("연구자가 직접 메타데이터 및 서류를 입력하는 폼입니다.")

elif menu == "코드북 매핑 & 정제":
    st.subheader("🧬 코드북 매핑 & 정제")
    st.info("코드북 항목 매핑 규칙 및 데이터 정제 규칙을 관리합니다.")