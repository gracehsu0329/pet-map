from flask import Flask, render_template, request
from geopy.geocoders import Nominatim
import overpy
import folium
import requests
from geopy.distance import geodesic

app = Flask(__name__)

def get_location_by_ip():
    try:
        r = requests.get("https://ipinfo.io/json")
        data = r.json()
        loc = data["loc"]
        lat, lon = map(float, loc.split(","))
        geolocator = Nominatim(user_agent="webmap")
        location = geolocator.reverse(f"{lat}, {lon}", language="zh-TW")
        full_address = location.address if location else "未知位置"
        return lat, lon, full_address
    except:
        return None, None, "無法取得位置"

def find_places(lat, lon, radius=2000):
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
    result = api.query(query)
    return result.nodes + result.ways + result.relations

def categorize_places(places, user_lat, user_lon):
    categorized = {
        "pet_shops": [],
        "animal_hospitals": [],
        "parks": []
    }

    for place in places:
        name = place.tags.get("name", "（未命名）")
        address = place.tags.get("addr:full", "")  # or leave blank
        if hasattr(place, "lat") and hasattr(place, "lon"):
            lat, lon = place.lat, place.lon
        elif hasattr(place, "center_lat") and hasattr(place, "center_lon"):
            lat, lon = place.center_lat, place.center_lon
        else:
            continue

        dist = round(geodesic((user_lat, user_lon), (lat, lon)).meters)

        info = {
            "name": name,
            "distance": dist,
            "address": address,
        }

        if "shop" in place.tags:
            categorized["pet_shops"].append(info)
        elif "amenity" in place.tags:
            categorized["animal_hospitals"].append(info)
        elif "leisure" in place.tags:
            categorized["parks"].append(info)

    # 依距離排序，只取前兩筆
    for key in categorized:
        categorized[key] = sorted(categorized[key], key=lambda x: x["distance"])[:2]

    return categorized

def generate_map(lat, lon, places, center_name):
    fmap = folium.Map(location=[lat, lon], zoom_start=15)
    folium.Marker([lat, lon], popup=center_name, icon=folium.Icon(color="blue", icon="home")).add_to(fmap)

    for place in places:
        name = place.tags.get("name", "（未命名）")

        if "shop" in place.tags:
            label = "寵物店 🐶"
            color = "green"
        elif "amenity" in place.tags:
            label = "動物醫院 🏥"
            color = "red"
        elif "leisure" in place.tags:
            label = "公園 🌳"
            color = "orange"
        else:
            label = "其他"
            color = "gray"

        if hasattr(place, "lat") and hasattr(place, "lon"):
            point = [place.lat, place.lon]
        elif hasattr(place, "center_lat") and hasattr(place, "center_lon"):
            point = [place.center_lat, place.center_lon]
        else:
            continue

        folium.Marker(
            point,
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
                geo = Nominatim(user_agent="webmap")
                location = geo.reverse(f"{lat}, {lon}", language="zh-TW")
                address = location.address if location else "未知位置"
                places = find_places(lat, lon)
                categorized = categorize_places(places, lat, lon)  # 加上 lat 和 lon
                map_html = generate_map(lat, lon, places, address)
        elif method == "manual":
            address = request.form.get("address")
            geo = Nominatim(user_agent="webmap")
            loc = geo.geocode(address)
            if not loc:
                error = "❌ 找不到該地址"
            else:
                lat, lon = loc.latitude, loc.longitude
                places = find_places(lat, lon)
                categorized = categorize_places(places, lat, lon)
                map_html = generate_map(lat, lon, places, address)
    
    
    else:  # ✅ GET: 嘗試 IP 定位
        lat, lon, address = get_location_by_ip()
        if lat and lon:
            places = find_places(lat, lon)
            categorized = categorize_places(places, lat, lon)
            map_html = generate_map(lat, lon, places, address)
        else:
            error = "❌ 無法透過 IP 取得位置"

    return render_template("index.html", map_html=map_html, address=address, error=error, categorized=categorized)

if __name__ == "__main__":
    from os import environ
    app.run(host='0.0.0.0', port=int(environ.get("PORT", 5000)))
