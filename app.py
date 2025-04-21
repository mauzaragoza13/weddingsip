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
        columnas_requeridas = [
            "Nombre del lead", "Presupuesto", "Número de interacciones", "Canal", "Estatus",
            "Contestó correo", "Contestó mensaje", "Contestó llamada"
        ]
        if all(col in df.columns for col in columnas_requeridas):

            def calcular_probabilidad(row):
                # Más estricto con interacciones
                if row["Número de interacciones"] >= 6:
                    base = 0.15
                elif row["Número de interacciones"] >= 4:
                    base = 0.08
                elif row["Número de interacciones"] >= 2:
                    base = 0.03
                else:
                    base = 0.0

                # Canal bonus reducido
                canal_bonus = 0.03 if row["Canal"] == "Meta" else 0.07

                # Estatus bonus más limitado
                estatus_bonus = {
                    "Análisis": 0.0,
                    "Diseño": 0.07,
                    "Negociación": 0.2
                }.get(row["Estatus"], 0)

                # Presupuesto ideal más específico
                presupuesto_bonus = 0.1 if 300000 <= row["Presupuesto"] <= 600000 else 0

                # Respuestas más conservadoras
                contacto_bonus = 0
                if row["Contestó correo"]:
                    contacto_bonus += 0.02
                if row["Contestó mensaje"]:
                    contacto_bonus += 0.03
                if row["Contestó llamada"]:
                    contacto_bonus += 0.15

                prob = base + canal_bonus + estatus_bonus + presupuesto_bonus + contacto_bonus
                return min(prob, 0.7)  # límite máximo más estricto

            df["Probabilidad de Cierre"] = df.apply(calcular_probabilidad, axis=1)
            df["Valor Estimado"] = df["Presupuesto"] * df["Probabilidad de Cierre"]

            st.subheader("Resultados del Funnel:")
            st.dataframe(df[[
                "Nombre del lead", "Presupuesto", "Canal", "Estatus",
                "Contestó correo", "Contestó mensaje", "Contestó llamada",
                "Probabilidad de Cierre", "Valor Estimado"
            ]])

            valor_total = df["Valor Estimado"].sum()
            st.metric("💰 Valor total estimado del funnel", f"${valor_total:,.2f}")

        else:
            st.error("Faltan columnas necesarias para procesar: asegúrate de incluir las columnas correctas.")

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")

