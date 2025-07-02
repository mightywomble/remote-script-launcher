// static/app.js
document.addEventListener('DOMContentLoaded', () => {

    const DOMElements = {
        addHostBtn: document.getElementById('add-host-btn'), addHostModal: document.getElementById('add-host-modal'), addHostForm: document.getElementById('add-host-form'),
        editHostModal: document.getElementById('edit-host-modal'), editHostForm: document.getElementById('edit-host-form'),
        saveScriptBtn: document.getElementById('save-script-btn'), saveScriptModal: document.getElementById('save-script-modal'), saveScriptForm: document.getElementById('save-script-form'),
        runCommandBtn: document.getElementById('run-command-btn'), clearResultsBtn: document.getElementById('clear-results-btn'),
        hostList: document.getElementById('host-list'), savedScriptsList: document.getElementById('saved-scripts-list'),
        commandInput: document.getElementById('command-input'), resultsOutput: document.getElementById('results-output'), toast: document.getElementById('toast-notification'),
        scriptTypeInput: document.getElementById('script-type-input'), settingsBtn: document.getElementById('settings-btn'), settingsModal: document.getElementById('settings-modal'),
        settingsForm: document.getElementById('settings-form'), geminiApiKeyInput: document.getElementById('gemini-api-key-input'),
        aiAnalyzeBtn: document.getElementById('ai-analyze-btn'), aiAnalysisModal: document.getElementById('ai-analysis-modal'), aiAnalysisOutput: document.getElementById('ai-analysis-output'),
        deleteSelectedScriptsBtn: document.getElementById('delete-selected-scripts-btn'),
    };

    let geminiApiKey = '';

    const scriptSnippets = {
        'bash-script': `#!/bin/bash

# This script will be executed on the remote host.
echo "Hello from a Bash script on $(hostname)!"`,
        'python-script': `#!/usr/bin/env python3

import os

print("Hello from a Python script!")
print(f"Current user: {os.getenv('USER')}")`,
        'ansible-playbook': `---
- name: Example Ansible Playbook
  hosts: localhost
  connection: local

  tasks:
    - name: Ping the host
      ansible.builtin.ping:`,
    };

    const showToast = (message, type = 'success') => {
        if (!DOMElements.toast) return;
        DOMElements.toast.textContent = message;
        DOMElements.toast.className = `show ${type}`;
        setTimeout(() => { DOMElements.toast.className = DOMElements.toast.className.replace('show', ''); }, 3000);
    };

    const apiCall = async (url, options = {}) => {
        try {
            const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: response.statusText }));
                throw new Error(errorData.message || `HTTP error! Status: ${response.status}`);
            }
            return response.headers.get("content-type")?.includes("application/json") ? response.json() : null;
        } catch (error) {
            console.error('API Call Error:', error);
            showToast(error.message, 'error');
            throw error;
        }
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
            safeAddEventListener(modal, 'click', (e) => { if (e.target === modal) modal.style.display = 'none'; });
        });
    };

    const loadApiKey = async () => {
        try {
            const data = await apiCall('/api/settings');
            geminiApiKey = data.apiKey;
            if (DOMElements.geminiApiKeyInput) DOMElements.geminiApiKeyInput.value = geminiApiKey;
        } catch (e) { console.error("Could not load API key:", e); }
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
                    DOMElements.editHostForm.querySelector('#edit-host-id').value = data.host.id;
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
    
    const handleEditHostSubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(DOMElements.editHostForm);
        const hostId = formData.get('host_id');
        const payload = {
            friendly_name: formData.get('friendly_name'),
            hostname: formData.get('hostname'),
            username: formData.get('username')
        };
        try {
            const result = await apiCall(`/api/hosts/${hostId}`, { method: 'PUT', body: JSON.stringify(payload) });
            showToast(result.message);
            const hostItem = DOMElements.hostList.querySelector(`.host-item[data-host-id='${hostId}']`);
            if (hostItem) {
                hostItem.querySelector('.host-name').textContent = result.host.friendly_name;
                hostItem.querySelector('small').textContent = `${result.host.username}@${result.host.hostname}`;
            }
            DOMElements.editHostModal.style.display = 'none';
        } catch (error) { /* Handled */ }
    };
    
    const addHostToList = (host) => {
        const item = document.createElement('div');
        item.className = 'host-item';
        item.dataset.hostId = host.id;
        item.innerHTML = `<input type="checkbox" class="host-select-checkbox" data-host-id="${host.id}"><div class="host-info"><strong class="host-name">${host.friendly_name}</strong><small>${host.username}@${host.hostname}</small></div><div class="host-actions"><button class="test-conn-btn icon-btn" title="Test Connection"><i class="fas fa-plug"></i></button><button class="edit-host-btn icon-btn" title="Edit Host"><i class="fas fa-pencil-alt"></i></button><button class="delete-host-btn icon-btn" title="Delete Host"><i class="fas fa-trash-alt"></i></button></div>`;
        DOMElements.hostList.appendChild(item);
    };

    const handleSaveScriptSubmit = async (e) => {
        e.preventDefault();
        const name = DOMElements.saveScriptForm.querySelector('#script-name-input').value;
        const type = DOMElements.scriptTypeInput.value;
        const content = DOMElements.commandInput.value;
        try {
            const result = await apiCall('/api/scripts', { method: 'POST', body: JSON.stringify({ name, type, content }) });
            addScriptToList(result.script);
            showToast(result.message);
            DOMElements.saveScriptModal.style.display = 'none';
        } catch (error) { /* Handled */ }
    };

    const addScriptToList = (script) => {
        const item = document.createElement('div');
        item.className = 'saved-script-item';
        item.dataset.scriptId = script.id;
        item.dataset.scriptType = script.script_type.toLowerCase();
        item.innerHTML = `<input type="checkbox" class="script-select-checkbox" data-script-id="${script.id}"><div class="script-info" title="Load: ${script.name}"><strong>${script.name}</strong><small>Type: ${script.script_type}</small></div><button class="delete-script-btn icon-btn" title="Delete Script"><i class="fas fa-times"></i></button>`;
        DOMElements.savedScriptsList.appendChild(item);
    };

    const handleRunCommand = async () => {
        const selectedHostIds = [...document.querySelectorAll('.host-select-checkbox:checked')].map(cb => cb.dataset.hostId);
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
            if (DOMElements.aiAnalyzeBtn && data.results.length > 0) {
                DOMElements.aiAnalyzeBtn.style.display = 'inline-flex';
            }
        } catch (error) {
            DOMElements.resultsOutput.innerHTML = `<div class="placeholder">An error occurred.</div>`;
        } finally {
            DOMElements.runCommandBtn.disabled = false;
        }
    };

    const displayResults = (results) => {
        DOMElements.resultsOutput.innerHTML = '';
        if (results.length === 0) {
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

    const escapeHtml = (unsafe) => unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");

    const updateDeleteSelectedBtnVisibility = () => {
        const anyChecked = DOMElements.savedScriptsList.querySelector('.script-select-checkbox:checked');
        if(DOMElements.deleteSelectedScriptsBtn) {
            DOMElements.deleteSelectedScriptsBtn.style.display = anyChecked ? 'inline-block' : 'none';
        }
    };

    const handleDeleteSelectedScripts = async () => {
        const selectedIds = [...DOMElements.savedScriptsList.querySelectorAll('.script-select-checkbox:checked')].map(cb => cb.dataset.scriptId);
        if (selectedIds.length === 0 || !confirm(`Are you sure you want to delete ${selectedIds.length} script(s)?`)) return;
        try {
            const result = await apiCall('/api/scripts/delete', { method: 'POST', body: JSON.stringify({ ids: selectedIds }) });
            showToast(result.message);
            selectedIds.forEach(id => document.querySelector(`.saved-script-item[data-script-id='${id}']`)?.remove());
            updateDeleteSelectedBtnVisibility();
        } catch (error) { /* Handled */ }
    };

    const handleSavedScriptsListClick = async (e) => {
        const scriptInfo = e.target.closest('.script-info');
        const deleteBtn = e.target.closest('.delete-script-btn');
        if (deleteBtn) {
            const scriptItem = deleteBtn.closest('.saved-script-item');
            const scriptId = scriptItem.dataset.scriptId;
            if (!confirm(`Are you sure you want to delete "${scriptItem.querySelector('strong').textContent}"?`)) return;
            try {
                await apiCall(`/api/scripts/${scriptId}`, { method: 'DELETE' });
                showToast('Script deleted.');
                scriptItem.remove();
                updateDeleteSelectedBtnVisibility();
            } catch (error) { /* Handled */ }
        } else if (scriptInfo) {
            const scriptId = scriptInfo.closest('.saved-script-item').dataset.scriptId;
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
    
    const handleScriptTypeChange = (e) => {
        const selectedType = e.target.value;
        const snippet = scriptSnippets[selectedType];
        // If a snippet exists for the selected type, update the command input.
        // Otherwise, clear it (for 'bash-command').
        if (snippet) {
            DOMElements.commandInput.value = snippet;
        } else {
            DOMElements.commandInput.value = '';
        }
    };

    // Initialize
    setupModals();
    loadApiKey();
    safeAddEventListener(DOMElements.settingsBtn, 'click', () => { DOMElements.settingsModal.style.display = 'flex'; loadApiKey(); });
    safeAddEventListener(DOMElements.settingsForm, 'submit', (e) => { e.preventDefault(); apiCall('/api/settings', { method: 'POST', body: JSON.stringify({ apiKey: DOMElements.geminiApiKeyInput.value }) }).then(() => { showToast('Settings saved!'); DOMElements.settingsModal.style.display = 'none'; }); });
    safeAddEventListener(DOMElements.addHostBtn, 'click', () => { DOMElements.addHostModal.style.display = 'flex'; DOMElements.addHostForm.reset(); });
    safeAddEventListener(DOMElements.addHostForm, 'submit', (e) => { e.preventDefault(); const fd = new FormData(DOMElements.addHostForm); apiCall('/api/hosts', { method: 'POST', body: JSON.stringify(Object.fromEntries(fd)) }).then(r => { addHostToList(r.host); showToast(r.message); DOMElements.addHostModal.style.display = 'none'; }); });
    safeAddEventListener(DOMElements.editHostForm, 'submit', handleEditHostSubmit);
    safeAddEventListener(DOMElements.hostList, 'click', handleHostListClick);
    safeAddEventListener(DOMElements.saveScriptBtn, 'click', () => DOMElements.saveScriptModal.style.display = 'flex');
    safeAddEventListener(DOMElements.saveScriptForm, 'submit', handleSaveScriptSubmit);
    safeAddEventListener(DOMElements.runCommandBtn, 'click', handleRunCommand);
    safeAddEventListener(DOMElements.aiAnalyzeBtn, 'click', handleAiAnalysis);
    safeAddEventListener(DOMElements.clearResultsBtn, 'click', () => { DOMElements.resultsOutput.innerHTML = '<div class="placeholder">Output will appear here...</div>'; DOMElements.aiAnalyzeBtn.style.display = 'none'; });
    safeAddEventListener(DOMElements.savedScriptsList, 'change', (e) => { if (e.target.classList.contains('script-select-checkbox')) { updateDeleteSelectedBtnVisibility(); } });
    safeAddEventListener(DOMElements.deleteSelectedScriptsBtn, 'click', handleDeleteSelectedScripts);
    safeAddEventListener(DOMElements.savedScriptsList, 'click', handleSavedScriptsListClick);
    safeAddEventListener(DOMElements.scriptTypeInput, 'change', handleScriptTypeChange);
});
