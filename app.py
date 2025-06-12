# app.py - VERSIÓN 12 (FINAL DEFINITIVA - CON AUTO-DIAGNÓSTICO DE IA)
import os, json, datetime, traceback
from flask import Flask, request, render_template, jsonify
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core import exceptions as google_exceptions
import PIL.Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- 1. CONFIGURACIÓN ---
genai.configure(api_key="AIzaSyB0tPsRAHZChnuiod4NGCYukz2LdlhP6lI")
DRIVE_FOLDER_ID = '12kvf0Xwdz-ovhEvgd9ZGtoM4qCvbh8c4'
SHEET_ID = '1JWfRnV15tUmBdKY-xTRJooUHJ8ORhGd1EfijvQgYDwQ'
WORKSHEET_NAME = 'Master_Data'
CREDS_FILE = 'google_credentials.json'
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# --- 2. INICIALIZACIÓN ---
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def create_drive_folder_and_upload(files_to_upload, folder_name):
    try:
        creds = service_account.Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds)
        folder_metadata = {'name': folder_name, 'parents': [DRIVE_FOLDER_ID], 'mimeType': 'application/vnd.google-apps.folder'}
        folder = service.files().create(body=folder_metadata, fields='id, webViewLink').execute()
        new_folder_id = folder.get('id')
        folder_link = folder.get('webViewLink')
        for filepath, filename in files_to_upload:
            file_metadata = {'name': filename, 'parents': [new_folder_id]}
            media = MediaFileUpload(filepath, mimetype='image/png', resumable=True)
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return folder_link
    except Exception as e:
        print(f"Error al interactuar con Drive: {e}")
        return None

# --- 3. RUTAS DE LA APLICACIÓN ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        campaign = request.form['campaign_name']
        influencer = request.form['influencer_name']
        platform = request.form['platform']
        format_type = request.form['format']
        content_id = request.form.get('content_id', '')
        image_files = request.files.getlist('metric_images[]')

        if not image_files:
            return jsonify({'status': 'error', 'message': 'No se recibieron archivos.'}), 400

        content_for_ai, files_for_drive = [], []
        
        # --- ¡NUEVO PROMPT CON AUTO-DIAGNÓSTICO! ---
        prompt = f"""
        INSTRUCCIÓN CRÍTICA: Eres un analista de datos experto. Recibirás un lote de {len(image_files)} imágenes de un único contenido de redes sociales. Tu tarea es consolidar toda la información en UN ÚNICO objeto JSON.

        REGLAS DE EXTRACCIÓN Y CONSOLIDACIÓN:
        1. Examina TODAS las imágenes para obtener una visión completa.
        2. Si una métrica (ej: 'likes') aparece en varias imágenes, usa el valor numérico más alto que encuentres.
        3. Convierte siempre abreviaturas ('K', 'M') a números completos (ej: 2.5K a 2500, 1.2M a 1200000).
        4. Si después de examinar todas las imágenes, no encuentras NINGUNA métrica, debes explicar por qué en el campo 'extraction_notes'. Por ejemplo: "Las imágenes no contienen contadores numéricos visibles de métricas."
        5. Tu respuesta DEBE ser ÚNICAMENTE el objeto JSON, sin ningún otro texto.

        El formato requerido es:
        {{"likes": null, "comments": null, "shares": null, "saves": null, "views": null, "reach": null, "extraction_notes": "Extracción exitosa."}}
        """
        content_for_ai.append(prompt)

        for image_file in image_files:
            filepath = os.path.join(UPLOAD_FOLDER, image_file.filename)
            image_file.save(filepath)
            files_for_drive.append((filepath, image_file.filename))
            content_for_ai.append(PIL.Image.open(filepath))
            
        generation_config = GenerationConfig(response_mime_type="application/json")
        model = genai.GenerativeModel('gemini-1.5-flash-latest', generation_config=generation_config)
        response = model.generate_content(content_for_ai)
        consolidated_metrics = json.loads(response.text)
        
        folder_name = f"{campaign} - {influencer} - {content_id or 'General'}-{datetime.datetime.now().strftime('%Y%m%d')}"
        drive_folder_link = create_drive_folder_and_upload(files_for_drive, folder_name)

        creds_gspread = gspread.service_account(filename=CREDS_FILE)
        workbook = creds_gspread.open_by_key(SHEET_ID)
        sheet = workbook.worksheet(WORKSHEET_NAME)
        
        new_row = [
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), campaign, influencer,
            platform, format_type, content_id,
            consolidated_metrics.get('likes'), consolidated_metrics.get('comments'),
            consolidated_metrics.get('shares'), consolidated_metrics.get('saves'),
            consolidated_metrics.get('views'), consolidated_metrics.get('reach'),
            drive_folder_link,
            consolidated_metrics.get('extraction_notes') # ¡La nueva columna!
        ]
        sheet.append_row(new_row, table_range="A1")

        return jsonify({'status': 'success', 'message': 'Lote procesado y guardado con éxito.'}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)