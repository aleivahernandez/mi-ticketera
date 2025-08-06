import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
# Se establece la configuración inicial de la página de Streamlit.
# Es importante que esto sea lo primero que se ejecute en el script.
st.set_page_config(
    page_title="Tablero Kanban de Tickets",
    page_icon="📋",
    layout="wide"
)

# --- CONEXIÓN A GOOGLE SHEETS ---
# Esta función se conecta a la API de Google usando las credenciales guardadas en los "Secrets" de Streamlit.
# @st.cache_resource se usa para que la conexión se realice solo una vez y se reutilice, ahorrando recursos.
@st.cache_resource(ttl=3600)
def connect_to_gsheets():
    try:
        # Carga las credenciales desde los secretos de Streamlit.
        creds_dict = st.secrets["gcp_service_account"]
        scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        return gc
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

# Esta función obtiene la hoja de cálculo específica por su nombre.
# También se cachea para no tener que buscarla en cada recarga.
@st.cache_resource(ttl=3600)
def get_spreadsheet(_gc, sheet_name):
    try:
        spreadsheet = _gc.open(sheet_name)
        return spreadsheet.worksheet("Hoja 1") # O el nombre exacto de tu hoja
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"No se encontró la hoja de cálculo '{sheet_name}'. Verifica el nombre y los permisos.")
        return None
    except Exception as e:
        st.error(f"Error al acceder a la hoja de cálculo: {e}")
        return None

# --- CARGA Y MANEJO DE DATOS ---
# Esta función carga todos los datos de la hoja y los convierte a un DataFrame de Pandas.
# @st.cache_data se usa para cachear los datos. El TTL (Time To Live) de 60 segundos
# significa que los datos se recargarán desde la hoja cada minuto para reflejar cambios.
@st.cache_data(ttl=60)
def load_data(_worksheet):
    if _worksheet is None:
        return pd.DataFrame()
    try:
        data = _worksheet.get_all_records()
        df = pd.DataFrame(data)
        # Se asegura de que las columnas esenciales existan para evitar errores.
        for col in ['ID Ticket', 'Estado', 'Prioridad', 'Título', 'Solicitante', 'Fecha Creacion']:
            if col not in df.columns:
                df[col] = None
        return df
    except Exception as e:
        st.error(f"Error al cargar los datos de la hoja: {e}")
        return pd.DataFrame()

# --- INTERFAZ DE USUARIO ---
st.title("📋 Tablero Kanban de Tickets")
st.markdown("Gestiona el flujo de solicitudes moviendo las tarjetas entre etapas.")

# Conectar y cargar los datos al iniciar la app.
gc = connect_to_gsheets()
if gc:
    # Obtiene el nombre de la hoja desde los secretos de Streamlit.
    worksheet = get_spreadsheet(gc, st.secrets["gcp_service_account"]["sheet_name"])
    if worksheet:
        df = load_data(worksheet)

        if df.empty:
            st.warning("No hay tickets para mostrar. Asegúrate de que la hoja de Google Sheets tenga datos.")
        else:
            # Definir las etapas del Kanban en el orden deseado.
            stages = ["Enfocar", "Detectar", "Idear", "Diseñar MVP", "Pilotear", "Escalar"]

            # Crear columnas visuales para cada etapa.
            cols = st.columns(len(stages))

            for i, stage in enumerate(stages):
                with cols[i]:
                    st.header(stage)
                    # Filtrar los tickets que pertenecen a la etapa actual.
                    stage_tickets = df[df['Estado'] == stage]
                    
                    for index, row in stage_tickets.iterrows():
                        ticket_id = row['ID Ticket']
                        
                        # Crear una tarjeta visual para cada ticket.
                        with st.container(border=True):
                            st.subheader(f"#{ticket_id}")
                            st.markdown(f"**{row['Título']}**")
                            st.caption(f"Solicitante: {row['Solicitante']}")
                            
                            # Formatear la fecha para que sea más legible.
                            try:
                                fecha_creacion = pd.to_datetime(row['Fecha Creacion']).strftime('%d/%m/%Y %H:%M')
                                st.caption(f"Creado: {fecha_creacion}")
                            except:
                                st.caption(f"Creado: {row['Fecha Creacion']}")

                            # Selector para cambiar de etapa.
                            # La clave (key) es única para cada ticket para que Streamlit los diferencie.
                            new_stage = st.selectbox(
                                "Mover a:",
                                options=stages,
                                index=stages.index(stage),
                                key=f"select_{ticket_id}"
                            )

                            # --- LÓGICA DE ACTUALIZACIÓN ---
                            # Este bloque se ejecuta solo si el usuario elige una nueva etapa en el selector.
                            if new_stage != stage:
                                try:
                                    # Busca el ID del ticket específicamente en la primera columna (columna A).
                                    # str(ticket_id) se asegura que busquemos el texto y no el número.
                                    cell = worksheet.find(str(ticket_id), in_column=1) 
                                    
                                    # Actualiza la celda en la misma fila, pero en la columna 8 ('Estado').
                                    # Basado en el orden: A=1, B=2, C=3, D=4, E=5, F=6, G=7, H=8.
                                    worksheet.update_cell(cell.row, 8, new_stage)
                                    
                                    st.success(f"Ticket #{ticket_id} movido a {new_stage}!")
                                    
                                    # Limpia el cache y re-ejecuta la app para ver el cambio al instante.
                                    st.cache_data.clear()
                                    st.rerun()

                                except gspread.exceptions.CellNotFound:
                                    st.error(f"Error Crítico: No se pudo encontrar la fila con el ID de Ticket '{ticket_id}' en la columna A de tu Google Sheet.")
                                except Exception as e:
                                    st.error(f"Ocurrió un error al intentar actualizar la hoja: {e}")
