import streamlit as st
import geopandas as gpd
from shapely.geometry import Point
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import os

st.set_page_config(page_title="定額エリア判別アプリ", layout="wide")

# ==========================================
# 1. パスワード認証機能
# ==========================================
# ※ 必要に応じて、ここの 'my_password_2026' をお好きな文字列に変更してください。
PASSWORD = "kobe-MKCC"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 セキュリティ認証")
    user_input = st.text_input("パスワードを入力してください：", type="password")
    if st.button("ログイン"):
        if user_input == PASSWORD:
            st.session_state.authenticated = True
            st.success("認証に成功しました！")
            st.rerun()
        else:
            st.error("パスワードが正しくありません。")
    st.stop()  # 認証されるまでこれ以降のコードを実行しない

# ==========================================
# 2. アプリ本編
# ==========================================
st.title("定額エリア判別アプリ")
st.write("「住所・施設名から検索」または「地図上をクリック」してエリアを判定できます。")

# --- セッション状態（データ保持用）の初期化 ---
if "target_coords" not in st.session_state:
    st.session_state.target_coords = None  # 判定対象の(緯度, 経度)
if "search_query" not in st.session_state:
    st.session_state.search_query = ""
if "trigger_rerun" not in st.session_state:
    st.session_state.trigger_rerun = False

# --- GeoJSONデータの読み込み ---
@st.cache_data
def load_geojson_data(folder_path):
    gdf_list = []
    if os.path.exists(folder_path):
        for file in os.listdir(folder_path):
            if file.endswith(".geojson"):
                file_path = os.path.join(folder_path, file)
                try:
                    gdf = gpd.read_file(file_path)
                    gdf["source_file"] = file  # ファイル名をエリア名として記録
                    gdf_list.append(gdf)
                except Exception as e:
                    st.error(f"{file} の読み込みに失敗しました: {e}")
    if gdf_list:
        return gpd.pd.concat(gdf_list, ignore_index=True)
    return None

geojson_folder = "data"
all_areas = load_geojson_data(geojson_folder)

if all_areas is None:
    st.error(f"「{geojson_folder}」フォルダ内に有効なGeoJSONファイルが見つかりません。")
    st.stop()

# 座標系を統一
if all_areas.crs is None:
    all_areas.set_crs(epsg=4326, inplace=True)
elif all_areas.crs.to_string() != "EPSG:4326":
    all_areas = all_areas.to_crs(epsg=4326)

# 地図の初期中心点を計算
center_lat = all_areas.geometry.centroid.y.mean()
center_lon = all_areas.geometry.centroid.x.mean()

# ==========================================
# 3. 画面左側：検索＆判定結果エリア
# ==========================================
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🔍 住所・施設名から検索")
    
    # ユーザー入力
    address_input = st.text_input(
        "住所または施設名を入力してください：", 
        value=st.session_state.search_query,
        placeholder="例: ラモール芦屋"
    )
    
    if st.button("検索実行"):
        if address_input:
            st.session_state.search_query = address_input
            try:
                geolocator = Nominatim(user_agent="my_geojson_app_2026")
                location = geolocator.geocode(address_input, timeout=10)
                if location:
                    # 検索成功時、その緯度経度をターゲットにする
                    st.session_state.target_coords = (location.latitude, location.longitude)
                    st.rerun()
                else:
                    st.error("該当する場所が見つかりませんでした。")
            except GeocoderTimedOut:
                st.error("検索サービスが混み合っています。少し時間をおいて再度お試しください。")
        else:
            st.warning("検索文字を入力してください。")

    st.write("---")
    
    # --- エリア判定の処理と表示 ---
    st.subheader("判定結果")
    if st.session_state.target_coords:
        lat, lon = st.session_state.target_coords
        st.write(f"**現在選択中の位置**")
        st.write(f"緯度: {lat:.5f} / 経度: {lon:.5f}")
        
        point = Point(lon, lat)
        matched_areas = all_areas[all_areas.geometry.contains(point)]
        
        if not matched_areas.empty:
            for idx, row in matched_areas.iterrows():
                area_name = row["source_file"].replace(".geojson", "")
                st.info(f"エリア名: **{area_name}**")
        else:
            st.warning("エリア外（メーター）")
            
        if st.button("選択位置をクリア"):
            st.session_state.target_coords = None
            st.session_state.search_query = ""
            st.rerun()
    else:
        st.info("💡 左の検索窓から調べるか、右の地図上をクリックしてピンを立ててください。")

# ==========================================
# 4. 画面右側：インタラクティブ地図エリア
# ==========================================
with col2:
    st.subheader("🗺️ 地図（クリックして直接ピンを立てる）")
    
    # 地図の中心を決定（検索した場所があればそこを中心に、なければGeoJSONの中心に）
    map_center = [center_lat, center_lon]
    zoom_val = 11
    if st.session_state.target_coords:
        map_center = st.session_state.target_coords
        zoom_val = 15  # 検索位置がある場合はズームインする

    m = folium.Map(location=map_center, zoom_start=zoom_val)

    # GeoJSONエリアを描画
    folium.GeoJson(
        all_areas,
        style_function=lambda x: {
            "fillColor": "#3186cc",
            "color": "#3186cc",
            "weight": 2,
            "fillOpacity": 0.2,
        },
    ).add_to(m)

    # ターゲット位置（検索、または手動クリック）に赤いピンを立てる
    if st.session_state.target_coords:
        folium.Marker(
            location=st.session_state.target_coords,
            popup="選択した位置",
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(m)

    # 地図を表示し、クリックイベントを検知
    map_output = st_folium(m, width="100%", height=550, key="geojson_map")

    # 地図上のクリックを検出した際の処理
    if map_output and map_output.get("last_clicked"):
        clicked = map_output["last_clicked"]
        clicked_coords = (clicked["lat"], clicked["lng"])
        
        # 連続クリックの誤作動防止をしながら座標を更新
        if st.session_state.target_coords != clicked_coords:
            st.session_state.target_coords = clicked_coords
            # 手動クリックした際は、住所検索のテキストをリセットする
            st.session_state.search_query = ""
            st.rerun()