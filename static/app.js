// static/app.js - v7 (FINAL CORREGIDO - Envía datos del formulario y archivos)
document.addEventListener('DOMContentLoaded', () => {
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
    
    let fileQueue = [];

    function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(e => { dropZone.addEventListener(e, preventDefaults, false); });
    ['dragenter', 'dragover'].forEach(e => { dropZone.addEventListener(e, () => dropZone.classList.add('highlight'), false); });
    ['dragleave', 'drop'].forEach(e => { dropZone.addEventListener(e, () => dropZone.classList.remove('highlight'), false); });
    dropZone.addEventListener('drop', e => { handleFiles(e.dataTransfer.files); });

    browseBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', e => { handleFiles(e.target.files); });

    function handleFiles(files) { fileQueue.push(...files); renderFileList(); }

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

    function enterUploadMode() {
        Array.from(form.elements).forEach(el => {
            if(el.tagName === 'INPUT' || el.tagName === 'SELECT') { el.disabled = true; }
        });
        prepareBtn.style.display = 'none';
        const campaign = document.getElementById('campaign').value;
        mainTitle.textContent = `Cargando para: ${campaign}`;
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
    }

    function renderFileList() {
        fileList.innerHTML = '';
        fileQueue.forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.classList.add('file-item');
            fileItem.innerHTML = `<span>${file.name}</span><span class="status pending">Listo para analizar</span>`;
            fileList.appendChild(fileItem);
        });
        if (fileQueue.length > 0) uploadBtn.style.display = 'block';
    }

    async function processAndConsolidate() {
        uploadBtn.disabled = true;
        uploadBtn.textContent = 'Analizando y Consolidando...';
        statusMessage.textContent = `Enviando ${fileQueue.length} imágenes a la IA...`;
        statusMessage.className = 'alert info-alert';
        statusMessage.style.display = 'block';

        // --- ¡LA CORRECCIÓN ESTÁ AQUÍ! ---
        // Creamos un FormData vacío y añadimos TODOS los campos manualmente.
        const formData = new FormData();
        formData.append('campaign_name', document.getElementById('campaign').value);
        formData.append('influencer_name', document.getElementById('influencer').value);
        formData.append('platform', document.getElementById('platform').value);
        formData.append('format', document.getElementById('format').value);
        formData.append('content_id', document.getElementById('content_id').value);
        
        // Ahora añadimos todas las imágenes al mismo paquete
        fileQueue.forEach(file => {
            formData.append('metric_images[]', file, file.name);
        });

        try {
            const response = await fetch('/upload', { method: 'POST', body: formData });
            const data = await response.json();
            if (response.ok && data.status === 'success') {
                statusMessage.textContent = '¡Éxito! Lote consolidado y guardado.';
                statusMessage.className = 'alert success-alert';
                uploadBtn.style.display = 'none';
                resetBtn.style.display = 'block';
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