from flask import Flask, render_template, request
import folium
import geopy
from geopy.geocoders import Nominatim
import overpy

app = Flask(__name__)
api = overpy.Overpass()

def query_places(lat, lon, radius=2000):
    query = f"""
    (
      node["shop"="pet"](around:{radius},{lat},{lon});
      node["amenity"="veterinary"](around:{radius},{lat},{lon});
      node["leisure"="park"](around:{radius},{lat},{lon});
    );
    out body;
    """
    return api.query(query).nodes

def generate_map(lat, lon, nodes, center_name):
    fmap = folium.Map(location=[lat, lon], zoom_start=15)
    folium.Marker([lat, lon], popup=center_name, icon=folium.Icon(color="blue", icon="home")).add_to(fmap)

    places = {"pet": [], "vet": [], "park": []}

    for node in nodes:
        name = node.tags.get("name", "（未命名）")
        if "shop" in node.tags:
            label = "寵物店"
            color = "green"
            places["pet"].append(name)
        elif "amenity" in node.tags:
            label = "動物醫院"
            color = "red"
            places["vet"].append(name)
        elif "leisure" in node.tags:
            label = "公園"
            color = "orange"
            places["park"].append(name)
        else:
            label = "其他"
            color = "gray"
        folium.Marker(
            [node.lat, node.lon],
            popup=f"{label}：{name}",
            icon=folium.Icon(color=color)
        ).add_to(fmap)

    return fmap._repr_html_(), places

@app.route("/", methods=["GET", "POST"])
def index():
    address = ""
    lat = lon = None
    map_html = ""
    error = ""
    places = {}

    if request.method == "POST":
        method = request.form.get("method")
        address = request.form.get("address", "")
        lat = request.form.get("lat")
        lon = request.form.get("lon")

        if method == "auto" and lat and lon:
            lat, lon = float(lat), float(lon)
            address = "目前位置"
        elif method == "manual" and address:
            geolocator = Nominatim(user_agent="pet_map")
            try:
                location = geolocator.geocode(address)
                if not location:
                    error = "找不到該地址，請重新輸入"
                else:
                    lat, lon = location.latitude, location.longitude
                    address = location.address
            except geopy.exc.GeocoderTimedOut:
                error = "地址查詢逾時，請稍後再試"
        else:
            error = "請提供有效的位置資訊"

        if lat and lon and not error:
            try:
                nodes = query_places(lat, lon)
                map_html, places = generate_map(lat, lon, nodes, address)
            except Exception as e:
                error = f"地點查詢失敗：{str(e)}"

    return render_template("index.html", map_html=map_html, address=address, error=error, places=places)

if __name__ == "__main__":
    app.run(debug=True)
