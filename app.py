import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np

st.set_page_config(page_title="Evaluador de Funnel - Isla Pasión", layout="wide")

st.title("📊 Evaluador de Funnel - Isla Pasión Weddings (ajuste por tiempo + horizonte)")
st.markdown(
    "Estimación ajustada usando: (1) score base, (2) decaimiento por tiempo (Created Time→hoy, promedio cierre 23 días), "
    "(3) escalones por atraso, (4) horizonte de cierre cercano (tipo 14–21 días)."
)

archivo = st.file_uploader("Sube tu archivo (.csv o .xlsx)", type=["csv", "xlsx"])

PROMEDIO_CIERRE = 23  # días promedio histórico a cierre

# --- Paso 1 + 2: ajuste por tiempo (agresivo + escalones) ---
def time_factor_estricto(dias, estatus):
    if pd.isna(dias) or dias < 0:
        return 1.0

    estatus = str(estatus).strip()

    # half-life agresivo: después de 23 días, cae a la mitad cada X días
    if estatus == "Análisis":
        half_life = 5
    elif estatus == "Diseño":
        half_life = 8
    elif estatus == "Negociación":
        half_life = 12
    else:
        half_life = 7

    overdue = max(0, dias - PROMEDIO_CIERRE)
    factor = 0.5 ** (overdue / half_life)

    # Paso 2: escalones duros para leads muy pasados (solo Análisis/Diseño)
    if estatus in ["Análisis", "Diseño"]:
        if dias > 35:
            factor *= 0.75
        if dias > 45:
            factor *= 0.65
        if dias > 60:
            factor *= 0.50

    return float(np.clip(factor, 0.02, 1.0))

# --- Paso 3: horizonte (queremos prob. de cierre pronto, no eventual) ---
def horizonte_factor(estatus):
    """
    Ajusta a “probabilidad de cerrar pronto” (ej. próximos 14–21 días).
    - Análisis: muy baja prob de cerrar pronto
    - Diseño: media
    - Negociación: alta (pero no 1)
    """
    estatus = str(estatus).strip()
    if estatus == "Análisis":
        return 0.50
    elif estatus == "Diseño":
        return 0.65
    elif estatus == "Negociación":
        return 0.85
    else:
        return 0.55

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
            "Contestó correo", "Contestó mensaje", "Contestó llamada", "Wedding Planner",
            "Created Time"  # 👈 ya lo tienes en tu archivo final
        ]

        if not all(col in df.columns for col in columnas_necesarias):
            faltan = [c for c in columnas_necesarias if c not in df.columns]
            st.error(f"Faltan columnas necesarias: {faltan}")
            st.stop()

        # Booleans robustos
        for col in ["Contestó correo", "Contestó mensaje", "Contestó llamada"]:
            df[col] = (
                df[col].astype(str).str.strip().str.upper()
                .map({
                    "VERDADERO": True, "TRUE": True, "1": True, "SI": True, "SÍ": True,
                    "FALSO": False, "FALSE": False, "0": False, "NO": False
                })
                .fillna(False)
            )

        # Parse Created Time
        df["Created Time"] = pd.to_datetime(df["Created Time"], errors="coerce")
        hoy = pd.Timestamp(datetime.now().date())
        df["Días desde creación"] = (hoy - df["Created Time"]).dt.days

        # --- tu score base (SIN tocar tus criterios) ---
        def prob_base(row):
            # si está en análisis y no respondió nada -> 0
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
            return float(np.clip(p, 0.0, 0.70))

        # --- prob final: base * tiempo (paso 1+2) * horizonte (paso 3) ---
        def calcular_probabilidad(row):
            # Si tienes un estatus de cerrado ganado y lo quieres como 100%:
            if str(row["Estatus"]).strip() in ["Cerrada Ganada", "Cerrado", "Closed Won"]:
                return 1.0

            p0 = prob_base(row)
            tf = time_factor_estricto(row["Días desde creación"], row["Estatus"])
            hf = horizonte_factor(row["Estatus"])
            p = p0 * tf * hf
            return float(np.clip(p, 0.0, 0.70))

        df["Probabilidad Base"] = df.apply(prob_base, axis=1)
        df["Probabilidad de Cierre"] = df.apply(calcular_probabilidad, axis=1)
        df["Valor Estimado"] = df["Presupuesto"] * df["Probabilidad de Cierre"]

        # Resumen
        st.subheader("Resumen de ajuste")
        st.write(f"📌 Promedio histórico de cierre: **{PROMEDIO_CIERRE} días**.")

        st.metric("Probabilidad promedio (base)", f"{df['Probabilidad Base'].mean()*100:.1f}%")
        st.metric("Probabilidad promedio (ajustada hoy)", f"{df['Probabilidad de Cierre'].mean()*100:.1f}%")

        overdue = int((df["Días desde creación"] > PROMEDIO_CIERRE).sum())
        st.metric("Leads 'pasados' (>23 días)", f"{overdue} de {len(df)}")

        valor_total = float(df["Valor Estimado"].sum())
        st.metric("💰 Valor total estimado del funnel (cierre cercano)", f"${valor_total:,.2f}")
        st.caption("Este valor está diseñado para representar un funnel 'cerrable pronto' (ej. próximas 2–3 semanas), "
                   "por eso es más conservador que el funnel 'eventual'.")

        # Tabla
        st.subheader("Resultados del Funnel:")
        st.dataframe(df[[
            "Nombre del lead", "Wedding Planner", "Presupuesto", "Número de interacciones",
            "Canal", "Estatus", "Contestó correo", "Contestó mensaje", "Contestó llamada",
            "Created Time", "Días desde creación",
            "Probabilidad Base", "Probabilidad de Cierre", "Valor Estimado"
        ]])

        # Gráfica por WP
        st.subheader("📊 Valor Estimado por Wedding Planner")
        resumen = df.groupby("Wedding Planner")["Valor Estimado"].sum().sort_values(ascending=False)

        fig, ax = plt.subplots(figsize=(6, 2.4))
        resumen.plot(kind="bar", ax=ax)
        ax.set_ylabel("Valor Estimado ($)")
        ax.set_title("Valor Estimado por WP (cierre cercano)")
        ax.tick_params(axis='x', rotation=45)
        st.pyplot(fig)

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
