import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np

st.set_page_config(page_title="Evaluador de Funnel - Isla Pasión", layout="wide")

st.title("📊 Evaluador de Funnel - Isla Pasión Weddings (tiempo + horizonte, sin cerrados ganados)")
st.markdown(
    "Estimación ajustada usando: (1) score base, (2) decaimiento por tiempo (Created Time→hoy, promedio cierre 23 días), "
    "(3) escalones por atraso, (4) horizonte de cierre cercano. "
    "**Se omiten Cerrada Ganada**."
)

archivo = st.file_uploader("Sube tu archivo (.csv o .xlsx)", type=["csv", "xlsx"])

PROMEDIO_CIERRE = 23  # días promedio histórico a cierre

# Paso 1+2: tiempo más agresivo
def time_factor_estricto(dias, estatus):
    if pd.isna(dias) or dias < 0:
        return 1.0

    estatus = str(estatus).strip()

    # más agresivo especialmente en Análisis
    if estatus == "Análisis":
        half_life = 4
    elif estatus == "Diseño":
        half_life = 7
    elif estatus == "Negociación":
        half_life = 11
    else:
        half_life = 6

    overdue = max(0, dias - PROMEDIO_CIERRE)
    factor = 0.5 ** (overdue / half_life)

    # escalones duros para muy pasados (Análisis/Diseño)
    if estatus in ["Análisis", "Diseño"]:
        if dias > 35:
            factor *= 0.70
        if dias > 45:
            factor *= 0.60
        if dias > 60:
            factor *= 0.45

    return float(np.clip(factor, 0.02, 1.0))

# Paso 3: horizonte (cierre cercano)
def horizonte_factor(estatus):
    estatus = str(estatus).strip()
    if estatus == "Análisis":
        return 0.35   # más conservador (antes 0.50)
    elif estatus == "Diseño":
        return 0.60
    elif estatus == "Negociación":
        return 0.85
    else:
        return 0.45

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
            "Created Time"
        ]
        if not all(col in df.columns for col in columnas_necesarias):
            faltan = [c for c in columnas_necesarias if c not in df.columns]
            st.error(f"Faltan columnas necesarias: {faltan}")
            st.stop()

        # Normalizar booleanos
        for col in ["Contestó correo", "Contestó mensaje", "Contestó llamada"]:
            df[col] = (
                df[col].astype(str).str.strip().str.upper()
                .map({
                    "VERDADERO": True, "TRUE": True, "1": True, "SI": True, "SÍ": True,
                    "FALSO": False, "FALSE": False, "0": False, "NO": False
                })
                .fillna(False)
            )

        # Parse Created Time y días desde creación
        df["Created Time"] = pd.to_datetime(df["Created Time"], errors="coerce")
        hoy = pd.Timestamp(datetime.now().date())
        df["Días desde creación"] = (hoy - df["Created Time"]).dt.days

        # 1) OMITIR cerrados ganados (y sinónimos)
        cerrados_ganados = ["Cerrada Ganada", "Cerrado", "Closed Won", "Ganada"]
        mask_ganados = df["Estatus"].astype(str).str.strip().isin(cerrados_ganados)
        st.caption(f"Se omitieron **{int(mask_ganados.sum())}** registros con estatus de cerrado ganado.")
        df = df.loc[~mask_ganados].copy()

        # ---- score base (lo que ya tenías) ----
        def prob_base(row):
            # compuerta: si está en análisis y NO respondió nada -> 0
            if row["Estatus"] == "Análisis" and not (row["Contestó correo"] or row["Contestó mensaje"] or row["Contestó llamada"]):
                return 0.0

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

        # ---- NUEVO: compuerta estricta solo para Análisis ----
        def gate_analisis(row):
            """
            En Análisis, solo dejamos prob si hay señales fuertes.
            """
            if str(row["Estatus"]).strip() != "Análisis":
                return True

            inter = row["Número de interacciones"]
            llamada = bool(row["Contestó llamada"])
            msg = bool(row["Contestó mensaje"])

            # Reglas: basta con 1 condición
            if llamada:
                return True
            if inter >= 4:
                return True
            if msg and inter >= 2:
                return True

            return False

        def calcular_probabilidad(row):
            # si no pasa la compuerta de Análisis -> 0
            if not gate_analisis(row):
                return 0.0

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

        # ¿cuántos de análisis quedaron vivos?
        analisis = df["Estatus"].astype(str).str.strip().eq("Análisis")
        analisis_vivos = int((analisis & (df["Probabilidad de Cierre"] > 0)).sum())
        st.metric("Análisis con prob > 0", f"{analisis_vivos}")

        valor_total = float(df["Valor Estimado"].sum())
        st.metric("💰 Valor total estimado del funnel (cierre cercano)", f"${valor_total:,.2f}")

        st.subheader("Resultados del Funnel:")
        st.dataframe(df[[
            "Nombre del lead", "Wedding Planner", "Presupuesto", "Número de interacciones",
            "Canal", "Estatus", "Contestó correo", "Contestó mensaje", "Contestó llamada",
            "Created Time", "Días desde creación",
            "Probabilidad Base", "Probabilidad de Cierre", "Valor Estimado"
        ]])

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
