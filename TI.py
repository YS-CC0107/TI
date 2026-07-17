import streamlit as st

# --- 簡易パスワード認証機能 ---
def check_password():
    """正しいパスワードが入力されたらTrueを返す"""
    def password_entered():
        """入力されたパスワードをチェックする"""
        if st.session_state["password"] == "kobe-MKCC":  # ← 好きなパスワードを設定
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # セキュリティのため保持しない
        else:
            st.session_state["password_correct"] = False

    # すでに認証済みならTrue
    if st.session_state.get("password_correct", False):
        return True

    # パスワード入力画面を表示
    st.title("🔒 認証が必要です")
    st.text_input(
        "パスワードを入力してください", type="password", on_change=password_entered, key="password"
    )
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 パスワードが違います")
    return False

# パスワードチェックを実行。間違っていればここで処理をストップする
if not check_password():
    st.stop()

# ------------------------------------
# ↑ これより下に、元のメイン処理（GeoJSONの読み込みなど）を続けます
# ------------------------------------
import streamlit as st
import geopandas as gpd
import os
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from shapely.geometry import Point
import folium
from streamlit_folium import st_folium

# ページ設定
st.set_page_config(page_title="定額エリア判定アプリ", layout="wide")
st.title("定額エリア判定アプリ")
st.write("住所や施設名を入力すると、どのGeoJSONファイルの範囲内に属しているかを自動で判定します。")

# --- 設定 ---
GEOJSON_DIR = "data"  # GeoJSONファイルが格納されているフォルダ名

# --- 関数定義 ---
@st.cache_data
def load_geojson_files(directory):
    """ディレクトリ内のGeoJSONファイルをすべて読み込む"""
    gdfs = {}
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    for filename in os.listdir(directory):
        if filename.endswith(".geojson") or filename.endswith(".json"):
            filepath = os.path.join(directory, filename)
            try:
                # GeoJSONの読み込み（EPSG:4326/WGS84 に統一）
                gdf = gpd.read_file(filepath)
                if gdf.crs is None:
                    gdf.set_crs(epsg=4326, inplace=True)
                else:
                    gdf = gdf.to_crs(epsg=4326)
                gdfs[filename] = gdf
            except Exception as e:
                st.error(f"ファイルの読み込みに失敗しました: {filename} (エラー: {e})")
    return gdfs

def geocode_address(address_str):
    """住所・施設名から緯度経度を取得する"""
    geolocator = Nominatim(user_agent="geojson_checker_app_2026")
    try:
        # 日本国内の検索に最適化
        location = geolocator.geocode(address_str, timeout=10)
        if location:
            return location.latitude, location.longitude, location.address
    except GeocoderTimedOut:
        st.error("位置情報の検索がタイムアウトしました。もう一度お試しください。")
    return None

# --- メイン処理 ---
# GeoJSONの読み込み
gdfs = load_geojson_files(GEOJSON_DIR)

if not gdfs:
    st.warning(f"⚠️ `{GEOJSON_DIR}/` フォルダ内にGeoJSONファイルが見つかりません。ファイルを配置してください。")
else:
    # ユーザー入力
    address_input = st.text_input(
        "住所または施設名を入力してください（例: ラモール芦屋）", 
        placeholder="ここに書き込んでEnter"
    )

    if address_input:
        with st.spinner("位置情報を特定中..."):
            geo_result = geocode_address(address_input)
        
        if geo_result:
            lat, lon, full_address = geo_result
            
            # 判定用ポイントデータの作成
            point = Point(lon, lat)
            
            # どのGeoJSONに含まれるか判定
            hit_files = []
            for filename, gdf in gdfs.items():
                # ポイントがポリゴンのいずれかに内包されているか確認
                is_inside = gdf.geometry.contains(point).any()
                if is_inside:
                    hit_files.append(filename)
            
            # --- 結果の表示 ---
            st.subheader("🔍 判定結果")
            if hit_files:
                for file in hit_files:
                    # 拡張子（.geojson や .json）を取り除く
                    display_name, _ = os.path.splitext(file)
                    st.success(f"所属: **{display_name}**")
            else:
                st.markdown("エリア外")
            
            # --- 地図表示 (Folium) ---
            st.subheader("🗺️ 地図で位置を確認")
            
            # マップ初期化
            m = folium.Map(location=[lat, lon], zoom_start=14)
            
            # 各GeoJSONのポリゴンを地図に追加
            for filename, gdf in gdfs.items():
                # 所属しているファイルとそれ以外で色を分ける
                color = "green" if filename in hit_files else "blue"
                fill_color = "green" if filename in hit_files else "cyan"
                
                # 地図上に表示する名前も拡張子なしにする
                display_name, _ = os.path.splitext(filename)
                
                # 地図に描画
                folium.GeoJson(
                    gdf,
                    name=display_name,
                    style_function=lambda x, color=color, fill_color=fill_color: {
                        'fillColor': fill_color,
                        'color': color,
                        'weight': 2,
                        'fillOpacity': 0.3
                    },
                    tooltip=display_name
                ).add_to(m)
            
            # 検索したピンを追加
            folium.Marker(
                [lat, lon],
                popup=address_input,
                tooltip="検索位置",
                icon=folium.Icon(color="red", icon="info-sign")
            ).add_to(m)
            
            # 地図コントローラーの追加
            folium.LayerControl().add_to(m)
            
            # Streamlit上でFoliumを描画
            st_folium(m, width="100%", height=500)
            
        else:
            st.error("入力された住所や施設名に該当する緯度経度が見つかりませんでした。表記を変えてみてください。")