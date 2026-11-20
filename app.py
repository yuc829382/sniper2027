import re
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="2027 정시 스나이퍼 대시보드",
    page_icon="🎯",
    layout="wide",
)

# ---------------------------------------------------------
# 1. 50개 정예 학과 데이터베이스 (2026 입결 + 2027 반영 구조)
# ---------------------------------------------------------
@st.cache_data
def load_50_targets():
    # rule_type 설명:
    # - tam1_best3_432: 국수 우수 40/30, 영탐(1) 우수 20/10 (가천대)
    # - tam1_pick1_433: 국수 중 택1 40, 영 30, 탐(1) 30 (가톨릭대 일반2)
    # - tam1_best4_4321: 국수영탐(1) 우수 순 40/30/20/10 (한성대 상상력인재)
    # - tam1_best4_35252515: 국수영탐(1) 우수 순 35/25/25/15 (삼육대)
    # - tam1_best3_453520: 우수 3영역 45/35/20 + 탐(1) (수원대/한국공학대 일반2)
    # - tam1_best_kor_math: 국수 우수 35/25, 영 20, 탐(1) 20 (가톨릭대 일반1 등)
    # - tam1_math35: 국30 수35 영20 탐(1)15 (경기대 자전 A형)
    # - tam1_hum: 국35 수25 영20 탐(1)20 (명지대/상명대 인문 등)
    # - tam1_nat_giha10: 국25 수35 영20 탐(1)20 + 기하 10% 가산 (상명대 자연/한국공학대)
    # - jigeo_pusan_hum: 부산대 인문 (국30 수25 영20 탐25, 영2 감점 2점)
    # - jigeo_knu_hum: 경북대 인문 (국300 수200 영100 탐200)
    # - jigeo_knu_free: 경북대 자전 (국250 수250 영100 탐200)
    # - jigeo_knu_nat: 경북대 자연 (국200 수300 영100 탐200)
    # - jigeo_cnu_hum: 충남대/전남대/전북대/충북대/강원대 탐구 비중 높음 (국수탐 평균 보정)
    # - std_4_all: 일반 4개 영역 균등/공학 (숭실/국민/아주/광운/단국/과기대/인천/외대)
    data = [
        # Tier 1: 인서울·수도권 중상위 초상향 스나이핑 (13)
        ("Tier 1 (초상향)", "다군", "서울과기대", "ST자유전공학부", "std_4_all", 84.5, 9.40, 145.0, "20명 모집 충원 145%, 다군 폭풍 추합"),
        ("Tier 1 (초상향)", "가군", "서울과기대", "환경공학과", "std_4_all", 82.0, 4.80, 92.0, "26명 모집 충원 92%, 수35·탐25 반영"),
        ("Tier 1 (초상향)", "가/나", "숭실대", "사회복지학부", "std_4_all", 83.5, 5.50, 85.0, "50%컷-70%컷 꼬리 격차 큼, 영2 유리"),
        ("Tier 1 (초상향)", "가/나", "숭실대", "산업정보시스템공학과", "std_4_all", 83.0, 5.20, 90.0, "공학 계열 대표 추합 꼬리 스나이핑"),
        ("Tier 1 (초상향)", "가/나", "국민대", "미래융합전공(C유형)", "tam1_best_kor_math", 83.5, 6.00, 75.0, "특수 반영비(수학 미반영 등) 유불리 체크"),
        ("Tier 1 (초상향)", "가/나", "국민대", "AI빅데이터융합경영", "std_4_all", 84.0, 5.40, 70.0, "국민대 일반 백분위 70%컷 최하위권"),
        ("Tier 1 (초상향)", "나군", "단국대(죽전)", "인공지능학과", "std_4_all", 79.0, 5.79, 60.0, "간판 대비 작년 백분위 70%컷 79 형성"),
        ("Tier 1 (초상향)", "다군", "단국대(죽전)", "과학교육과", "std_4_all", 76.0, 7.50, 208.0, "충원율 208%, 다군 백분위 최저 74 구간"),
        ("Tier 1 (초상향)", "가/나", "아주대", "환경안전공학과", "std_4_all", 81.0, 7.40, 80.0, "자연계 하위 스나이핑"),
        ("Tier 1 (초상향)", "가/나", "아주대", "수학과", "std_4_all", 82.0, 8.70, 75.0, "기하 성적 활용 공학/자연 틈새"),
        ("Tier 1 (초상향)", "다군", "아주대", "행정학과", "std_4_all", 83.0, 13.30, 110.0, "높은 경쟁률 속 충원 다수 발생"),
        ("Tier 1 (초상향)", "가군", "광운대", "전자융합공학과", "std_4_all", 81.2, 6.70, 88.9, "인서울 공대 상향 스나이핑"),
        ("Tier 1 (초상향)", "가군", "광운대", "건축학과", "std_4_all", 83.3, 6.10, 107.1, "충원율 107.1% 고회전"),

        # Tier 2: 인서울·수도권 탐1·우수순 주력 라인 (13)
        ("Tier 2 (주력·유리)", "다/가", "가톨릭대", "무전공·자전(일반Ⅱ)", "tam1_pick1_433", 79.0, 6.50, 95.0, "국어 삭제! 기하40+영30+세계사30"),
        ("Tier 2 (주력·유리)", "가군", "가톨릭대", "인문사회계열(일반Ⅰ)", "tam1_best_kor_math", 79.0, 5.50, 70.0, "국수 우수 35/25 + 영20 + 탐(1)20"),
        ("Tier 2 (주력·유리)", "가/나/다", "가천대", "AI인문·자전(일반1)", "tam1_best3_432", 81.0, 6.20, 85.0, "백분위: 국수 40/30 + 영탐(1) 20/10"),
        ("Tier 2 (주력·유리)", "가/나/다", "가천대", "경영·공학(일반2)", "tam1_best3_432", 80.5, 6.80, 90.0, "등급 활용(세계사1·영2 교차 계산)"),
        ("Tier 2 (주력·유리)", "다/나", "한성대", "상상력인재학부", "tam1_best4_4321", 78.5, 7.20, 105.0, "서울권 무전공! 우수순 40/30/20/10"),
        ("Tier 2 (주력·유리)", "가/나/다", "삼육대", "자유전공·인문", "tam1_best4_35252515", 77.5, 6.50, 85.0, "우수순 35/25/25/15 + 탐(1)"),
        ("Tier 2 (주력·유리)", "가/나/다", "인천대", "일본지역문화학과", "std_4_all", 78.0, 8.20, 163.6, "국립대 + 충원율 163.6% 1위"),
        ("Tier 2 (주력·유리)", "가/나/다", "인천대", "독어독문학과", "std_4_all", 78.0, 7.90, 145.5, "충원율 145.5% 고회전 비인기 어문"),
        ("Tier 2 (주력·유리)", "가/나/다", "인천대", "사회복지학과", "std_4_all", 79.0, 17.10, 130.0, "높은 경쟁률·충원율 동반"),
        ("Tier 2 (주력·유리)", "가/다", "경기대", "자유전공학부", "tam1_math35", 79.0, 6.40, 80.0, "A/B형 자동 유리적용 + 탐(1)"),
        ("Tier 2 (주력·유리)", "나/다", "상명대(서울)", "자연·인문", "tam1_nat_giha10", 81.0, 6.10, 75.0, "탐(1) + 자연 기하 10% 가산"),
        ("Tier 2 (주력·유리)", "가/나/다", "명지대", "인문사회·경영", "tam1_hum", 81.5, 5.90, 70.0, "탐구 1과목(세계사) 반영"),
        ("Tier 2 (주력·유리)", "가/나/다", "한국외대(글로벌)", "인문·지역학", "std_4_all", 76.5, 5.80, 75.0, "2027 반영비율 개편 혼선 틈새"),

        # Tier 3: 지거국 상위 간판 - 부산대·경북대 (14)
        ("Tier 3 (지거국 상위)", "가군", "부산대", "유아교육과", "jigeo_pusan_hum", 78.0, 10.50, 133.0, "부산대 가군 최저컷 + 충원 133%"),
        ("Tier 3 (지거국 상위)", "가군", "부산대", "특수교육과", "jigeo_pusan_hum", 78.0, 7.00, 83.0, "높은 추합 회전율"),
        ("Tier 3 (지거국 상위)", "가군", "부산대", "독어독문학과", "jigeo_pusan_hum", 79.0, 6.09, 64.0, "11명 모집, 사탐2(93%) 강점 발휘"),
        ("Tier 3 (지거국 상위)", "가군", "부산대", "불어불문학과", "jigeo_pusan_hum", 79.0, 6.27, 36.0, "11명 모집, 비인기 어문"),
        ("Tier 3 (지거국 상위)", "가군", "부산대", "고고학과", "jigeo_pusan_hum", 80.0, 5.63, 100.0, "충원율 100%, 소신 스나이핑"),
        ("Tier 3 (지거국 상위)", "나군", "부산대", "사학과", "jigeo_pusan_hum", 79.0, 6.73, 64.0, "나군 인문 컷 하위권"),
        ("Tier 3 (지거국 상위)", "나군", "부산대", "한문학과", "jigeo_pusan_hum", 79.0, 6.78, 78.0, "어문·인문 스나이핑"),
        ("Tier 3 (지거국 상위)", "가군", "경북대", "사학과", "jigeo_knu_hum", 78.0, 9.71, 129.0, "높은 경쟁률 대비 낮은 컷 + 충원 129%"),
        ("Tier 3 (지거국 상위)", "가군", "경북대", "불어불문학과", "jigeo_knu_hum", 80.0, 9.00, 57.0, "가군 인문 환산 최저권"),
        ("Tier 3 (지거국 상위)", "가군", "경북대", "산림과학조경학부", "jigeo_knu_nat", 76.0, 7.83, 50.0, "대구캠 자연 사탐 허용"),
        ("Tier 3 (지거국 상위)", "나군", "경북대", "자율전공학부", "jigeo_knu_free", 79.0, 4.35, 60.0, "78명 대규모, 국250·수250·영100·탐200"),
        ("Tier 3 (지거국 상위)", "나군", "경북대", "고고인류학과", "jigeo_knu_hum", 76.0, 9.00, 0.0, "나군 인문 평균백분위 최저(76)"),
        ("Tier 3 (지거국 상위)", "나군", "경북대", "경제통상학부", "jigeo_knu_hum", 78.0, 4.71, 39.0, "28명 대규모 모집"),
        ("Tier 3 (지거국 상위)", "나군", "경북대", "지리교육과", "jigeo_knu_hum", 77.0, 6.75, 0.0, "나군 사범대 틈새"),

        # Tier 4: 전남·전북·충남·충북·강원 & 수도권 안정 (10)
        ("Tier 4 (지거국·안정)", "가/나", "전남대", "정치외교학과", "jigeo_cnu_hum", 77.0, 6.50, 157.0, "충원율 157%, 세계사 표점 비율 강점"),
        ("Tier 4 (지거국·안정)", "가군", "전남대", "경영학부", "jigeo_cnu_hum", 78.0, 3.36, 65.0, "56명 대규모 저경쟁(3.36:1)"),
        ("Tier 4 (지거국·안정)", "가군", "전북대", "국어교육과", "jigeo_cnu_hum", 75.0, 5.70, 167.0, "충원율 167%, 사범대 안정권"),
        ("Tier 4 (지거국·안정)", "가군", "전북대", "사회과교육학부", "jigeo_cnu_hum", 72.0, 5.40, 60.0, "확실한 안정선"),
        ("Tier 4 (지거국·안정)", "가군", "전북대", "농업생명과학계열", "jigeo_cnu_hum", 74.0, 6.50, 80.0, "충원 51명 대량 추합"),
        ("Tier 4 (지거국·안정)", "가군", "충남대", "화학공학교육과", "jigeo_cnu_hum", 70.0, 4.50, 50.0, "탐구 30% 반영 시 매우 안정"),
        ("Tier 4 (지거국·안정)", "나군", "충남대", "중어중문·언어학과", "jigeo_cnu_hum", 72.0, 5.00, 55.0, "사탐 평균 93%로 안정 방어"),
        ("Tier 4 (지거국·안정)", "나군", "충북대", "건축공학과", "jigeo_cnu_hum", 66.0, 4.13, 60.0, "확실한 안전 방어선"),
        ("Tier 4 (지거국·안정)", "나군", "강원대(춘천)", "컴퓨터공학과", "jigeo_cnu_hum", 67.0, 3.18, 55.0, "저경쟁 최후 방어 보루"),
        ("Tier 4 (지거국·안정)", "가/나/다", "한국공학대", "공학계열(일반2)", "tam1_best3_453520", 72.0, 5.50, 70.0, "우수 3영역 + 기하 10% 가산 + 탐(1)"),
    ]
    cols = ["티어", "모집군", "대학", "모집단위", "반영유형", "작년70컷", "작년경쟁률", "작년충원율", "핵심포인트"]
    return pd.DataFrame(data, columns=cols)

def eng_to_pct(grade: int) -> float:
    mapping = {1: 98.0, 2: 91.0, 3: 80.0, 4: 65.0, 5: 50.0}
    return mapping.get(grade, 40.0)

def calc_effective_percentile(rule_type: str, k_p: float, m_p: float, e_g: int, t1_p: float, t2_p: float, is_giha: bool) -> float:
    e_p = eng_to_pct(e_g)
    t_best = max(t1_p, t2_p)
    t_avg = (t1_p + t2_p) / 2.0
    km_hi, km_lo = max(k_p, m_p), min(k_p, m_p)

    if rule_type == "tam1_pick1_433":  # 가톨릭대 일반2
        return round(km_hi * 0.40 + e_p * 0.30 + t_best * 0.30, 2)
    elif rule_type == "tam1_best3_432":  # 가천대
        et_hi, et_lo = max(e_p, t_best), min(e_p, t_best)
        return round(km_hi * 0.40 + km_lo * 0.30 + et_hi * 0.20 + et_lo * 0.10, 2)
    elif rule_type == "tam1_best4_4321":  # 한성대 상상력
        s = sorted([k_p, m_p, e_p, t_best], reverse=True)
        return round(s[0] * 0.40 + s[1] * 0.30 + s[2] * 0.20 + s[3] * 0.10, 2)
    elif rule_type == "tam1_best4_35252515":  # 삼육대
        s = sorted([k_p, m_p, e_p, t_best], reverse=True)
        return round(s[0] * 0.35 + s[1] * 0.25 + s[2] * 0.25 + s[3] * 0.15, 2)
    elif rule_type == "tam1_best3_453520":  # 수원대/한국공학대 일반2
        m_adj = m_p * (1.10 if is_giha else 1.0)
        s = sorted([k_p, min(m_adj, 100.0), e_p, t_best], reverse=True)
        return round(s[0] * 0.45 + s[1] * 0.35 + s[2] * 0.20, 2)
    elif rule_type == "tam1_best_kor_math":  # 가톨릭대 일반1 등
        return round(km_hi * 0.35 + km_lo * 0.25 + e_p * 0.20 + t_best * 0.20, 2)
    elif rule_type == "tam1_math35":  # 경기대 자전 A형
        return round(m_p * 0.35 + k_p * 0.30 + e_p * 0.20 + t_best * 0.15, 2)
    elif rule_type == "tam1_hum":  # 명지대 등
        return round(k_p * 0.35 + m_p * 0.25 + e_p * 0.20 + t_best * 0.20, 2)
    elif rule_type == "tam1_nat_giha10":  # 상명대 자연 등
        m_adj = min(m_p * (1.10 if is_giha else 1.0), 100.0)
        return round(k_p * 0.25 + m_adj * 0.35 + e_p * 0.20 + t_best * 0.20, 2)
    elif rule_type == "jigeo_pusan_hum":
        return round(k_p * 0.30 + m_p * 0.25 + e_p * 0.20 + t_avg * 0.25, 2)
    elif rule_type == "jigeo_knu_hum":
        return round((k_p * 300 + m_p * 200 + e_p * 100 + t_avg * 200) / 800, 2)
    elif rule_type == "jigeo_knu_free":
        return round((k_p * 250 + m_p * 250 + e_p * 100 + t_avg * 200) / 800, 2)
    elif rule_type == "jigeo_knu_nat":
        return round((k_p * 200 + m_p * 300 + e_p * 100 + t_avg * 200) / 800, 2)
    elif rule_type == "jigeo_cnu_hum":
        return round(k_p * 0.25 + m_p * 0.25 + e_p * 0.20 + t_avg * 0.30, 2)
    else:  # std_4_all (국수탐 단순 평균 기준)
        return round((k_p + m_p + t_avg) / 3.0, 2)

# ---------------------------------------------------------
# 2. 사이드바: 내 성적 입력 (EBS 가채점 기본값 탑재)
# ---------------------------------------------------------
st.sidebar.header("📝 내 2027 수능 성적표")
st.sidebar.caption("기본값은 EBS 최신 가채점 기준이며, 실채점 발표 후 숫자만 수정하세요.")

k_pct = st.sidebar.number_input("국어 (언매) 백분위", 0.0, 100.0, 68.0, 0.5)
k_std = st.sidebar.number_input("국어 표준점수", 50.0, 160.0, 112.0, 1.0)
m_pct = st.sidebar.number_input("수학 (기하) 백분위", 0.0, 100.0, 72.5, 0.5)
m_std = st.sidebar.number_input("수학 표준점수", 50.0, 160.0, 116.0, 1.0)
is_giha = st.sidebar.checkbox("미적분/기하 선택자 가산 적용", value=True)
e_grade = st.sidebar.selectbox("영어 등급", [1, 2, 3, 4, 5], index=1)
t1_pct = st.sidebar.number_input("탐구1 (세계사) 백분위", 0.0, 100.0, 97.5, 0.5)
t2_pct = st.sidebar.number_input("탐구2 (생윤) 백분위", 0.0, 100.0, 89.0, 0.5)

simple_avg = round((k_pct + m_pct + (t1_pct + t2_pct) / 2.0) / 3.0, 2)
st.sidebar.divider()
st.sidebar.metric("국수탐(2) 단순 평균 백분위", f"{simple_avg}%")
st.sidebar.metric("탐구 최상위(세계사)", f"{max(t1_pct, t2_pct)}%")

# ---------------------------------------------------------
# 3. 메인 화면 및 계산
# ---------------------------------------------------------
st.title("🎯 2027 정시 스나이퍼 & 행동심리 분석 대시보드")
st.markdown(f"**단순 평균 백분위 `{simple_avg}%`** 대비 **유리 반영비(탐1·우수순·지거국) 적용 시 체감 백분위 상승분**을 실시간 추적합니다.")

df = load_50_targets().copy()
df["내체감백분위"] = df["반영유형"].apply(
    lambda r: calc_effective_percentile(r, k_pct, m_pct, e_grade, t1_pct, t2_pct, is_giha)
)
df["마진(내점수-70컷)"] = (df["내체감백분위"] - df["작년70컷"]).round(2)
# 스나이핑 지수 = 마진 + 충원율 보정(100%당 +1.5점)
df["스나이핑지수"] = (df["마진(내점수-70컷)"] + (df["작년충원율"] / 100.0) * 1.5).round(2)

def judge_status(margin):
    if margin >= 2.0:
        return "🟢 안정/적정"
    elif margin >= -1.0:
        return "🟡 소신/적정"
    elif margin >= -4.0:
        return "🟠 스나이핑"
    else:
        return "🔴 초상향"

df["지원판정"] = df["마진(내점수-70컷)"].apply(judge_status)

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 50개 정예 학과 유불리",
    "🩻 진학사 표본 복붙 X-레이",
    "🌪️ 전국 CSV 3,000개 깔때기",
    "📡 실시간 경쟁률 크롤러(준비)",
])

# --- TAB 1: 50개 학과 분석 ---
with tab1:
    c1, c2, c3 = st.columns(3)
    sel_tier = c1.multiselect("티어 필터", df["티어"].unique(), default=list(df["티어"].unique()))
    sel_gun = c2.multiselect("모집군 필터", df["모집군"].unique(), default=list(df["모집군"].unique()))
    sel_judge = c3.multiselect("판정 필터", df["지원판정"].unique(), default=list(df["지원판정"].unique()))

    fdf = df[df["티어"].isin(sel_tier) & df["모집군"].isin(sel_gun) & df["지원판정"].isin(sel_judge)]
    fdf = fdf.sort_values(by="스나이핑지수", ascending=False)

    fig = px.scatter(
        fdf,
        x="작년70컷",
        y="내체감백분위",
        size="작년충원율",
        color="지원판정",
        hover_name="대학",
        hover_data=["모집단위", "모집군", "마진(내점수-70컷)", "스나이핑지수"],
        title="작년 70%컷 vs 내 체감 백분위 (원 크기 = 작년 충원율)",
    )
    fig.add_shape(type="line", x0=65, y0=65, x1=86, y1=86, line=dict(color="gray", dash="dash"))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        fdf[["지원판정", "티어", "모집군", "대학", "모집단위", "내체감백분위", "작년70컷", "마진(내점수-70컷)", "작년충원율", "스나이핑지수", "핵심포인트"]],
        use_container_width=True,
        hide_index=True,
    )

# --- TAB 2: 진학사 모의지원 표본 복붙 분석기 ---
with tab2:
    st.subheader("진학사 표본 화면 복붙 X-레이 (허수 이탈 시뮬레이터)")
    st.caption("진학사 모의지원 표본 리스트를 마우스/터치로 드래그 복사(Ctrl+C)해서 아래에 붙여넣으세요.")

    col_a, col_b = st.columns([2, 1])
    sample_text = col_a.text_area(
        "표본 텍스트 붙여넣기",
        height=220,
        placeholder="예시: 1등 705.2 (5칸) / 2등 703.8 (4칸) ... 또는 진학사 표 복사 내용",
    )
    quota = col_b.number_input("해당 학과 정시 모집인원(명)", 1, 200, 10)
    my_rank = col_b.number_input("현재 모의지원 내 등수", 1, 500, 14)
    escape_rate = col_b.slider("내 위 표본 중 타군 추합 이탈 예상률 (%)", 0, 90, 35, 5)

    if sample_text.strip():
        nums = re.findall(r"\d+\.\d+|\d+", sample_text)
        st.info(f"텍스트에서 총 **{len(nums)}개**의 수치 데이터를 감지했습니다. (12월 모의지원 오픈 후 실제 표 형식에 맞춰 자동 파싱 고도화 가능)")

    real_above = max(0.0, (my_rank - 1) * (1.0 - escape_rate / 100.0))
    est_real_rank = round(real_above + 1, 1)
    st.metric(
        "이탈 보정 후 실질 예상 등수",
        f"{est_real_rank}등 / {quota}명 정원",
        delta="합격권 진입!" if est_real_rank <= quota else f"정원 대비 +{round(est_real_rank - quota, 1)}명 초과",
    )

# --- TAB 3: 전국 3,000개 CSV 깔때기 ---
with tab3:
    st.subheader("전국 대학 입결 CSV 일괄 스캐너 (3,000개 → Top 10 압축)")
    st.caption("어디가 등에서 받은 전국 정시 입결 CSV 파일을 올리면, 내 사정권 학과만 즉시 추려줍니다.")
    uploaded = st.file_uploader("입결 CSV 파일 업로드 (열 이름 예시: 대학, 모집단위, 백분위70컷, 충원율)", type=["csv"])
    min_cut, max_cut = st.slider("탐색할 백분위 70%컷 구간 설정", 50.0, 99.0, (70.0, 85.0), 0.5)

    if uploaded is not None:
        raw_df = pd.read_csv(uploaded)
        st.write(f"총 {len(raw_df)}개 학과 로드 완료!")
        cut_col = st.selectbox("백분위 70%컷에 해당하는 열 선택", raw_df.columns)
        filtered = raw_df[(pd.to_numeric(raw_df[cut_col], errors="coerce") >= min_cut) & (pd.to_numeric(raw_df[cut_col], errors="coerce") <= max_cut)]
        st.success(f"사정권 필터링 결과: **{len(filtered)}개** 학과로 압축되었습니다.")
        st.dataframe(filtered, use_container_width=True)

# --- TAB 4: 실시간 경쟁률 크롤러 뼈대 ---
with tab4:
    st.subheader("실시간 원서접수 경쟁률 크롤러 (1월 원서철 가동용)")
    st.caption("원서접수 기간에 진학사 어플라이 / 유웨이어플라이의 대학별 실시간 경쟁률 공개 URL을 입력하면 표를 즉시 읽어옵니다.")
    target_url = st.text_input("실시간 경쟁률 페이지 URL 입력", placeholder="https://apply.jinhakapply.com/...")
    if st.button("테스트 수집 실행") and target_url:
        try:
            res = requests.get(target_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            tables = pd.read_html(str(soup))
            st.success(f"페이지에서 {len(tables)}개의 표를 성공적으로 읽었습니다!")
            st.dataframe(tables[0], use_container_width=True)
        except Exception as e:
            st.error(f"수집 중 오류 발생: {e}")
