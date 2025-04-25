import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Evaluador de Funnel - Isla Pasión", layout="wide")

st.title("📊 Evaluador de Funnel - Isla Pasión Weddings (con gráficas por WP)")
st.markdown("Carga tu base de leads para estimar la probabilidad de cierre y visualizar resultados por Wedding Planner.")

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

        columnas_necesarias = [
            "Nombre del lead", "Presupuesto", "Número de interacciones", "Canal", "Estatus",
            "Contestó correo", "Contestó mensaje", "Contestó llamada", "Wedding Planner"
        ]

        if all(col in df.columns for col in columnas_necesarias):

            for col in ["Contestó correo", "Contestó mensaje", "Contestó llamada"]:
                df[col] = df[col].astype(str).str.upper().map({"VERDADERO": True, "FALSO": False}).fillna(False)

            def calcular_probabilidad(row):
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

                presupuesto_bonus = 0.06 if 450000 <= row["Presupuesto"] <= 520000 else 0

                contacto_bonus = 0
                if row["Contestó correo"]:
                    contacto_bonus += 0.01
                if row["Contestó mensaje"]:
                    contacto_bonus += 0.02
                if row["Contestó llamada"]:
                    contacto_bonus += 0.10

                prob = base + canal_bonus + estatus_bonus + presupuesto_bonus + contacto_bonus
                return min(prob, 0.70)

            df["Probabilidad de Cierre"] = df.apply(calcular_probabilidad, axis=1)
            df["Valor Estimado"] = df["Presupuesto"] * df["Probabilidad de Cierre"]

            st.subheader("Resultados del Funnel:")
            st.dataframe(df[[
                "Nombre del lead", "Wedding Planner", "Presupuesto", "Canal", "Estatus",
                "Contestó correo", "Contestó mensaje", "Contestó llamada",
                "Probabilidad de Cierre", "Valor Estimado"
            ]])

            valor_total = df["Valor Estimado"].sum()
            st.metric("💰 Valor total estimado del funnel", f"${valor_total:,.2f}")

            if valor_total > 1000000:
                st.warning("⚠️ El valor estimado del funnel supera el cierre mensual histórico ($1,000,000). Revisa criterios o prioriza leads.")

            # Gráfico de Wedding Planner aún más pequeño
            st.subheader("📊 Valor Estimado por Wedding Planner")
            resumen = df.groupby("Wedding Planner")["Valor Estimado"].sum().sort_values(ascending=False)

            fig, ax = plt.subplots(figsize=(5, 2))  # tamaño más pequeño
            resumen.plot(kind="bar", ax=ax)
            ax.set_ylabel("Valor Estimado ($)")
            ax.set_title("Valor Estimado por Wedding Planner", fontsize=10)
            ax.tick_params(axis='x', rotation=45, labelsize=8)
            ax.tick_params(axis='y', labelsize=8)
            st.pyplot(fig)

        else:
            st.error("Faltan columnas necesarias. Asegúrate de incluir la columna 'Wedding Planner' también.")

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
