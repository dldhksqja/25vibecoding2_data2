
import streamlit as st
import pandas as pd
import numpy as np
import requests
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt

# -----------------------------
# SGIS AccessToken 발급 함수
# -----------------------------
@st.cache_data(ttl=60 * 60 * 4)
def get_access_token(consumer_key, consumer_secret):
    url = "https://sgisapi.kostat.go.kr/OpenAPI3/auth/authentication.json"
    params = {
        "consumer_key": consumer_key,
        "consumer_secret": consumer_secret
    }
    try:
        response = requests.get(url, params=params)
        result = response.json()
        if result.get("errCd") == "0":
            return result["result"]["accessToken"]
        else:
            st.error(f"AccessToken 발급 오류: {result.get('errMsg')}")
    except Exception as e:
        st.error(f"AccessToken 요청 실패: {e}")
    return None

# -----------------------------
# 주소 → 위경도 변환 (SGIS 지오코딩)
# -----------------------------
def geocode_with_access_token(address, access_token):
    url = "https://sgisapi.kostat.go.kr/OpenAPI3/addr/geocode.json"
    params = {
        "accessToken": access_token,
        "address": address,
        "pagenum": 0,
        "resultcount": 1
    }
    try:
        response = requests.get(url, params=params)
        st.code(f"📡 요청 URL: {response.url}")
        result = response.json()
        if result.get("errCd") == "0":
            coords = result["result"]["resultdata"][0]
            return float(coords["y"]), float(coords["x"])
        else:
            st.warning(f"SGIS 오류: {result.get('errMsg')} (코드: {result.get('errCd')})")
    except Exception as e:
        st.error(f"지오코딩 실패: {e}")
    return None, None

# -----------------------------
# 인구 데이터 불러오기
# -----------------------------
@st.cache_data
def load_population_data():
    df = pd.read_csv("202504_202504_연령별인구현황_월간.csv", encoding="cp949")
    age_columns = [col for col in df.columns if "세" in col or "100세 이상" in col]
    df[age_columns] = df[age_columns].replace(",", "", regex=True).astype(int)
    df["총합"] = df[age_columns].sum(axis=1)
    df_ratio = df.copy()
    df_ratio[age_columns] = df[age_columns].div(df["총합"], axis=0)
    return df, df_ratio, age_columns

# -----------------------------
# 가장 유사한 동 찾기
# -----------------------------
def find_most_similar(df_ratio, age_columns, selected_name):
    target = df_ratio[df_ratio["행정구역"] == selected_name][age_columns].values[0]
    df_ratio["거리"] = df_ratio[age_columns].apply(lambda row: np.abs(row.values - target).sum(), axis=1)
    df_filtered = df_ratio[df_ratio["행정구역"] != selected_name]
    closest_row = df_filtered.sort_values("거리").iloc[0]
    return closest_row["행정구역"], closest_row[age_columns]

# -----------------------------
# 지도 표시 함수
# -----------------------------
def draw_map(center1, center2, name1, name2):
    if not center1 or not center2 or None in center1 or None in center2:
        st.error("❌ 지도에 표시할 위치 정보를 가져오지 못했습니다.")
        return
    center_lat = (center1[0] + center2[0]) / 2
    center_lon = (center1[1] + center2[1]) / 2
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
    folium.Marker(center1, tooltip=name1, popup=name1, icon=folium.Icon(color="blue")).add_to(m)
    folium.Marker(center2, tooltip=name2, popup=name2, icon=folium.Icon(color="green")).add_to(m)
    st_folium(m, width=700, height=500)

# -----------------------------
# 인구 구조 비교 그래프
# -----------------------------
def plot_comparison(name1, data1, name2, data2, age_columns):
    x = range(len(age_columns))
    plt.figure(figsize=(12, 4))
    plt.bar(x, data1, width=0.4, label=name1, alpha=0.7)
    plt.bar([i + 0.4 for i in x], data2, width=0.4, label=name2, alpha=0.7)
    plt.xticks([i + 0.2 for i in x], age_columns, rotation=90, fontsize=6)
    plt.legend()
    plt.title("연령별 인구 비율 비교")
    st.pyplot(plt)

# -----------------------------
# Streamlit 앱 시작
# -----------------------------
st.set_page_config(layout="wide")
st.title("📍 SGIS OAuth 기반 유사 인구 구조 동 찾기 + 지도 시각화")

# 인증키 입력
consumer_key = st.text_input("🔑 SGIS consumer_key (서비스 ID)", type="password")
consumer_secret = st.text_input("🛡 SGIS consumer_secret (보안 Key)", type="password")

# 주소 입력
address_input = st.text_input("🏘 주소(읍면동)를 입력하세요 (예: 서울특별시 송도4동)")

# 데이터 로드
df_raw, df_ratio, age_columns = load_population_data()
matched_rows = df_raw[df_raw["행정구역"].str.contains(address_input, case=False, na=False)] if address_input else pd.DataFrame()

if st.button("분석 및 지도 표시"):
    if not consumer_key or not consumer_secret or not address_input:
        st.warning("모든 정보를 입력해 주세요.")
    elif matched_rows.empty:
        st.error("입력한 주소에 해당하는 동을 찾을 수 없습니다.")
    else:
        access_token = get_access_token(consumer_key, consumer_secret)
        if access_token:
            selected_full_name = matched_rows.iloc[0]["행정구역"] if len(matched_rows) == 1 else st.selectbox("여러 후보가 있습니다. 선택하세요", matched_rows["행정구역"].values)
            similar_name, similar_ratio = find_most_similar(df_ratio, age_columns, selected_full_name)
            user_ratio = df_ratio[df_ratio["행정구역"] == selected_full_name][age_columns].values[0]

            st.success(f"✅ '{selected_full_name}'와 인구 구조가 가장 유사한 동은 → '{similar_name}' 입니다.")
            plot_comparison(selected_full_name, user_ratio, similar_name, similar_ratio, age_columns)

            loc1 = geocode_with_access_token(selected_full_name.split(" (")[0], access_token)
            loc2 = geocode_with_access_token(similar_name.split(" (")[0], access_token)
            draw_map(loc1, loc2, selected_full_name, similar_name)
