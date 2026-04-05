import base64
import zlib
import urllib.request
import os

puml = """@startuml
skinparam roundcorner 5
skinparam linetype ortho

entity "FACT_Emissionen" {
  * dim_iso_code
  * dim_year
  * dim_traeger_name
  --
  v_gesamt_co2_mt
  v_bevoelkerung
  v_bip_usd_wb
  v_co2_intensitaet
  v_bevoelkerungs_klasse
}

entity "DIM_Land" {
  * dim_iso_code
  --
  v_landname
  v_kontinent
  v_sub_region
}

entity "DIM_Zeit" {
  * dim_year
  --
  v_jahrzehnt
  v_zeitraum_label
}

entity "DIM_Energietraeger" {
  * dim_traeger_name
  --
  v_traegerid
  v_kategorie
}

DIM_Land ||--o{ FACT_Emissionen
DIM_Zeit ||--o{ FACT_Emissionen
DIM_Energietraeger ||--o{ FACT_Emissionen
@enduml
"""

# Kroki compress and encode
compressed = zlib.compress(puml.encode('utf-8'), 9)
encoded = base64.urlsafe_b64encode(compressed).decode('utf-8')
# Auf svg ändern für Vektorgrafik!
url = f"https://kroki.io/plantuml/svg/{encoded}"

# Create Images dir if it doesn't exist
os.makedirs("Images", exist_ok=True)

print("Downloading PlantUML SVG diagram from Kroki...")
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response, open("Images/StarSchema.svg", 'wb') as out_file:
    out_file.write(response.read())
print("✅ Saved to Images/StarSchema.svg")
