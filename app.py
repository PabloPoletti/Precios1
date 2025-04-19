# ───────────────────────────────  app.py  ───────────────────────────────
import subprocess, pathlib, nest_asyncio, streamlit as st
import duckdb, pandas as pd, altair as alt

nest_asyncio.apply()                                  # re‑usa el event‑loop

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

# ▸ Opción 1 (use SHOW TABLES)  ───────────────────────────────────────────
tbls = con.execute("SHOW TABLES").fetchall()          # devuelve [('prices',)]
if ("prices",) not in tbls:
    from etl.indexer import update_all_sources
    update_all_sources(str(DB_PATH))

# ▸ Opción 2 (si prefieres seguir con duckdb_tables()) --------------------
# exists = con.execute(
#     "SELECT 1 FROM duckdb_tables() WHERE table_name='prices'"
# ).fetchone()
# if not exists:
#     from etl.indexer import update_all_sources
#     update_all_sources(str(DB_PATH))
# ------------------------------------------------------------------------

# ---------- C)  Streamlit UI --------------------------------------------
st.set_page_config(page_title="Índice diario IPC‑Online 🇦🇷", layout="wide")
st.title("Índice Diario de Precios al Consumidor (experimental)")

with st.sidebar:
    if st.button("Actualizar precios ahora"):
        from etl.indexer import update_all_sources
        update_all_sources(str(DB_PATH))
        st.success("¡Datos actualizados!")

    provincia = st.selectbox(
        "Provincia / Región",
        ["Nacional", "GBA", "Pampeana", "Noreste", "Noroeste", "Cuyo", "Patagonia"],
    )

from etl.indexer import compute_indices
raw = con.execute("SELECT * FROM prices").fetch_df()
raw = raw[(raw["province"] == provincia) | (raw["province"] == "Nacional")]

idx = compute_indices(raw)

st.subheader(f"Evolución {provincia}")
st.altair_chart(
    alt.Chart(idx).mark_line().encode(
        x="date:T", y="index:Q", tooltip=["date:T", "index:Q"]
    ),
    use_container_width=True,
)

st.subheader("Divisiones IPC")
div_df = raw.groupby(["division", "date"]).price.mean().reset_index()
st.altair_chart(
    alt.Chart(div_df).mark_line().encode(
        x="date:T", y="price:Q", color="division:N",
        tooltip=["division:N", "price:Q", "date:T"],
    ),
    use_container_width=True,
)
# ─────────────────────────────────────────────────────────────────────────
