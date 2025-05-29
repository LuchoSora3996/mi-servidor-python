import pandas as pd
import matplotlib.pyplot as plt
import sqlite3
from flask import Flask, render_template
from io import BytesIO
import base64
import os
import math

app = Flask(__name__)

# Configuración
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'metro_data.db')
EXCEL_FILE = os.path.join(BASE_DIR, 'INCIDENCIA DELICTIVA NUEVA.xlsx')

def manual_correlation(x, y):
    """Calcula la correlación de Pearson manualmente"""
    n = len(x)
    if n != len(y) or n == 0:
        return 0
    
    sum_x = sum(x)
    sum_y = sum(y)
    sum_x_sq = sum(xi**2 for xi in x)
    sum_y_sq = sum(yi**2 for yi in y)
    sum_xy = sum(xi*yi for xi, yi in zip(x, y))
    
    numerator = sum_xy - (sum_x * sum_y)/n
    denominator = math.sqrt((sum_x_sq - sum_x**2/n) * (sum_y_sq - sum_y**2/n))
    
    if denominator == 0:
        return 0
    return numerator / denominator

def load_data():
    """Carga y normaliza los datos del Excel"""
    try:
        sheets = ['2020', '2021', '2022', '2023', '2024']
        dfs = []
        
        for year in sheets:
            try:
                df = pd.read_excel(EXCEL_FILE, sheet_name=year)
                
                # Normalizar nombres de columnas
                df.columns = [col.strip().lower().replace('ó', 'o').replace('é', 'e')
                             .replace('í', 'i').replace('á', 'a').replace('ú', 'u')
                             .replace('ñ', 'n').replace(' ', '_') for col in df.columns]
                
                # Mapear nombres de columnas
                robos_col = next((c for c in df.columns if 'robo' in c or 'reporte' in c), None)
                estacion_col = next((c for c in df.columns if 'estacion' in c), None)
                
                if not robos_col or not estacion_col:
                    continue
                
                df = df.rename(columns={
                    robos_col: 'robos',
                    estacion_col: 'estacion',
                    'alcaldia': 'alcaldia',
                    'linea': 'linea'
                })
                
                # Limpieza
                df['robos'] = pd.to_numeric(df['robos'], errors='coerce').fillna(0)
                df['año'] = int(year)
                
                # Normalizar líneas
                if 'linea' in df.columns:
                    df['linea'] = (df['linea'].astype(str).str.upper()
                                  .str.replace('LÍNEA', 'L').str.replace('LINEA', 'L')
                                  .str.strip().fillna('DESCONOCIDA'))
                
                dfs.append(df[['año', 'alcaldia', 'linea', 'estacion', 'robos']].dropna())
                
            except Exception as e:
                print(f"Error en hoja {year}: {str(e)}")
                continue
        
        if not dfs:
            return pd.DataFrame()
        
        return pd.concat(dfs, ignore_index=True)
    
    except Exception as e:
        print(f"Error al cargar archivo: {str(e)}")
        return pd.DataFrame()

def generate_gender_plot():
    """Genera la gráfica de distribución por género con manejo robusto de errores"""
    try:
        # 1. Leer datos
        try:
            df_gender = pd.read_excel(EXCEL_FILE, sheet_name='Hoja1')
        except Exception as e:
            print(f"No se pudo leer Hoja1: {str(e)}")
            return None

        # 2. Normalizar columnas
        df_gender.columns = [str(col).strip().lower() for col in df_gender.columns]
        
        # 3. Verificar columnas requeridas
        required_cols = ['genero', 'frecuencia']
        if not all(col in df_gender.columns for col in required_cols):
            print("Columnas faltantes. Se encontraron:", df_gender.columns)
            return None

        # 4. Limpiar datos
        df_gender = df_gender[required_cols].dropna()
        df_gender['frecuencia'] = pd.to_numeric(df_gender['frecuencia'], errors='coerce')
        df_gender = df_gender.dropna(subset=['frecuencia'])
        
        if df_gender.empty:
            print("Datos vacíos después de limpieza")
            return None

        # 5. Crear gráfico
        fig, ax = plt.subplots(figsize=(10, 8))
        colors = ['#4e79a7', '#e15759', '#76b7b2']
        
        wedges, texts, autotexts = ax.pie(
            df_gender['frecuencia'],
            labels=df_gender['genero'],
            autopct='%1.1f%%',
            colors=colors,
            startangle=90,
            textprops={'color': 'white', 'weight': 'bold', 'size': 12},
            wedgeprops={'edgecolor': 'white', 'linewidth': 1}
        )
        
        ax.set_title('Distribución de Robos por Género', pad=20, fontweight='bold')
        plt.tight_layout()
        
        return fig_to_base64(fig)
        
    except Exception as e:
        print(f"Error inesperado en generate_gender_plot: {str(e)}")
        return None
    
def generate_plots(df):
    """Genera todas las gráficas y análisis"""
    plots = {}
    analysis = {}
    
    if df.empty:
        return plots, analysis
    
    # 1. Datos por año
    yearly = df.groupby('año')['robos'].sum().reset_index()
    analysis['total'] = f"{yearly['robos'].sum():,}"
    analysis['first_year'] = yearly['año'].min()
    analysis['last_year'] = yearly['año'].max()
    
    # Calcular correlación manualmente
    if len(yearly) >= 2:
        corr = manual_correlation(yearly['año'], yearly['robos'])
        analysis['correlation'] = corr
        analysis['trend'] = '↑ Aumenta' if corr > 0 else '↓ Disminuye'
        analysis['strength'] = 'Fuerte' if abs(corr) > 0.7 else 'Moderada'
    else:
        analysis['correlation'] = 0
        analysis['trend'] = 'No hay suficientes datos'
        analysis['strength'] = ''
    
    # Gráfica 1: Robos por año
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(yearly['año'], yearly['robos'], color='#fd9c08')
    
    # Añadir porcentajes
    total = yearly['robos'].sum()
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, height,
               f'{height:,}\n({height/total:.1%})',
               ha='center', va='bottom')
    
    ax.set_title('Robos por Año', fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    plots['year'] = fig_to_base64(fig)
    plt.close(fig)
    
    # Gráfica 2: Top estaciones
    top_stations = df.groupby('estacion')['robos'].sum().nlargest(10).reset_index()
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(top_stations['estacion'], top_stations['robos'], color='#ee3320')
    
    for i, (est, val) in enumerate(zip(top_stations['estacion'], top_stations['robos'])):
        ax.text(val + max(top_stations['robos'])*0.01, i, 
               f'{val:,} ({val/top_stations["robos"].sum():.1%})',
               va='center', fontsize=10)
    
    ax.set_title('Top 10 Estaciones con Más Robos', fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='x', linestyle='--', alpha=0.7)
    plots['stations'] = fig_to_base64(fig)
    plt.close(fig)
    
    # Gráfica 3: Por alcaldía
    by_alcaldia = df.groupby('alcaldia')['robos'].sum().nlargest(15).reset_index()
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(by_alcaldia['alcaldia'], by_alcaldia['robos'], color='#9d0377')
    
    for i, (alc, val) in enumerate(zip(by_alcaldia['alcaldia'], by_alcaldia['robos'])):
        ax.text(val + max(by_alcaldia['robos'])*0.01, i,
               f'{val:,} ({val/by_alcaldia["robos"].sum():.1%})',
               va='center', fontsize=10)
    
    ax.set_title('Robos por Alcaldía', fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='x', linestyle='--', alpha=0.7)
    plots['alcaldia'] = fig_to_base64(fig)
    plt.close(fig)
    
    # Gráfica 4: Por línea
    if 'linea' in df.columns:
        by_line = df[df['linea'] != 'DESCONOCIDA']
        by_line = by_line.groupby('linea')['robos'].sum().reset_index()
        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(by_line['linea'], by_line['robos'], color=['#d35590', '#ff6f61', '#6fa3ef', '#ffcc00', '#4caf50', '#e91e63', 
               '#9b59b6', '#3498db', '#2ecc71', '#f39c12'])
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, height,
                   f'{height:,}\n({height/by_line["robos"].sum():.1%})',
                   ha='center', va='bottom', fontsize=10)
        
        ax.set_title('Robos por Línea', fontsize=14, fontweight='bold', pad=20)
        plt.xticks(rotation=45)
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        plots['linea'] = fig_to_base64(fig)
        plt.close(fig)
    
    return plots, analysis

def fig_to_base64(fig):
    """Convierte figura matplotlib a base64"""
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    try:
        df = load_data()
        if df.empty:
            return render_template('error.html', 
                                message="No se encontraron datos válidos en el archivo Excel")
        
        plots, analysis = generate_plots(df)
        gender_plot = generate_gender_plot()
        
        return render_template('dashboard.html',
                            plots=plots,
                            analysis=analysis,
                            gender_plot=gender_plot,
                            canva_link="https://www.canva.com/design/DAGonCX66Yo/2hdY0vZkxsxQbi8cDdofuw/edit")
    
    except Exception as e:
        return render_template('error.html',
                            message=f"Error inesperado: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)