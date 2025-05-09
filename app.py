import subprocess
import pathlib

import nest_asyncio
import streamlit as st

# ——— Debe ser la PRIMERA llamada a Streamlit ———
st.set_page_config(
    page_title="Índice diario IPC‑Online 🇦🇷",
    layout="wide",
)

import duckdb
import pandas as pd
import altair as alt

# Importamos el scraper liviano de ML
from etl.ml_scraper import ml_price_stats
from etl.indexer import update_all_sources, compute_indices

nest_asyncio.apply()  # re‑usa el event‑loop

# ---------- A)  Garantizar Chromium (Playwright) -------------------------
def ensure_playwright():
    cache = pathlib.Path.home() / ".cache" / "ms-playwright" / "chromium"
    if cache.exists():
        return
    st.info("Descargando Chromium… (sólo la primera vez)")
    subprocess.run(["playwright", "install", "chromium"], check=True)

ensure_playwright()

# ---------- B)  Base DuckDB ---------------------------------------------
DB_PATH = pathlib.Path("data/prices.duckdb")
DB_PATH.parent.mkdir(exist_ok=True)
con = duckdb.connect(str(DB_PATH))

# Si no existe la tabla, la creamos y lanzamos el ETL
tbls = con.execute("SHOW TABLES").fetchall()
if ("prices",) not in tbls:
    update_all_sources(str(DB_PATH))

# ---------- C)  Streamlit UI --------------------------------------------
st.title("Índice Diario de Precios al Consumidor (experimental)")

with st.sidebar:
    if st.button("Actualizar precios ahora"):
        update_all_sources(str(DB_PATH))
        st.success("¡Datos actualizados!")

    provincia = st.selectbox(
        "Provincia / Región",
        ["Nacional", "GBA", "Pampeana", "Noreste", "Noroeste", "Cuyo", "Patagonia"],
    )

# ─────────────────────────────────────────────────────────────────────────
#   Carga de datos y cálculo de índice simple (sin diferenciación provincial)
# ─────────────────────────────────────────────────────────────────────────
raw = con.execute("SELECT * FROM prices").fetch_df()
idx = compute_indices(raw)  # nueva firma: solo DataFrame

# ─────────────────────────────────────────────────────────────────────────
#   Gráficos IPC
# ─────────────────────────────────────────────────────────────────────────
st.subheader(f"Evolución general de precios")
st.altair_chart(
    alt.Chart(idx)
       .mark_line()
       .encode(
           x="date:T",
           y="index:Q",
           tooltip=["date:T", "index:Q"],
       ),
    use_container_width=True,
)

st.subheader("Divisiones IPC")
div_df = (
    raw.groupby(["division", "date"])
       .price.mean()
       .reset_index()
)
st.altair_chart(
    alt.Chart(div_df)
       .mark_line()
       .encode(
           x="date:T",
           y="price:Q",
           color="division:N",
           tooltip=["division:N", "price:Q", "date:T"],
       ),
    use_container_width=True,
)

# ─────────────────────────────────────────────────────────────────────────
#   Sección Mercado Libre (scraping de HTML público)
# ─────────────────────────────────────────────────────────────────────────
st.subheader("Comparativo de precios en Mercado Libre")

# Ejemplo de consultas
queries = ["leche entera", "pan francés", "aceite girasol"]
ml_stats = {}

for q in queries:
    stats = ml_price_stats(q)
    if stats:
        ml_stats[q] = stats
    else:
        st.warning(f"No se encontraron precios para '{q}' en Mercado Libre.")

if ml_stats:
    ml_df = pd.DataFrame(ml_stats).T.reset_index().rename(columns={
        "index": "producto",
        "avg_price": "Precio promedio ML",
        "min_price": "Precio mínimo ML",
        "max_price": "Precio máximo ML",
    })
    st.dataframe(ml_df, use_container_width=True)

    chart = (
        alt.Chart(
            ml_df.melt(
                id_vars="producto",
                value_vars=["Precio promedio ML", "Precio mínimo ML", "Precio máximo ML"]
            )
        )
        .mark_bar()
        .encode(
            x="producto:N",
            y="value:Q",
            color="variable:N",
            tooltip=["producto:N", "variable:N", "value:Q"]
        )
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("No se obtuvieron datos de Mercado Libre para las consultas definidas.")
