import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Tablero Kanban de Tickets",
    page_icon="📋",
    layout="wide"
)

# --- CONEXIÓN A GOOGLE SHEETS ---
# Función para conectar con Google Sheets usando las credenciales de st.secrets
# Se cachea para no reconectar en cada re-ejecución.
@st.cache_resource(ttl=3600)
def connect_to_gsheets():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        return gc
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

# Función para obtener la hoja de cálculo
# Se cachea para no volver a buscarla.
@st.cache_resource(ttl=3600)
def get_spreadsheet(_gc, sheet_name):
    try:
        spreadsheet = _gc.open(sheet_name)
        return spreadsheet.worksheet("Hoja 1") # O el nombre de tu hoja
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"No se encontró la hoja de cálculo '{sheet_name}'. Verifica el nombre y los permisos.")
        return None
    except Exception as e:
        st.error(f"Error al acceder a la hoja de cálculo: {e}")
        return None

# --- CARGA Y MANEJO DE DATOS ---
# Función para cargar los datos y convertirlos a un DataFrame de Pandas
# Se cachea con un TTL corto para reflejar cambios rápidamente.
@st.cache_data(ttl=60)
def load_data(_worksheet):
    if _worksheet is None:
        return pd.DataFrame()
    try:
        data = _worksheet.get_all_records()
        df = pd.DataFrame(data)
        # Asegurarse de que las columnas esenciales existan
        for col in ['ID Ticket', 'Estado', 'Prioridad', 'Título', 'Solicitante', 'Fecha Creacion']:
            if col not in df.columns:
                df[col] = None # Añadir columna vacía si no existe
        return df
    except Exception as e:
        st.error(f"Error al cargar los datos de la hoja: {e}")
        return pd.DataFrame()

# --- INTERFAZ DE USUARIO ---
st.title("📋 Tablero Kanban de Tickets")
st.markdown("Gestiona el flujo de solicitudes moviendo las tarjetas entre etapas.")

# Conectar y cargar datos
gc = connect_to_gsheets()
if gc:
    worksheet = get_spreadsheet(gc, st.secrets["gcp_service_account"]["sheet_name"])
    if worksheet:
        df = load_data(worksheet)

        if df.empty:
            st.warning("No hay tickets para mostrar. Asegúrate de que la hoja de Google Sheets tenga datos.")
        else:
            # Definir las etapas del Kanban
            stages = ["Enfocar", "Detectar", "Idear", "Diseñar MVP", "Pilotear", "Escalar"]

            # Crear columnas para cada etapa
            cols = st.columns(len(stages))

            for i, stage in enumerate(stages):
                with cols[i]:
                    st.header(stage)
                    # Filtrar tickets para la etapa actual
                    stage_tickets = df[df['Estado'] == stage]
                    
                    for index, row in stage_tickets.iterrows():
                        ticket_id = row['ID Ticket']
                        
                        # Crear una tarjeta para cada ticket
                        with st.container(border=True):
                            st.subheader(f"#{ticket_id}")
                            st.markdown(f"**{row['Título']}**")
                            st.caption(f"Solicitante: {row['Solicitante']}")
                            
                            # Formatear fecha
                            try:
                                fecha_creacion = pd.to_datetime(row['Fecha Creacion']).strftime('%d/%m/%Y %H:%M')
                                st.caption(f"Creado: {fecha_creacion}")
                            except:
                                st.caption(f"Creado: {row['Fecha Creacion']}")

                            # Selector para cambiar de etapa
                            new_stage = st.selectbox(
                                "Mover a:",
                                options=stages,
                                index=stages.index(stage),
                                key=f"select_{ticket_id}" # Clave única para cada selector
                            )

                            # Si el estado cambia, actualizar Google Sheets
                            if new_stage != stage:
                                try:
                                    # Encontrar la fila en la hoja por ID de Ticket
                                    cell = worksheet.find(str(ticket_id))
                                    # Actualizar la celda de la columna "Estado" (asumiendo que es la columna 8)
                                    worksheet.update_cell(cell.row, 8, new_stage)
                                    st.success(f"Ticket #{ticket_id} movido a {new_stage}.")
                                    # Forzar la re-ejecución para ver el cambio inmediatamente
                                    st.rerun()
                                except gspread.exceptions.CellNotFound:
                                    st.error(f"No se pudo encontrar el Ticket ID {ticket_id} en la hoja para actualizarlo.")
                                except Exception as e:
                                    st.error(f"Error al actualizar la hoja: {e}")
