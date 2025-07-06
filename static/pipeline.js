document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('pipeline-canvas');
    const saveBtn = document.getElementById('save-pipeline-btn');
    const runBtn = document.getElementById('run-pipeline-btn');
    const dryRunBtn = document.getElementById('dry-run-pipeline-btn');
    const pipelineNameInput = document.getElementById('pipeline-name');
    const yamlOutput = document.getElementById('yaml-output');
    const runOutputModal = document.getElementById('run-output-modal');
    const runOutputLog = document.getElementById('run-output-log');
    const localScriptList = document.getElementById('local-script-list-draggable');
    const githubScriptList = document.getElementById('github-script-list-draggable');

    let nodes = [];
    let edges = [];
    let lines = [];
    let nextNodeId = 1;
    let selectedOutput = null;
    let scriptContentCache = {}; // Store content for both local and GH scripts

    const socket = io();

    // --- API Calls ---
    const apiCall = async (url, options = {}) => {
        try {
            const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: `HTTP ${response.status}` }));
                throw new Error(errorData.message);
            }
            // Handle cases where the response might not be JSON
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                return response.json();
            }
            return null;
        } catch (error) {
            alert(`API Error: ${error.message}`);
            throw error;
        }
    };

    // --- Core Pipeline Logic ---
    const createNode = (options) => {
        const { id, name, type, x, y, scriptId, hostId, scriptPath } = options;
        const nodeEl = document.createElement('div');
        nodeEl.className = `pipeline-node ${type}-node`;
        nodeEl.id = `node-${id}`;
        nodeEl.style.left = `${x}px`;
        nodeEl.style.top = `${y}px`;
        nodeEl.dataset.nodeId = id;

        let headerIcon = 'fa-scroll';
        if (type === 'host') headerIcon = 'fa-server';
        if (type === 'if') headerIcon = 'fa-code-branch';
        if (type === 'ai-analysis') headerIcon = 'fa-brain';
        if (type === 'discord') headerIcon = 'fab fa-discord';
        if (type === 'email') headerIcon = 'fa-envelope';

        nodeEl.innerHTML = `
            <div class="node-header">
                <span><i class="fas ${headerIcon}"></i> ${name}</span>
                <button class="delete-node-btn icon-btn">&times;</button>
            </div>
            <div class="node-connector input" data-node-id="${id}"></div>
            <div class="node-connector output success" data-node-id="${id}" data-output-type="success"></div>
            ${type === 'if' || type === 'script' ? `<div class="node-connector output failure" data-node-id="${id}" data-output-type="failure"></div>` : ''}
        `;
        
        canvas.appendChild(nodeEl);
        makeDraggable(nodeEl);
        
        nodes.push({ id, name, type, x, y, scriptId, hostId, scriptPath });
        generateYaml();
        return nodeEl;
    };
    
    const deleteNode = (nodeId) => {
        nodes = nodes.filter(n => n.id !== nodeId);
        edges = edges.filter(e => e.from !== nodeId && e.to !== nodeId);
        const nodeEl = document.getElementById(`node-${nodeId}`);
        if (nodeEl) nodeEl.remove();
        drawLines();
        generateYaml();
    };

    const connectNodes = (startNode, endNode) => {
        const startId = parseInt(startNode.dataset.nodeId, 10);
        const endId = parseInt(endNode.dataset.nodeId, 10);
        const outputType = selectedOutput.dataset.outputType;

        if (startId === endId) return;

        const edge = { from: startId, to: endId, type: outputType };
        edges.push(edge);
        drawLines();
        generateYaml();
    };

    const drawLines = () => {
        lines.forEach(line => line.remove());
        lines = [];
        edges.forEach(edge => {
            const startEl = document.querySelector(`.node-connector.output[data-node-id='${edge.from}'][data-output-type='${edge.type}']`);
            const endEl = document.querySelector(`.node-connector.input[data-node-id='${edge.to}']`);
            if (startEl && endEl) {
                const color = edge.type === 'failure' ? '#F44336' : '#4CAF50';
                const line = new LeaderLine(startEl, endEl, { color, size: 3, path: 'fluid', endPlug: 'arrow1' });
                lines.push(line);
            }
        });
    };
    
    const generateYaml = () => {
        const pipelineName = pipelineNameInput.value || 'unnamed-pipeline';
        const yamlObject = {
            name: pipelineName,
            on: 'workflow_dispatch',
            jobs: {}
        };

        const hostNodes = nodes.filter(n => n.type === 'host');
        
        hostNodes.forEach(hostNode => {
            const jobKey = `run-on-${hostNode.name.replace(/\s+/g, '-').toLowerCase()}`;
            const job = {
                'runs-on': hostNode.name,
                steps: []
            };

            const findSteps = (startNodeId) => {
                const connectedEdges = edges.filter(e => e.from === startNodeId);
                connectedEdges.forEach(edge => {
                    const nextNode = nodes.find(n => n.id === edge.to);
                    if (nextNode) {
                        let step = {};
                        if (nextNode.type === 'script') {
                            const scriptContent = scriptContentCache[nextNode.scriptId] || `# Script content for '${nextNode.name}' not loaded.`;
                            step = { name: `Run ${nextNode.name}`, run: scriptContent };
                        } else if (nextNode.type === 'ai-analysis') {
                            step = { name: 'Analyze Output', uses: 'actions/ai-analyze@v1' };
                        } else if (nextNode.type === 'discord') {
                            step = { name: 'Send Discord Notification', uses: 'actions/discord-notify@v1' };
                        } else if (nextNode.type === 'email') {
                            step = { name: 'Send Email Notification', uses: 'actions/email-notify@v1' };
                        }
                        if (Object.keys(step).length > 0) {
                            job.steps.push(step);
                        }
                        findSteps(nextNode.id);
                    }
                });
            };

            findSteps(hostNode.id);
            if (job.steps.length > 0) {
                yamlObject.jobs[jobKey] = job;
            }
        });

        yamlOutput.textContent = jsyaml.dump(yamlObject, { indent: 2 });
    };

    // --- UI Interactions ---
    const makeDraggable = (element) => {
        element.addEventListener('mousedown', (e) => {
            if (e.target.classList.contains('node-connector') || e.target.closest('.delete-node-btn')) return;
            const offsetX = e.clientX - element.offsetLeft;
            const offsetY = e.clientY - element.offsetTop;

            const move = (e) => {
                element.style.left = `${e.clientX - offsetX}px`;
                element.style.top = `${e.clientY - offsetY}px`;
                lines.forEach(line => line.position());
            };

            const stop = () => {
                document.removeEventListener('mousemove', move);
                document.removeEventListener('mouseup', stop);
                const node = nodes.find(n => n.id == element.dataset.nodeId);
                if (node) {
                    node.x = element.offsetLeft;
                    node.y = element.offsetTop;
                }
                generateYaml();
            };

            document.addEventListener('mousemove', move);
            document.addEventListener('mouseup', stop);
        });
    };

    canvas.addEventListener('dragover', (e) => e.preventDefault());
    canvas.addEventListener('drop', (e) => {
        e.preventDefault();
        if (canvas.querySelector('.placeholder')) {
            canvas.querySelector('.placeholder').remove();
        }
        const nodeType = e.dataTransfer.getData('node-type');
        const name = e.dataTransfer.getData('name');
        const id = e.dataTransfer.getData('id');
        const scriptPath = e.dataTransfer.getData('script-path');
        
        createNode({
            id: nextNodeId++,
            name: name,
            type: nodeType,
            x: e.clientX - canvas.getBoundingClientRect().left,
            y: e.clientY - canvas.getBoundingClientRect().top,
            scriptId: nodeType === 'script' ? id : null,
            hostId: nodeType === 'host' ? id : null,
            scriptPath: scriptPath || null
        });
    });

    document.addEventListener('dragstart', (e) => {
        if (e.target.classList.contains('draggable-item')) {
            e.dataTransfer.setData('node-type', e.target.dataset.nodeType);
            e.dataTransfer.setData('name', e.target.dataset.name);
            e.dataTransfer.setData('id', e.target.dataset.id);
            if (e.target.dataset.scriptPath) {
                e.dataTransfer.setData('script-path', e.target.dataset.scriptPath);
            }
        }
    });

    canvas.addEventListener('click', (e) => {
        const target = e.target;
        if (target.classList.contains('node-connector')) {
            if (target.classList.contains('output')) {
                document.querySelectorAll('.node-connector.selected').forEach(el => el.classList.remove('selected'));
                target.classList.add('selected');
                selectedOutput = target;
            } else if (target.classList.contains('input') && selectedOutput) {
                connectNodes(selectedOutput, target);
                selectedOutput.classList.remove('selected');
                selectedOutput = null;
            }
        } else if (target.closest('.delete-node-btn')) {
            const nodeEl = target.closest('.pipeline-node');
            const nodeId = parseInt(nodeEl.dataset.nodeId, 10);
            deleteNode(nodeId);
        }
    });
    
    // --- Save and Load Pipeline ---
    saveBtn.addEventListener('click', async () => {
        const name = pipelineNameInput.value;
        if (!name) return alert("Please enter a name for the pipeline.");
        
        const method = PIPELINE_ID ? 'PUT' : 'POST';
        const url = PIPELINE_ID ? `/api/pipelines/${PIPELINE_ID}` : '/api/pipelines';
        
        try {
            const result = await apiCall(url, {
                method: method,
                body: JSON.stringify({ name, nodes, edges })
            });
            alert(result.message);
            if (!PIPELINE_ID && result.id) {
                window.history.replaceState({}, '', `/pipeline-editor/${result.id}`);
            }
        } catch(e) { console.error("Failed to save pipeline:", e); }
    });

    const loadPipeline = async (id) => {
        if (!id) return;
        try {
            const data = await apiCall(`/api/pipelines/${id}`);
            pipelineNameInput.value = data.name;
            nodes = [];
            edges = [];
            if (canvas.querySelector('.placeholder')) {
                canvas.querySelector('.placeholder').remove();
            }
            data.nodes.forEach(nodeData => {
                createNode(nodeData);
                if (nodeData.id >= nextNodeId) {
                    nextNodeId = nodeData.id + 1;
                }
            });
            edges = data.edges;
            drawLines();
            generateYaml();
        } catch (e) {
            console.error("Failed to load pipeline:", e);
            alert("Could not load pipeline.");
            window.location.href = "/pipeline-editor";
        }
    };

    const handleRun = async (isDryRun) => {
        if (!PIPELINE_ID) return alert("Please save the pipeline before running.");

        runOutputLog.innerHTML = '';
        runOutputModal.style.display = 'flex';

        try {
            await apiCall(`/api/pipelines/${PIPELINE_ID}/run`, {
                method: 'POST',
                body: JSON.stringify({ dry_run: isDryRun })
            });
        } catch (e) {
            console.error("Failed to start pipeline run:", e);
        }
    };

    socket.on('pipeline_log', (data) => {
        const logLine = document.createElement('div');
        logLine.className = `log-line ${data.type}`;
        
        let iconClass = 'fa-info-circle';
        if (data.type === 'success') iconClass = 'fa-check-circle';
        if (data.type === 'error') iconClass = 'fa-times-circle';
        
        if (data.type === 'output') {
            logLine.innerHTML = `<pre>${escapeHtml(data.message)}</pre>`;
        } else {
            logLine.innerHTML = `<div class="log-header"><span class="icon"><i class="fas ${iconClass}"></i></span><span>${escapeHtml(data.message)}</span></div>`;
            if (data.message.startsWith('Executing step:')) {
                const progressContainer = document.createElement('div');
                progressContainer.className = 'progress-bar-container';
                const progressBar = document.createElement('div');
                progressBar.className = 'progress-bar';
                progressContainer.appendChild(progressBar);
                logLine.appendChild(progressContainer);
                setTimeout(() => { progressBar.style.width = '90%'; }, 100);
            }
        }
        
        if (data.type === 'success' || data.type === 'error') {
            const allProgress = runOutputLog.querySelectorAll('.progress-bar');
            const lastProgressBar = allProgress[allProgress.length - 1];
            if (lastProgressBar && lastProgressBar.style.width !== '100%') {
                lastProgressBar.style.width = '100%';
                lastProgressBar.classList.add(data.type);
            }
        }
        
        runOutputLog.appendChild(logLine);
        runOutputLog.scrollTop = runOutputLog.scrollHeight;
    });

    const escapeHtml = (unsafe) => unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");

    // --- Initial Load ---
    const initializeEditor = async () => {
        try {
            // Fetch all local scripts and cache their content
            const localScripts = await apiCall('/api/scripts');
            localScripts.forEach(script => {
                scriptContentCache[script.id] = script.content;
            });

            // Load GitHub scripts (content will be fetched on demand)
            const githubScripts = await apiCall('/api/github/scripts');
            githubScriptList.innerHTML = '';
            if (githubScripts && githubScripts.length > 0) {
                githubScripts.forEach(script => {
                    const div = document.createElement('div');
                    div.className = 'draggable-item script-node-item';
                    div.draggable = true;
                    div.dataset.nodeType = 'script';
                    div.dataset.id = `gh-${script.sha}`;
                    div.dataset.name = script.name;
                    div.dataset.scriptPath = script.path;
                    div.innerHTML = `<i class="fab fa-github"></i><strong>${script.name}</strong>`;
                    githubScriptList.appendChild(div);
                });
            } else {
                githubScriptList.innerHTML = '<div class="placeholder">No GitHub scripts.</div>';
            }

            if (PIPELINE_ID) {
                loadPipeline(PIPELINE_ID);
            }
        } catch (e) {
            console.error("Failed to initialize editor with script data:", e);
        }
    };

    initializeEditor();
    pipelineNameInput.addEventListener('input', generateYaml);
    runBtn.addEventListener('click', () => handleRun(false));
    dryRunBtn.addEventListener('click', () => handleRun(true));
    
    const closeBtn = runOutputModal.querySelector('.close-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            runOutputModal.style.display = 'none';
        });
    }
});
