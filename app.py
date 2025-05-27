
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import streamlit as st
import matplotlib.pyplot as plt
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# 데이터 불러오기
@st.cache_data
def load_data():
    df = pd.read_csv("202504_202504_연령별인구현황_월간.csv", encoding="cp949")
    df = df.copy()
    age_columns = [col for col in df.columns if "세" in col or "100세 이상" in col]
    df[age_columns] = df[age_columns].replace(",", "", regex=True).astype(int)
    df["총합"] = df[age_columns].sum(axis=1)
    df_ratio = df.copy()
    df_ratio[age_columns] = df[age_columns].div(df["총합"], axis=0)
    return df, df_ratio, age_columns

# 유사한 동 찾기 (인구비율 기반 거리)
def find_most_similar(df_ratio, age_columns, selected_name):
    if selected_name not in df_ratio["행정구역"].values:
        return None, None
    target = df_ratio[df_ratio["행정구역"] == selected_name][age_columns].values[0]
    df_ratio["거리"] = df_ratio[age_columns].apply(lambda row: np.abs(row.values - target).sum(), axis=1)
    df_ratio_filtered = df_ratio[df_ratio["행정구역"] != selected_name]
    closest_row = df_ratio_filtered.sort_values("거리").iloc[0]
    return closest_row["행정구역"], closest_row[age_columns]

# 주소를 위경도로 변환
@st.cache_data
def geocode(address):
    try:
        geolocator = Nominatim(user_agent="geoapiExercises")
        location = geolocator.geocode(address)
        if location:
            return (location.latitude, location.longitude)
    except GeocoderTimedOut:
        return None
    return None

# 지도 그리기
def draw_map(loc1, loc2, name1, name2):
    if loc1 is None or loc2 is None:
        st.error("위치 정보를 가져오지 못했습니다.")
        return
    lat_center = (loc1[0] + loc2[0]) / 2
    lon_center = (loc1[1] + loc2[1]) / 2
    m = folium.Map(location=[lat_center, lon_center], zoom_start=12)
    folium.Marker(loc1, popup=name1, tooltip=name1, icon=folium.Icon(color="blue")).add_to(m)
    folium.Marker(loc2, popup=name2, tooltip=name2, icon=folium.Icon(color="green")).add_to(m)
    st_folium(m, width=700, height=500)

# 인구구조 그래프
def plot_comparison(name1, data1, name2, data2, age_columns):
    x = list(range(len(age_columns)))
    plt.figure(figsize=(12, 4))
    plt.bar(x, data1, width=0.4, label=name1, alpha=0.7)
    plt.bar([i + 0.4 for i in x], data2, width=0.4, label=name2, alpha=0.7)
    plt.xticks([i + 0.2 for i in x], age_columns, rotation=90, fontsize=6)
    plt.legend()
    plt.title("연령별 인구 비율 비교")
    st.pyplot(plt)

# Streamlit 앱 시작
st.set_page_config(layout="wide")
st.title("🧑‍🤝‍🧑 인구 구조가 비슷한 동 찾기")
st.markdown("입력한 동과 연령별 인구 비율이 가장 비슷한 동을 찾아 지도와 함께 보여줍니다.")

df_raw, df_ratio, age_columns = load_data()
user_input = st.text_input("동 이름을 정확히 입력하세요 (예: 서울특별시 종로구 사직동(1111053000))")

if user_input:
    if user_input not in df_raw["행정구역"].values:
        st.error("입력하신 동을 찾을 수 없습니다. 정확히 입력해 주세요.")
    else:
        similar_name, similar_ratio = find_most_similar(df_ratio, age_columns, user_input)
        user_ratio = df_ratio[df_ratio["행정구역"] == user_input][age_columns].values[0]
        st.success(f"'{user_input}'와 인구 구조가 가장 비슷한 동은 ➡️ **'{similar_name}'** 입니다.")

        plot_comparison(user_input, user_ratio, similar_name, similar_ratio, age_columns)

        loc1 = geocode(user_input.split(" (")[0])
        loc2 = geocode(similar_name.split(" (")[0])
        draw_map(loc1, loc2, user_input, similar_name)
