import streamlit as st
import pandas as pd
import plotly.express as px
import json
import re
import unicodedata

st.set_page_config(page_title="Precios en la Calle", layout="wide")

st.title("📊 Precios en la Calle - GT")

# ------------------------------
# 1. CARGA DE DATOS (mes actual + mes anterior)
# ------------------------------
ARCHIVO_MES_ACTUAL = "mes actual.xlsx"
ARCHIVO_MES_ANTERIOR = "mes anterior.xlsx"
NOMBRE_HOJA = "Hoja2"
FILA_ENCABEZADOS = 3  # Los encabezados están en la fila 4 del Excel (índice 3)

COLUMNAS_REQUERIDAS = [
    "Mes",
    "Fecha Comprobante",
    "Cliente",
    "Razon Social",
    "Codigo de Articulo",
    "Descripcion de Articulo",
    "Descripción DIVISION",
    "Btos",
    "% desc",
    "Suma de PTR",
    "PTR unit",
    "PTC",
]

# ------------------------------
# Normalización de nombres de columnas
# ------------------------------
def normalizar(texto):
    texto = str(texto)
    texto = texto.strip()
    texto = re.sub(r"\s+", " ", texto)
    texto_sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )
    return texto_sin_acentos.lower()

ALIAS_A_CANONICO = {
    normalizar("Mes"): "Mes",
    normalizar("Fecha Comprobante"): "Fecha Comprobante",
    normalizar("Cliente"): "Cliente",
    normalizar("Razon Social"): "Razon Social",
    normalizar("Codigo de Articulo"): "Codigo de Articulo",
    normalizar("Descripcion de Articulo"): "Descripcion de Articulo",
    normalizar("Descripción DIVISION"): "Descripción DIVISION",
    normalizar("Btos"): "Btos",
    normalizar("% desc"): "% desc",
    normalizar("Suma de PTR"): "Suma de PTR",
    normalizar("PTR unit"): "PTR unit",
    normalizar("PTR Unit"): "PTR unit",
    normalizar("PTC"): "PTC",
}

def normalizar_columnas(df):
    nuevas_columnas = {}
    for col in df.columns:
        clave = normalizar(col)
        if clave in ALIAS_A_CANONICO:
            nuevas_columnas[col] = ALIAS_A_CANONICO[clave]
    return df.rename(columns=nuevas_columnas)

@st.cache_data
def cargar_datos(path):
    df = pd.read_excel(path, sheet_name=NOMBRE_HOJA, header=FILA_ENCABEZADOS)
    df.columns = [str(c).strip() for c in df.columns]
    df = normalizar_columnas(df)
    return df

@st.cache_data
def cargar_y_combinar(archivos):
    dfs = []
    info_columnas = {}
    for a in archivos:
        try:
            d = cargar_datos(a)
            info_columnas[a] = list(d.columns)
            dfs.append(d)
        except Exception as e:
            st.error(f"No se pudo leer '{a}': {e}")
    if not dfs:
        return pd.DataFrame(), info_columnas
    return pd.concat(dfs, ignore_index=True), info_columnas

df, info_columnas = cargar_y_combinar([ARCHIVO_MES_ACTUAL, ARCHIVO_MES_ANTERIOR])

if df.empty:
    st.error(
        "No se pudieron cargar los datos. Verificá que existan los archivos "
        f"'{ARCHIVO_MES_ACTUAL}' y '{ARCHIVO_MES_ANTERIOR}' en la carpeta del proyecto, "
        f"y que tengan una hoja llamada '{NOMBRE_HOJA}'."
    )
    st.stop()

with st.expander("🔍 Ver columnas detectadas en cada archivo"):
    for archivo, cols in info_columnas.items():
        st.write(f"**{archivo}**:", cols)

# ------------------------------
# Validación de columnas requeridas
# ------------------------------
faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]

if faltantes:
    st.error(
        "❌ Faltan columnas requeridas en los datos combinados: "
        f"{faltantes}\n\n"
        "Revisá el expander de arriba para ver qué columnas tiene cada archivo "
        "y corregí los nombres en el Excel (o avisame para ajustar el código)."
    )
    st.stop()

# Etiqueta más legible para elegir clientes (Código - Razón Social)
df["Cliente_label"] = df["Cliente"].astype(str) + " - " + df["Razon Social"].astype(str)

# ------------------------------
# Convertir Fecha Comprobante
# ------------------------------
def convertir_fecha(serie):
    if pd.api.types.is_datetime64_any_dtype(serie):
        return serie

    fecha_directa = pd.to_datetime(serie, errors="coerce", dayfirst=True)
    if fecha_directa.notna().mean() > 0.5:
        return fecha_directa

    serie_numerica = pd.to_numeric(serie, errors="coerce")
    return pd.to_datetime(serie_numerica, unit="D", origin="1899-12-30", errors="coerce")

df["Fecha Comprobante"] = convertir_fecha(df["Fecha Comprobante"])

# ------------------------------
# Limpiar columna "Mes"
# (algunas celdas vienen como JSON tipo {"formula":"","result":9}
#  y siempre debe quedar como entero, sin decimales)
# ------------------------------
def limpiar_mes(valor):
    if isinstance(valor, str) and valor.strip().startswith("{"):
        try:
            data = json.loads(valor)
            valor = data.get("result", valor)
        except (json.JSONDecodeError, TypeError):
            pass
    try:
        return int(float(valor))
    except (ValueError, TypeError):
        return valor

df["Mes"] = df["Mes"].apply(limpiar_mes)

# ------------------------------
# 2. FILTROS (arriba, en la página principal)
# ------------------------------
st.markdown("### 🔎 Filtros")

fcol1, fcol2, fcol3, fcol4 = st.columns(4)

with fcol1:
    clientes_sel = st.multiselect(
        "Cliente (dejar vacío = todos)",
        options=sorted(df["Cliente_label"].dropna().unique()),
    )

if clientes_sel:
    df_base = df[df["Cliente_label"].isin(clientes_sel)]
else:
    df_base = df.copy()

def multiselect_filtro(contenedor, dframe, col_nombre, label, default=None):
    if col_nombre not in dframe.columns:
        contenedor.warning(f"⚠️ No se encontró la columna '{col_nombre}'")
        return []
    opciones = sorted(dframe[col_nombre].dropna().unique())
    if default is None:
        default = []
    else:
        default = [d for d in default if d in opciones]
    seleccion = contenedor.multiselect(label, opciones, default=default, key=f"filtro_{col_nombre}")
    return seleccion

with fcol2:
    meses = multiselect_filtro(st, df_base, "Mes", "Mes")

with fcol3:
    divisiones = multiselect_filtro(st, df_base, "Descripción DIVISION", "División")

codigo_default = 7634
desc_default = df_base.loc[
    pd.to_numeric(df_base["Codigo de Articulo"], errors="coerce") == codigo_default,
    "Descripcion de Articulo"
].dropna().unique()
desc_default = list(desc_default)

with fcol4:
    productos = multiselect_filtro(
        st, df_base, "Descripcion de Articulo", "Producto", default=desc_default
    )

df_filtrado = df_base.copy()

if meses:
    df_filtrado = df_filtrado[df_filtrado["Mes"].isin(meses)]
if divisiones:
    df_filtrado = df_filtrado[df_filtrado["Descripción DIVISION"].isin(divisiones)]
if productos:
    df_filtrado = df_filtrado[df_filtrado["Descripcion de Articulo"].isin(productos)]

st.markdown("---")

# ------------------------------
# 3. MÉTRICAS RÁPIDAS
# ------------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("Registros", len(df_filtrado))
col2.metric("Bultos totales", round(df_filtrado["Btos"].sum(), 2) if "Btos" in df_filtrado else "-")
col3.metric("PTR promedio", round(df_filtrado["PTR unit"].mean(), 2) if "PTR unit" in df_filtrado else "-")
col4.metric("PTC promedio", round(df_filtrado["PTC"].mean(), 2) if "PTC" in df_filtrado else "-")

# ------------------------------
# 4. CUADRO DE VOLUMEN POR DIVISIÓN Y MES
# ------------------------------
st.markdown("---")
st.subheader("📦 Volumen (Bultos) por División y Mes")

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
    )

    tabla_html = pivot.style.format("{:,.1f}").to_html()
    st.markdown(
        f"""
        <style>
        .pivot-table table {{
            width: auto !important;
            border-collapse: collapse;
        }}
        .pivot-table th, .pivot-table td {{
            padding: 4px 10px !important;
            white-space: nowrap;
            text-align: right;
            border: 1px solid #444;
        }}
        </style>
        <div class="pivot-table">
        {tabla_html}
        </div>
        """,
        unsafe_allow_html=True,
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
# 5. TABLA DETALLE
# ------------------------------
st.subheader("📋 Detalle de precios")

columnas_detalle = [
    "Fecha Comprobante",
    "Codigo de Articulo",
    "Descripcion de Articulo",
    "Btos",
    "% desc",
    "Suma de PTR",
    "PTR unit",
    "PTC",
]

columnas_disponibles = [c for c in columnas_detalle if c in df_filtrado.columns]

df_detalle = df_filtrado[columnas_disponibles].rename(columns={
    "Fecha Comprobante": "Fecha",
    "Codigo de Articulo": "Código de Producto",
    "Descripcion de Articulo": "Descripción de Producto",
    "Btos": "Bultos",
    "% desc": "Descuento (%)",
    "Suma de PTR": "PTR Total",
})

st.dataframe(df_detalle, use_container_width=True)

# ------------------------------
# 6. GRÁFICO DE EVOLUCIÓN DE PRECIOS
# ------------------------------
st.subheader("📈 Evolución de precios (PTR unit)")

if not productos:
    st.info("👆 Seleccioná al menos un **Producto** en los filtros de arriba para ver su evolución de precios.")
elif "Fecha Comprobante" in df_filtrado.columns and "PTR unit" in df_filtrado.columns:
    df_evol = (
        df_filtrado.groupby(["Fecha Comprobante", "Descripcion de Articulo"])["PTR unit"]
        .mean()
        .reset_index()
        .sort_values("Fecha Comprobante")
    )
    fig = px.line(
        df_evol,
        x="Fecha Comprobante",
        y="PTR unit",
        color="Descripcion de Articulo",
        markers=True,
        title="Evolución del PTR unit por producto",
    )
    fig.update_xaxes(tickformat="%d-%b-%Y")
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------
# 7. DESCARGA GENERAL
# ------------------------------
st.markdown("---")
csv = df_filtrado.to_csv(index=False).encode("utf-8")
st.download_button(
    "📥 Descargar filtro actual (CSV)",
    csv,
    "precios_filtrados.csv",
    "text/csv",
)