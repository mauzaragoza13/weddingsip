
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np

st.set_page_config(page_title="Evaluador de Funnel - Isla Pasión", layout="wide")

st.title("📊 Evaluador de Funnel - Isla Pasión Weddings (con ajuste por tiempo)")
st.markdown("Carga tu base de leads para estimar la probabilidad de cierre y visualizar resultados por Wedding Planner. "
            "Ahora ajusta por antigüedad usando Created Time vs hoy (promedio cierre: 23 días).")

archivo = st.file_uploader("Sube tu archivo (.csv o .xlsx)", type=["csv", "xlsx"])

PROMEDIO_CIERRE = 23  # días promedio de cierre

def time_factor(dias, estatus):
    """
    Ajuste por vigencia temporal:
    - Antes de 23 días: casi no castiga.
    - Después de 23: decae exponencialmente.
    - Decae más rápido en 'Análisis', más lento en 'Negociación'.
    """
    if pd.isna(dias) or dias < 0:
        return 1.0

    estatus = str(estatus).strip()

    # Half-life: cuántos días "pasados" para reducirse a la mitad
    if estatus == "Análisis":
        half_life = 8     # muy estricto
    elif estatus == "Diseño":
        half_life = 12
    elif estatus == "Negociación":
        half_life = 18    # más tolerante
    else:
        half_life = 10

    overdue = max(0, dias - PROMEDIO_CIERRE)
    factor = 0.5 ** (overdue / half_life)

    # piso mínimo para no matar totalmente por regla
    return float(np.clip(factor, 0.03, 1.0))


if archivo:
    try:
        if archivo.name.endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)

        st.success("Archivo cargado correctamente.")
        st.subheader("Vista previa de los datos:")
        st.dataframe(df.head())

        columnas_necesarias = [
            "Nombre del lead", "Presupuesto", "Número de interacciones", "Canal", "Estatus",
            "Contestó correo", "Contestó mensaje", "Contestó llamada", "Wedding Planner"
        ]

        if not all(col in df.columns for col in columnas_necesarias):
            st.error("Faltan columnas necesarias. Asegúrate de incluir: "
                     + ", ".join(columnas_necesarias))
            st.stop()

        # --- detectar columna Created Time ---
        posibles_created = [
            "Created Time", "Created time", "created time", "Fecha creación", "Fecha de creación",
            "Creado", "Fecha creado", "Fecha alta", "Created", "created", "Creation Date"
        ]
        created_candidates = [c for c in df.columns if c in posibles_created]

        # también detecta por coincidencia parcial
        if not created_candidates:
            created_candidates = [c for c in df.columns if "created" in c.lower() or "crea" in c.lower()]

        if not created_candidates:
            st.error("No encuentro la columna de fecha de creación (Created Time). "
                     "Agrega una columna tipo 'Created Time' o 'Fecha de creación'.")
            st.stop()

        if len(created_candidates) == 1:
            created_col = created_candidates[0]
        else:
            created_col = st.selectbox("Selecciona la columna de Created Time (fecha de creación):", created_candidates)

        # normalizar booleanos (más robusto)
        for col in ["Contestó correo", "Contestó mensaje", "Contestó llamada"]:
            df[col] = (
                df[col].astype(str).str.strip().str.upper()
                .map({
                    "VERDADERO": True, "TRUE": True, "1": True, "SI": True, "SÍ": True,
                    "FALSO": False, "FALSE": False, "0": False, "NO": False
                })
                .fillna(False)
            )

        # parsear created time
        df[created_col] = pd.to_datetime(df[created_col], errors="coerce")

        hoy = pd.Timestamp(datetime.now().date())
        df["Días desde creación"] = (hoy - df[created_col]).dt.days

        # ------- tu score base (igual, pero luego ajusta por tiempo) -------
        def prob_base(row):
            # Regla dura: si está en análisis y no respondió nada -> 0
            if row["Estatus"] == "Análisis" and not (row["Contestó correo"] or row["Contestó mensaje"] or row["Contestó llamada"]):
                return 0.0

            # base por interacciones
            if row["Número de interacciones"] >= 6:
                base = 0.06
            elif row["Número de interacciones"] >= 4:
                base = 0.03
            elif row["Número de interacciones"] >= 2:
                base = 0.01
            else:
                base = 0.0

            canal_bonus = 0.01 if row["Canal"] == "Meta" else 0.04

            if row["Estatus"] == "Análisis":
                estatus_bonus = 0.0
            elif row["Estatus"] == "Diseño":
                estatus_bonus = 0.05
            elif row["Estatus"] == "Negociación":
                estatus_bonus = 0.20
            else:
                estatus_bonus = 0.0

            presupuesto_bonus = 0.06 if 450000 <= row["Presupuesto"] <= 520000 else 0.0

            contacto_bonus = 0.0
            if row["Contestó correo"]:
                contacto_bonus += 0.01
            if row["Contestó mensaje"]:
                contacto_bonus += 0.02
            if row["Contestó llamada"]:
                contacto_bonus += 0.10

            p = base + canal_bonus + estatus_bonus + presupuesto_bonus + contacto_bonus
            return min(max(p, 0.0), 0.70)

        def calcular_probabilidad(row):
            p0 = prob_base(row)
            tf = time_factor(row["Días desde creación"], row["Estatus"])
            p = p0 * tf
            return float(np.clip(p, 0.0, 0.70))

        df["Probabilidad Base"] = df.apply(prob_base, axis=1)
        df["Probabilidad de Cierre"] = df.apply(calcular_probabilidad, axis=1)
        df["Valor Estimado"] = df["Presupuesto"] * df["Probabilidad de Cierre"]

        # métricas útiles para explicar calibración
        st.subheader("Resumen de ajuste por tiempo")
        st.write(f"📌 Promedio histórico de cierre: **{PROMEDIO_CIERRE} días** (ancla del decaimiento).")
        st.metric("Probabilidad promedio (base)", f"{df['Probabilidad Base'].mean()*100:.1f}%")
        st.metric("Probabilidad promedio (ajustada hoy)", f"{df['Probabilidad de Cierre'].mean()*100:.1f}%")

        overdue = (df["Días desde creación"] > PROMEDIO_CIERRE).sum()
        st.metric("Leads 'pasados' (>23 días)", f"{overdue} de {len(df)}")

        st.subheader("Resultados del Funnel:")
        st.dataframe(df[[
            "Nombre del lead", "Wedding Planner", "Presupuesto", "Número de interacciones",
            "Canal", "Estatus", "Contestó correo", "Contestó mensaje", "Contestó llamada",
            created_col, "Días desde creación",
            "Probabilidad Base", "Probabilidad de Cierre", "Valor Estimado"
        ]])

        valor_total = df["Valor Estimado"].sum()
        st.metric("💰 Valor total estimado del funnel (ajustado hoy)", f"${valor_total:,.2f}")

        st.subheader("📊 Valor Estimado por Wedding Planner")
        resumen = df.groupby("Wedding Planner")["Valor Estimado"].sum().sort_values(ascending=False)

        fig, ax = plt.subplots(figsize=(6, 2.4))
        resumen.plot(kind="bar", ax=ax)
        ax.set_ylabel("Valor Estimado ($)")
        ax.set_title("Valor Estimado por WP (ajustado por tiempo)")
        ax.tick_params(axis='x', rotation=45)
        st.pyplot(fig)

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
