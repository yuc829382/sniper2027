import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# =========================================================
# Page Config & Design System
# =========================================================
st.set_page_config(
    page_title="2027 정시 전략 시뮬레이터 v3 (19개 대학 2026 최신입결)",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-header {
        font-size: 1.85rem;
        font-weight: 800;
        color: #0F172A;
        letter-spacing: -0.02em;
        margin-bottom: 0.25rem;
    }
    .sub-header {
        font-size: 0.95rem;
        color: #475569;
        margin-bottom: 1.25rem;
    }
    .kpi-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 14px 18px;
    }
    .kpi-label {
        font-size: 0.80rem;
        color: #64748B;
        font-weight: 600;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 1.45rem;
        color: #0F172A;
        font-weight: 800;
    }
    .kpi-sub {
        font-size: 0.76rem;
        color: #475569;
        margin-top: 2px;
    }
    .badge-info {
        background-color: #EFF6FF;
        border-left: 4px solid #2563EB;
        padding: 10px 14px;
        border-radius: 6px;
        font-size: 0.88rem;
        color: #1E3A8A;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# Data Loading
# =========================================================
DEFAULT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "univ_2026_master.csv")

@st.cache_data
def load_master_data(file_bytes=None):
    if file_bytes is not None:
        df = pd.read_csv(file_bytes)
    elif os.path.exists(DEFAULT_CSV):
        df = pd.read_csv(DEFAULT_CSV)
    else:
        return pd.DataFrame()

    num_cols = [
        "모집인원", "경쟁률", "충원순위", "충원율", "백분위_70컷_2026",
        "환산점수_70컷", "영어_등급평균", "탐구_반영과목수",
        "국어_비중", "수학_비중", "탐구_비중", "영어_비중",
        "백분위_70컷_2025", "백분위_70컷_2024", "백분위_70컷_2023",
        "백분위_70컷_2022", "백분위_70컷_2021", "전년대비_변화"
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# =========================================================
# Scoring & Classification Engine
# =========================================================
ENG_PENALTY_DEFAULT = {1: 0.0, 2: -0.4, 3: -1.3, 4: -3.0, 5: -5.5, 6: -8.5, 7: -12.0, 8: -16.0, 9: -20.0}

def compute_personalized_scores(df, kor, math, tam1, tam2, eng_grade, math_sel, tam_type, apply_bonus, apply_eng):
    out = df.copy()
    tam_avg2 = (tam1 + tam2) / 2.0
    tam_best1 = max(tam1, tam2)

    # 1) 대학별 탐구 반영과목수 적용 (1과목 vs 2과목)
    tam_applied = np.where(out["탐구_반영과목수"] == 1, tam_best1, tam_avg2)

    # 2) 국·수·탐 정규화 가중평균
    w_sum = out["국어_비중"] + out["수학_비중"] + out["탐구_비중"]
    w_kor = out["국어_비중"] / w_sum
    w_math = out["수학_비중"] / w_sum
    w_tam = out["탐구_비중"] / w_sum

    base_score = w_kor * kor + w_math * math + w_tam * tam_applied

    # 3) 자연/의약학 계열 미적·기하 / 과탐 가산점 체감 보정
    bonus = np.zeros(len(out))
    if apply_bonus:
        is_sci_track = out["계열"].isin(["자연", "의약학/보건"])
        if math_sel == "미적분/기하":
            bonus += np.where(is_sci_track, 1.2, 0.0)
        if tam_type == "과학탐구":
            bonus += np.where(is_sci_track, 1.0, 0.0)

    # 4) 영어 등급 영향력 보정 (대학 영어 평균등급 대비 유불리 + 기본 감점)
    eng_adj = np.zeros(len(out))
    if apply_eng:
        base_pen = ENG_PENALTY_DEFAULT.get(eng_grade, -3.0)
        # 영어 비중이 높거나(0.20 이상) 평균등급이 공개된 경우 상대 보정
        eng_weight_scale = out["영어_비중"] / 0.20
        eng_adj = base_pen * np.clip(eng_weight_scale, 0.5, 1.2)

    out["내_맞춤_백분위"] = (base_score + bonus + eng_adj).clip(0, 100).round(2)
    out["격차"] = (out["내_맞춤_백분위"] - out["백분위_70컷_2026"]).round(2)

    def judge(gap):
        if pd.isna(gap): return "⚪ 판정불가"
        if gap >= 2.5: return "🟢 안정"
        if gap >= 0.5: return "🔵 적정"
        if gap >= -1.5: return "🟡 소신"
        if gap >= -4.0: return "🟠 상향"
        return "🔴 위험"

    out["지원_판정"] = out["격차"].apply(judge)
    return out

TIER_COLORS = {
    "🟢 안정": "#16A34A",
    "🔵 적정": "#2563EB",
    "🟡 소신": "#D97706",
    "🟠 상향": "#EA580C",
    "🔴 위험": "#DC2626",
    "⚪ 판정불가": "#94A3B8",
}

# =========================================================
# Sidebar: Student CSAT Input & Options
# =========================================================
with st.sidebar:
    st.markdown("### 📝 내 수능/모의고사 성적 입력")
    kor_pct = st.number_input("국어 백분위", min_value=0.0, max_value=100.0, value=83.0, step=0.5)
    math_pct = st.number_input("수학 백분위", min_value=0.0, max_value=100.0, value=85.0, step=0.5)
    math_sel = st.radio("수학 선택과목", ["미적분/기하", "확률과통계"], horizontal=True)

    c1, c2 = st.columns(2)
    with c1:
        tam1_pct = st.number_input("탐구1 백분위", min_value=0.0, max_value=100.0, value=88.0, step=0.5)
    with c2:
        tam2_pct = st.number_input("탐구2 백분위", min_value=0.0, max_value=100.0, value=74.0, step=0.5)
    tam_type = st.radio("탐구 응시유형", ["과학탐구", "사회탐구", "사탐+과탐"], horizontal=True)

    eng_grade = st.selectbox("영어 등급", [1, 2, 3, 4, 5, 6, 7, 8, 9], index=1)
    hist_grade = st.selectbox("한국사 등급", [1, 2, 3, 4, 5, 6, 7, 8, 9], index=1)

    st.divider()
    st.markdown("### ⚙️ 정밀 보정 옵션")
    apply_bonus = st.checkbox("자연계 미적·기하/과탐 가산점 체감 반영", value=True)
    apply_eng = st.checkbox("영어 등급 감점 체감 반영", value=True)

    st.divider()
    st.markdown("### 📂 데이터 파일 교체(선택)")
    uploaded_csv = st.file_uploader("커스텀 `univ_2026_master.csv` 업로드", type=["csv"])

raw_df = load_master_data(uploaded_csv)

if raw_df.empty:
    st.error("`univ_2026_master.csv` 파일을 찾을 수 없습니다. `app_v3.py`와 같은 폴더에 배치하거나 사이드바에서 CSV를 업로드해 주세요.")
    st.stop()

scored_df = compute_personalized_scores(
    raw_df, kor_pct, math_pct, tam1_pct, tam2_pct, eng_grade, math_sel, tam_type, apply_bonus, apply_eng
)

# =========================================================
# Header & Executive KPI Ribbon
# =========================================================
st.markdown('<div class="main-header">🎯 2027 정시 전략 시뮬레이터 v3</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">19개 주요 대학(21개 캠퍼스) 2026 최신 입결 + 대교협 2021~2025 5개년 추이 · 대학별 탐구 반영과목수(1 vs 2) 및 반영비율 정밀 계산</div>',
    unsafe_allow_html=True,
)

simple_avg2 = round((kor_pct + math_pct + (tam1_pct + tam2_pct) / 2) / 3, 2)
simple_avg1 = round((kor_pct + math_pct + max(tam1_pct, tam2_pct)) / 3, 2)
tam_diff = round(simple_avg1 - simple_avg2, 2)

pass_cnt = scored_df["지원_판정"].isin(["🟢 안정", "🔵 적정"]).sum()
sos_cnt = (scored_df["지원_판정"] == "🟡 소신").sum()
yoy_med = scored_df["전년대비_변화"].median()

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">단순 평균 백분위 (탐구2 vs 탐구1)</div>
        <div class="kpi-value">{simple_avg2:.1f} <span style="font-size:1rem;color:#2563EB;">/ {simple_avg1:.1f}</span></div>
        <div class="kpi-sub">탐구 1과목 반영 대학 유리폭: <b>+{tam_diff:.2f}%p</b></div>
    </div>""", unsafe_allow_html=True)
with k2:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">지원가능권 (안정+적정)</div>
        <div class="kpi-value">{pass_cnt}개 <span style="font-size:0.95rem;color:#64748B;">/ {len(scored_df)}개 학과</span></div>
        <div class="kpi-sub">소신 지원권(±1.5%p 내외): <b>{sos_cnt}개 학과</b></div>
    </div>""", unsafe_allow_html=True)
with k3:
    tam1_univs = scored_df[scored_df["탐구_반영과목수"] == 1]["대학명"].nunique()
    tam2_univs = scored_df[scored_df["탐구_반영과목수"] == 2]["대학명"].nunique()
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">분석 대학 커버리지</div>
        <div class="kpi-value">19개교 <span style="font-size:0.95rem;color:#64748B;">(21캠퍼스)</span></div>
        <div class="kpi-sub">탐구1과목 {tam1_univs}곳 · 탐구2과목 {tam2_univs}곳</div>
    </div>""", unsafe_allow_html=True)
with k4:
    yoy_str = f"{yoy_med:+.2f}%p" if pd.notna(yoy_med) else "-"
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">2025 → 2026 입결 변화(중앙값)</div>
        <div class="kpi-value">{yoy_str}</div>
        <div class="kpi-sub">대교협 2025 vs 2026 매칭 학과 기준</div>
    </div>""", unsafe_allow_html=True)

st.write("")

# =========================================================
# Tabs
# =========================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 19개 대학 통합 배치 & 맞춤 판정",
    "🧩 가·나·다군 3장 포트폴리오 조합기",
    "📈 5개년 추이 & 권역별 포지셔닝",
    "🔍 데이터 기준 & 출처 X-Ray",
])

# ---------------------------------------------------------
# TAB 1: Integrated Dashboard
# ---------------------------------------------------------
with tab1:
    f1, f2, f3, f4, f5 = st.columns([1.2, 1.5, 1.0, 1.1, 1.2])
    with f1:
        sel_regions = st.multiselect("권역", sorted(scored_df["권역"].unique()), default=sorted(scored_df["권역"].unique()))
    with f2:
        avail_univs = sorted(scored_df[scored_df["권역"].isin(sel_regions)]["대학명"].unique())
        sel_univs = st.multiselect("대학 선택", avail_univs, default=avail_univs)
    with f3:
        sel_guns = st.multiselect("모집군", ["가", "나", "다", "미상"], default=["가", "나", "다"])
    with f4:
        sel_tracks = st.multiselect("계열", sorted(scored_df["계열"].unique()), default=["인문", "자연", "자율/무전공", "의약학/보건"])
    with f5:
        sel_tiers = st.multiselect("판정 구간", ["🟢 안정", "🔵 적정", "🟡 소신", "🟠 상향", "🔴 위험"], default=["🟢 안정", "🔵 적정", "🟡 소신", "🟠 상향"])

    search_kw = st.text_input("🔎 학과명 키워드 검색 (예: 컴퓨터, 전자, 경영, 간호, 자율)", "")

    fdf = scored_df[
        scored_df["권역"].isin(sel_regions)
        & scored_df["대학명"].isin(sel_univs)
        & scored_df["모집군"].isin(sel_guns)
        & scored_df["계열"].isin(sel_tracks)
        & scored_df["지원_판정"].isin(sel_tiers)
    ].copy()

    if search_kw.strip():
        fdf = fdf[fdf["모집단위"].str.contains(search_kw.strip(), case=False, na=False)]

    st.caption(f"검색 결과: **{len(fdf)}개** 모집단위 (정렬: 적정/안정 격차 순)")

    if fdf.empty:
        st.warning("선택한 필터 조건에 맞는 모집단위가 없습니다. 필터를 넓혀 보세요.")
    else:
        plot_df = fdf.copy()
        plot_df["버블크기"] = plot_df["충원율"].fillna(50).clip(20, 300)

        fig = px.scatter(
            plot_df,
            x="백분위_70컷_2026",
            y="내_맞춤_백분위",
            color="지원_판정",
            color_discrete_map=TIER_COLORS,
            size="버블크기",
            size_max=18,
            hover_name="모집단위",
            hover_data={
                "대학명": True,
                "모집군": True,
                "계열": True,
                "백분위_70컷_2026": ":.2f",
                "내_맞춤_백분위": ":.2f",
                "격차": ":+.2f",
                "경쟁률": ":.2f",
                "충원율": ":.1f",
                "탐구_반영과목수": True,
                "버블크기": False,
            },
            title="2026 입결 70%컷 vs 내 맞춤 체감 백분위 (대각선 위쪽 = 합격 유리권)",
            height=520,
        )
        min_v = max(55, min(plot_df["백분위_70컷_2026"].min(), plot_df["내_맞춤_백분위"].min()) - 2)
        max_v = min(100, max(plot_df["백분위_70컷_2026"].max(), plot_df["내_맞춤_백분위"].max()) + 2)
        fig.add_shape(
            type="line", x0=min_v, y0=min_v, x1=max_v, y1=max_v,
            line=dict(color="#64748B", width=1.5, dash="dash")
        )
        fig.update_layout(
            xaxis_title="2026학년도 입결 70%컷 (백분위)",
            yaxis_title="내 대학별 맞춤 체감 백분위",
            legend_title="지원 판정",
            plot_bgcolor="#FFFFFF",
            margin=dict(l=20, r=20, t=50, b=20),
        )
        fig.update_xaxes(showgrid=True, gridcolor="#F1F5F9")
        fig.update_yaxes(showgrid=True, gridcolor="#F1F5F9")
        st.plotly_chart(fig, use_container_width=True)

        disp_cols = [
            "지원_판정", "대학명", "모집군", "계열", "모집단위",
            "백분위_70컷_2026", "내_맞춤_백분위", "격차",
            "백분위_70컷_2025", "전년대비_변화", "모집인원", "경쟁률", "충원순위", "충원율",
            "탐구_반영과목수", "백분위_기준"
        ]
        show_df = fdf[disp_cols].sort_values(by=["격차", "백분위_70컷_2026"], ascending=[False, False]).reset_index(drop=True)
        st.dataframe(
            show_df,
            use_container_width=True,
            height=450,
            column_config={
                "백분위_70컷_2026": st.column_config.NumberColumn("2026 70%컷", format="%.2f"),
                "내_맞춤_백분위": st.column_config.NumberColumn("내 체감점수", format="%.2f"),
                "격차": st.column_config.NumberColumn("점수차", format="%+.2f"),
                "백분위_70컷_2025": st.column_config.NumberColumn("2025 70%컷", format="%.2f"),
                "전년대비_변화": st.column_config.NumberColumn("전년대비", format="%+.2f"),
                "경쟁률": st.column_config.NumberColumn("경쟁률", format="%.2f:1"),
                "충원율": st.column_config.NumberColumn("충원율", format="%.1f%%"),
            }
        )

# ---------------------------------------------------------
# TAB 2: 가/나/다군 3-Card Portfolio Builder
# ---------------------------------------------------------
with tab2:
    st.markdown('<div class="badge-info">정시는 <b>가군 1장 + 나군 1장 + 다군 1장</b> 총 3장의 카드를 씁니다. 각 군에서 내 성적에 맞는 상향/적정/안정 조합을 시뮬레이션하세요.</div>', unsafe_allow_html=True)

    p_col1, p_col2, p_col3 = st.columns(3)
    with p_col1:
        p_tracks = st.multiselect("희망 계열(포트폴리오)", sorted(scored_df["계열"].unique()), default=["자연", "인문", "자율/무전공"], key="pt_tr")
    with p_col2:
        p_kw = st.text_input("선호 학과 키워드 (쉼표로 복수 입력 가능)", "", placeholder="예: 컴퓨터, 전자, 소프트웨어, 경영")
    with p_col3:
        strategy = st.selectbox("추천 조합 전략", [
            "밸런스형 (1상향/소신 + 1적정 + 1안정)",
            "공격형 (2상향/소신 + 1적정)",
            "안정 추구형 (1적정 + 2안정)",
        ])

    pool = scored_df[scored_df["계열"].isin(p_tracks) & scored_df["모집군"].isin(["가", "나", "다"])].copy()
    if p_kw.strip():
        kws = [k.strip() for k in p_kw.split(",") if k.strip()]
        pattern = "|".join(kws)
        pool = pool[pool["모집단위"].str.contains(pattern, case=False, na=False)]

    # Pick best candidates per 군 and tier
    def pick_candidate(gun, target_tiers):
        sub = pool[(pool["모집군"] == gun) & (pool["지원_판정"].isin(target_tiers))].copy()
        if sub.empty:
            sub = pool[pool["모집군"] == gun].copy()
        if sub.empty:
            return pd.DataFrame()
        # Sort by closeness to ideal gap (for 상향/소신: highest gap in tier; for 안정: highest 70%cut)
        return sub.sort_values(by=["격차", "충원율"], ascending=[False, False]).head(12)

    if "밸런스형" in strategy:
        tier_map = {"가": ["🟡 소신", "🟠 상향"], "나": ["🔵 적정"], "다": ["🟢 안정", "🔵 적정"]}
    elif "공격형" in strategy:
        tier_map = {"가": ["🟠 상향", "🟡 소신"], "나": ["🟡 소신", "🟠 상향"], "다": ["🔵 적정", "🟡 소신"]}
    else:
        tier_map = {"가": ["🔵 적정", "🟢 안정"], "나": ["🟢 안정"], "다": ["🟢 안정"]}

    g_cols = st.columns(3)
    selected_cards = []
    for col, gun in zip(g_cols, ["가", "나", "다"]):
        with col:
            st.markdown(f"#### 🎯 {gun}군 후보")
            cand = pick_candidate(gun, tier_map[gun])
            if cand.empty:
                st.info(f"{gun}군에 조건을 만족하는 학과가 없습니다.")
            else:
                cand["라벨"] = cand.apply(lambda r: f"{r['지원_판정']} {r['대학명']} · {r['모집단위']} (컷 {r['백분위_70컷_2026']:.1f} / 격차 {r['격차']:+.1f})", axis=1)
                choice = st.selectbox(f"{gun}군 선택", cand["라벨"].tolist(), key=f"sel_{gun}")
                row = cand[cand["라벨"] == choice].iloc[0]
                selected_cards.append(row)
                st.metric("내 체감점수 vs 2026 70%컷", f"{row['내_맞춤_백분위']:.2f}", f"{row['격차']:+.2f}%p")
                st.write(f"- **모집인원 / 경쟁률**: {int(row['모집인원']) if pd.notna(row['모집인원']) else '-'}명 / {row['경쟁률']:.2f}:1" if pd.notna(row['경쟁률']) else "- **경쟁률**: 미공개")
                st.write(f"- **충원순위 / 충원율**: {int(row['충원순위']) if pd.notna(row['충원순위']) else '-'}번 / {row['충원율']:.1f}%" if pd.notna(row['충원율']) else "- **충원**: 미공개")
                st.write(f"- **탐구반영**: {int(row['탐구_반영과목수'])}과목")

    if selected_cards:
        st.divider()
        port_df = pd.DataFrame(selected_cards)
        fig_p = go.Figure()
        fig_p.add_trace(go.Bar(
            name="2026 70%컷",
            x=[f"{r['모집군']}군: {r['대학명']} {r['모집단위']}" for _, r in port_df.iterrows()],
            y=port_df["백분위_70컷_2026"],
            marker_color="#94A3B8"
        ))
        fig_p.add_trace(go.Bar(
            name="내 맞춤 체감 백분위",
            x=[f"{r['모집군']}군: {r['대학명']} {r['모집단위']}" for _, r in port_df.iterrows()],
            y=port_df["내_맞춤_백분위"],
            marker_color="#2563EB"
        ))
        fig_p.update_layout(
            barmode="group",
            title="선택한 가·나·다군 3장 포트폴리오 비교",
            yaxis_title="백분위",
            yaxis_range=[max(50, port_df["백분위_70컷_2026"].min() - 10), 100],
            height=360,
        )
        st.plotly_chart(fig_p, use_container_width=True)

# ---------------------------------------------------------
# TAB 3: 5-Year Trend & University Positioning
# ---------------------------------------------------------
with tab3:
    t_col1, t_col2 = st.columns([1.2, 2.0])
    with t_col1:
        st.markdown("#### 🔍 학과별 2021~2026 6개년 추이")
        u_sel = st.selectbox("대학 선택", sorted(scored_df["대학명"].unique()), key="tr_u")
        u_sub = scored_df[scored_df["대학명"] == u_sel]
        d_sel = st.selectbox("모집단위 선택", sorted(u_sub["모집단위"].unique()), key="tr_d")
        d_row = u_sub[u_sub["모집단위"] == d_sel].iloc[0]

        yrs = ["2021", "2022", "2023", "2024", "2025", "2026"]
        vals = [
            d_row.get("백분위_70컷_2021", np.nan),
            d_row.get("백분위_70컷_2022", np.nan),
            d_row.get("백분위_70컷_2023", np.nan),
            d_row.get("백분위_70컷_2024", np.nan),
            d_row.get("백분위_70컷_2025", np.nan),
            d_row.get("백분위_70컷_2026", np.nan),
        ]
        tr_df = pd.DataFrame({"학년도": yrs, "70%컷": vals}).dropna()
        if len(tr_df) >= 2:
            fig_t = px.line(tr_df, x="학년도", y="70%컷", markers=True, title=f"{u_sel} {d_sel} 연도별 70%컷 추이")
            fig_t.add_hline(y=d_row["내_맞춤_백분위"], line_dash="dash", line_color="#2563EB", annotation_text=f"내 점수 ({d_row['내_맞춤_백분위']:.1f})")
            fig_t.update_layout(height=350, yaxis_range=[max(50, tr_df["70%컷"].min()-5), 100])
            st.plotly_chart(fig_t, use_container_width=True)
        else:
            st.info(f"2026 70%컷: **{d_row['백분위_70컷_2026']:.2f}** (대교협 과거 연도 동일 학과명 매칭 없음)")

    with t_col2:
        st.markdown("#### 🏫 19개 대학 2026 입결 분포 비교 (계열별)")
        bx_track = st.radio("비교 계열", ["전체(예체능 제외)", "인문", "자연", "자율/무전공"], horizontal=True)
        bx_df = scored_df[scored_df["계열"] != "예체능"] if bx_track == "전체(예체능 제외)" else scored_df[scored_df["계열"] == bx_track]
        order_u = bx_df.groupby("대학명")["백분위_70컷_2026"].median().sort_values(ascending=False).index.tolist()
        fig_b = px.box(
            bx_df,
            x="대학명",
            y="백분위_70컷_2026",
            color="권역",
            category_orders={"대학명": order_u},
            title=f"대학별 2026 70%컷 분포 ({bx_track})",
            height=430,
        )
        fig_b.add_hline(y=simple_avg2, line_dash="dot", line_color="#DC2626", annotation_text=f"내 단순평균(탐2): {simple_avg2:.1f}")
        fig_b.update_layout(xaxis_tickangle=-35, yaxis_title="백분위 70%컷")
        st.plotly_chart(fig_b, use_container_width=True)

# ---------------------------------------------------------
# TAB 4: Data Transparency & Audit
# ---------------------------------------------------------
with tab4:
    st.markdown("#### 🔍 대학별 데이터 기준 · 탐구 반영과목수 · 출처 감사")
    audit_df = scored_df.groupby(["대학명", "권역", "탐구_반영과목수", "백분위_기준", "데이터_출처"], as_index=False).agg(
        모집단위수=("모집단위", "count"),
        평균_70컷=("백분위_70컷_2026", "mean"),
        최저_70컷=("백분위_70컷_2026", "min"),
        최고_70컷=("백분위_70컷_2026", "max"),
        전년매칭수=("백분위_70컷_2025", lambda s: s.notna().sum()),
    ).sort_values(by="평균_70컷", ascending=False)
    st.dataframe(audit_df, use_container_width=True, hide_index=True)

    st.download_button(
        label="📥 통합 마스터 데이터셋 CSV 다운로드 (univ_2026_master.csv)",
        data=scored_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="univ_2026_master_scored.csv",
        mime="text/csv",
    )
