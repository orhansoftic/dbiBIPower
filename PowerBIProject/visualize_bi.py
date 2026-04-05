import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as plt_sns
import os

# Set paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bi_cube.sqlite")
IMG_DIR = os.path.join(BASE_DIR, "Images")

os.makedirs(IMG_DIR, exist_ok=True)

def generate_visualizations():
    # Style
    plt.style.use('ggplot')
    
    # Connect
    conn = sqlite3.connect(DB_PATH)
    
    # ==========================
    # 1. Serious Report (Slide 6a)
    # ==========================
    # Map data (Top 20 Emitters Total in 2022)
    query_map = """
    SELECT l.Landname, SUM(f.Gesamt_CO2_Mt) as Total_CO2
    FROM FACT_Emissionen f
    JOIN DIM_Land l ON f.iso_code = l.iso_code
    WHERE f.year = 2022
    GROUP BY l.Landname
    ORDER BY Total_CO2 DESC
    LIMIT 15
    """
    df_top = pd.read_sql(query_map, conn)
    
    plt.figure(figsize=(12, 6))
    plt_sns.barplot(data=df_top, x='Total_CO2', y='Landname', palette='Reds_r', hue='Landname', legend=False)
    plt.title('Top 15 CO2 Emittenten weltweit im Jahr 2022 (Slice)', fontsize=14)
    plt.xlabel('CO2 in Megatonnen (Mt)')
    plt.ylabel('Land')
    plt.tight_layout()
    plt.savefig(os.path.join(IMG_DIR, 'Serious_TopEmitters.png'))
    plt.close()

    # Time series (Europe Emissions by Energy carrier over time)
    query_ts = """
    SELECT f.year, f.Traeger_Name, SUM(f.CO2_Energietraeger_Mt) as CO2
    FROM FACT_Emissionen f
    JOIN DIM_Land l ON f.iso_code = l.iso_code
    WHERE l.Kontinent = 'Europe' AND f.year >= 2000 AND f.year <= 2022
    GROUP BY f.year, f.Traeger_Name
    """
    df_ts = pd.read_sql(query_ts, conn)
    # Pivot for stacked area or line
    df_ts_pivot = df_ts.pivot(index='year', columns='Traeger_Name', values='CO2').fillna(0)
    
    plt.figure(figsize=(10, 6))
    plt.plot(df_ts_pivot.index, df_ts_pivot['Kohle'], label='Kohle', color='#4d4d4d', linewidth=2)
    plt.plot(df_ts_pivot.index, df_ts_pivot['Öl'], label='Öl', color='#b30000', linewidth=2)
    plt.plot(df_ts_pivot.index, df_ts_pivot['Gas'], label='Gas', color='#0066cc', linewidth=2)
    plt.title('CO2 Emissionen nach Energieträger in Europa (2000-2022) (Dice)', fontsize=14)
    plt.xlabel('Jahr')
    plt.ylabel('CO2 Emissionen (Mt)')
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(IMG_DIR, 'Serious_TimeSeries.png'))
    plt.close()

    # Scatter plot: GDP vs. CO2 Intensity (Drill-down insights)
    query_scatter = """
    SELECT l.Landname, l.Kontinent, AVG(f.CO2_Intensitaet) as Avg_Intensitaet, AVG(f.BIP_USD) as Avg_BIP
    FROM FACT_Emissionen f
    JOIN DIM_Land l ON f.iso_code = l.iso_code
    WHERE f.year > 2015 AND f.BIP_USD > 0
    GROUP BY l.Landname, l.Kontinent
    """
    df_scatter = pd.read_sql(query_scatter, conn)
    plt.figure(figsize=(10, 6))
    plt_sns.scatterplot(data=df_scatter, x='Avg_BIP', y='Avg_Intensitaet', hue='Kontinent', alpha=0.7)
    plt.title('BIP pro Kopf vs. CO2-Intensität (Post-Paris)', fontsize=14)
    plt.xlabel('BIP (USD)')
    plt.ylabel('CO2 Intensität')
    plt.xscale('log')
    plt.yscale('log')
    plt.tight_layout()
    plt.savefig(os.path.join(IMG_DIR, 'Serious_ScatterBIP.png'))
    plt.close()

    # ==========================
    # 2. Ridiculous Report (Slide 6b)
    # ==========================
    # Correlation Name Length and CO2
    query_rid1 = """
    SELECT l.Namenlaenge_Klasse, AVG(f.CP2_pro_Kopf_t) as Avg_CO2_Kopf
    FROM FACT_Emissionen f
    JOIN DIM_Sinnlos l ON f.iso_code = l.iso_code
    WHERE f.year = 2022
    GROUP BY l.Namenlaenge_Klasse
    """
    try:
        df_rid1 = pd.read_sql(query_rid1, conn)
        plt.figure(figsize=(8, 5))
        plt_sns.barplot(data=df_rid1, x='Namenlaenge_Klasse', y='Avg_CO2_Kopf', palette='Purples')
        plt.title('Einfluss der Länge des Ländernamens auf CO2 (Sinnlos)', fontsize=14)
        plt.xlabel('Klasse der Namenslänge')
        plt.ylabel('Durchsch. CO2 pro Kopf (t)')
        plt.tight_layout()
        plt.savefig(os.path.join(IMG_DIR, 'Ridiculous_NameLength.png'))
        plt.close()
    except Exception as e:
        print("Sinnlose Dimension 1 noch nicht im Cube:", e)

    # Correlation Beer and CO2
    query_rid2 = """
    SELECT l.Bierkonsum_Klasse, AVG(f.CP2_pro_Kopf_t) as Avg_CO2_Kopf
    FROM FACT_Emissionen f
    JOIN DIM_Sinnlos l ON f.iso_code = l.iso_code
    WHERE f.year = 2022
    GROUP BY l.Bierkonsum_Klasse
    ORDER BY Avg_CO2_Kopf DESC
    """
    try:
        df_rid2 = pd.read_sql(query_rid2, conn)
        plt.figure(figsize=(8, 5))
        plt_sns.barplot(data=df_rid2, x='Bierkonsum_Klasse', y='Avg_CO2_Kopf', palette='YlOrBr', hue='Bierkonsum_Klasse', legend=False)
        plt.title('Bierkonsum vs. CO2-Ausstoß (Sinnlose Korrelation)', fontsize=14)
        plt.xlabel('Bierkonsum Klasse')
        plt.ylabel('Durchsch. CO2 pro Kopf (t)')
        plt.tight_layout()
        plt.savefig(os.path.join(IMG_DIR, 'Ridiculous_BeerCO2.png'))
        plt.close()
    except Exception as e:
        print("Sinnlose Dimension 2 noch nicht im Cube:", e)

    print("Alle Visualisierungen wurden im Images/ Ordner gespeichert!")
    conn.close()

if __name__ == "__main__":
    generate_visualizations()
