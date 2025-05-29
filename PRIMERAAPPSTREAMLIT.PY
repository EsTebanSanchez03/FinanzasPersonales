import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import json
from typing import Dict, List

# Configuración de la página
st.set_page_config(
    page_title="📊 Mi Dashboard Financiero",
    page_icon="💰",
    layout="wide"
)

# Inicializar session state
if 'metas' not in st.session_state:
    st.session_state.metas = []
if 'df_transacciones' not in st.session_state:
    st.session_state.df_transacciones = pd.DataFrame()
if 'archivo_cargado' not in st.session_state:
    st.session_state.archivo_cargado = False

def parsear_fecha_flexible(fecha_valor):
    """
    Función para parsear fechas de manera más flexible
    Maneja múltiples formatos y valores problemáticos
    """
    if pd.isna(fecha_valor):
        return None
    
    # Si ya es datetime, convertir a date
    if isinstance(fecha_valor, pd.Timestamp) or isinstance(fecha_valor, datetime):
        return fecha_valor
    
    # Si es un número (timestamp de Excel), convertir
    if isinstance(fecha_valor, (int, float)):
        try:
            # Excel cuenta desde 1900-01-01, pero Python desde 1970-01-01
            # Verificar si es un timestamp de Excel válido
            if fecha_valor > 25569:  # Fecha mínima aproximada de Excel (1970)
                return pd.to_datetime(fecha_valor, origin='1899-12-30', unit='D')
            else:
                return None
        except:
            return None
    
    # Si es string, intentar múltiples formatos
    if isinstance(fecha_valor, str):
        fecha_str = str(fecha_valor).strip()
        
        # Lista de formatos comunes
        formatos = [
            '%d/%m/%Y',     # 15/01/2024
            '%d-%m-%Y',     # 15-01-2024
            '%Y-%m-%d',     # 2024-01-15
            '%Y/%m/%d',     # 2024/01/15
            '%d/%m/%y',     # 15/01/24
            '%d-%m-%y',     # 15-01-24
            '%m/%d/%Y',     # 01/15/2024
            '%m-%d-%Y',     # 01-15-2024
        ]
        
        for formato in formatos:
            try:
                return datetime.strptime(fecha_str, formato)
            except:
                continue
        
        # Si no funciona ningún formato específico, usar pandas
        try:
            return pd.to_datetime(fecha_str, dayfirst=True, errors='coerce')
        except:
            return None
    
    return None

def crear_plantilla_excel():
    """Crear plantilla de Excel para descargar"""
    datos_ejemplo = {
        'Fecha': ['15/01/2024', '16/01/2024', '17/01/2024'],
        'Categoria': ['Alimentación', 'Transporte', 'Entretenimiento'],
        'Tipo': ['Gasto', 'Gasto', 'Gasto'],
        'Monto': [-150, -80, -200]
    }
    df_transacciones = pd.DataFrame(datos_ejemplo)
    
    # Crear DataFrame de metas vacío para la plantilla
    df_metas = pd.DataFrame({
        'Nombre_Meta': [],
        'Monto_Objetivo': [],
        'Fecha_Limite': [],
        'Fecha_Creacion': []
    })
    
    # Convertir a Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl', mode='w') as writer:
        df_transacciones.to_excel(writer, index=False, sheet_name='Transacciones')
        df_metas.to_excel(writer, index=False, sheet_name='Metas')
        
        # Agregar instrucciones como DataFrame simple
        instrucciones = pd.DataFrame({
            'INSTRUCCIONES': [
                '=== HOJA TRANSACCIONES ===',
                '1. Llena la columna Fecha con formato DD/MM/YYYY',
                '2. Categoria: Alimentación, Transporte, Entretenimiento, Salario, etc.',
                '3. Tipo: Gasto (negativo) o Ingreso (positivo)',
                '4. Monto: Usa números negativos para gastos, positivos para ingresos',
                '5. Elimina estas filas de ejemplo antes de subir tu archivo',
                '',
                '=== HOJA METAS ===',
                '6. Las metas se guardan automáticamente en esta hoja',
                '7. NO modifiques manualmente la hoja de Metas',
                '8. Usa la aplicación para agregar/eliminar metas',
                '',
                '=== IMPORTANTE ===',
                '9. Siempre descarga tu archivo actualizado después de hacer cambios',
                '10. Usa ese archivo actualizado para futuras cargas',
                '11. FORMATO DE FECHA: DD/MM/YYYY (ejemplo: 15/01/2024)'
            ]
        })
        instrucciones.to_excel(writer, index=False, sheet_name='Instrucciones')
    
    return output.getvalue()

def crear_excel_con_datos_actuales():
    """Crear Excel con histórico y hoja de transacciones vacía para nuevos datos"""
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl', mode='w') as writer:
        # Hoja de TRANSACCIONES - SIEMPRE VACÍA para nuevos registros
        df_transacciones_vacia = pd.DataFrame({
            'Fecha': ['17/04/2024'],  # Ejemplo con formato DD/MM/YYYY
            'Categoria': ['Vivienda'],
            'Tipo': ['Gasto'],
            'Monto': [-900]
        })
        df_transacciones_vacia.to_excel(writer, index=False, sheet_name='Transacciones')
        
        # Hoja de HISTORICO - Todas las transacciones previas
        if not st.session_state.df_transacciones.empty:
            # Formatear fechas antes de guardar
            df_historico = st.session_state.df_transacciones.copy()
            df_historico['Fecha'] = df_historico['Fecha'].dt.strftime('%d/%m/%Y')
            df_historico.to_excel(writer, index=False, sheet_name='Historico')
        else:
            # Si no hay histórico, crear hoja vacía con headers
            df_historico_vacio = pd.DataFrame(columns=['Fecha', 'Categoria', 'Tipo', 'Monto'])
            df_historico_vacio.to_excel(writer, index=False, sheet_name='Historico')
        
        # Guardar metas
        if st.session_state.metas:
            df_metas = pd.DataFrame(st.session_state.metas)
            # Renombrar columnas para el Excel
            df_metas_excel = df_metas.rename(columns={
                'nombre': 'Nombre_Meta',
                'monto': 'Monto_Objetivo',
                'fecha_limite': 'Fecha_Limite',
                'fecha_creacion': 'Fecha_Creacion'
            })
            
            # Formatear fechas en las metas
            if 'Fecha_Limite' in df_metas_excel.columns:
                df_metas_excel['Fecha_Limite'] = df_metas_excel['Fecha_Limite'].apply(
                    lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) and x is not None else ''
                )
            if 'Fecha_Creacion' in df_metas_excel.columns:
                df_metas_excel['Fecha_Creacion'] = df_metas_excel['Fecha_Creacion'].apply(
                    lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) and x is not None else ''
                )
            
            df_metas_excel.to_excel(writer, index=False, sheet_name='Metas')
        else:
            # Crear hoja de metas vacía con headers
            df_metas_vacio = pd.DataFrame(columns=['Nombre_Meta', 'Monto_Objetivo', 'Fecha_Limite', 'Fecha_Creacion'])
            df_metas_vacio.to_excel(writer, index=False, sheet_name='Metas')
        
        # Agregar instrucciones actualizadas como DataFrame simple
        instrucciones = pd.DataFrame({
            'INSTRUCCIONES_ACTUALIZADAS': [
                '=== TU ARCHIVO PERSONAL ===',
                f'Archivo generado el: {datetime.now().strftime("%d/%m/%Y %H:%M")}',
                f'Transacciones en histórico: {len(st.session_state.df_transacciones)}',
                f'Metas activas: {len(st.session_state.metas)}',
                '',
                '=== CÓMO USAR ===',
                '1. Agrega NUEVAS transacciones SOLO en la hoja "Transacciones"',
                '2. ELIMINA el ejemplo antes de agregar tus datos',
                '3. NO modifiques las hojas "Historico" ni "Metas"',
                '4. La app combinará histórico + nuevos datos automáticamente',
                '',
                '=== FORMATO TRANSACCIONES ===',
                'Fecha: DD/MM/YYYY (ej: 17/04/2024) - ¡MUY IMPORTANTE!',
                'Categoria: Vivienda, Alimentación, Transporte, etc.',
                'Tipo: Gasto o Ingreso',
                'Monto: Negativo para gastos (-900), positivo para ingresos',
                '',
                '=== EJEMPLO CORRECTO ===',
                '17/04/2024    Vivienda    Gasto    -900',
                '18/04/2024    Salario     Ingreso   3000',
                '',
                '=== IMPORTANTE FECHAS ===',
                'Excel puede cambiar formato automáticamente.',
                'Si ves fechas raras, verifica que estén en DD/MM/YYYY'
            ]
        })
        instrucciones.to_excel(writer, index=False, sheet_name='Instrucciones')
    
    return output.getvalue()

def procesar_archivo(uploaded_file):
    """Procesar archivo Excel subido (combinando histórico + nuevas transacciones)"""
    try:
        # Leer todas las hojas disponibles
        excel_sheets = pd.read_excel(uploaded_file, sheet_name=None)
        
        df_todas_transacciones = pd.DataFrame()
        metas_cargadas = []
        nuevas_transacciones = 0
        historicas_transacciones = 0
        fechas_problematicas = []
        
        # Procesar hoja de NUEVAS transacciones
        if 'Transacciones' in excel_sheets:
            df_nuevas = excel_sheets['Transacciones']
            
            # Validar columnas requeridas
            required_columns = ['Fecha', 'Categoria', 'Tipo', 'Monto']
            if all(col in df_nuevas.columns for col in required_columns):
                # Limpiar y procesar nuevas transacciones
                df_nuevas = df_nuevas.dropna()
                if not df_nuevas.empty:
                    # Procesar fechas con función mejorada
                    fechas_procesadas = []
                    for idx, fecha_valor in enumerate(df_nuevas['Fecha']):
                        fecha_procesada = parsear_fecha_flexible(fecha_valor)
                        if fecha_procesada is None:
                            fechas_problematicas.append(f"Fila {idx+2}: {fecha_valor}")
                        fechas_procesadas.append(fecha_procesada)
                    
                    df_nuevas['Fecha'] = fechas_procesadas
                    # Eliminar filas con fechas inválidas
                    df_nuevas_validas = df_nuevas.dropna(subset=['Fecha'])
                    
                    if len(df_nuevas_validas) < len(df_nuevas):
                        st.warning(f"⚠️ Se omitieron {len(df_nuevas) - len(df_nuevas_validas)} filas con fechas inválidas")
                    
                    if not df_nuevas_validas.empty:
                        nuevas_transacciones = len(df_nuevas_validas)
                        df_todas_transacciones = pd.concat([df_todas_transacciones, df_nuevas_validas], ignore_index=True)
        
        # Procesar hoja de HISTORICO
        if 'Historico' in excel_sheets:
            df_historico = excel_sheets['Historico']
            
            if not df_historico.empty:
                required_columns = ['Fecha', 'Categoria', 'Tipo', 'Monto']
                if all(col in df_historico.columns for col in required_columns):
                    df_historico = df_historico.dropna()
                    if not df_historico.empty:
                        # Procesar fechas del histórico con función mejorada
                        fechas_procesadas = []
                        for fecha_valor in df_historico['Fecha']:
                            fecha_procesada = parsear_fecha_flexible(fecha_valor)
                            fechas_procesadas.append(fecha_procesada)
                        
                        df_historico['Fecha'] = fechas_procesadas
                        df_historico = df_historico.dropna(subset=['Fecha'])
                        
                        if not df_historico.empty:
                            historicas_transacciones = len(df_historico)
                            df_todas_transacciones = pd.concat([df_historico, df_todas_transacciones], ignore_index=True)
        
        # Si no hay hoja de histórico pero sí de transacciones (archivo viejo)
        elif 'Transacciones' in excel_sheets and df_todas_transacciones.empty:
            st.info("📋 Detectado archivo en formato anterior. Todas las transacciones se tratarán como históricas.")
            df_transacciones_viejas = excel_sheets['Transacciones']
            if not df_transacciones_viejas.empty:
                required_columns = ['Fecha', 'Categoria', 'Tipo', 'Monto']
                if all(col in df_transacciones_viejas.columns for col in required_columns):
                    df_transacciones_viejas = df_transacciones_viejas.dropna()
                    if not df_transacciones_viejas.empty:
                        # Procesar fechas con función mejorada
                        fechas_procesadas = []
                        for fecha_valor in df_transacciones_viejas['Fecha']:
                            fecha_procesada = parsear_fecha_flexible(fecha_valor)
                            fechas_procesadas.append(fecha_procesada)
                        
                        df_transacciones_viejas['Fecha'] = fechas_procesadas
                        df_transacciones_viejas = df_transacciones_viejas.dropna(subset=['Fecha'])
                        
                        if not df_transacciones_viejas.empty:
                            historicas_transacciones = len(df_transacciones_viejas)
                            df_todas_transacciones = df_transacciones_viejas
        
        # Procesar hoja de metas
        if 'Metas' in excel_sheets:
            df_metas = excel_sheets['Metas']
            
            if not df_metas.empty and 'Nombre_Meta' in df_metas.columns:
                for _, row in df_metas.iterrows():
                    if pd.notna(row['Nombre_Meta']) and pd.notna(row['Monto_Objetivo']):
                        meta = {
                            'nombre': str(row['Nombre_Meta']),
                            'monto': float(row['Monto_Objetivo']),
                            'fecha_creacion': datetime.now().date()
                        }
                        
                        # Procesar fecha de creación
                        if pd.notna(row.get('Fecha_Creacion')):
                            fecha_creacion = parsear_fecha_flexible(row['Fecha_Creacion'])
                            if fecha_creacion:
                                meta['fecha_creacion'] = fecha_creacion.date() if hasattr(fecha_creacion, 'date') else fecha_creacion
                        
                        # Procesar fecha límite opcional
                        if pd.notna(row.get('Fecha_Limite')):
                            fecha_limite = parsear_fecha_flexible(row['Fecha_Limite'])
                            if fecha_limite:
                                meta['fecha_limite'] = fecha_limite.date() if hasattr(fecha_limite, 'date') else fecha_limite
                            else:
                                meta['fecha_limite'] = None
                        else:
                            meta['fecha_limite'] = None
                        
                        metas_cargadas.append(meta)
        
        # Mostrar advertencias sobre fechas problemáticas
        if fechas_problematicas:
            st.error("🚨 **Fechas problemáticas encontradas:**")
            for fecha_prob in fechas_problematicas[:5]:  # Mostrar solo las primeras 5
                st.write(f"• {fecha_prob}")
            if len(fechas_problematicas) > 5:
                st.write(f"• ... y {len(fechas_problematicas) - 5} más")
            st.info("💡 **Solución:** Asegúrate de usar formato DD/MM/YYYY (ejemplo: 15/01/2024)")
        
        # Mostrar resumen de lo procesado
        if not df_todas_transacciones.empty or metas_cargadas:
            st.success("✅ Archivo procesado correctamente:")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Nuevas", nuevas_transacciones)
            with col2:
                st.metric("📚 Históricas", historicas_transacciones)
            with col3:
                st.metric("🎯 Metas", len(metas_cargadas))
        
        return df_todas_transacciones if not df_todas_transacciones.empty else None, metas_cargadas
        
    except Exception as e:
        st.error(f"Error al procesar el archivo: {str(e)}")
        st.info("💡 Verifica que el archivo tenga el formato correcto y las fechas estén en formato DD/MM/YYYY")
        return None, []

def calcular_insights(df, metas):
    """Calcular insights financieros"""
    insights = []
    
    if not df.empty:
        # Insights básicos
        total_ingresos = df[df['Monto'] > 0]['Monto'].sum()
        total_gastos = abs(df[df['Monto'] < 0]['Monto'].sum())
        balance = total_ingresos - total_gastos
        
        insights.append(f"💰 Balance total: ${balance:,.2f}")
        insights.append(f"📈 Ingresos totales: ${total_ingresos:,.2f}")
        insights.append(f"📉 Gastos totales: ${total_gastos:,.2f}")
        
        # Categoría con más gastos
        gastos_por_categoria = df[df['Monto'] < 0].groupby('Categoria')['Monto'].sum().abs()
        if not gastos_por_categoria.empty:
            categoria_mayor_gasto = gastos_por_categoria.idxmax()
            monto_mayor_gasto = gastos_por_categoria.max()
            insights.append(f"🔍 Mayor gasto por categoría: {categoria_mayor_gasto} (${monto_mayor_gasto:,.2f})")
        
        # Promedio de gastos diarios
        if len(df[df['Monto'] < 0]) > 0:
            dias_unicos = df['Fecha'].dt.date.nunique()
            promedio_diario = total_gastos / dias_unicos if dias_unicos > 0 else 0
            insights.append(f"📅 Promedio de gasto diario: ${promedio_diario:,.2f}")
    
    # Insights de metas
    for meta in metas:
        if df.empty:
            insights.append(f"🎯 {meta['nombre']}: Te faltan ${meta['monto']:,.2f} para tu meta")
        else:
            ahorro_actual = max(0, df['Monto'].sum())  # Solo contar balance positivo como ahorro
            faltante = meta['monto'] - ahorro_actual
            
            if faltante <= 0:
                insights.append(f"🎉 ¡Meta '{meta['nombre']}' alcanzada!")
            else:
                # Calcular tiempo estimado
                if meta.get('fecha_limite'):
                    dias_restantes = (meta['fecha_limite'] - datetime.now().date()).days
                    if dias_restantes > 0:
                        ahorro_diario_necesario = faltante / dias_restantes
                        insights.append(f"🎯 {meta['nombre']}: Te faltan ${faltante:,.2f}. Necesitas ahorrar ${ahorro_diario_necesario:,.2f} diarios")
                    else:
                        insights.append(f"⏰ {meta['nombre']}: Meta vencida. Te faltan ${faltante:,.2f}")
                else:
                    insights.append(f"🎯 {meta['nombre']}: Te faltan ${faltante:,.2f} para tu meta")
    
    return insights

def main():
    st.title("📊 Mi Dashboard Financiero Personal")
    st.markdown("---")
    
    # Sidebar para navegación
    st.sidebar.title("🧭 Navegación")
    pagina = st.sidebar.selectbox(
        "Selecciona una sección:",
        ["📥 Cargar Datos", "📊 Dashboard", "🎯 Metas Financieras", "💡 Insights", "💾 Descargar Datos"]
    )
    
    if pagina == "📥 Cargar Datos":
        st.header("📥 Gestión de Datos Financieros")
        
        # Información importante sobre fechas
        st.info("🗓️ **¡IMPORTANTE SOBRE FECHAS!** Usa formato DD/MM/YYYY (ejemplo: 15/01/2024) para evitar errores")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("1️⃣ Primera vez - Descargar Plantilla")
            st.write("Si es tu primera vez, descarga la plantilla inicial:")
            
            plantilla = crear_plantilla_excel()
            st.download_button(
                label="📁 Descargar Plantilla Nueva",
                data=plantilla,
                file_name="plantilla_finanzas_inicial.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            st.info("💡 Esta plantilla incluye ejemplos e instrucciones")
        
        with col2:
            st.subheader("2️⃣ Subir Archivo")
            uploaded_file = st.file_uploader(
                "Sube tu archivo Excel (con transacciones y metas):",
                type=['xlsx', 'xls'],
                help="Puede ser la plantilla inicial o tu archivo personal actualizado"
            )
            
            if uploaded_file is not None:
                df_transacciones, metas_cargadas = procesar_archivo(uploaded_file)
                
                if df_transacciones is not None or metas_cargadas:
                    # Actualizar session state
                    if df_transacciones is not None:
                        st.session_state.df_transacciones = df_transacciones
                    
                    if metas_cargadas:
                        st.session_state.metas = metas_cargadas
                    
                    st.session_state.archivo_cargado = True
                    
                    # Mostrar resumen de lo cargado
                    if not st.session_state.df_transacciones.empty:
                        st.write("**Vista previa de todas las transacciones (histórico + nuevas):**")
                        # Mostrar fechas formateadas correctamente
                        preview_df = st.session_state.df_transacciones.tail(10).copy()
                        preview_df['Fecha'] = preview_df['Fecha'].dt.strftime('%d/%m/%Y')
                        st.dataframe(preview_df)
                    
                    if st.session_state.metas:
                        st.write("**Metas cargadas:**")
                        for meta in st.session_state.metas:
                            st.write(f"- {meta['nombre']}: ${meta['monto']:,.2f}")
    
    elif pagina == "📊 Dashboard":
        st.header("📊 Dashboard Financiero")
        
        if st.session_state.df_transacciones.empty:
            st.warning("⚠️ No hay datos cargados. Ve a la sección 'Cargar Datos' primero.")
            return
        
        df = st.session_state.df_transacciones
        
        # Métricas principales
        col1, col2, col3, col4 = st.columns(4)
        
        total_ingresos = df[df['Monto'] > 0]['Monto'].sum()
        total_gastos = abs(df[df['Monto'] < 0]['Monto'].sum())
        balance = total_ingresos - total_gastos
        num_transacciones = len(df)
        
        with col1:
            st.metric("💰 Balance Total", f"${balance:,.2f}")
        with col2:
            st.metric("📈 Ingresos", f"${total_ingresos:,.2f}")
        with col3:
            st.metric("📉 Gastos", f"${total_gastos:,.2f}")
        with col4:
            st.metric("📝 Transacciones", num_transacciones)
        
        st.markdown("---")
        
        # Gráficos
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Gastos por Categoría")
            gastos_categoria = df[df['Monto'] < 0].groupby('Categoria')['Monto'].sum().abs()
            if not gastos_categoria.empty:
                fig_pie = px.pie(
                    values=gastos_categoria.values,
                    names=gastos_categoria.index,
                    title="Distribución de Gastos"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            st.subheader("📈 Ingresos vs Gastos por Mes")
            df['Mes'] = df['Fecha'].dt.to_period('M').astype(str)
            
            ingresos_mes = df[df['Monto'] > 0].groupby('Mes')['Monto'].sum()
            gastos_mes = df[df['Monto'] < 0].groupby('Mes')['Monto'].sum().abs()
            
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(name='Ingresos', x=ingresos_mes.index, y=ingresos_mes.values))
            fig_bar.add_trace(go.Bar(name='Gastos', x=gastos_mes.index, y=gastos_mes.values))
            fig_bar.update_layout(title="Ingresos vs Gastos Mensuales", barmode='group')
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # Tabla de transacciones recientes
        st.subheader("📋 Transacciones Recientes")
        df_display = df.sort_values('Fecha', ascending=False).head(10).copy()
        df_display['Fecha'] = df_display['Fecha'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_display, use_container_width=True)
    
    elif pagina == "🎯 Metas Financieras":
        st.header("🎯 Gestión de Metas Financieras")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("➕ Agregar Nueva Meta")
            
            with st.form("nueva_meta"):
                nombre_meta = st.text_input("Nombre de la meta", placeholder="Ej: Comprar un carro")
                monto_meta = st.number_input("Monto objetivo ($)", min_value=0.0, step=100.0)
                fecha_limite = st.date_input("Fecha límite (opcional)")
                usar_fecha = st.checkbox("Usar fecha límite")
                
                submitted = st.form_submit_button("🎯 Agregar Meta")
                
                if submitted and nombre_meta and monto_meta > 0:
                    nueva_meta = {
                        'nombre': nombre_meta,
                        'monto': monto_meta,
                        'fecha_limite': fecha_limite if usar_fecha else None,
                        'fecha_creacion': datetime.now().date()
                    }
                    st.session_state.metas.append(nueva_meta)
                    st.success(f"✅ Meta '{nombre_meta}' agregada correctamente!")
                    st.info("💡 No olvides descargar tu archivo actualizado en la sección 'Descargar Datos'")
        
        with col2:
            st.subheader("📋 Mis Metas Actuales")
            
            if not st.session_state.metas:
                st.info("No tienes metas configuradas aún. ¡Agrega tu primera meta!")
            else:
                for i, meta in enumerate(st.session_state.metas):
                    with st.expander(f"🎯 {meta['nombre']} - ${meta['monto']:,.2f}"):
                    # Calcular progreso
                        if not st.session_state.df_transacciones.empty:
                            balance_actual = st.session_state.df_transacciones['Monto'].sum()
                            ahorro_actual = max(0, balance_actual)
                            progreso = min(100, (ahorro_actual / meta['monto']) * 100)
                        else:
                            ahorro_actual = 0
                            progreso = 0
                    
                    # Mostrar progreso
                    st.progress(progreso / 100)
                    st.write(f"Progreso: {progreso:.1f}% (${ahorro_actual:,.2f} de ${meta['monto']:,.2f})")
                    
                    # Información adicional
                    if meta.get('fecha_limite'):
                        dias_restantes = (meta['fecha_limite'] - datetime.now().date()).days
                        if dias_restantes > 0:
                            st.write(f"⏰ Días restantes: {dias_restantes}")
                            if ahorro_actual < meta['monto']:
                                faltante = meta['monto'] - ahorro_actual
                                ahorro_diario = faltante / dias_restantes
                                st.write(f"💪 Ahorro diario necesario: ${ahorro_diario:.2f}")
                        else:
                            st.error("⏰ Meta vencida")
                    
                    # Botón para eliminar
                    if st.button(f"🗑️ Eliminar", key=f"eliminar_{i}"):
                        st.session_state.metas.pop(i)
                        st.rerun()
    
    elif pagina == "💡 Insights":
        st.header("💡 Insights Financieros")
        
        if st.session_state.df_transacciones.empty:
            st.warning("⚠️ No hay datos cargados. Ve a la sección 'Cargar Datos' primero.")
            return
        
        insights = calcular_insights(st.session_state.df_transacciones, st.session_state.metas)
        
        st.subheader("📊 Análisis Automático de tus Finanzas")
        
        for insight in insights:
            st.write(f"• {insight}")
        
        # Análisis de tendencias
        st.markdown("---")
        st.subheader("📈 Tendencias Mensuales")
        
        df = st.session_state.df_transacciones
        df['Mes'] = df['Fecha'].dt.to_period('M').astype(str)
        
        # Tendencia de gastos
        gastos_mensuales = df[df['Monto'] < 0].groupby('Mes')['Monto'].sum().abs()
        if len(gastos_mensuales) > 1:
            tendencia_gastos = gastos_mensuales.iloc[-1] - gastos_mensuales.iloc[-2]
            if tendencia_gastos > 0:
                st.warning(f"📈 Tus gastos aumentaron ${tendencia_gastos:.2f} el último mes")
            else:
                st.success(f"📉 Tus gastos disminuyeron ${abs(tendencia_gastos):.2f} el último mes")
        
        # Gráfico de tendencia
        fig_line = px.line(
            x=gastos_mensuales.index,
            y=gastos_mensuales.values,
            title="Evolución de Gastos Mensuales",
            labels={'x': 'Mes', 'y': 'Gastos ($)'}
        )
        st.plotly_chart(fig_line, use_container_width=True)
    
    elif pagina == "💾 Descargar Datos":
        st.header("💾 Descargar y Gestionar Datos")
        
        st.info("🔄 **¡IMPORTANTE!** Siempre descarga tu archivo actualizado después de hacer cambios para mantener tu información sincronizada.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Tu Archivo Personal")
            st.write("Descarga tu archivo con:")
            st.write("• 📚 Todo tu histórico de transacciones")
            st.write("• 🎯 Todas tus metas guardadas")
            st.write("• 📝 Hoja vacía para nuevas transacciones")
            
            if st.session_state.df_transacciones.empty and not st.session_state.metas:
                st.warning("⚠️ No hay datos para descargar. Carga datos primero.")
            else:
                archivo_personal = crear_excel_con_datos_actuales()
                fecha_actual = datetime.now().strftime("%Y%m%d_%H%M")
                
                st.download_button(
                    label="📥 Descargar Mi Archivo Personal",
                    data=archivo_personal,
                    file_name=f"mis_finanzas_{fecha_actual}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                st.success("✅ Este archivo incluye tu histórico completo")
        
        with col2:
            st.subheader("📋 Resumen de Datos")
            
            # Estadísticas de transacciones
            if not st.session_state.df_transacciones.empty:
                df = st.session_state.df_transacciones
                st.metric("📊 Total Transacciones", len(df))
                
                fecha_min = df['Fecha'].min().strftime('%d/%m/%Y')
                fecha_max = df['Fecha'].max().strftime('%d/%m/%Y')
                st.write(f"📅 Período: {fecha_min} - {fecha_max}")
                
                balance = df['Monto'].sum()
                st.metric("💰 Balance Total", f"${balance:,.2f}")
            else:
                st.info("Sin transacciones cargadas")
            
            # Estadísticas de metas
            st.metric("🎯 Metas Activas", len(st.session_state.metas))
            
            if st.session_state.metas:
                monto_total_metas = sum(meta['monto'] for meta in st.session_state.metas)
                st.metric("🎯 Monto Total Metas", f"${monto_total_metas:,.2f}")
        
        st.markdown("---")
        st.subheader("🔧 Gestión de Datos")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**🗑️ Limpiar Datos**")
            if st.button("🗑️ Borrar Todas las Transacciones", type="secondary"):
                if st.button("⚠️ Confirmar Borrado de Transacciones"):
                    st.session_state.df_transacciones = pd.DataFrame()
                    st.success("✅ Transacciones borradas")
                    st.rerun()
        
        with col2:
            st.write("**🎯 Gestión de Metas**")
            if st.button("🗑️ Borrar Todas las Metas", type="secondary"):
                if st.button("⚠️ Confirmar Borrado de Metas"):
                    st.session_state.metas = []
                    st.success("✅ Metas borradas")
                    st.rerun()
    
    # Footer
    st.markdown("---")
    st.markdown("💡 **Consejos de uso:**")
    st.markdown("• Usa formato DD/MM/YYYY para fechas (ej: 15/01/2024)")
    st.markdown("• Descarga tu archivo actualizado después de hacer cambios")
    st.markdown("• Usa montos negativos para gastos y positivos para ingresos")

if __name__ == "__main__":
    main()
