
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Evaluador de Funnel - Isla Pasión", layout="wide")

st.title("📊 Evaluador de Funnel - Isla Pasión Weddings")
st.markdown("Sube tu base de datos de leads para analizar su valor estimado y probabilidad de cierre.")

# Cargar archivo
archivo = st.file_uploader("Sube tu archivo (.csv o .xlsx)", type=["csv", "xlsx"])

if archivo:
    try:
        if archivo.name.endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)

        st.success("Archivo cargado correctamente.")
        st.subheader("Vista previa de los datos:")
        st.dataframe(df.head())

        # Verificar columnas necesarias
        columnas_requeridas = ["Nombre del lead", "Presupuesto", "Número de interacciones", "Canal", "Estatus"]
        if all(col in df.columns for col in columnas_requeridas):

            # Cálculo de probabilidad simple con bonus por canal y estatus
            def calcular_probabilidad(row):
                base = min(row["Número de interacciones"] * 0.1, 1)
                canal_bonus = 0.05 if row["Canal"] == "Meta" else 0.1  # Google mejor conversión
                estatus_bonus = {
                    "Análisis": 0.05,
                    "Diseño": 0.15,
                    "Negociación": 0.3
                }.get(row["Estatus"], 0)
                return min(base + canal_bonus + estatus_bonus, 1)

            df["Probabilidad de Cierre"] = df.apply(calcular_probabilidad, axis=1)
            df["Valor Estimado"] = df["Presupuesto"] * df["Probabilidad de Cierre"]

            st.subheader("Resultados del Funnel:")
            st.dataframe(df[["Nombre del lead", "Presupuesto", "Canal", "Estatus",
                            "Probabilidad de Cierre", "Valor Estimado"]])

            valor_total = df["Valor Estimado"].sum()
            st.metric("💰 Valor total estimado del funnel", f"${valor_total:,.2f}")

        else:
            st.error("Faltan columnas necesarias: 'Nombre del lead', 'Presupuesto', 'Número de interacciones', 'Canal', 'Estatus'.")

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")

