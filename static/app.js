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
        runSudoCommandBtn: document.getElementById('run-sudo-command-btn'),
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
        scheduleEditForm: document.getElementById('schedule-edit-form'),
        suggestScriptBtn: document.getElementById('suggest-script-btn'),
        suggestScriptModal: document.getElementById('suggest-script-modal'),
        suggestScriptForm: document.getElementById('suggest-script-form'),
        suggestionOutput: document.getElementById('suggestion-output')
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
            const contentType = response.headers.get("content-type");
            return contentType?.includes("application/json") ? response.json() : null;
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
    
    const handleSuggestScriptSubmit = async (e) => {
        e.preventDefault();
        if (!geminiApiKey) return showToast('Please set your Gemini API Key in Settings first.', 'error');
        
        const prompt = DOMElements.suggestScriptForm.querySelector('textarea[name="prompt"]').value;
        DOMElements.suggestionOutput.innerHTML = '<div class="placeholder"><i class="fas fa-spinner fa-spin"></i> Generating suggestions...</div>';

        try {
            const data = await apiCall('/api/suggest-script', {
                method: 'POST',
                body: JSON.stringify({ prompt, apiKey: geminiApiKey })
            });

            if (data.status === 'success') {
                displaySuggestions(data.suggestions);
            }
        } catch (error) {
            DOMElements.suggestionOutput.innerHTML = `<p style="color: var(--error-color);">Suggestion failed. ${error.message}</p>`;
        }
    };

    const displaySuggestions = (suggestions) => {
        DOMElements.suggestionOutput.innerHTML = '';
        const suggestionMap = {
            'bash_command': { title: 'Bash Command', type: 'bash-command' },
            'bash_script': { title: 'Bash Script', type: 'bash-script' },
            'python_script': { title: 'Python Script', type: 'python-script' },
            'ansible_playbook': { title: 'Ansible Playbook', type: 'ansible-playbook' }
        };

        for (const key in suggestionMap) {
            if (suggestions[key]) {
                const { title, type } = suggestionMap[key];
                const box = document.createElement('div');
                box.className = 'suggestion-box';
                box.innerHTML = `
                    <div class="suggestion-box-header">${title}</div>
                    <pre><code>${escapeHtml(suggestions[key])}</code></pre>
                    <button class="action-btn use-suggestion-btn">Use this script</button>
                `;
                box.querySelector('.use-suggestion-btn').addEventListener('click', () => {
                    DOMElements.commandInput.value = suggestions[key];
                    DOMElements.scriptTypeInput.value = type;
                    DOMElements.suggestScriptModal.style.display = 'none';
                    showToast(`${title} loaded into editor.`);
                });
                DOMElements.suggestionOutput.appendChild(box);
            }
        }
    };
    
    const escapeHtml = (unsafe) => unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");

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
        item.innerHTML = `<input type="checkbox" class="script-select-checkbox"><div class="script-info" title="Load: ${script.name}"><strong>${script.name}</strong><small>Type: ${script.script_type}</small></div><div class="script-actions"><button class="edit-script-btn icon-btn" title="Edit Script"><i class="fas fa-pencil-alt"></i></button><button class="delete-script-btn icon-btn" title="Delete Script"><i class="fas fa-times"></i></button></div>`;
        DOMElements.savedScriptsList.appendChild(item);
    };

    const handleRunCommand = async (useSudo = false) => {
        const selectedHostIds = [...document.querySelectorAll('.host-select-checkbox:checked')].map(cb => cb.closest('.host-item').dataset.hostId);
        const command = DOMElements.commandInput.value;
        const type = DOMElements.scriptTypeInput.value;
        if (selectedHostIds.length === 0) return showToast('Please select at least one host.', 'error');
        if (!command.trim()) return showToast('Command cannot be empty.', 'error');
        DOMElements.resultsOutput.innerHTML = '<div class="placeholder">Running... <i class="fas fa-spinner fa-spin"></i></div>';
        DOMElements.runCommandBtn.disabled = true;
        if(DOMElements.runSudoCommandBtn) DOMElements.runSudoCommandBtn.disabled = true;
        DOMElements.aiAnalyzeBtn.style.display = 'none';
        try {
            const data = await apiCall('/api/run', { method: 'POST', body: JSON.stringify({ host_ids: selectedHostIds, command, type, use_sudo: useSudo }) });
            displayResults(data.results);
            if (DOMElements.aiAnalyzeBtn && data.results && data.results.length > 0) {
                DOMElements.aiAnalyzeBtn.style.display = 'inline-flex';
            }
        } catch (error) {
            DOMElements.resultsOutput.innerHTML = `<div class="placeholder">An error occurred.</div>`;
        } finally {
            DOMElements.runCommandBtn.disabled = false;
            if(DOMElements.runSudoCommandBtn) DOMElements.runSudoCommandBtn.disabled = false;
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

    const handleSettingsSubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(DOMElements.settingsForm);
        await apiCall('/api/settings', { method: 'POST', body: JSON.stringify(Object.fromEntries(formData)) });
        showToast('Settings saved!');
        DOMElements.settingsModal.style.display = 'none';
        loadInitialData();
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
        }
        DOMElements.editScriptModal.style.display = 'none';
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
                showToast('Schedule deleted. Restart scheduler to deactivate.');
                loadSchedules();
            }
        }
    };

    // Initialize
    setupModals();
    loadInitialData();

    // Wire up all event listeners
    safeAddEventListener(DOMElements.suggestScriptBtn, 'click', () => { DOMElements.suggestScriptModal.style.display = 'flex'; DOMElements.suggestScriptForm.reset(); DOMElements.suggestionOutput.innerHTML = ''; });
    safeAddEventListener(DOMElements.suggestScriptForm, 'submit', handleSuggestScriptSubmit);
    safeAddEventListener(DOMElements.settingsBtn, 'click', () => { loadInitialData(); DOMElements.settingsModal.style.display = 'flex'; });
    safeAddEventListener(DOMElements.settingsForm, 'submit', handleSettingsSubmit);
    safeAddEventListener(DOMElements.addHostBtn, 'click', () => { DOMElements.addHostModal.style.display = 'flex'; DOMElements.addHostForm.reset(); });
    safeAddEventListener(DOMElements.addHostForm, 'submit', handleAddHostSubmit);
    safeAddEventListener(DOMElements.editHostForm, 'submit', handleEditHostSubmit);
    safeAddEventListener(DOMElements.hostList, 'click', handleHostListClick);
    safeAddEventListener(DOMElements.saveScriptBtn, 'click', () => { DOMElements.saveScriptModal.style.display = 'flex'; DOMElements.saveScriptForm.reset(); });
    safeAddEventListener(DOMElements.saveScriptForm, 'submit', handleSaveScriptSubmit);
    safeAddEventListener(DOMElements.editScriptForm, 'submit', handleEditScriptSubmit);
    safeAddEventListener(DOMElements.runCommandBtn, 'click', () => handleRunCommand(false));
    safeAddEventListener(DOMElements.runSudoCommandBtn, 'click', () => handleRunCommand(true));
    safeAddEventListener(DOMElements.clearResultsBtn, 'click', () => { DOMElements.resultsOutput.innerHTML = '<div class="placeholder">Output appears here...</div>'; if(DOMElements.aiAnalyzeBtn) DOMElements.aiAnalyzeBtn.style.display = 'none'; });
    safeAddEventListener(DOMElements.savedScriptsList, 'click', handleSavedScriptsListClick);
    safeAddEventListener(DOMElements.scriptTypeInput, 'change', (e) => { DOMElements.commandInput.value = scriptSnippets[e.target.value] || ''; });
    safeAddEventListener(DOMElements.scheduleBtn, 'click', () => { loadSchedules(); DOMElements.scheduleListModal.style.display = 'flex'; });
    safeAddEventListener(DOMElements.addScheduleBtn, 'click', () => { DOMElements.scheduleEditForm.reset(); populateScheduleFormDropdowns(); DOMElements.scheduleEditModal.style.display = 'flex'; });
    safeAddEventListener(DOMElements.scheduleEditForm, 'submit', handleScheduleFormSubmit);
    safeAddEventListener(DOMElements.scheduleList, 'click', handleScheduleListClick);
});
