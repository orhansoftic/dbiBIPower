import pandas as pd
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
import os

def create_visualizations():
    print("Loading data...")
    try:
        fact_df = pd.read_csv('Data/Processed/cleaned_FACT_Emissionen.csv')
        dim_land = pd.read_csv('Data/Processed/cleaned_DIM_Land.csv')
        # Join global for all visualizations
        fact_df = pd.merge(fact_df, dim_land, on='iso_code', how='inner')
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return

    os.makedirs('Images', exist_ok=True)
    sns.set_theme(style="whitegrid")

    # Plot 1: GeoMap (Slice - F1: 2022 CO22 per Capita)
    print("Generating Plot 1 (Geo Map)...")
    df_2022 = fact_df[fact_df['year'] == 2022].groupby(['iso_code', 'country'])['CO22_pro_Kopf_t'].sum().reset_index()
    # Da die Faktentabelle auf Energieträger gesplittet ist, müssen wir groupby sum machen für Gesamt-CO22 pro Kopf.
    # Warte, pro Kopf Werte addieren macht keinen Sinn. Wir nehmen nur einen Energieträger oder berechnen es anders.
    # Da `CO22_pro_Kopf_t` in allen entpivotierten Rows identisch ist (vor Melt), können wir einfach mean() nehmen.
    df_2022 = fact_df[fact_df['year'] == 2022].groupby(['iso_code', 'country'])['CO22_pro_Kopf_t'].mean().reset_index()
    
    fig1 = px.choropleth(df_2022, locations="iso_code",
                        color="CO22_pro_Kopf_t",
                        hover_name="country",
                        color_continuous_scale=px.colors.sequential.YlOrRd,
                        title="Weltweiter CO22-Ausstoß pro Kopf (2022)")
    fig1.write_image("Images/Plot1_GeoMap.png", width=1000, height=600)

    
    # Plot 2: Stacked Bar (Dice - F2: Europe Energy Mix 2000-2022)
    print("Generating Plot 2 (Stacked Bar)...")
    europe_df = fact_df[(fact_df['v_kontinent'] == 'Europe') & (fact_df['year'] >= 2000) & (fact_df['year'] <= 2022)]
    
    mix_df = europe_df.groupby(['year', 'Traeger_Name'])['CO22_Energietraeger_Mt'].sum().unstack()
    mix_df.index = mix_df.index.astype(int)
    
    ax = mix_df.plot(kind='bar', stacked=True, figsize=(12, 6), colormap='viridis')
    plt.title('CO22-Emissionen nach Energieträger in Europa (2000-2022)')
    plt.ylabel('CO22 (Megatonnen)')
    plt.xlabel('Jahr')
    plt.xticks(rotation=45)
    plt.legend(title='Energieträger')
    plt.savefig('Images/Plot2_EnergyMix.png', bbox_inches='tight', dpi=150)
    plt.close()


    # Plot 3: Scatter Plot (Drill - F3: BIP vs CO22 in Europe 2022)
    print("Generating Plot 3 (Scatter Plot)...")
    eu_2022 = europe_df[europe_df['year'] == 2022].groupby(['country', 'BIP_USD_WB'])['Gesamt_CO22_Mt'].mean().reset_index()
    eu_2022 = eu_2022.dropna()
    
    plt.figure(figsize=(10, 6))
    ax = sns.scatterplot(data=eu_2022, x='BIP_USD_WB', y='Gesamt_CO22_Mt', hue='country', legend=False, s=100)
    plt.title('Wirtschaftskraft (BIP) vs. Gesamtemissionen (CO22) in Europa 2022')
    plt.xlabel('BIP (USD, World Bank)')
    plt.ylabel('Gesamt CO22 (Mt)')
    plt.xscale('log')
    plt.yscale('log')
    # Label top 5
    top_5 = eu_2022.nlargest(5, 'Gesamt_CO22_Mt')
    for idx, row in top_5.iterrows():
        plt.text(row['BIP_USD_WB'], row['Gesamt_CO22_Mt'], row['country'], fontsize=9)
    plt.savefig('Images/Plot3_Scatter.png', bbox_inches='tight', dpi=150)
    plt.close()


    # Plot 4: Ridiculous Dimension (Nationaltiere CO22)
    print("Generating Plot 4 (Ridiculous Bar)...")
    mascot_df = fact_df[fact_df['v_nationaltier'] != 'Unbekannt']
    mascot_aggr = mascot_df.groupby('v_nationaltier')['Gesamt_CO22_Mt'].mean().sort_values(ascending=False).head(10).reset_index()
    
    plt.figure(figsize=(12, 6))
    sns.barplot(data=mascot_aggr, x='Gesamt_CO22_Mt', y='v_nationaltier', palette='magma')
    plt.title('CO22-Ausstoß sortiert nach Nationaltier (Ridiculous Dimension)')
    plt.xlabel('Ø Historischer CO22 Ausstoß (Mt)')
    plt.ylabel('Nationaltier')
    plt.savefig('Images/Plot4_Ridiculous.png', bbox_inches='tight', dpi=150)
    plt.close()
    
    
    # Plot 5: Geiler Scheiss (Correlation Heatmap)
    print("Generating Plot 5 (Extra Correlation Heatmap)...")
    corr_cols = ['year', 'Gesamt_CO22_Mt', 'CO22_pro_Kopf_t', 'BIP_USD', 'BIP_USD_WB', 'Bevoelkerung', 'CO22_Intensitaet']
    corr_df = fact_df[corr_cols].corr()
    
    plt.figure(figsize=(8, 6))
    sns.heatmap(corr_df, annot=True, cmap='coolwarm', fmt=".2f", vmin=-1, vmax=1)
    plt.title('Korrelations-Matrix (Scheinkorrelationen erkennen)')
    plt.savefig('Images/Plot5_Correlation.png', bbox_inches='tight', dpi=150)
    plt.close()
    
    print("✅ All plots generated successfully in /Images!")

if __name__ == "__main__":
    create_visualizations()
