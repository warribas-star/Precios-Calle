import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Precios en la Calle", layout="wide")

st.title("📊 Precios en la Calle - GT")

# ------------------------------
# 1. CARGA DE DATOS
# ------------------------------
st.sidebar.header("Cargar datos")

archivo = st.sidebar.file_uploader("Subí un Excel actualizado (opcional)", type=["xlsx"])

@st.cache_data
def cargar_datos(path_or_buffer):
    df = pd.read_excel(path_or_buffer, sheet_name="datos")
    df.columns = [c.strip() for c in df.columns]  # limpia espacios
    return df

try:
    if archivo is not None:
        df = cargar_datos(archivo)
        st.sidebar.success("Archivo cargado correctamente ✅")
    else:
        df = cargar_datos("Precios en la calle GT 08-09 2026.xlsx")
        st.sidebar.info("Usando archivo local por defecto")
except Exception as e:
    st.error(f"Error al cargar el archivo: {e}")
    st.stop()

with st.expander("🔍 Ver columnas detectadas en el Excel"):
    st.write(list(df.columns))

# Etiqueta más legible para elegir clientes (Código - Razón Social)
df["Cliente_label"] = df["Cliente"].astype(str) + " - " + df["Razon Social"].astype(str)

# ------------------------------
# 2. FILTRO DE CLIENTE (ÚNICO, se usa en todo)  🆕
# ------------------------------
st.sidebar.header("Filtro de Cliente")

clientes_sel = st.sidebar.multiselect(
    "Cliente (dejar vacío = todos)",
    options=sorted(df["Cliente_label"].dropna().unique()),
)

# Aplicamos el filtro de cliente a TODO el dataset base
if clientes_sel:
    df_base = df[df["Cliente_label"].isin(clientes_sel)]
else:
    df_base = df.copy()

# ------------------------------
# 3. OTROS FILTROS (solo afectan al detalle, no al cuadro pivot)
# ------------------------------
st.sidebar.header("Otros filtros (detalle)")

def multiselect_filtro(dframe, col_nombre, label):
    if col_nombre not in dframe.columns:
        st.sidebar.warning(f"⚠️ No se encontró la columna '{col_nombre}'")
        return []
    opciones = sorted(dframe[col_nombre].dropna().unique())
    seleccion = st.sidebar.multiselect(label, opciones, key=f"filtro_{col_nombre}")
    return seleccion

meses = multiselect_filtro(df_base, "Mes", "Mes")
divisiones = multiselect_filtro(df_base, "Descripción DIVISION", "División")
productos = multiselect_filtro(df_base, "Descripcion de Articulo", "Producto")

df_filtrado = df_base.copy()

if meses:
    df_filtrado = df_filtrado[df_filtrado["Mes"].isin(meses)]
if divisiones:
    df_filtrado = df_filtrado[df_filtrado["Descripción DIVISION"].isin(divisiones)]
if productos:
    df_filtrado = df_filtrado[df_filtrado["Descripcion de Articulo"].isin(productos)]

# ------------------------------
# 4. MÉTRICAS RÁPIDAS
# ------------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("Registros", len(df_filtrado))
col2.metric("Bultos totales", round(df_filtrado["Btos"].sum(), 2) if "Btos" in df_filtrado else "-")
col3.metric("PTR promedio", round(df_filtrado["PTR unit"].mean(), 2) if "PTR unit" in df_filtrado else "-")
col4.metric("PTC promedio", round(df_filtrado["PTC"].mean(), 2) if "PTC" in df_filtrado else "-")

# ------------------------------
# 5. CUADRO DE VOLUMEN POR DIVISIÓN Y MES
#    (usa df_base → ya filtrado por Cliente)
# ------------------------------
st.markdown("---")
st.subheader("📦 Volumen (Bultos) por División y Mes")

mostrar_total = st.checkbox("Mostrar fila/columna de Total", value=True)

if df_base.empty:
    st.warning("No hay datos para ese cliente.")
else:
    pivot = pd.pivot_table(
        df_base,
        values="Btos",
        index="Descripción DIVISION",
        columns="Mes",
        aggfunc="sum",
        fill_value=0,
        margins=mostrar_total,
        margins_name="Total"
    )
    st.dataframe(
        pivot.style.format("{:,.1f}"),
        use_container_width=True
    )

    csv_pivot = pivot.to_csv().encode("utf-8")
    st.download_button(
        "📥 Descargar este cuadro (CSV)",
        csv_pivot,
        "volumen_division_mes.csv",
        "text/csv",
        key="download_pivot"
    )

st.markdown("---")

# ------------------------------
# 6. TABLA DETALLE
#    (usa df_filtrado → mismo cliente + otros filtros)
# ------------------------------
st.subheader("📋 Detalle de precios")
st.dataframe(df_filtrado, use_container_width=True)

# ------------------------------
# 7. GRÁFICOS
# ------------------------------
st.subheader("📈 Evolución de precios")

if "Mes" in df_filtrado.columns and "PTC" in df_filtrado.columns:
    df_evol = (
        df_filtrado.groupby(["Mes", "Descripcion de Articulo"])["PTC"]
        .mean()
        .reset_index()
    )
    fig = px.line(
        df_evol,
        x="Mes",
        y="PTC",
        color="Descripcion de Articulo",
        markers=True,
        title="Evolución del PTC por producto",
    )
    st.plotly_chart(fig, use_container_width=True)

st.subheader("🏆 Top productos por PTR")

if "PTR x bulto" in df_filtrado.columns:
    top_ptr = (
        df_filtrado.groupby("Descripcion de Articulo")["PTR x bulto"]
        .mean()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )
    fig2 = px.bar(
        top_ptr,
        x="PTR x bulto",
        y="Descripcion de Articulo",
        orientation="h",
        title="Top 10 productos - PTR por bulto",
    )
    st.plotly_chart(fig2, use_container_width=True)

# ------------------------------
# 8. DESCARGA GENERAL
# ------------------------------
st.sidebar.header("Exportar")
csv = df_filtrado.to_csv(index=False).encode("utf-8")
st.sidebar.download_button(
    "📥 Descargar filtro actual (CSV)",
    csv,
    "precios_filtrados.csv",
    "text/csv",
)