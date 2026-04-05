import pandas as pd
import numpy as np
import sqlite3
import os

# Set paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OWID_PATH = os.path.join(BASE_DIR, "owid-co2-data.csv")
ISO_PATH = os.path.join(BASE_DIR, "all.csv")
WB_PATH = os.path.join(BASE_DIR, "API_NY.GDP.PCAP.CD_DS2_en_csv_v2_207559", "API_NY.GDP.PCAP.CD_DS2_en_csv_v2_207559.csv")
DRINKS_PATH = os.path.join(BASE_DIR, "drinks.csv")
DB_PATH = os.path.join(BASE_DIR, "bi_cube.sqlite")

def create_dim_zeit():
    print("Creating DIM_Zeit...")
    years = list(range(1990, 2024))
    df_zeit = pd.DataFrame({'Value': years})
    
    def get_jahrzehnt(year):
        if year < 2000: return "1990er"
        elif year < 2010: return "2000er"
        elif year < 2020: return "2010er"
        else: return "2020er"
    
    def get_zeitraum(year):
        if year < 1997: return "Vor Kyoto"
        elif year < 2016: return "Post-Kyoto"
        else: return "Post-Paris"
        
    df_zeit['Jahrzehnt'] = df_zeit['Value'].apply(get_jahrzehnt)
    df_zeit['Zeitraum_Label'] = df_zeit['Value'].apply(get_zeitraum)
    return df_zeit

def create_dim_energietraeger():
    print("Creating DIM_Energietraeger...")
    return pd.DataFrame({
        'TraegerID': [1, 2, 3],
        'Traeger_Name': ['Kohle', 'Öl', 'Gas'],
        'Kategorie': ['Fossil', 'Fossil', 'Fossil']
    })

def create_dim_land():
    print("Creating DIM_Land...")
    df = pd.read_csv(ISO_PATH)
    # Select specific columns
    df = df[['name', 'alpha-3', 'region', 'sub-region']].copy()
    # Rename columns
    df.rename(columns={
        'name': 'Landname',
        'alpha-3': 'iso_code',
        'region': 'Kontinent',
        'sub-region': 'Sub_Region'
    }, inplace=True)
    return df

def create_dim_gdp_update():
    print("Creating DIM_GDP (World Bank Update Source)...")
    # Read with skipping the first 4 rows which are metadata
    df = pd.read_csv(WB_PATH, skiprows=4)
    # Columns to keep (drop unnecessary ones)
    cols = ['Country Name', 'Country Code', 'Indicator Name', 'Indicator Code']
    # Unpivot all year columns
    year_cols = [c for c in df.columns if c.isnumeric()]
    df_melted = pd.melt(df, id_vars=['Country Code'], value_vars=year_cols, 
                        var_name='year', value_name='BIP_USD')
    
    # Filter metadata/NaN values
    df_melted.dropna(subset=['BIP_USD'], inplace=True)
    df_melted['year'] = pd.to_numeric(df_melted['year'], errors='coerce')
    df_melted.rename(columns={'Country Code': 'iso_code'}, inplace=True)
    return df_melted

def create_dim_sinnlos():
    print("Creating DIM_Sinnlos (Ridiculous Dimensions)...")
    # 1. Base table with ISO codes
    df_iso = pd.read_csv(ISO_PATH)[['name', 'alpha-3']].copy()
    df_iso.rename(columns={'name': 'Landname', 'alpha-3': 'iso_code'}, inplace=True)
    
    # Sinnlose Dimension 1 (Internal): Länge des Namens
    def name_length_class(name):
        if not isinstance(name, str): return "Unbekannt"
        if len(name) < 6: return "Kurz"
        elif len(name) <= 10: return "Mittel"
        else: return "Lang"
    df_iso['Namenlaenge_Klasse'] = df_iso['Landname'].apply(name_length_class)
    
    # 2. Sinnlose Dimension 2 (External Enrichment): Bierkonsum
    try:
        df_drinks = pd.read_csv(DRINKS_PATH)
        # We need to map country names to ISO codes since drinks.csv has no ISO code
        # We do a basic string matching inner join (lower case)
        df_iso['name_lower'] = df_iso['Landname'].str.lower()
        df_drinks['name_lower'] = df_drinks['country'].str.lower()
        
        # Merge
        df_merged = pd.merge(df_iso, df_drinks, on='name_lower', how='left')
        df_merged.drop(columns=['name_lower'], inplace=True)
        
        def beer_class(val):
            if pd.isna(val): return "Keine Daten"
            if val > 200: return "Trinkfest (>200)"
            elif val > 100: return "Moderat (100-200)"
            else: return "Wenig Trinker (<100)"
            
        df_merged['Bierkonsum_Klasse'] = df_merged['beer_servings'].apply(beer_class)
    except Exception as e:
        print("Konnte drinks.csv nicht lesen:", e)
        df_iso['Bierkonsum_Klasse'] = "Keine Daten"
        df_merged = df_iso
        
    return df_merged[['iso_code', 'Namenlaenge_Klasse', 'Bierkonsum_Klasse']]

def create_fact_emissionen():
    print("Creating FACT_Emissionen...")
    df = pd.read_csv(OWID_PATH)
    
    # 1. Filter: select required columns
    req_cols = ['country', 'iso_code', 'year', 'co2', 'co2_per_capita', 
                'coal_co2', 'oil_co2', 'gas_co2', 'gdp', 'population']
    # Some rows might not have all columns in older CSVs, check if exist
    for c in req_cols:
        if c not in df.columns:
            df[c] = np.nan
    df = df[req_cols].copy()
    
    # 2. Filter: drop empty iso_code and OWID_ prefixes
    df = df.dropna(subset=['iso_code'])
    df = df[~df['iso_code'].str.startswith('OWID_')]
    
    # 3. Filter: Year 1990 - 2023
    df = df[(df['year'] >= 1990) & (df['year'] <= 2023)]
    
    # Fill NAs
    df[['coal_co2', 'oil_co2', 'gas_co2']] = df[['coal_co2', 'oil_co2', 'gas_co2']].fillna(0)
    
    # Unpivot (Melt) for energy carriers
    id_vars = ['country', 'iso_code', 'year', 'co2', 'co2_per_capita', 'gdp', 'population']
    df_melted = pd.melt(df, id_vars=id_vars, value_vars=['coal_co2', 'oil_co2', 'gas_co2'],
                        var_name='Traeger_Name_Raw', value_name='CO2_Energietraeger_Mt')
    
    # Map energy carrier names
    traeger_mapping = {'coal_co2': 'Kohle', 'oil_co2': 'Öl', 'gas_co2': 'Gas'}
    df_melted['Traeger_Name'] = df_melted['Traeger_Name_Raw'].map(traeger_mapping)
    df_melted.drop(columns=['Traeger_Name_Raw'], inplace=True)
    
    # Rename columns
    df_melted.rename(columns={
        'co2': 'Gesamt_CO2_Mt',
        'co2_per_capita': 'CP2_pro_Kopf_t',
        'gdp': 'BIP_USD',
        'population': 'Bevoelkerung'
    }, inplace=True)
    
    # Calculate CO2 Intensity: Gesamt_CO2_Mt / (BIP_USD / 1000000)
    df_melted['CO2_Intensitaet'] = df_melted['Gesamt_CO2_Mt'] / (df_melted['BIP_USD'] / 1_000_000)
    
    # Binning
    def get_population_class(pop):
        if pd.isna(pop): return "Unbekannt"
        if pop > 100_000_000: return "Gigantisch"
        elif pop > 10_000_000: return "Groß"
        elif pop > 1_000_000: return "Mittel"
        else: return "Klein"
        
    df_melted['Bevoelkerungs_Klasse'] = df_melted['Bevoelkerung'].apply(get_population_class)
    return df_melted

def compute_measures(fact_df):
    print("--- Calculated Measures equivalent ---")
    avg_pro_kopf = fact_df['CP2_pro_Kopf_t'].mean()
    # Da Fakten entpivotiert sind, hat jedes Land/Jahr 3 Einträge! Die Baseline Metriken 
    # (Gesamt_CO2) sind pro Land/Jahr dupliziert, außer man achtet beim Summieren darauf. 
    # In Power BI würde das durch die Relationen geregelt, hier machen wir es auf den Uniques:
    unique_df = fact_df.drop_duplicates(subset=['iso_code', 'year'])
    gesamt_co2_all = unique_df['Gesamt_CO2_Mt'].sum()
    kohle_co2_all = fact_df[fact_df['Traeger_Name'] == 'Kohle']['CO2_Energietraeger_Mt'].sum()
    prozent_kohle = (kohle_co2_all / gesamt_co2_all) * 100 if gesamt_co2_all > 0 else 0
    avg_co2_intensitaet = unique_df['CO2_Intensitaet'].mean()
    
    print(f"Ø CO2 pro Kopf (t): {avg_pro_kopf:.2f}")
    print(f"Gesamt CO2 Mt: {gesamt_co2_all:.2f}")
    print(f"Prozent Kohle: {prozent_kohle:.2f}%")
    print(f"CO2-Intensität Ø: {avg_co2_intensitaet:.5f}")

def main():
    dim_zeit = create_dim_zeit()
    dim_energietraeger = create_dim_energietraeger()
    dim_land = create_dim_land()
    dim_gdp = create_dim_gdp_update()
    dim_sinnlos = create_dim_sinnlos()
    fact_emissionen = create_fact_emissionen()
    
    compute_measures(fact_emissionen)
    
    print("Exporting model to SQLite database...")
    # Optionally export to sqlite database!
    with sqlite3.connect(DB_PATH) as conn:
        dim_zeit.to_sql("DIM_Zeit", conn, if_exists="replace", index=False)
        dim_energietraeger.to_sql("DIM_Energietraeger", conn, if_exists="replace", index=False)
        dim_land.to_sql("DIM_Land", conn, if_exists="replace", index=False)
        dim_gdp.to_sql("DIM_GDP", conn, if_exists="replace", index=False)
        dim_sinnlos.to_sql("DIM_Sinnlos", conn, if_exists="replace", index=False)
        fact_emissionen.to_sql("FACT_Emissionen", conn, if_exists="replace", index=False)
    
    print(f"Database successfully saved to: {DB_PATH}")
    print("Done! (Star Schema created purely in Python)")

if __name__ == "__main__":
    main()
