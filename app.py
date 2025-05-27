
import pandas as pd
import numpy as np
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import os

# -----------------------------
# SGIS 지오코딩 API (API 인증키 방식)
# -----------------------------
def geocode_with_sgis_key(address, api_key):
    url = "https://sgisapi.kostat.go.kr/OpenAPI3/addr/geocode.json"
    params = {
        "address": address,
        "consumer_key": api_key
    }

    st.code(f"🔍 요청 주소: {address}")
    st.code(f"🔐 사용된 인증키 앞부분: {api_key[:5]}****")

    try:
        response = requests.get(url, params=params)
        st.code(f"📡 요청 URL: {response.url}")
        if response.status_code == 200:
            result = response.json()
            st.json(result)
            if result.get("errCd") == "0":
                lon = float(result["result"]["x"])
                lat = float(result["result"]["y"])
                return lat, lon
            else:
                st.warning(f"SGIS 오류: {result.get('errMsg')} (코드: {result.get('errCd')})")
        else:
            st.warning(f"HTTP 오류: {response.status_code}")
    except Exception as e:
        st.error(f"요청 실패: {e}")
    return None, None

# -----------------------------
# 인구 데이터 로딩
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
# 유사한 동 찾기
# -----------------------------
def find_most_similar(df_ratio, age_columns, selected_name):
    target = df_ratio[df_ratio["행정구역"] == selected_name][age_columns].values[0]
    df_ratio["거리"] = df_ratio[age_columns].apply(lambda row: np.abs(row.values - target).sum(), axis=1)
    df_filtered = df_ratio[df_ratio["행정구역"] != selected_name]
    closest_row = df_filtered.sort_values("거리").iloc[0]
    return closest_row["행정구역"], closest_row[age_columns]

# -----------------------------
# 지도 표시
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
# 인구 그래프
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
# Streamlit App 시작
# -----------------------------
st.set_page_config(layout="wide")
st.title("📍 SGIS API (인증키) 기반 인구 구조 유사 동 찾기 + 지도 표시 (디버깅 포함)")

# API 키 관리
api_key = st.secrets["SGIS_API_KEY"] if "SGIS_API_KEY" in st.secrets else os.getenv("SGIS_API_KEY")
if not api_key:
    api_key = st.text_input("SGIS API 인증키를 입력하세요", type="password")

address_input = st.text_input("주소(읍면동)를 입력하세요 (예: 서울특별시 송도4동)")

df_raw, df_ratio, age_columns = load_population_data()
matched_rows = df_raw[df_raw["행정구역"].str.contains(address_input, case=False, na=False)] if address_input else pd.DataFrame()

if st.button("분석 시작"):
    if not api_key or not address_input:
        st.warning("API 키와 주소를 모두 입력해 주세요.")
    elif matched_rows.empty:
        st.error("입력하신 주소를 포함하는 동을 찾을 수 없습니다.")
    else:
        selected_full_name = matched_rows.iloc[0]["행정구역"] if len(matched_rows) == 1 else st.selectbox("여러 후보가 있습니다. 선택하세요", matched_rows["행정구역"].values)
        similar_name, similar_ratio = find_most_similar(df_ratio, age_columns, selected_full_name)
        user_ratio = df_ratio[df_ratio["행정구역"] == selected_full_name][age_columns].values[0]

        st.success(f"✅ '{selected_full_name}'와 인구 구조가 가장 유사한 동은 → '{similar_name}' 입니다.")
        plot_comparison(selected_full_name, user_ratio, similar_name, similar_ratio, age_columns)

        loc1 = geocode_with_sgis_key(selected_full_name.split(" (")[0], api_key)
        loc2 = geocode_with_sgis_key(similar_name.split(" (")[0], api_key)
        draw_map(loc1, loc2, selected_full_name, similar_name)
