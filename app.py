import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Tablero de Innovación",
    page_icon="💡",
    layout="wide"
)

# --- ESTILOS CSS PERSONALIZADOS ---
st.markdown("""
<style>
    /* Estilo para las columnas del Kanban */
    .st-emotion-cache-1fGnr9u {
        background-color: #f0f2f6;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.25rem;
    }

    /* Línea separadora entre etapas */
    div[data-testid="stHorizontalBlock"] > div:not(:last-child) {
        border-right: 2px solid #d1d5db;
        padding-right: 1.5rem;
    }

    /* Estilo para las tarjetas de las ideas */
    .kanban-card {
        background-color: white;
        border-radius: 0.5rem;
        padding: 1rem;
        margin-bottom: 0.5rem; /* Espacio para el botón de detalle */
        box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
    }
    .kanban-card h3 {
        margin-top: 0;
        margin-bottom: 0.5rem;
        font-size: 1.2rem;
    }
    .kanban-card p {
        margin-bottom: 0.25rem;
        font-size: 0.9rem;
        color: #4a5568;
    }
    
    /* Píldoras de prioridad con colores */
    .priority-pill {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.75rem;
        color: white;
        margin-bottom: 0.75rem;
    }
    .priority-Urgente { background-color: #e53e3e; } /* Rojo */
    .priority-Alta { background-color: #ed8936; } /* Naranja */
    .priority-Media { background-color: #4299e1; } /* Azul */
    .priority-Baja { background-color: #48bb78; } /* Verde */

</style>
""", unsafe_allow_html=True)


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
        # Asegurarse que las columnas existan y tengan el tipo correcto
        for col in ['ID Ticket', 'Estado', 'Prioridad', 'Título', 'Solicitante', 'Fecha Creacion', 'Descripcion', 'Email']:
            if col not in df.columns:
                df[col] = '' # Usar string vacío como default
        if 'ID Ticket' in df.columns:
            df['ID Ticket'] = df['ID Ticket'].astype(str)
        return df
    except Exception as e:
        st.error(f"Error al cargar los datos de la hoja: {e}")
        return pd.DataFrame()

# --- INTERFAZ DE USUARIO ---
st.title("💡 Tablero de Iniciativas de Innovación")

gc = connect_to_gsheets()
if gc:
    worksheet = get_spreadsheet(gc, st.secrets["gcp_service_account"]["sheet_name"])
    if worksheet:
        df = load_data(worksheet)

        if df.empty:
            st.warning("No hay ideas para mostrar. ¡Registra la primera desde el formulario!")
        else:
            stages = ["Enfocar", "Detectar", "Idear", "Diseñar MVP", "Pilotear", "Escalar"]
            cols = st.columns(len(stages))

            for i, stage in enumerate(stages):
                with cols[i]:
                    st.header(stage)
                    stage_tickets = df[df['Estado'] == stage]
                    
                    for index, row in stage_tickets.iterrows():
                        ticket_id = row['ID Ticket']
                        priority = row['Prioridad']

                        # Usamos st.markdown con HTML para crear la tarjeta personalizada
                        st.markdown(f"""
                        <div class="kanban-card">
                            <div class="priority-pill priority-{priority}">{priority}</div>
                            <h3>{row['Título']}</h3>
                            <p><strong>#{ticket_id}</strong></p>
                            <p>👤 <strong>Solicitante:</strong> {row['Solicitante']}</p>
                            <p>📅 <strong>Creado:</strong> {pd.to_datetime(row['Fecha Creacion']).strftime('%d/%m/%Y')}</p>
                        </div>
                        """, unsafe_allow_html=True)

                        # --- EDITADO: Expansor para ver solo la descripción ---
                        with st.expander("Ver Descripción"):
                            st.write(row.get('Descripcion', 'No disponible'))


                        # El selector para mover la tarjeta
                        new_stage = st.selectbox(
                            f"Mover #{ticket_id}",
                            options=stages,
                            index=stages.index(stage),
                            key=f"select_{ticket_id}",
                            label_visibility="collapsed"
                        )

                        # Lógica de actualización
                        if new_stage != stage:
                            try:
                                list_of_ids = worksheet.col_values(1)
                                row_number = list_of_ids.index(str(ticket_id)) + 1
                                worksheet.update_cell(row_number, 8, new_stage)
                                st.success(f"Idea #{ticket_id} movida a {new_stage}!")
                                st.cache_data.clear()
                                st.rerun()
                            except ValueError:
                                st.error(f"Error Crítico: No se pudo encontrar el ID '{ticket_id}'.")
                            except Exception as e:
                                st.error(f"Error inesperado al actualizar: {e}")
