import re
from datetime import datetime
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="2027 정시 스나이퍼 v2",
    page_icon="🎯",
    layout="wide",
)

# ---------------------------------------------------------
# 0. 간단 비밀번호 잠금 (Public 저장소 보안용)
# ---------------------------------------------------------
ACCESS_PIN = "2027"  # 원하시는 비밀번호로 변경 가능

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 2027 정시 스나이퍼 v2")
    pin_input = st.text_input("접속 비밀번호를 입력하세요", type="password", placeholder="기본값: 2027")
    if st.button("잠금 해제", type="primary"):
        if pin_input == ACCESS_PIN:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 일치하지 않습니다.")
    st.stop()

# ---------------------------------------------------------
# 1. 20개 대학 정예 학과 DB (2026 입결 + 2027 실제 공식 매핑)
# ---------------------------------------------------------
@st.cache_data
def load_v2_targets():
    data = [
        # Tier 1: 상향 스나이핑 (숭실·단국·인하·아주·국민·광운·과기대·외대글로벌)
        ("Tier 1 (상향 스나이핑)", "다군", "서울과기대", "ST자유전공학부", "std_nat", 84.5, 9.40, 145.0, "20명 모집 충원 145%, 다군 폭풍 추합"),
        ("Tier 1 (상향 스나이핑)", "가군", "서울과기대", "환경공학과", "std_nat", 82.0, 4.80, 92.0, "26명 모집 충원 92%, 수35·탐25"),
        ("Tier 1 (상향 스나이핑)", "가/나", "숭실대", "사회복지학부", "ssu_hum", 83.5, 5.50, 85.0, "2027 영2=1등급 만점 동일! 50-70컷 격차 큼"),
        ("Tier 1 (상향 스나이핑)", "가/나", "숭실대", "산업정보시스템공학과", "ssu_nat", 83.0, 5.20, 90.0, "2027 영2=1등급 만점 동일, 추합 꼬리 긺"),
        ("Tier 1 (상향 스나이핑)", "가/나", "국민대", "미래융합전공(C유형)", "tam1_best_kor_math", 83.5, 6.00, 75.0, "특수 반영비(수학 미반영 등) 유불리"),
        ("Tier 1 (상향 스나이핑)", "가/나", "국민대", "AI빅데이터융합경영", "std_hum", 84.0, 5.40, 70.0, "국민대 일반 백분위 70컷 최하위권"),
        ("Tier 1 (상향 스나이핑)", "나군", "단국대(죽전)", "인공지능학과", "dku_nat", 79.0, 5.79, 60.0, "간판 대비 작년 백분위 70컷 79"),
        ("Tier 1 (상향 스나이핑)", "다군", "단국대(죽전)", "과학교육과", "dku_nat", 76.0, 7.50, 208.0, "충원율 208%, 다군 최저 74 구간"),
        ("Tier 1 (상향 스나이핑)", "가/나", "인하대", "어문·인문하위", "std_hum", 81.5, 6.10, 85.0, "인하대 인문·어문 막판 추합 스나이핑"),
        ("Tier 1 (상향 스나이핑)", "가/나", "아주대", "환경안전공학과", "std_nat", 81.0, 7.40, 80.0, "자연계 하위 스나이핑"),
        ("Tier 1 (상향 스나이핑)", "다군", "아주대", "행정학과", "std_hum", 83.0, 13.30, 110.0, "높은 경쟁률 속 충원 다수 발생"),
        ("Tier 1 (상향 스나이핑)", "가군", "광운대", "전자융합공학과", "kwu_nat", 81.2, 6.70, 88.9, "영2 감점 2점, 인서울 공대 상향"),
        ("Tier 1 (상향 스나이핑)", "가군", "광운대", "건축학과", "kwu_nat", 83.3, 6.10, 107.1, "충원율 107.1% 고회전"),

        # Tier 2: 인서울·수도권 탐1·우수순·반영비 개편 주력 (외대글로벌·가톨릭·가천·명지·상명·인천·경기·한성)
        ("Tier 2 (주력·유리)", "다군", "한국외대(글로벌)", "자유전공학부(글로벌)", "hufs_b", 77.5, 6.20, 110.0, "102명 대규모 + 인문B(수35·영15, 2등급 198점)"),
        ("Tier 2 (주력·유리)", "가/나", "한국외대(글로벌)", "인문·지역학", "hufs_a", 76.5, 5.80, 75.0, "2027 반영비율 개편 혼선 틈새"),
        ("Tier 2 (주력·유리)", "다/가", "가톨릭대", "무전공·자전(일반Ⅱ)", "tam1_pick1_433", 79.0, 6.50, 95.0, "국어 삭제! 기하40+영30+세계사30"),
        ("Tier 2 (주력·유리)", "가군", "가톨릭대", "인문사회계열(일반Ⅰ)", "tam1_best_kor_math", 79.0, 5.50, 70.0, "국수 우수 35/25 + 영20 + 탐(1)20"),
        ("Tier 2 (주력·유리)", "가/나/다", "가천대", "AI인문·자전(일반1)", "tam1_best3_432", 81.0, 6.20, 85.0, "백분위: 국수 40/30 + 영탐(1) 20/10"),
        ("Tier 2 (주력·유리)", "가/나/다", "가천대", "경영·공학(일반2)", "tam1_best3_432", 80.5, 6.80, 90.0, "등급 활용(세계사1·영2 교차 계산)"),
        ("Tier 2 (주력·유리)", "다/나", "한성대", "상상력인재학부", "tam1_best4_4321", 78.5, 7.20, 105.0, "서울권 무전공! 우수순 40/30/20/10"),
        ("Tier 2 (주력·유리)", "가/나/다", "인천대", "일본지역문화학과", "std_hum", 78.0, 8.20, 163.6, "국립대 + 충원율 163.6% 1위"),
        ("Tier 2 (주력·유리)", "가/나/다", "인천대", "독어독문학과", "std_hum", 78.0, 7.90, 145.5, "충원율 145.5% 고회전 비인기 어문"),
        ("Tier 2 (주력·유리)", "가/다", "경기대", "자유전공학부", "tam1_math35", 79.0, 6.40, 80.0, "A/B형 자동 유리적용 + 탐(1)"),
        ("Tier 2 (주력·유리)", "나/다", "상명대(서울)", "자연·인문", "tam1_nat_giha10", 81.0, 6.10, 75.0, "탐(1) + 자연 기하 10% 가산"),
        ("Tier 2 (주력·유리)", "가/나/다", "명지대", "인문사회·경영", "tam1_hum", 81.5, 5.90, 70.0, "탐구 1과목(세계사) 반영"),

        # Tier 3: 지거국 6개교 정밀 공략 (부산·경북·전남·전북·충남·충북)
        ("Tier 3 (지거국)", "가군", "부산대", "유아교육과", "pusan_hum", 78.0, 10.50, 133.0, "영2 감점 2점, 한국사+10, 충원 133%"),
        ("Tier 3 (지거국)", "가군", "부산대", "특수교육과", "pusan_hum", 78.0, 7.00, 83.0, "부산대 가군 하위 컷 + 고회전"),
        ("Tier 3 (지거국)", "가군", "부산대", "독어독문학과", "pusan_hum", 79.0, 6.09, 64.0, "11명 모집, 사탐2(93%) 강점"),
        ("Tier 3 (지거국)", "가군", "부산대", "고고학과", "pusan_hum", 80.0, 5.63, 100.0, "충원율 100%, 소신 스나이핑"),
        ("Tier 3 (지거국)", "나군", "부산대", "사학과", "pusan_hum", 79.0, 6.73, 64.0, "나군 인문 컷 하위권"),
        ("Tier 3 (지거국)", "가군", "경북대", "사학과", "knu_hum", 78.0, 9.71, 129.0, "영2 -3.75점, 충원 129%"),
        ("Tier 3 (지거국)", "가군", "경북대", "산림과학조경학부", "knu_nat", 76.0, 7.83, 50.0, "대구캠 자연 사탐 허용"),
        ("Tier 3 (지거국)", "나군", "경북대", "자율전공학부", "knu_free", 79.0, 4.35, 60.0, "78명 대규모, 국250·수250·영100·탐200"),
        ("Tier 3 (지거국)", "나군", "경북대", "고고인류학과", "knu_hum", 76.0, 9.00, 0.0, "나군 인문 평균백분위 최저(76)"),
        ("Tier 3 (지거국)", "나군", "경북대", "경제통상학부", "knu_hum", 78.0, 4.71, 39.0, "28명 대규모 모집"),
        ("Tier 3 (지거국)", "가/나", "전남대", "정치외교학과", "jnu_hum", 77.0, 6.50, 157.0, "세계사 표점비율 유리(단, 영2 -10점)"),
        ("Tier 3 (지거국)", "가군", "전남대", "경영학부", "jnu_hum", 78.0, 3.36, 65.0, "56명 대규모 저경쟁(3.36:1)"),
        ("Tier 3 (지거국)", "가군", "전북대", "국어교육과", "jbnu_hum", 75.0, 5.70, 167.0, "영2 27/30점, 충원율 167%"),
        ("Tier 3 (지거국)", "가군", "전북대", "농업생명과학계열", "jbnu_hum", 74.0, 6.50, 80.0, "충원 51명 대량 추합"),
        ("Tier 3 (지거국)", "가군", "충남대", "화학공학교육과", "cnu_hum", 70.0, 4.50, 50.0, "탐구 30% 반영 안정선"),
        ("Tier 3 (지거국)", "나군", "충남대", "중어중문·언어학과", "cnu_hum", 72.0, 5.00, 55.0, "사탐 평균 93% 안정 방어"),
        ("Tier 3 (지거국)", "나군", "충북대", "건축공학과", "cbnu_nat", 66.0, 4.13, 60.0, "확실한 안전 방어선"),
    ]
    cols = ["티어", "모집군", "대학", "모집단위", "공식키", "작년70컷", "작년경쟁률", "작년충원율", "핵심포인트"]
    return pd.DataFrame(data, columns=cols)

def eng_score_pct(grade: int, penalty_level: str = "normal") -> float:
    # 대학별 영어 2등급 실질 방어력을 백분위 등가로 보정
    if penalty_level == "zero":  # 숭실대 (2등급=1등급 만점 동일)
        return {1: 99.0, 2: 99.0, 3: 90.0, 4: 75.0}.get(grade, 50.0)
    elif penalty_level == "tiny":  # 외대·부산대·경북대·전북대 (2등급 감점 1.5~3.75점)
        return {1: 99.0, 2: 95.5, 3: 86.0, 4: 70.0}.get(grade, 50.0)
    elif penalty_level == "heavy":  # 전남대 등 (2등급 감점 10점)
        return {1: 99.0, 2: 83.0, 3: 70.0, 4: 55.0}.get(grade, 40.0)
    else:  # 일반 수도권/국립
        return {1: 98.5, 2: 91.5, 3: 80.0, 4: 65.0}.get(grade, 45.0)

def calc_v2_score(rule: str, kp: float, mp: float, ks: float, ms: float, eg: int, t1p: float, t2p: float, t1s: float, t2s: float, giha: bool):
    tb = max(t1p, t2p)
    ta = (t1p + t2p) / 2.0
    km_hi, km_lo = max(kp, mp), min(kp, mp)

    # 1) 대학별 체감 백분위 계산
    if rule == "ssu_hum":
        ep = eng_score_pct(eg, "zero")
        eff = kp * 0.35 + mp * 0.25 + ep * 0.20 + ta * 0.20
    elif rule == "ssu_nat":
        ep = eng_score_pct(eg, "zero")
        eff = kp * 0.20 + mp * 0.35 + ep * 0.20 + ta * 0.25
    elif rule == "hufs_b":
        ep = eng_score_pct(eg, "tiny")
        eff = kp * 0.30 + mp * 0.35 + ep * 0.15 + ta * 0.20
    elif rule == "hufs_a":
        ep = eng_score_pct(eg, "tiny")
        eff = kp * 0.30 + mp * 0.30 + ep * 0.20 + ta * 0.20
    elif rule == "tam1_pick1_433":
        ep = eng_score_pct(eg, "normal")
        eff = km_hi * 0.40 + ep * 0.30 + tb * 0.30
    elif rule == "tam1_best3_432":
        ep = eng_score_pct(eg, "normal")
        et_hi, et_lo = max(ep, tb), min(ep, tb)
        eff = km_hi * 0.40 + km_lo * 0.30 + et_hi * 0.20 + et_lo * 0.10
    elif rule == "tam1_best4_4321":
        ep = eng_score_pct(eg, "normal")
        s = sorted([kp, mp, ep, tb], reverse=True)
        eff = s[0] * 0.40 + s[1] * 0.30 + s[2] * 0.20 + s[3] * 0.10
    elif rule == "tam1_best_kor_math":
        ep = eng_score_pct(eg, "normal")
        eff = km_hi * 0.35 + km_lo * 0.25 + ep * 0.20 + tb * 0.20
    elif rule == "tam1_math35":
        ep = eng_score_pct(eg, "normal")
        eff = mp * 0.35 + kp * 0.30 + ep * 0.20 + tb * 0.15
    elif rule == "tam1_hum":
        ep = eng_score_pct(eg, "normal")
        eff = kp * 0.35 + mp * 0.25 + ep * 0.20 + tb * 0.20
    elif rule == "tam1_nat_giha10":
        ep = eng_score_pct(eg, "normal")
        m_adj = min(mp * (1.10 if giha else 1.0), 100.0)
        eff = kp * 0.25 + m_adj * 0.35 + ep * 0.20 + tb * 0.20
    elif rule == "pusan_hum":
        ep = eng_score_pct(eg, "tiny")
        eff = kp * 0.30 + mp * 0.25 + ep * 0.20 + ta * 0.25
    elif rule == "knu_hum":
        ep = eng_score_pct(eg, "tiny")
        eff = (kp * 300 + mp * 200 + ep * 100 + ta * 200) / 800.0
    elif rule == "knu_free":
        ep = eng_score_pct(eg, "tiny")
        eff = (kp * 250 + mp * 250 + ep * 100 + ta * 200) / 800.0
    elif rule == "knu_nat":
        ep = eng_score_pct(eg, "tiny")
        eff = (kp * 200 + mp * 300 + ep * 100 + ta * 200) / 800.0
    elif rule == "jnu_hum":
        ep = eng_score_pct(eg, "heavy")
        eff = kp * 0.30 + mp * 0.20 + ep * 0.20 + ta * 0.30
    elif rule in ("jbnu_hum", "cnu_hum"):
        ep = eng_score_pct(eg, "tiny")
        eff = kp * 0.25 + mp * 0.25 + ep * 0.20 + ta * 0.30
    elif rule == "cbnu_nat":
        ep = eng_score_pct(eg, "normal")
        eff = kp * 0.20 + mp * 0.30 + ep * 0.20 + ta * 0.30
    elif rule == "kwu_nat":
        ep = eng_score_pct(eg, "tiny")
        eff = kp * 0.20 + mp * 0.35 + ep * 0.20 + ta * 0.25
    elif rule == "dku_nat":
        ep = eng_score_pct(eg, "normal")
        eff = kp * 0.20 + mp * 0.35 + ep * 0.15 + ta * 0.30
    elif rule == "std_nat":
        ep = eng_score_pct(eg, "normal")
        eff = kp * 0.20 + mp * 0.35 + ep * 0.20 + ta * 0.25
    else:
        ep = eng_score_pct(eg, "normal")
        eff = (kp + mp + ta) / 3.0

    # 2) 지거국 실제 1,000점 환산 추정치 (2026 요강 공식 기반)
    univ_1000 = None
    t_sum = t1s + t2s
    if rule == "pusan_hum":
        e_pt = {1: 200, 2: 198, 3: 195, 4: 190}.get(eg, 185)
        univ_1000 = round(ks * 1.5 + ms * 1.25 + t_sum * 1.25 + e_pt + 10.0, 2)
    elif rule.startswith("knu_"):
        e_pen = {1: 0, 2: -3.75, 3: -10.0, 4: -16.25}.get(eg, -22.5)
        if rule == "knu_hum":
            base = (ks * 1.5 + ms * 1.0 + 100.0 + t_sum * 1.0) * 1.25
        elif rule == "knu_free":
            base = (ks * 1.25 + ms * 1.25 + 100.0 + t_sum * 1.0) * 1.25
        else:
            base = (ks * 1.0 + ms * 1.5 + 100.0 + t_sum * 1.0) * 1.25
        univ_1000 = round(base + e_pen + 10.0, 2)
    elif rule == "jnu_hum":
        # 전국 최고 표점(가정치 국140/수142/탐70) 대비 비율 예시
        e_pt = {1: 200, 2: 190, 3: 180, 4: 170}.get(eg, 160)
        univ_1000 = round((ks / 140) * 300 + (ms / 142) * 200 + (t_sum / 140) * 300 + e_pt + 10.0, 2)

    return round(eff, 2), univ_1000

# ---------------------------------------------------------
# 2. 사이드바: 내 성적 입력 (가채점 기본값 → 12월 실채점 수정)
# ---------------------------------------------------------
st.sidebar.header("📝 내 2027 수능 성적표")
kp = st.sidebar.number_input("국어 (언매) 백분위", 0.0, 100.0, 68.0, 0.5)
ks = st.sidebar.number_input("국어 표준점수", 50.0, 160.0, 112.0, 1.0)
mp = st.sidebar.number_input("수학 (기하) 백분위", 0.0, 100.0, 72.5, 0.5)
ms = st.sidebar.number_input("수학 표준점수", 50.0, 160.0, 116.0, 1.0)
giha = st.sidebar.checkbox("미적/기하 선택 가산 반영", value=True)
eg = st.sidebar.selectbox("영어 등급", [1, 2, 3, 4, 5], index=1)
t1p = st.sidebar.number_input("탐구1 (세계사) 백분위", 0.0, 100.0, 97.5, 0.5)
t1s = st.sidebar.number_input("탐구1 표준점수", 30.0, 100.0, 68.5, 0.5)
t2p = st.sidebar.number_input("탐구2 (생윤) 백분위", 0.0, 100.0, 89.0, 0.5)
t2s = st.sidebar.number_input("탐구2 표준점수", 30.0, 100.0, 61.0, 0.5)

simple_avg = round((kp + mp + (t1p + t2p) / 2.0) / 3.0, 2)
st.sidebar.divider()
st.sidebar.metric("국수탐(2) 단순 평균", f"{simple_avg}%")
st.sidebar.metric("국수탐(2) 표점 합", f"{round(ks + ms + t1s + t2s, 1)}점")

# ---------------------------------------------------------
# 3. 메인 계산 & 세션 DB 관리
# ---------------------------------------------------------
if "custom_df" not in st.session_state:
    st.session_state.custom_df = load_v2_targets().copy()

df = st.session_state.custom_df.copy()
res = df["공식키"].apply(lambda r: calc_v2_score(r, kp, mp, ks, ms, eg, t1p, t2p, t1s, t2s, giha))
df["내체감백분위"] = [x[0] for x in res]
df["추정환산(1000)"] = [x[1] for x in res]
df["마진"] = (df["내체감백분위"] - df["작년70컷"]).round(2)
df["스나이핑지수"] = (df["마진"] + (df["작년충원율"] / 100.0) * 1.5).round(2)

def judge(m):
    if m >= 2.0:
        return "🟢 안정/적정"
    elif m >= -1.0:
        return "🟡 소신/적정"
    elif m >= -4.0:
        return "🟠 스나이핑"
    else:
        return "🔴 초상향"

df["판정"] = df["마진"].apply(judge)

st.title("🎯 2027 정시 스나이퍼 v2 (20개 대학 정밀 엔진)")

t1, t2, t3, t4 = st.tabs([
    "📊 20개 대학 유불리·편집",
    "🩻 진학사 표본 X-레이",
    "📡 20개 대학 일괄 크롤러",
    "🌪️ 전국 CSV 깔때기",
])

with t1:
    c1, c2, c3 = st.columns(3)
    f_tier = c1.multiselect("티어", df["티어"].unique(), default=list(df["티어"].unique()))
    f_gun = c2.multiselect("모집군", df["모집군"].unique(), default=list(df["모집군"].unique()))
    f_judge = c3.multiselect("판정", df["판정"].unique(), default=list(df["판정"].unique()))

    vdf = df[df["티어"].isin(f_tier) & df["모집군"].isin(f_gun) & df["판정"].isin(f_judge)].sort_values("스나이핑지수", ascending=False)

    fig = px.scatter(
        vdf,
        x="작년70컷",
        y="내체감백분위",
        size="작년충원율",
        color="판정",
        hover_name="대학",
        hover_data=["모집단위", "모집군", "마진", "스나이핑지수", "추정환산(1000)"],
        title="20개 대학 42+ 정예 학과 포지셔닝 (점선 위 = 작년 70컷 초과)",
    )
    fig.add_shape(type="line", x0=65, y0=65, x1=86, y1=86, line=dict(color="gray", dash="dash"))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        vdf[["판정", "티어", "모집군", "대학", "모집단위", "내체감백분위", "작년70컷", "마진", "작년충원율", "스나이핑지수", "추정환산(1000)", "핵심포인트"]],
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("➕ 학과 직접 추가하기 (12월 수시 이월·추가 학과 입력용)"):
        with st.form("add_dept_form"):
            fc1, fc2, fc3, fc4 = st.columns(4)
            n_tier = fc1.selectbox("티어", ["Tier 1 (상향 스나이핑)", "Tier 2 (주력·유리)", "Tier 3 (지거국)"])
            n_gun = fc2.selectbox("모집군", ["가군", "나군", "다군"])
            n_univ = fc3.text_input("대학명", placeholder="예: 숭실대")
            n_dept = fc4.text_input("모집단위", placeholder="예: 철학과")
            fc5, fc6, fc7, fc8 = st.columns(4)
            n_rule = fc5.selectbox("반영공식", ["std_hum", "std_nat", "ssu_hum", "hufs_b", "tam1_best3_432", "tam1_pick1_433", "pusan_hum", "knu_hum", "jnu_hum"])
            n_cut = fc6.number_input("작년70컷(%)", 50.0, 99.0, 78.0, 0.5)
            n_comp = fc7.number_input("작년경쟁률", 0.0, 50.0, 5.0, 0.1)
            n_turn = fc8.number_input("작년충원율(%)", 0.0, 500.0, 80.0, 5.0)
            n_note = st.text_input("메모", placeholder="특이사항 메모")
            if st.form_submit_button("리스트에 추가") and n_univ and n_dept:
                new_row = pd.DataFrame([[n_tier, n_gun, n_univ, n_dept, n_rule, n_cut, n_comp, n_turn, n_note]], columns=st.session_state.custom_df.columns)
                st.session_state.custom_df = pd.concat([st.session_state.custom_df, new_row], ignore_index=True)
                st.success(f"{n_univ} {n_dept} 추가 완료!")
                st.rerun()

with t2:
    st.subheader("진학사 표본 복붙 X-레이 v2 (허수·공포 이탈 시뮬레이터)")
    col_a, col_b = st.columns([2, 1])
    raw_txt = col_a.text_area("진학사 표본 화면 드래그 복사(Ctrl+C) 후 붙여넣기", height=240)
    quota = col_b.number_input("정시 모집인원(명)", 1, 200, 12)
    my_rank = col_b.number_input("모의지원 내 현재 등수", 1, 500, 16)
    esc_upper = col_b.slider("상위 대학 추합으로 빠질 허수 (%)", 0, 80, 30, 5)
    fear_drop = col_b.slider("4칸 경계선 공포로 도망갈 표본 (%)", 0, 50, 15, 5)

    total_drop = min(0.90, (esc_upper + fear_drop) / 100.0)
    real_rank = round(max(0.0, (my_rank - 1) * (1.0 - total_drop)) + 1, 1)

    m1, m2 = st.columns(2)
    m1.metric("이탈 보정 실질 예상 등수", f"{real_rank}등 / {quota}명", delta="합격권 진입!" if real_rank <= quota else f"+{round(real_rank - quota, 1)}명 초과")
    if raw_txt.strip():
        scores = [float(x) for x in re.findall(r"\b\d{3}\.\d+\b", raw_txt)]
        m2.metric("추출된 표본 환산점수 개수", f"{len(scores)}개")
        if scores:
            st.caption(f"표본 최고점: {max(scores)} / 평균: {round(sum(scores)/len(scores), 2)} / 최저점: {min(scores)}")

with t3:
    st.subheader("📡 20개 대학 실시간 경쟁률 일괄 크롤러 & 가속도 모니터")
    st.caption("1월 4~6일 원서접수 기간에 진학사/유웨이 실시간 경쟁률 URL을 아래 표에 넣고 '전체 스캔'을 누르면 한 번에 긁어옵니다.")

    if "url_df" not in st.session_state:
        st.session_state.url_df = pd.DataFrame({
            "대학명": ["숭실대", "단국대", "부산대", "경북대", "가천대"],
            "경쟁률URL": ["", "", "", "", ""],
        })
    if "crawl_logs" not in st.session_state:
        st.session_state.crawl_logs = []

    edited_urls = st.data_editor(st.session_state.url_df, num_rows="dynamic", use_container_width=True)
    st.session_state.url_df = edited_urls

    if st.button("🚀 등록된 URL 전체 실시간 스캔 실행", type="primary"):
        now_str = datetime.now().strftime("%m/%d %H:%M")
        valid_rows = edited_urls[edited_urls["경쟁률URL"].astype(str).str.startswith("http")]
        if valid_rows.empty:
            st.warning("최소 1개 이상의 http로 시작하는 실제 경쟁률 페이지 URL을 입력해 주세요.")
        else:
            for _, row in valid_rows.iterrows():
                u_name, u_url = row["대학명"], row["경쟁률URL"]
                try:
                    r = requests.get(u_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
                    tables = pd.read_html(r.text)
                    st.success(f"[{now_str}] {u_name}: 표 {len(tables)}개 수집 성공!")
                    st.dataframe(tables[0].head(10), use_container_width=True)
                    st.session_state.crawl_logs.append({"시간": now_str, "대학": u_name, "상태": "성공", "표개수": len(tables)})
                except Exception as e:
                    st.error(f"{u_name} 수집 실패: {e}")

with t4:
    st.subheader("전국 입결 CSV 일괄 스캐너")
    up = st.file_uploader("CSV 업로드", type=["csv"])
    lo, hi = st.slider("백분위 70%컷 범위", 50.0, 99.0, (70.0, 85.0), 0.5)
    if up is not None:
        rdf = pd.read_csv(up)
        col = st.selectbox("백분위 열 선택", rdf.columns)
        fdf = rdf[(pd.to_numeric(rdf[col], errors="coerce") >= lo) & (pd.to_numeric(rdf[col], errors="coerce") <= hi)]
        st.dataframe(fdf, use_container_width=True)
