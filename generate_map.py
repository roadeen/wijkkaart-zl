import pandas as pd
import folium
from folium.plugins import MarkerCluster, LocateControl
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import time
import json

# ----------------------------
# 1. Instellingen
# ----------------------------
sheet_name = "Adressen_Checklist_ZLimburg"

LOCAL_OUTPUT = "index.html"
OPMERKING_COLOR = '#9b59b6'  # Purple

# ----------------------------
# 2. Google Setup
# ----------------------------
def get_credentials():
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON_ZL')

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    if not creds_json:
        raise ValueError("Missing GOOGLE_CREDENTIALS_JSON_ZL environment variable")

    creds_dict = json.loads(creds_json)
    return ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)


# ----------------------------
# 3. Map generation
# ----------------------------
def generate_interactive_map():
    start_time = time.time()

    print("☁️ Data ophalen uit Google Sheets...")

    try:
        creds = get_credentials()
        client = gspread.authorize(creds)

        sheet = client.open(sheet_name).worksheet("Master_Sheet")
        data = sheet.get_all_records()

        df = pd.DataFrame(data)

    except Exception as e:
        raise RuntimeError(f"Google Sheets fout: {e}")

    print(f"📊 Totaal adressen: {len(df)}")

    # ----------------------------
    # Map init
    # ----------------------------
    m = folium.Map(
        location=[df['lat'].mean(), df['lon'].mean()],
        zoom_start=16,
        tiles='cartodbpositron',
        control_scale=True
    )

    LocateControl(auto_start=False, flyTo=True).add_to(m)

    icon_create_function = """
    function(cluster) {
        var childMarkers = cluster.getAllChildMarkers();
        var totalAddresses = 0;
        var doneAddresses = 0;
        var hasOpmerking = false;

        childMarkers.forEach(function(marker) {
            totalAddresses += marker.options.totalAddresses || 1;
            doneAddresses += marker.options.doneAddresses || 0;
            if (marker.options.hasOpmerking) {
                hasOpmerking = true;
            }
        });

        var percentage = totalAddresses > 0 ? (doneAddresses / totalAddresses) * 100 : 0;

        var color;
        if (percentage === 100) color = '#28a745';
        else if (percentage >= 75) color = '#7cb342';
        else if (percentage >= 50) color = '#ffc107';
        else if (percentage >= 25) color = '#fd7e14';
        else color = '#dc3545';

        var borderColor = hasOpmerking ? '#9b59b6' : 'white';
        var borderWidth = hasOpmerking ? '4px' : '3px';

        var displayNumber = totalAddresses > 999 ? '999+' : totalAddresses;

        return L.divIcon({
            html: '<div style="background-color:' + color + '; width: 40px; height: 40px; border-radius: 50%; display:flex; align-items:center; justify-content:center; border:' + borderWidth + ' solid ' + borderColor + ';"><span style="color:white;font-weight:bold;">' + displayNumber + '</span></div>',
            className: 'marker-cluster-custom',
            iconSize: L.point(40, 40)
        });
    }
    """

    marker_cluster = MarkerCluster(
        name='Adressen',
        icon_create_function=icon_create_function,
        options={
            'maxClusterRadius': 30,
            'disableClusteringAtZoom': 19
        }
    )

    address_groups = {}

    # ----------------------------
    # Group addresses
    # ----------------------------
    for _, row in df.iterrows():
        try:
            lat = float(row['lat'])
            lon = float(row['lon'])

            if lat == 0 or lon == 0:
                continue

            loc_key = f"{lat:.6f},{lon:.6f}"

            if loc_key not in address_groups:
                address_groups[loc_key] = {
                    "lat": lat,
                    "lon": lon,
                    "addresses": []
                }

            address_groups[loc_key]["addresses"].append(row)

        except Exception as e:
            print(f"Skip row error: {e}")

    # ----------------------------
    # Create markers
    # ----------------------------
    for _, group in address_groups.items():
        lat = group["lat"]
        lon = group["lon"]
        addresses = group["addresses"]

        done = sum(
            1 for r in addresses
            if str(r.get("Afgevinkt", "")).strip().lower() == "ja"
        )

        has_opmerking = any(
            r.get("Opmerkingen") not in [None, "", "nan"]
            for r in addresses
        )

        popup = f"<b>{len(addresses)} adressen</b>"

        marker = folium.CircleMarker(
            location=[lat, lon],
            radius=7,
            popup=popup,
            color=OPMERKING_COLOR if has_opmerking else "white",
            fill=True,
            fill_opacity=0.8
        )

        marker.options["totalAddresses"] = len(addresses)
        marker.options["doneAddresses"] = done
        marker.options["hasOpmerking"] = has_opmerking

        marker.add_to(marker_cluster)

    marker_cluster.add_to(m)

    # ----------------------------
    # Save HTML
    # ----------------------------
    m.save(LOCAL_OUTPUT)

    print(f"✅ Map generated: {LOCAL_OUTPUT}")
    print(f"📍 Groups: {len(address_groups)}")


# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    generate_interactive_map()
