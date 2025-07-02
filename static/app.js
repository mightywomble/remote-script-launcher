// static/app.js
document.addEventListener('DOMContentLoaded', () => {
    // A single object to hold all DOM element references
    const DOMElements = {
        addHostBtn: document.getElementById('add-host-btn'),
        addHostModal: document.getElementById('add-host-modal'),
        addHostForm: document.getElementById('add-host-form'),
        editHostModal: document.getElementById('edit-host-modal'),
        editHostForm: document.getElementById('edit-host-form'),
        saveScriptBtn: document.getElementById('save-script-btn'),
        saveScriptModal: document.getElementById('save-script-modal'),
        saveScriptForm: document.getElementById('save-script-form'),
        editScriptModal: document.getElementById('edit-script-modal'),
        editScriptForm: document.getElementById('edit-script-form'),
        runCommandBtn: document.getElementById('run-command-btn'),
        clearResultsBtn: document.getElementById('clear-results-btn'),
        hostList: document.getElementById('host-list'),
        savedScriptsList: document.getElementById('saved-scripts-list'),
        commandInput: document.getElementById('command-input'),
        resultsOutput: document.getElementById('results-output'),
        toast: document.getElementById('toast-notification'),
        scriptTypeInput: document.getElementById('script-type-input'),
        settingsBtn: document.getElementById('settings-btn'),
        settingsModal: document.getElementById('settings-modal'),
        settingsForm: document.getElementById('settings-form'),
        geminiApiKeyInput: document.getElementById('gemini-api-key-input'),
        discordWebhookUrlInput: document.getElementById('discord-webhook-url-input'),
        aiAnalyzeBtn: document.getElementById('ai-analyze-btn'),
        aiAnalysisModal: document.getElementById('ai-analysis-modal'),
        aiAnalysisOutput: document.getElementById('ai-analysis-output'),
        deleteSelectedScriptsBtn: document.getElementById('delete-selected-scripts-btn'),
        scheduleBtn: document.getElementById('schedule-btn'),
        scheduleListModal: document.getElementById('schedule-list-modal'),
        scheduleList: document.getElementById('schedule-list'),
        addScheduleBtn: document.getElementById('add-schedule-btn'),
        scheduleEditModal: document.getElementById('schedule-edit-modal'),
        scheduleEditForm: document.getElementById('schedule-edit-form')
    };

    let geminiApiKey = '';

    const scriptSnippets = {
        'bash-script': `#!/bin/bash\necho "Hello from $(hostname)!"`,
        'python-script': `#!/usr/bin/env python3\nimport os\nprint(f"Hello from Python on {os.name}!")`,
        'ansible-playbook': `---\n- name: Example Playbook\n  hosts: localhost\n  tasks:\n    - name: Ping\n      ansible.builtin.ping:`,
    };

    const apiCall = async (url, options = {}) => {
        try {
            const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
            if (!response.ok) throw new Error((await response.json()).message || `HTTP ${response.status}`);
            return response.headers.get("content-type")?.includes("application/json") ? response.json() : null;
        } catch (error) {
            showToast(error.message, 'error');
            throw error;
        }
    };

    const showToast = (message, type = 'success') => {
        if (!DOMElements.toast) return;
        DOMElements.toast.textContent = message;
        DOMElements.toast.className = `show ${type}`;
        setTimeout(() => { DOMElements.toast.className = ''; }, 3000);
    };

    const safeAddEventListener = (element, event, handler) => {
        if (element) {
            element.addEventListener(event, handler);
        } else {
            console.error(`Initialization Error: Element not found for event listener.`);
        }
    };

    const setupModals = () => {
        document.querySelectorAll('.modal').forEach(modal => {
            safeAddEventListener(modal.querySelector('.close-btn'), 'click', () => modal.style.display = 'none');
        });
    };

    const loadInitialData = async () => {
        try {
            const settings = await apiCall('/api/settings');
            geminiApiKey = settings.apiKey;
            if (DOMElements.geminiApiKeyInput) DOMElements.geminiApiKeyInput.value = settings.apiKey;
            if (DOMElements.discordWebhookUrlInput) DOMElements.discordWebhookUrlInput.value = settings.discordUrl;
        } catch (e) { console.error("Failed to load initial data:", e); }
    };

    const populateScheduleFormDropdowns = () => {
        const hostSelect = DOMElements.scheduleEditForm.querySelector('select[name="host_id"]');
        const scriptSelect = DOMElements.scheduleEditForm.querySelector('select[name="script_id"]');
        
        hostSelect.innerHTML = '';
        document.querySelectorAll('#host-list .host-item').forEach(item => {
            const option = document.createElement('option');
            option.value = item.dataset.hostId;
            option.textContent = item.querySelector('.host-info strong').textContent;
            hostSelect.appendChild(option);
        });

        scriptSelect.innerHTML = '';
        document.querySelectorAll('#saved-scripts-list .saved-script-item').forEach(item => {
            const option = document.createElement('option');
            option.value = item.dataset.scriptId;
            option.textContent = item.querySelector('.script-info strong').textContent;
            scriptSelect.appendChild(option);
        });
    };

    const loadSchedules = async () => {
        try {
            const schedules = await apiCall('/api/schedules');
            DOMElements.scheduleList.innerHTML = schedules.map(s => `
                <div class="schedule-item" data-schedule-id="${s.id}">
                    <div><strong>${s.name}</strong><small>${s.host_name} &rarr; ${s.script_name} at ${String(s.hour).padStart(2,'0')}:${String(s.minute).padStart(2,'0')}</small></div>
                    <div class="schedule-actions">
                        <button class="delete-schedule-btn icon-btn" title="Delete Schedule"><i class="fas fa-trash-alt"></i></button>
                    </div>
                </div>
            `).join('') || '<div class="placeholder">No schedules found.</div>';
        } catch (e) { console.error("Failed to load schedules:", e); }
    };

    // --- All Event Handlers ---
    const handleSettingsSubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(DOMElements.settingsForm);
        await apiCall('/api/settings', { method: 'POST', body: JSON.stringify(Object.fromEntries(formData)) });
        showToast('Settings saved!');
        DOMElements.settingsModal.style.display = 'none';
    };

    const handleAddHostSubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(DOMElements.addHostForm);
        const result = await apiCall('/api/hosts', { method: 'POST', body: JSON.stringify(Object.fromEntries(formData)) });
        addHostToList(result.host);
        showToast(result.message);
        DOMElements.addHostModal.style.display = 'none';
    };

    const handleEditHostSubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(DOMElements.editHostForm);
        const hostId = formData.get('host_id');
        const payload = Object.fromEntries(formData);
        const result = await apiCall(`/api/hosts/${hostId}`, { method: 'PUT', body: JSON.stringify(payload) });
        showToast(result.message);
        const hostItem = DOMElements.hostList.querySelector(`.host-item[data-host-id='${hostId}']`);
        if (hostItem) {
            hostItem.querySelector('.host-name').textContent = result.host.friendly_name;
            hostItem.querySelector('small').textContent = `${result.host.username}@${result.host.hostname}`;
        }
        DOMElements.editHostModal.style.display = 'none';
    };

    const handleSaveScriptSubmit = async (e) => {
        e.preventDefault();
        const name = DOMElements.saveScriptForm.querySelector('input[name="name"]').value;
        const type = DOMElements.scriptTypeInput.value;
        const content = DOMElements.commandInput.value;
        const result = await apiCall('/api/scripts', { method: 'POST', body: JSON.stringify({ name, type, content }) });
        addScriptToList(result.script);
        showToast(result.message);
        DOMElements.saveScriptModal.style.display = 'none';
    };
    
    const handleEditScriptSubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(DOMElements.editScriptForm);
        const scriptId = formData.get('script_id');
        const payload = {
            name: formData.get('name'),
            type: formData.get('script_type'),
            content: formData.get('content')
        };
        const result = await apiCall(`/api/scripts/${scriptId}`, { method: 'PUT', body: JSON.stringify(payload) });
        showToast(result.message);
        const scriptItem = DOMElements.savedScriptsList.querySelector(`.saved-script-item[data-script-id='${scriptId}']`);
        if (scriptItem) {
            scriptItem.querySelector('strong').textContent = result.script.name;
            scriptItem.querySelector('small').textContent = `Type: ${result.script.script_type}`;
            scriptItem.dataset.scriptType = result.script.script_type.toLowerCase();
        }
        DOMElements.editScriptModal.style.display = 'none';
    };

    const handleRunCommand = async () => {
        const selectedHostIds = [...document.querySelectorAll('.host-select-checkbox:checked')].map(cb => cb.closest('.host-item').dataset.hostId);
        const command = DOMElements.commandInput.value;
        const type = DOMElements.scriptTypeInput.value;
        if (selectedHostIds.length === 0) return showToast('Please select at least one host.', 'error');
        if (!command.trim()) return showToast('Command cannot be empty.', 'error');
        DOMElements.resultsOutput.innerHTML = '<div class="placeholder">Running... <i class="fas fa-spinner fa-spin"></i></div>';
        DOMElements.runCommandBtn.disabled = true;
        DOMElements.aiAnalyzeBtn.style.display = 'none';
        try {
            const data = await apiCall('/api/run', { method: 'POST', body: JSON.stringify({ host_ids: selectedHostIds, command, type }) });
            displayResults(data.results);
            if (DOMElements.aiAnalyzeBtn && data.results && data.results.length > 0) {
                DOMElements.aiAnalyzeBtn.style.display = 'inline-flex';
            }
        } catch (error) {
            DOMElements.resultsOutput.innerHTML = `<div class="placeholder">An error occurred.</div>`;
        } finally {
            DOMElements.runCommandBtn.disabled = false;
        }
    };
    
    const handleAiAnalysis = async () => {
        if (!geminiApiKey) return showToast('Please set your Gemini API Key in Settings first.', 'error');
        const outputText = [...DOMElements.resultsOutput.querySelectorAll('.result-block')].map(block => block.innerText).join('\n---\n');
        if (!outputText.trim()) return showToast('There is no output to analyze.', 'error');
        DOMElements.aiAnalysisModal.style.display = 'flex';
        DOMElements.aiAnalysisOutput.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';
        try {
            const data = await apiCall('/api/analyze', { method: 'POST', body: JSON.stringify({ output: outputText, apiKey: geminiApiKey }) });
            let html = data.analysis.replace(/^### (.*$)/gim, '<h3>$1</h3>').replace(/^## (.*$)/gim, '<h2>$1</h2>').replace(/^# (.*$)/gim, '<h1>$1</h1>').replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>').replace(/\*(.*)\*/gim, '<em>$1</em>').replace(/`([^`]+)`/gim, '<code>$1</code>').replace(/\n/g, '<br>');
            DOMElements.aiAnalysisOutput.innerHTML = html;
        } catch (error) {
            DOMElements.aiAnalysisOutput.innerHTML = `<p style="color: var(--error-color);">Analysis failed. ${error.message}</p>`;
        }
    };
    
    const handleScheduleFormSubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(DOMElements.scheduleEditForm);
        const payload = Object.fromEntries(formData);
        await apiCall('/api/schedules', { method: 'POST', body: JSON.stringify(payload) });
        showToast('Schedule saved! Restart scheduler process to activate.');
        DOMElements.scheduleEditModal.style.display = 'none';
        loadSchedules();
    };

    const handleScheduleListClick = async (e) => {
        if (e.target.closest('.delete-schedule-btn')) {
            const scheduleItem = e.target.closest('.schedule-item');
            const scheduleId = scheduleItem.dataset.scheduleId;
            if (confirm('Are you sure you want to delete this schedule?')) {
                await apiCall(`/api/schedules/${scheduleId}`, { method: 'DELETE' });
                showToast('Schedule deleted. Restart scheduler process to deactivate.');
                loadSchedules();
            }
        }
    };
    
    const displayResults = (results) => {
        DOMElements.resultsOutput.innerHTML = '';
        if (!results || results.length === 0) {
            DOMElements.resultsOutput.innerHTML = '<div class="placeholder">No results returned.</div>';
            return;
        }
        results.forEach(res => {
            const block = document.createElement('div');
            block.className = `result-block ${res.status}`;
            const output = res.output ? `<pre class="result-content">${escapeHtml(res.output)}</pre>` : '';
            const error = res.error ? `<pre class="result-content error-output">${escapeHtml(res.error)}</pre>` : '';
            block.innerHTML = `<div class="result-header">${res.host_name}</div>${output}${error}`;
            DOMElements.resultsOutput.appendChild(block);
        });
    };
    
    const addHostToList = (host) => {
        const item = document.createElement('div');
        item.className = 'host-item';
        item.dataset.hostId = host.id;
        item.innerHTML = `<input type="checkbox" class="host-select-checkbox"><div class="host-info"><strong>${host.friendly_name}</strong><small>${host.username}@${host.hostname}</small></div><div class="host-actions"><button class="test-conn-btn icon-btn" title="Test Connection"><i class="fas fa-plug"></i></button><button class="edit-host-btn icon-btn" title="Edit Host"><i class="fas fa-pencil-alt"></i></button><button class="delete-host-btn icon-btn" title="Delete Host"><i class="fas fa-trash-alt"></i></button></div>`;
        DOMElements.hostList.appendChild(item);
    };

    const addScriptToList = (script) => {
        const item = document.createElement('div');
        item.className = 'saved-script-item';
        item.dataset.scriptId = script.id;
        item.dataset.scriptType = script.script_type.toLowerCase();
        item.innerHTML = `<input type="checkbox" class="script-select-checkbox"><div class="script-info" title="Load: ${script.name}"><strong>${script.name}</strong><small>Type: ${script.script_type}</small></div><div class="script-actions"><button class="edit-script-btn icon-btn" title="Edit Script"><i class="fas fa-pencil-alt"></i></button><button class="delete-script-btn icon-btn" title="Delete Script"><i class="fas fa-times"></i></button></div>`;
        DOMElements.savedScriptsList.appendChild(item);
    };
    
    const escapeHtml = (unsafe) => unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");

    const updateDeleteSelectedBtnVisibility = () => {
        const anyChecked = DOMElements.savedScriptsList.querySelector('.script-select-checkbox:checked');
        if(DOMElements.deleteSelectedScriptsBtn) {
            DOMElements.deleteSelectedScriptsBtn.style.display = anyChecked ? 'inline-block' : 'none';
        }
    };

    const handleDeleteSelectedScripts = async () => {
        const selectedIds = [...DOMElements.savedScriptsList.querySelectorAll('.script-select-checkbox:checked')].map(cb => cb.closest('.saved-script-item').dataset.scriptId);
        if (selectedIds.length === 0 || !confirm(`Are you sure you want to delete ${selectedIds.length} script(s)?`)) return;
        try {
            const result = await apiCall('/api/scripts/delete', { method: 'POST', body: JSON.stringify({ ids: selectedIds }) });
            showToast(result.message);
            selectedIds.forEach(id => document.querySelector(`.saved-script-item[data-script-id='${id}']`)?.remove());
            updateDeleteSelectedBtnVisibility();
        } catch (error) { /* Handled */ }
    };

    const handleSavedScriptsListClick = async (e) => {
        const scriptItem = e.target.closest('.saved-script-item');
        if (!scriptItem) return;
        const scriptId = scriptItem.dataset.scriptId;

        if (e.target.closest('.delete-script-btn')) {
            if (!confirm(`Are you sure you want to delete "${scriptItem.querySelector('strong').textContent}"?`)) return;
            try {
                await apiCall(`/api/scripts/${scriptId}`, { method: 'DELETE' });
                showToast('Script deleted.');
                scriptItem.remove();
                updateDeleteSelectedBtnVisibility();
            } catch (error) { /* Handled */ }
        } else if (e.target.closest('.edit-script-btn')) {
            const data = await apiCall(`/api/scripts/${scriptId}`);
            if (data?.status === 'success') {
                DOMElements.editScriptForm.querySelector('input[name="script_id"]').value = data.script.id;
                DOMElements.editScriptForm.querySelector('input[name="name"]').value = data.script.name;
                DOMElements.editScriptForm.querySelector('select[name="script_type"]').value = data.script.type;
                DOMElements.editScriptForm.querySelector('textarea[name="content"]').value = data.script.content;
                DOMElements.editScriptModal.style.display = 'flex';
            }
        } else if (e.target.closest('.script-info')) {
            try {
                const data = await apiCall(`/api/scripts/${scriptId}`);
                if (data?.status === 'success') {
                    DOMElements.commandInput.value = data.script.content;
                    DOMElements.scriptTypeInput.value = data.script.type.toLowerCase();
                    showToast(`Script '${data.script.name}' loaded.`);
                }
            } catch (error) { /* Handled */ }
        }
    };
    
    const handleHostListClick = async (e) => {
        const hostItem = e.target.closest('.host-item');
        if (!hostItem) return;
        const hostId = hostItem.dataset.hostId;
        
        if (e.target.closest('.test-conn-btn')) {
            const button = e.target.closest('.test-conn-btn');
            const icon = button.querySelector('i');
            icon.className = 'fas fa-spinner fa-spin';
            button.disabled = true;
            try {
                const data = await apiCall(`/api/hosts/${hostId}/test`, { method: 'POST' });
                showToast(data.message, data.status);
                icon.className = data.status === 'success' ? 'fas fa-check-circle' : 'fas fa-times-circle';
            } catch (error) { icon.className = 'fas fa-times-circle'; }
            finally { setTimeout(() => { icon.className = 'fas fa-plug'; button.disabled = false; }, 3000); }
        } else if (e.target.closest('.edit-host-btn')) {
            try {
                const data = await apiCall(`/api/hosts/${hostId}`);
                if (data?.status === 'success') {
                    DOMElements.editHostForm.querySelector('input[name="host_id"]').value = data.host.id;
                    DOMElements.editHostForm.querySelector('#edit-friendly-name-input').value = data.host.friendly_name;
                    DOMElements.editHostForm.querySelector('#edit-hostname-input').value = data.host.hostname;
                    DOMElements.editHostForm.querySelector('#edit-username-input').value = data.host.username;
                    DOMElements.editHostModal.style.display = 'flex';
                }
            } catch (error) { /* Handled */ }
        } else if (e.target.closest('.delete-host-btn')) {
            if (confirm(`Are you sure you want to delete "${hostItem.querySelector('.host-name').textContent}"?`)) {
                try {
                    await apiCall(`/api/hosts/${hostId}`, { method: 'DELETE' });
                    showToast('Host deleted.');
                    hostItem.remove();
                } catch (error) { /* Handled */ }
            }
        }
    };

    // Initialize
    setupModals();
    loadInitialData();

    // Wire up all event listeners
    safeAddEventListener(DOMElements.settingsBtn, 'click', () => { loadInitialData(); DOMElements.settingsModal.style.display = 'flex'; });
    safeAddEventListener(DOMElements.settingsForm, 'submit', handleSettingsSubmit);
    safeAddEventListener(DOMElements.scheduleBtn, 'click', () => { loadSchedules(); DOMElements.scheduleListModal.style.display = 'flex'; });
    safeAddEventListener(DOMElements.addScheduleBtn, 'click', () => { DOMElements.scheduleEditForm.reset(); populateScheduleFormDropdowns(); DOMElements.scheduleEditModal.style.display = 'flex'; });
    safeAddEventListener(DOMElements.scheduleEditForm, 'submit', handleScheduleFormSubmit);
    safeAddEventListener(DOMElements.scheduleList, 'click', handleScheduleListClick);
    safeAddEventListener(DOMElements.addHostBtn, 'click', () => { DOMElements.addHostModal.style.display = 'flex'; DOMElements.addHostForm.reset(); });
    safeAddEventListener(DOMElements.addHostForm, 'submit', handleAddHostSubmit);
    safeAddEventListener(DOMElements.editHostForm, 'submit', handleEditHostSubmit);
    safeAddEventListener(DOMElements.hostList, 'click', handleHostListClick);
    safeAddEventListener(DOMElements.saveScriptBtn, 'click', () => { DOMElements.saveScriptModal.style.display = 'flex'; DOMElements.saveScriptForm.reset(); });
    safeAddEventListener(DOMElements.saveScriptForm, 'submit', handleSaveScriptSubmit);
    safeAddEventListener(DOMElements.editScriptForm, 'submit', handleEditScriptSubmit);
    safeAddEventListener(DOMElements.runCommandBtn, 'click', handleRunCommand);
    safeAddEventListener(DOMElements.aiAnalyzeBtn, 'click', handleAiAnalysis);
    safeAddEventListener(DOMElements.clearResultsBtn, 'click', () => { DOMElements.resultsOutput.innerHTML = '<div class="placeholder">Output appears here...</div>'; DOMElements.aiAnalyzeBtn.style.display = 'none'; });
    safeAddEventListener(DOMElements.scriptTypeInput, 'change', (e) => { DOMElements.commandInput.value = scriptSnippets[e.target.value] || ''; });
    safeAddEventListener(DOMElements.savedScriptsList, 'change', (e) => { if (e.target.classList.contains('script-select-checkbox')) { updateDeleteSelectedBtnVisibility(); } });
    safeAddEventListener(DOMElements.deleteSelectedScriptsBtn, 'click', handleDeleteSelectedScripts);
    safeAddEventListener(DOMElements.savedScriptsList, 'click', handleSavedScriptsListClick);
});
