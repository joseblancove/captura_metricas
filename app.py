import os
import json
import datetime
import traceback
from flask import Flask, request, render_template, jsonify
from werkzeug.utils import secure_filename
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core import exceptions as google_exceptions
import PIL.Image
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- 1. CONFIGURACIÓN DE PRODUCCIÓN ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")
SHEET_ID = os.environ.get("SHEET_ID")
WORKSHEET_NAME = 'Master_Data'
GOOGLE_CREDS_JSON_STRING = os.environ.get("GOOGLE_CREDS_JSON_STRING")

genai.configure(api_key=GEMINI_API_KEY)

GOOGLE_CREDS_DICT = json.loads(GOOGLE_CREDS_JSON_STRING)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# --- 2. INICIALIZACIÓN DE FLASK ---
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- 3. FUNCIONES EXPERTAS DE GOOGLE DRIVE ---

def find_or_create_folder(service, parent_id, folder_name):
    """Busca una carpeta por nombre en un directorio padre, si no existe la crea."""
    folder_name_escaped = folder_name.replace("'", "\\'")
    query = f"name = '{folder_name_escaped}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    
    response = service.files().list(q=query, spaces='drive', fields='files(id)').execute()
    files = response.get('files', [])

    if files:
        return files[0].get('id')
    else:
        folder_metadata = {
            'name': folder_name,
            'parents': [parent_id],
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')

def upload_files_to_structured_folders(service, client_name, campaign_name, influencer_name, platform, format_type, post_folder_name, files_to_upload):
    """Sube archivos a una estructura jerárquica profunda."""
    try:
        client_folder_id = find_or_create_folder(service, DRIVE_FOLDER_ID, client_name)
        campaign_folder_id = find_or_create_folder(service, client_folder_id, campaign_name)
        influencer_folder_id = find_or_create_folder(service, campaign_folder_id, influencer_name)
        platform_folder_id = find_or_create_folder(service, influencer_folder_id, platform)
        format_folder_id = find_or_create_folder(service, platform_folder_id, format_type)

        post_folder_metadata = {
            'name': post_folder_name,
            'parents': [format_folder_id],
            'mimeType': 'application/vnd.google-apps.folder'
        }
        post_folder = service.files().create(body=post_folder_metadata, fields='id, webViewLink').execute()
        post_folder_id = post_folder.get('id')
        post_folder_link = post_folder.get('webViewLink')

        for filepath, filename in files_to_upload:
            file_metadata = {'name': filename, 'parents': [post_folder_id]}
            media = MediaFileUpload(filepath, mimetype='image/png', resumable=True)
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        
        return post_folder_link
    except Exception as e:
        print(f"Error al interactuar con Drive: {e}")
        traceback.print_exc()
        return None

# --- 4. RUTAS DE LA APLICACIÓN ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    filepaths_to_delete = []
    try:
        print("--- NUEVO ENVÍO RECIBIDO ---")
        # --- Obtención de datos del formulario ---
        client_name = request.form['client_name']
        campaign_name = request.form['campaign_name']
        influencer_name = request.form['influencer_name']
        platform = request.form['platform']
        format_type = request.form['format']
        organic_paid = request.form['organic_paid']
        content_id = request.form.get('content_id', '')
        image_files = request.files.getlist('metric_images[]')

        if not image_files:
            return jsonify({'status': 'error', 'message': 'No se recibieron archivos.'}), 400

        # --- Lógica para preparar el contenido para Gemini (AHORA EN EL ORDEN CORRECTO) ---
        content_for_ai = []
        files_for_drive = []
        prompt = f"""INSTRUCCIÓN CRÍTICA: Recibirás un lote de {len(image_files)} imágenes que pertenecen a la MISMA publicación o contenido. Tu tarea es actuar como un analista de datos y consolidar toda la información que encuentres en UN ÚNICO objeto JSON. REGLAS DE CONSOLIDACIÓN: 1. Examina TODAS las imágenes antes de responder. 2. Si una misma métrica (ej: 'likes') aparece en varias imágenes, utiliza el valor numérico más alto y más completo que encuentres. 3. Rellena cada campo del JSON con la mejor información disponible entre todas las imágenes. 4. ¡IMPORTANTE! Convierte siempre abreviaturas ('K', 'M') a números completos (ej: 2.5K a 2500, 1.2M a 1200000). 5. Si después de examinar todas las imágenes, no encuentras NINGUNA métrica, debes explicar por qué en el campo 'extraction_notes'. Por ejemplo: "Las imágenes no contienen contadores numéricos visibles de métricas." 6. Tu respuesta DEBE ser ÚNICAMENTE el objeto JSON, sin ningún otro texto. El formato requerido es: {{"likes": null, "comments": null, "shares": null, "saves": null, "views": null, "reach": null, "link_clicks": null, "clicks_stickers": null, "extraction_notes": "Extracción exitosa."}}"""
        
        content_for_ai.append(prompt)
        for image_file in image_files:
            filename = secure_filename(image_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(filepath)
            filepaths_to_delete.append(filepath)
            files_for_drive.append((filepath, filename))
            content_for_ai.append(PIL.Image.open(filepath))
            
        # --- Llamada a Gemini ---
        print("1. Empezando análisis con Gemini...")
        model = genai.GenerativeModel('gemini-1.5-flash-latest', generation_config=GenerationConfig(response_mime_type="application/json"))
        response = model.generate_content(content_for_ai)
        consolidated_metrics = json.loads(response.text)
        print("2. Análisis de Gemini completado.")
        
        # --- Lógica de Google Drive ---
        print("3. Subiendo a Drive...")
        creds_drive = service_account.Credentials.from_service_account_info(GOOGLE_CREDS_DICT, scopes=SCOPES)
        drive_service = build('drive', 'v3', credentials=creds_drive)
        post_folder_name = f"{content_id or 'General'} - {datetime.datetime.now().strftime('%Y-%m-%d_%H%M')}"
        
        drive_folder_link = upload_files_to_structured_folders(
            service=drive_service, client_name=client_name, campaign_name=campaign_name,
            influencer_name=influencer_name, platform=platform, format_type=format_type,
            post_folder_name=post_folder_name, files_to_upload=files_for_drive
        )
        print("4. Subida a Drive completada.")

        # --- Lógica de Google Sheets ---
        print("5. Guardando en Sheets...")
        creds_gspread = gspread.service_account_from_dict(GOOGLE_CREDS_DICT)
        workbook = creds_gspread.open_by_key(SHEET_ID)
        sheet = workbook.worksheet(WORKSHEET_NAME)
        
        new_row = [
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), client_name, campaign_name,
            influencer_name, platform, format_type, content_id, organic_paid,
            consolidated_metrics.get('reach'), consolidated_metrics.get('views'),
            consolidated_metrics.get('likes'), consolidated_metrics.get('comments'),
            consolidated_metrics.get('saves'), consolidated_metrics.get('shares'),
            consolidated_metrics.get('link_clicks'), consolidated_metrics.get('clicks_stickers'),
            drive_folder_link, consolidated_metrics.get('extraction_notes')
        ]
        sheet.append_row(new_row, table_range="A1")
        print("6. Guardado en Sheets completado. ¡Todo OK!")

        return jsonify({'status': 'success', 'message': 'Lote procesado y guardado.'}), 200

    except google_exceptions.RetryError as e:
        print(f"!!! ERROR DE API DE GOOGLE: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': 'El servicio de IA está sobrecargado. Inténtalo más tarde.'}), 503
    except Exception as e:
        print(f"!!! ERROR ATRAPADO: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        print("--- Limpiando archivos temporales ---")
        for path in filepaths_to_delete:
            try:
                os.remove(path)
            except OSError as e:
                print(f"Error al eliminar el archivo {path}: {e}")