// static/app.js - v16 (VERSIÓN FINAL DEFINITIVA)

// --- CONFIGURACIÓN ---
// ¡IMPORTANTE! REEMPLAZA ESTO CON EL ID REAL DE TU GOOGLE SHEET
const SHEET_ID = '1JWfRnV15tUmBdKY-xTRJooUHJ8ORhGd1EfijvQgYDwQ'; 

document.addEventListener('DOMContentLoaded', () => {
    // --- Referencias a Elementos del DOM ---
    const form = document.getElementById('metric-form');
    const prepareBtn = document.getElementById('prepare-btn');
    const uploadSection = document.getElementById('upload-section');
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const browseBtn = document.getElementById('browse-btn');
    const fileList = document.getElementById('file-list');
    const uploadBtn = document.getElementById('upload-btn');
    const resetBtn = document.getElementById('reset-btn');
    const statusMessage = document.getElementById('status-message');
    const mainTitle = document.getElementById('main-title');
    const summaryContainer = document.getElementById('success-summary');
    
    let fileQueue = [];

    // --- MANEJO DE DRAG & DROP Y SUBIDA MANUAL ---
    function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => dropZone.addEventListener(eventName, preventDefaults, false));
    ['dragenter', 'dragover'].forEach(e => dropZone.addEventListener(e, () => dropZone.classList.add('highlight'), false));
    ['dragleave', 'drop'].forEach(e => dropZone.addEventListener(e, () => dropZone.classList.remove('highlight'), false));
    
    dropZone.addEventListener('drop', e => handleFiles(e.dataTransfer.files));
    browseBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', e => {
        handleFiles(e.target.files);
        e.target.value = '';
    });

    function handleFiles(files) {
        const newFiles = [...files].filter(file => !fileQueue.some(existing => existing.name === file.name && existing.size === file.size));
        fileQueue.push(...newFiles);
        renderFileList();
    }

    fileList.addEventListener('click', (e) => {
        if (e.target && e.target.classList.contains('delete-btn')) {
            const fileIdToRemove = e.target.dataset.fileId;
            fileQueue = fileQueue.filter(file => `file-${file.name}-${file.size}` !== fileIdToRemove);
            renderFileList();
        }
    });

    // --- LÓGICA DE FLUJO DE TRABAJO ---
    prepareBtn.addEventListener('click', () => {
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }
        enterUploadMode();
    });
    
    uploadBtn.addEventListener('click', () => {
        if (fileQueue.length === 0) {
            alert('Por favor, selecciona o arrastra al menos una captura.');
            return;
        }
        processAndConsolidate();
    });

    resetBtn.addEventListener('click', () => resetToInitialState());

    // --- FUNCIONES DE ESTADO DE LA UI ---
    function enterUploadMode() {
        Array.from(form.elements).forEach(el => {
            if(el.tagName === 'INPUT' || el.tagName === 'SELECT') { el.disabled = true; }
        });
        prepareBtn.style.display = 'none';
        mainTitle.textContent = `Cargando para: ${document.getElementById('campaign_name').value}`;
        uploadSection.style.display = 'block';
    }

    function resetToInitialState() {
        fileQueue = [];
        fileList.innerHTML = '';
        form.reset();
        Array.from(form.elements).forEach(el => el.disabled = false);
        prepareBtn.style.display = 'block';
        uploadSection.style.display = 'none';
        resetBtn.style.display = 'none';
        statusMessage.style.display = 'none';
        mainTitle.textContent = 'Registrar Contenido';
        form.style.display = 'flex';
    }

    function renderFileList() {
        fileList.innerHTML = '';
        fileQueue.forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.classList.add('file-item');
            const fileId = `file-${file.name}-${file.size}`;
            fileItem.innerHTML = `<span>${file.name}</span><button type="button" class="delete-btn" data-file-id="${fileId}">&times;</button>`;
            fileList.appendChild(fileItem);
        });
        uploadBtn.style.display = fileQueue.length > 0 ? 'block' : 'none';
    }

    // --- FUNCIÓN PARA MOSTRAR LA TARJETA DE ÉXITO ---
    function displaySuccessSummary(processedData) {
        const metrics = processedData.metrics;
        const driveLink = processedData.drive_folder_link;
        
        const icons = {
            likes: 'fa-thumbs-up', comments: 'fa-comments', shares: 'fa-share-square',
            saves: 'fa-bookmark', views: 'fa-eye', reach: 'fa-users'
        };

        let metricsHtml = '';
        const relevantMetrics = ['reach', 'views', 'likes', 'comments', 'shares', 'saves'];
        relevantMetrics.forEach(key => {
            if (metrics[key] !== null && metrics[key] !== undefined) {
                metricsHtml += `
                    <div class="metric-box">
                        <i class="fas ${icons[key]}"></i>
                        <div class="metric-label">${key}</div>
                        <div class="metric-value">${Number(metrics[key]).toLocaleString('es-ES')}</div>
                    </div>
                `;
            }
        });

        summaryContainer.innerHTML = `
            <h2 class="summary-title"><i class="fas fa-check-circle"></i>¡Publicación Registrada!</h2>
            <div class="metrics-grid">${metricsHtml || '<p>No se extrajeron métricas visuales.</p>'}</div>
            <div class="action-buttons">
                <a href="${driveLink}" target="_blank" title="Abrir carpeta con las capturas">
                    <i class="fab fa-google-drive"></i> Ver en Drive
                </a>
                <a href="https://docs.google.com/spreadsheets/d/${SHEET_ID}" target="_blank" title="Abrir la base de datos">
                    <i class="fas fa-table"></i> Ver en Sheets
                </a>
            </div>
        `;

        form.style.display = 'none';
        uploadSection.style.display = 'none';
        summaryContainer.style.display = 'block';
    }

    // --- FUNCIÓN PRINCIPAL DE PROCESAMIENTO ---
    async function processAndConsolidate() {
        uploadBtn.disabled = true;
        uploadBtn.textContent = 'Analizando y Consolidando...';
        statusMessage.textContent = `Enviando ${fileQueue.length} imágenes a la IA...`;
        statusMessage.className = 'alert info-alert';
        statusMessage.style.display = 'block';

        const formData = new FormData();
        formData.append('client_name', document.getElementById('client_name').value);
        formData.append('campaign_name', document.getElementById('campaign_name').value);
        formData.append('influencer_name', document.getElementById('influencer').value);
        formData.append('platform', document.getElementById('platform').value);
        formData.append('format', document.getElementById('format').value);
        formData.append('organic_paid', document.getElementById('organic_paid').value);
        formData.append('content_id', document.getElementById('content_id').value);
        fileQueue.forEach(file => { formData.append('metric_images[]', file, file.name); });

        try {
            const response = await fetch('/upload', { method: 'POST', body: formData });
            const data = await response.json();
            if (response.ok && data.status === 'success') {
                statusMessage.style.display = 'none';
                displaySuccessSummary(data.processed_data);

                setTimeout(() => {
                    summaryContainer.style.display = 'none';
                    resetToInitialState();
                }, 15000); // 15 segundos
            } else {
                throw new Error(data.message || 'Error desconocido del servidor.');
            }
        } catch (error) {
            statusMessage.textContent = `Error: ${error.message}`;
            statusMessage.className = 'alert error-alert';
            uploadBtn.disabled = false;
            uploadBtn.textContent = 'Analizar y Consolidar Métricas';
        }
    }
});