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

@st.cache_resource(ttl=3600)
def get_spreadsheet(_gc, sheet_name):
    try:
        spreadsheet = _gc.open(sheet_name)
        return spreadsheet.worksheet("Hoja 1")
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"No se encontró la hoja de cálculo '{sheet_name}'. Verifica el nombre y los permisos.")
        return None
    except Exception as e:
        st.error(f"Error al acceder a la hoja de cálculo: {e}")
        return None

# --- CARGA Y MANEJO DE DATOS ---
@st.cache_data(ttl=60)
def load_data(_worksheet):
    if _worksheet is None:
        return pd.DataFrame()
    try:
        data = _worksheet.get_all_records()
        df = pd.DataFrame(data)
        for col in ['ID Ticket', 'Estado', 'Prioridad', 'Título', 'Solicitante', 'Fecha Creacion']:
            if col not in df.columns:
                df[col] = None
        # Asegurarse que la columna ID Ticket sea de tipo string para evitar errores de tipo
        if 'ID Ticket' in df.columns:
            df['ID Ticket'] = df['ID Ticket'].astype(str)
        return df
    except Exception as e:
        st.error(f"Error al cargar los datos de la hoja: {e}")
        return pd.DataFrame()

# --- INTERFAZ DE USUARIO ---
st.title("📋 Tablero Kanban de Tickets")
st.markdown("Gestiona el flujo de solicitudes moviendo las tarjetas entre etapas.")

gc = connect_to_gsheets()
if gc:
    worksheet = get_spreadsheet(gc, st.secrets["gcp_service_account"]["sheet_name"])
    if worksheet:
        df = load_data(worksheet)

        if df.empty:
            st.warning("No hay tickets para mostrar. Asegúrate de que la hoja de Google Sheets tenga datos.")
        else:
            stages = ["Enfocar", "Detectar", "Idear", "Diseñar MVP", "Pilotear", "Escalar"]
            cols = st.columns(len(stages))

            for i, stage in enumerate(stages):
                with cols[i]:
                    st.header(stage)
                    stage_tickets = df[df['Estado'] == stage]
                    
                    for index, row in stage_tickets.iterrows():
                        ticket_id = row['ID Ticket']
                        
                        with st.container(border=True):
                            st.subheader(f"#{ticket_id}")
                            st.markdown(f"**{row['Título']}**")
                            st.caption(f"Solicitante: {row['Solicitante']}")
                            
                            try:
                                fecha_creacion = pd.to_datetime(row['Fecha Creacion']).strftime('%d/%m/%Y %H:%M')
                                st.caption(f"Creado: {fecha_creacion}")
                            except:
                                st.caption(f"Creado: {row['Fecha Creacion']}")

                            new_stage = st.selectbox(
                                "Mover a:",
                                options=stages,
                                index=stages.index(stage),
                                key=f"select_{ticket_id}"
                            )

                            # --- LÓGICA DE ACTUALIZACIÓN (VERSIÓN MEJORADA) ---
                            if new_stage != stage:
                                try:
                                    # Obtener todos los IDs de la primera columna para una búsqueda más robusta.
                                    list_of_ids = worksheet.col_values(1)
                                    
                                    # Encontrar la fila. Se suma 1 porque las listas en Python empiezan en 0 y las filas en gspread en 1.
                                    # Se convierte a string a ambos lados para evitar errores de tipo de dato (ej: '123' vs 123).
                                    row_number = list_of_ids.index(str(ticket_id)) + 1

                                    # Actualiza la celda en la fila encontrada y en la columna 8 ('Estado').
                                    worksheet.update_cell(row_number, 8, new_stage)
                                    
                                    st.success(f"Ticket #{ticket_id} movido a {new_stage}!")
                                    
                                    # Limpia el cache y re-ejecuta la app para ver el cambio al instante.
                                    st.cache_data.clear()
                                    st.rerun()

                                except ValueError:
                                    # Este error ocurre si .index() no encuentra el valor en la lista.
                                    st.error(f"Error Crítico: No se pudo encontrar el ID de Ticket '{ticket_id}' en la columna A de tu Google Sheet. Revisa que el ID exista y no tenga espacios extra.")
                                except Exception as e:
                                    st.error(f"Ocurrió un error inesperado al intentar actualizar la hoja: {e}")
