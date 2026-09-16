import streamlit as st
import pandas as pd
import re
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="Precios en la calle", layout="wide")

ARCHIVO = "Precios en la calle GT 08-09 2026.xlsx"
HOJA = "datos"

COL_MES = "Mes"
COL_FECHA = "Fecha Comprobante"
COL_CLIENTE = "Cliente"
COL_RAZON = "Razon Social"
COL_DIVISION = "Descripción DIVISION"
COL_CODIGO = "Codigo de Articulo"
COL_DESC = "Descripcion de Articulo"
COL_PTR = "Suma de PTR"
COL_PTC = "PTC"


def extraer_mes(valor):
    if valor is None:
        return None
    valor = str(valor).strip()
    if valor.startswith("{"):
        match = re.search(r'"result"\s*:\s*(-?\d+\.?\d*)', valor)
        return int(float(match.group(1))) if match else None
    try:
        return int(float(valor))
    except ValueError:
        return None


def serial_a_fecha(valor):
    """Convierte el número de serie de Excel a fecha real."""
    try:
        num = float(valor)
        return (datetime(1899, 12, 30) + timedelta(days=num)).date()
    except (ValueError, TypeError):
        return None


@st.cache_data
def cargar_datos():
    df = pd.read_excel(ARCHIVO, sheet_name=HOJA, dtype=str)

    # Limpiar mes (por si viene con formato JSON de fórmula)
    df[COL_MES] = df[COL_MES].apply(extraer_mes)

    # Convertir fecha de número de serie a fecha real
    df[COL_FECHA] = df[COL_FECHA].apply(serial_a_fecha)

    # Completar división faltante cruzando por código de artículo
    dicc_div = (
        df.dropna(subset=[COL_CODIGO, COL_DIVISION])
        .groupby(COL_CODIGO)[COL_DIVISION]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else None)
        .to_dict()
    )
    df[COL_DIVISION] = df[COL_DIVISION].fillna(df[COL_CODIGO].map(dicc_div))

    # Completar código faltante cruzando por descripción de artículo
    dicc_cod = (
        df.dropna(subset=[COL_DESC, COL_CODIGO])
        .groupby(COL_DESC)[COL_CODIGO]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else None)
        .to_dict()
    )
    df[COL_CODIGO] = df[COL_CODIGO].fillna(df[COL_DESC].map(dicc_cod))

    # Convertir columnas numéricas
    for col in [COL_PTR, COL_PTC]:
        df[col] = (
            df[col].astype(str)
            .str.replace(r"[^\d.,-]", "", regex=True)
            .str.replace(",", "", regex=False)
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


df = cargar_datos()

# ============================================================
# SIDEBAR - FILTROS
# ============================================================
st.sidebar.title("🔍 Filtros")

meses_disponibles = sorted(df[COL_MES].dropna().unique())
mes_sel = st.sidebar.multiselect("Mes", meses_disponibles, default=meses_disponibles)

divisiones = sorted(df[COL_DIVISION].dropna().unique())
division_sel = st.sidebar.multiselect("División", divisiones, default=divisiones)

clientes = sorted(df[COL_RAZON].dropna().unique())
cliente_sel = st.sidebar.multiselect("Cliente", clientes)

buscar_producto = st.sidebar.text_input("Buscar producto")

# Aplicar filtros
df_filtrado = df[df[COL_MES].isin(mes_sel) & df[COL_DIVISION].isin(division_sel)]

if cliente_sel:
    df_filtrado = df_filtrado[df_filtrado[COL_RAZON].isin(cliente_sel)]

if buscar_producto:
    df_filtrado = df_filtrado[
        df_filtrado[COL_DESC].str.contains(buscar_producto, case=False, na=False)
    ]

# ============================================================
# CONTENIDO PRINCIPAL
# ============================================================
st.title("📊 Precios en la Calle - GT 08/09 2026")

col1, col2, col3 = st.columns(3)
col1.metric("Registros filtrados", f"{len(df_filtrado):,}")
col2.metric("Suma PTR", f"$ {df_filtrado[COL_PTR].sum():,.2f}")
col3.metric("Clientes únicos", df_filtrado[COL_RAZON].nunique())

st.divider()

# Gráfico por división
st.subheader("💰 PTR por División")
resumen_division = (
    df_filtrado.groupby(COL_DIVISION)[COL_PTR]
    .sum()
    .sort_values(ascending=False)
    .reset_index()
)
fig = px.bar(resumen_division, x=COL_DIVISION, y=COL_PTR, text_auto=".2s")
st.plotly_chart(fig, use_container_width=True)

# Comparativo entre meses
if len(mes_sel) >= 2:
    st.subheader("📈 Comparativo entre meses")
    comparativo = (
        df_filtrado.groupby([COL_MES, COL_DIVISION])[COL_PTR]
        .sum()
        .reset_index()
    )
    fig2 = px.bar(
        comparativo, x=COL_DIVISION, y=COL_PTR, color=COL_MES,
        barmode="group", text_auto=".2s"
    )
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ============================================================
# TABLA DE DETALLE - Ordenada por fecha, más reciente primero
# ============================================================
st.subheader("📋 Detalle de registros")

df_ordenado = df_filtrado.sort_values(by=COL_FECHA, ascending=False)

st.dataframe(
    df_ordenado[[COL_MES, COL_FECHA, COL_CLIENTE, COL_RAZON, COL_DIVISION,
                 COL_CODIGO, COL_DESC, COL_PTR, COL_PTC]],
    use_container_width=True,
    height=400,
)

# Descarga (también ordenada por fecha descendente)
csv = df_ordenado.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Descargar tabla filtrada (CSV)",
    csv,
    "datos_filtrados.csv",
    "text/csv",
)