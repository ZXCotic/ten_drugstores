import sys
import math
import requests
import tempfile
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt


GEOCODE_API_URL = "https://geocode-maps.yandex.ru/1.x/"
SEARCH_API_URL = "https://search-maps.yandex.ru/v1/"
STATIC_MAPS_API_URL = "https://static-maps.yandex.ru/1.x/"
GEOCODE_API_KEY = "af8378fd-9ded-4076-99e2-636abd678ba7"
SEARCH_API_KEY = "dda3ddba-c9ea-4ead-9010-f43fbc15c6e3"
STATIC_MAPS_API_KEY = "059355dd-b624-4e9e-a139-88710341c3cb"


class PharmacyMapWindow(QWidget):
    def __init__(self, image_path):
        super().__init__()
        self.setWindowTitle("Pharmacy Locator")
        self.setGeometry(100, 100, 800, 600)
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label)
        pixmap = QPixmap(image_path)
        self.image_label.setPixmap(pixmap.scaledToWidth(800))


def calculate_distance(lon1, lat1, lon2, lat2):
    radius = 6371000
    phi1, phi2 = map(math.radians, [lat1, lat2])
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(dlambda / 2) ** 2)
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def make_request(url, params):
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def geocode_address(address):
    params = {"apikey": GEOCODE_API_KEY, "geocode": address, "format": "json"}
    response = make_request(GEOCODE_API_URL, params)
    members = response["response"]["GeoObjectCollection"]["featureMember"]
    if not members:
        raise ValueError("Address not found")
    return members[0]["GeoObject"]["Point"]["pos"].replace(" ", ",")


def search_pharmacies(coordinates):
    params = {
        "apikey": SEARCH_API_KEY,
        "text": "аптека",
        "ll": coordinates,
        "type": "biz",
        "lang": "ru_RU",
        "results": 50,
    }
    response = make_request(SEARCH_API_URL, params)
    features = response.get("features", [])
    orig_lon, orig_lat = map(float, coordinates.split(","))
    pharmacies = []
    for feature in features:
        coords = feature["geometry"]["coordinates"]
        dist = calculate_distance(orig_lon, orig_lat, coords[0], coords[1])
        pharmacies.append((dist, feature))
    return sorted(pharmacies, key=lambda x: x[0])[:10]


def pharmacy_marker_color(hours):
    if hours:
        if "круглосуточно" in hours.lower():
            return "pm2gnm"
        return "pm2blm"
    return "pm2grm"


def calculate_span(points):
    lons = [float(p.split(",")[0]) for p in points]
    lats = [float(p.split(",")[1]) for p in points]
    delta_lon = abs(max(lons) - min(lons)) * 1.2
    delta_lat = abs(max(lats) - min(lats)) * 1.2
    return f"{delta_lon},{delta_lat}"


def display_map(center_coordinates, span, markers):
    params = {
        "ll": center_coordinates,
        "spn": span,
        "l": "map",
        "pt": "~".join(markers),
        "apikey": STATIC_MAPS_API_KEY,
    }
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        response = requests.get(STATIC_MAPS_API_URL, params=params)
        response.raise_for_status()
        tmp_file.write(response.content)
        tmp_file.flush()
        app = QApplication(sys.argv)
        window = PharmacyMapWindow(tmp_file.name)
        window.show()
        app.exec()


def main():
    address = input("Введите адрес").strip()
    try:
        orig_ll = geocode_address(address)
        pharmacies = search_pharmacies(orig_ll)
        if not pharmacies:
            print("Аптек не найдено")
            return

        all_points = [orig_ll]
        markers = [f"{orig_ll},pm2rdm"]
        for dist, pharmacy in pharmacies:
            meta = pharmacy["properties"].get("CompanyMetaData", {})
            name = meta.get("name", "Name unavailable")
            addr = meta.get("address", "Address unavailable")
            hrs = meta.get("Hours", {}).get("text", "")
            coords = pharmacy["geometry"]["coordinates"]
            color = pharmacy_marker_color(hrs)
            all_points.append(f"{coords[0]},{coords[1]}")
            markers.append(f"{coords[0]},{coords[1]},{color}")
            print(f"Name: {name}, Address: {addr}, Hours: {hrs}, Distance: {round(dist)}m")

        center_lon = (max(float(p.split(",")[0]) for p in all_points) + min(float(p.split(",")[0]) for p in all_points)) / 2
        center_lat = (max(float(p.split(",")[1]) for p in all_points) + min(float(p.split(",")[1]) for p in all_points)) / 2
        span = calculate_span(all_points)
        display_map(f"{center_lon},{center_lat}", span, markers)

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
