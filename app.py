from flask import Flask, render_template, request
from geopy.geocoders import Nominatim
import overpy
import folium
import requests

app = Flask(__name__)

def find_places(lat, lon, radius=2000):
    api = overpy.Overpass()
    query = f"""
    (
      node["shop"="pet"](around:{radius},{lat},{lon});
      node["amenity"="veterinary"](around:{radius},{lat},{lon});
      node["leisure"="park"](around:{radius},{lat},{lon});
    );
    out center;
    """
    return api.query(query).nodes

def generate_map(lat, lon, nodes, center_name):
    fmap = folium.Map(location=[lat, lon], zoom_start=15)
    folium.Marker([lat, lon], popup=center_name, icon=folium.Icon(color="blue", icon="home")).add_to(fmap)
    for node in nodes:
        name = node.tags.get("name", "（未命名）")
        if "shop" in node.tags:
            label = "寵物店"
            color = "green"
        elif "amenity" in node.tags:
            label = "動物醫院"
            color = "red"
        elif "leisure" in node.tags:
            label = "公園"
            color = "orange"
        else:
            label = "其他"
            color = "gray"
        folium.Marker(
            [node.lat, node.lon],
            popup=f"{label}：{name}",
            icon=folium.Icon(color=color)
        ).add_to(fmap)
    return fmap._repr_html_()

@app.route("/", methods=["GET", "POST"])
def index():
    map_html = ""
    address = ""
    error = ""

    if request.method == "POST":
        method = request.form.get("method")
        if method == "auto":
            lat = request.form.get("lat", type=float)
            lon = request.form.get("lon", type=float)
            if not lat or not lon:
                error = "❌ 無法取得定位資訊"
            else:
                geo = Nominatim(user_agent="pet-map")
                location = geo.reverse(f"{lat}, {lon}", language="zh-TW")
                address = location.address if location else "未知位置"
                nodes = find_places(lat, lon)
                map_html = generate_map(lat, lon, nodes, address)
        elif method == "manual":
            address = request.form.get("address")
            geo = Nominatim(user_agent="pet-map")
            loc = geo.geocode(address)
            if not loc:
                error = "❌ 找不到該地址"
            else:
                lat, lon = loc.latitude, loc.longitude
                nodes = find_places(lat, lon)
                map_html = generate_map(lat, lon, nodes, address)

    return render_template("index.html", map_html=map_html, address=address, error=error)

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
