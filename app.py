from flask import Flask, render_template, request
from geopy.geocoders import Nominatim
import overpy
import folium
import requests
from geopy.distance import geodesic
import time

app = Flask(__name__)

# 建立共用 Geolocator 物件（避免每次都重建）
geolocator = Nominatim(user_agent="webmap")

def get_location_by_ip():
    try:
        r = requests.get("https://ipinfo.io/json", timeout=2)
        data = r.json()
        lat, lon = map(float, data["loc"].split(","))
        location = geolocator.reverse((lat, lon), language="zh-TW", timeout=2)
        address = location.address if location else "未知位置"
        return lat, lon, address
    except Exception:
        return None, None, "無法取得位置"

def find_places(lat, lon, radius=2000, retries=2):
    api = overpy.Overpass()
    query = f"""
    (
      node["shop"="pet"](around:{radius},{lat},{lon});
      way["shop"="pet"](around:{radius},{lat},{lon});
      node["amenity"="veterinary"](around:{radius},{lat},{lon});
      way["amenity"="veterinary"](around:{radius},{lat},{lon});
      node["leisure"="park"](around:{radius},{lat},{lon});
      way["leisure"="park"](around:{radius},{lat},{lon});
      relation["leisure"="park"](around:{radius},{lat},{lon});
    );
    out center;
    """
    for attempt in range(retries):
        try:
            return api.query(query).nodes + api.query(query).ways + api.query(query).relations
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                raise e

def categorize_places(places, user_lat, user_lon):
    categorized = {"pet_shops": [], "animal_hospitals": [], "parks": []}

    for place in places:
        name = place.tags.get("name", "（未命名）")
        address = place.tags.get("addr:full", "")
        lat, lon = (getattr(place, "lat", None), getattr(place, "lon", None))
        if lat is None or lon is None:
            lat, lon = (getattr(place, "center_lat", None), getattr(place, "center_lon", None))
        if lat is None or lon is None:
            continue

        dist = round(geodesic((user_lat, user_lon), (lat, lon)).meters)
        info = {"name": name, "distance": dist, "address": address}

        if "shop" in place.tags:
            categorized["pet_shops"].append(info)
        elif "amenity" in place.tags:
            categorized["animal_hospitals"].append(info)
        elif "leisure" in place.tags:
            categorized["parks"].append(info)

    for key in categorized:
        categorized[key] = sorted(categorized[key], key=lambda x: x["distance"])[:2]

    return categorized

def generate_map(lat, lon, places, center_name):
    fmap = folium.Map(location=[lat, lon], zoom_start=15)
    folium.Marker([lat, lon], popup=center_name, icon=folium.Icon(color="blue", icon="home")).add_to(fmap)

    for place in places:
        name = place.tags.get("name", "（未命名）")
        lat, lon = (getattr(place, "lat", None), getattr(place, "lon", None))
        if lat is None or lon is None:
            lat, lon = (getattr(place, "center_lat", None), getattr(place, "center_lon", None))
        if lat is None or lon is None:
            continue

        if "shop" in place.tags:
            label, color = "寵物店 🐶", "green"
        elif "amenity" in place.tags:
            label, color = "動物醫院 🏥", "red"
        elif "leisure" in place.tags:
            label, color = "公園 🌳", "orange"
        else:
            label, color = "其他", "gray"

        folium.Marker(
            [lat, lon],
            popup=f"{label}：{name}",
            icon=folium.Icon(color=color)
        ).add_to(fmap)

    return fmap._repr_html_()

@app.route("/", methods=["GET", "POST"])
def index():
    map_html = ""
    address = ""
    categorized = {"pet_shops": [], "animal_hospitals": [], "parks": []}
    error = ""

    if request.method == "POST":
        method = request.form.get("method")
        if method == "auto":
            lat = request.form.get("lat", type=float)
            lon = request.form.get("lon", type=float)
            if not lat or not lon:
                error = "❌ 無法取得定位"
            else:
                try:
                    location = geolocator.reverse((lat, lon), language="zh-TW", timeout=2)
                    address = location.address if location else "未知位置"
                    places = find_places(lat, lon)
                    categorized = categorize_places(places, lat, lon)
                    map_html = generate_map(lat, lon, places, address)
                except Exception as e:
                    error = f"❌ 資料擷取失敗：{e}"
        elif method == "manual":
            address_input = request.form.get("address")
            try:
                loc = geolocator.geocode(address_input, timeout=3)
                if not loc:
                    error = "❌ 找不到該地址"
                else:
                    lat, lon = loc.latitude, loc.longitude
                    address = loc.address
                    places = find_places(lat, lon)
                    categorized = categorize_places(places, lat, lon)
                    map_html = generate_map(lat, lon, places, address)
            except Exception as e:
                error = f"❌ 找不到該地址或查詢失敗：{e}"

    return render_template("index.html", map_html=map_html, address=address, error=error, categorized=categorized)

if __name__ == "__main__":
    from os import environ
    app.run(host='0.0.0.0', port=int(environ.get("PORT", 5000)))
