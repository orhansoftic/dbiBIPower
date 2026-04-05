import pandas as pd
import numpy as np
import os

def run_etl():
    print("Starting Data Extraction...")
    
    # --- 1. Hauptquelle: OWID CO22 Data ---
    owid_df = pd.read_csv('Data/Raw/owid-co2-data.csv')
    
    # Data Cleansing: Spalten auswählen & Filtern
    cols_to_keep = ['country', 'iso_code', 'year', 'co2', 'co2_per_capita', 'coal_co2', 'oil_co2', 'gas_co2', 'gdp', 'population']
    fact_df = owid_df[cols_to_keep].copy()
    
    # Null-Werte bei iso_code entfernen (aggregierte Regionen ausschließen)
    fact_df = fact_df.dropna(subset=['iso_code'])
    fact_df = fact_df[~fact_df['iso_code'].str.startswith('OWID_')]
    
    # Jahresfilter (1990 - 2023)
    fact_df = fact_df[(fact_df['year'] >= 1990) & (fact_df['year'] <= 2023)]
    
    # Null-Behandlung für Energieträger (Fillna mit 0)
    for col in ['coal_co2', 'oil_co2', 'gas_co2']:
        fact_df[col] = fact_df[col].fillna(0)
        
    # Umbenennung
    rename_mapping = {
        'co2': 'Gesamt_CO22_Mt',
        'co2_per_capita': 'CO22_pro_Kopf_t',
        'gdp': 'BIP_USD',
        'population': 'Bevoelkerung'
    }
    fact_df = fact_df.rename(columns=rename_mapping)
    
    
    # --- 2. Update Quelle: World Bank GDP direkt mergen ---
    print("Loading Update Source: World Bank GDP...")
    # Da World Bank eine ZIP mit spezieller Datei ist, suchen wir die korrekte CSV
    wb_dir = 'Data/Raw/API_NY.GDP.PCAP.CD_DS2_en_csv_v2_207559'
    wb_file = [f for f in os.listdir(wb_dir) if f.startswith('API_NY.GDP')][0]
    
    # Lade mit pd.read_csv (Skip erster 4 rows metadata)
    wb_df = pd.read_csv(os.path.join(wb_dir, wb_file), skiprows=4)
    # Entferne irrelevante Spalten
    wb_df = wb_df.drop(columns=['Indicator Name', 'Indicator Code', 'Unnamed: 67'], errors='ignore')
    
    # Unpivot World Bank
    dim_gdp = pd.melt(wb_df, id_vars=['Country Name', 'Country Code'], var_name='year', value_name='BIP_USD_WB')
    dim_gdp = dim_gdp.rename(columns={'Country Code': 'iso_code'})
    # Konvertiere year auf Int
    dim_gdp = dim_gdp[dim_gdp['year'].str.isnumeric()]
    dim_gdp['year'] = dim_gdp['year'].astype(int)
    dim_gdp = dim_gdp.dropna(subset=['BIP_USD_WB'])
    dim_gdp = dim_gdp[['iso_code', 'year', 'BIP_USD_WB']] # Nur join keys und value behalten
    
    # Left Join an die Fact Tabelle
    print("Merging World Bank Data into Fact Table...")
    fact_df = pd.merge(fact_df, dim_gdp, on=['iso_code', 'year'], how='left')


    # --- 3. Calculated Value ---
    print("Calculating metrics...")
    # CO22 Intensität = Gesamt_CO22_Mt / (BIP_USD / 1.000.000)
    # Anmerkung: Wir könnten hier auch BIP_USD_WB verwenden, nehmen aber konsistent BIP_USD von OWID
    fact_df['CO22_Intensitaet'] = fact_df['Gesamt_CO22_Mt'] / (fact_df['BIP_USD'] / 1000000)
    fact_df['CO22_Intensitaet'] = fact_df['CO22_Intensitaet'].replace([np.inf, -np.inf], np.nan)
    
    
    # --- 4. Extras: Binning ---
    print("Applying Binning...")
    bins = [0, 1_000_000, 10_000_000, 100_000_000, np.inf]
    labels = ["Klein", "Mittel", "Groß", "Gigantisch"]
    fact_df['Bevoelkerungs_Klasse'] = pd.cut(fact_df['Bevoelkerung'], bins=bins, labels=labels)
    
    # --- 5. Entpivotieren (Unpivot / Melt) der Energieträger ---
    print("Unpivoting energy sources...")
    id_vars = ['country', 'iso_code', 'year', 'Gesamt_CO22_Mt', 'CO22_pro_Kopf_t', 'BIP_USD', 'BIP_USD_WB', 'Bevoelkerung', 'CO22_Intensitaet', 'Bevoelkerungs_Klasse']
    fact_df = pd.melt(fact_df, id_vars=id_vars, value_vars=['coal_co2', 'oil_co2', 'gas_co2'], 
                      var_name='Traeger_Roh', value_name='CO22_Energietraeger_Mt')
    
    # Mapping der Namen
    traeger_map = {'coal_co2': 'Kohle', 'oil_co2': 'Öl', 'gas_co2': 'Gas'}
    fact_df['Traeger_Name'] = fact_df['Traeger_Roh'].map(traeger_map)
    fact_df = fact_df.drop(columns=['Traeger_Roh'])
    
    
    # --- 6. Dimensionstabellen generieren ---
    print("Building Dimension tables...")
    
    # DIM_Energietraeger
    dim_energietraeger = pd.DataFrame({
        'TraegerID': [1, 2, 3],
        'Traeger_Name': ['Kohle', 'Öl', 'Gas'],
        'Kategorie': ['Fossil', 'Fossil', 'Fossil']
    })
    
    # DIM_Zeit (Berechnet in Python analog zu DAX)
    years = list(range(1990, 2024))
    dim_zeit = pd.DataFrame({'Value': years, 'Jahr': years})
    dim_zeit['Jahrzehnt'] = pd.cut(dim_zeit['Value'], bins=[1989, 1999, 2009, 2019, 2029], labels=["1990er", "2000er", "2010er", "2020er"])
    def get_zeitraum(y):
        if y < 1997: return "Vor Kyoto"
        elif y < 2016: return "Post-Kyoto"
        else: return "Post-Paris"
    dim_zeit['Zeitraum_Label'] = dim_zeit['Value'].apply(get_zeitraum)


    # --- 7. Enrichments ---
    # Enrichment 1: DIM_Land (ISO Codes + Kontinent)
    print("Loading Enrichment: Country Codes...")
    dim_land = pd.read_csv('Data/Raw/all.csv')
    dim_land = dim_land[['name', 'alpha-3', 'region', 'sub-region']]
    dim_land = dim_land.rename(columns={'name': 'v_landname', 'alpha-3': 'iso_code', 'region': 'v_kontinent', 'sub-region': 'v_sub_region'})
    
    # Ridiculous Dimensions auf DIM_Land anwenden
    def get_alpha_group(name):
        first_char = str(name)[0].upper()
        if 'A' <= first_char <= 'F': return "A-F"
        elif 'G' <= first_char <= 'L': return "G-L"
        elif 'M' <= first_char <= 'R': return "M-R"
        else: return "S-Z"
    dim_land['v_alphabetische_gruppe'] = dim_land['v_landname'].apply(get_alpha_group)
    
    if os.path.exists('Data/Raw/national_animals.csv'):
        dim_mascot = pd.read_csv('Data/Raw/national_animals.csv')
        dim_land = pd.merge(dim_land, dim_mascot, on='iso_code', how='left')
        dim_land['v_nationaltier'] = dim_land['v_nationaltier'].fillna('Unbekannt')
    else:
        dim_land['v_nationaltier'] = 'Fehlt'
    
    
    print("Exporting datasets...")
    # Speichern der bereinigten Dateien (Star Schema)
    fact_df.to_csv('Data/Processed/cleaned_FACT_Emissionen.csv', index=False)
    dim_land.to_csv('Data/Processed/cleaned_DIM_Land.csv', index=False)
    dim_zeit.to_csv('Data/Processed/cleaned_DIM_Zeit.csv', index=False)
    dim_energietraeger.to_csv('Data/Processed/cleaned_DIM_Energietraeger.csv', index=False)
    print("✅ ETL process completed successfully! Output saved to CSVs.")

if __name__ == "__main__":
    run_etl()
