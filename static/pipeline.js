document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('pipeline-canvas');
    const saveBtn = document.getElementById('save-pipeline-btn');
    const runBtn = document.getElementById('run-pipeline-btn');
    const dryRunBtn = document.getElementById('dry-run-pipeline-btn');
    const pipelineNameInput = document.getElementById('pipeline-name');
    const yamlOutput = document.getElementById('yaml-output');
    const runOutputModal = document.getElementById('run-output-modal');
    const runOutputLog = document.getElementById('run-output-log');

    let nodes = [];
    let edges = [];
    let lines = [];
    let nextNodeId = 1;
    let selectedOutput = null;
    let scriptData = {}; // Store script content locally

    const socket = io();

    // --- API Calls ---
    const apiCall = async (url, options = {}) => {
        try {
            const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: `HTTP ${response.status}` }));
                throw new Error(errorData.message);
            }
            return response.json();
        } catch (error) {
            alert(`API Error: ${error.message}`);
            throw error;
        }
    };

    // --- Core Pipeline Logic ---
    const createNode = (options) => {
        const { id, name, type, x, y, scriptId, hostId } = options;
        const nodeEl = document.createElement('div');
        nodeEl.className = `pipeline-node ${type}-node`;
        nodeEl.id = `node-${id}`;
        nodeEl.style.left = `${x}px`;
        nodeEl.style.top = `${y}px`;
        nodeEl.dataset.nodeId = id;

        let headerIcon = 'fa-scroll';
        if (type === 'host') headerIcon = 'fa-server';
        if (type === 'if') headerIcon = 'fa-code-branch';

        nodeEl.innerHTML = `
            <div class="node-header"><i class="fas ${headerIcon}"></i> ${name}</div>
            <div class="node-connector input" data-node-id="${id}"></div>
            <div class="node-connector output success" data-node-id="${id}" data-output-type="success"></div>
            ${type === 'if' ? `<div class="node-connector output failure" data-node-id="${id}" data-output-type="failure"></div>` : ''}
        `;
        
        canvas.appendChild(nodeEl);
        makeDraggable(nodeEl);
        
        nodes.push({ id, name, type, x, y, scriptId, hostId });
        generateYaml();
        return nodeEl;
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
                    if (nextNode && nextNode.type === 'script') {
                        const scriptContent = scriptData[nextNode.scriptId] || `# Script content for '${nextNode.name}' not found.`;
                        const step = {
                            name: `Run ${nextNode.name}`,
                            run: scriptContent
                        };
                        job.steps.push(step);
                        findSteps(nextNode.id); // Continue traversal
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
            if (e.target.classList.contains('node-connector')) return;
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
        
        createNode({
            id: nextNodeId++,
            name: name,
            type: nodeType,
            x: e.clientX - canvas.getBoundingClientRect().left,
            y: e.clientY - canvas.getBoundingClientRect().top,
            scriptId: nodeType === 'script' ? id : null,
            hostId: nodeType === 'host' ? id : null
        });
    });

    document.addEventListener('dragstart', (e) => {
        if (e.target.classList.contains('draggable-item')) {
            e.dataTransfer.setData('node-type', e.target.dataset.nodeType);
            e.dataTransfer.setData('name', e.target.dataset.name);
            e.dataTransfer.setData('id', e.target.dataset.id);
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
            logLine.innerHTML = `<span class="icon"><i class="fas ${iconClass}"></i></span><span>${escapeHtml(data.message)}</span>`;
            if (data.message.startsWith('Executing step:')) {
                const progressContainer = document.createElement('div');
                progressContainer.className = 'progress-bar-container';
                const progressBar = document.createElement('div');
                progressBar.className = 'progress-bar';
                progressContainer.appendChild(progressBar);
                logLine.appendChild(progressContainer);
                // Animate progress
                setTimeout(() => { progressBar.style.width = '90%'; }, 100);
            }
        }
        
        // Finalize progress bar on success/error
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
            // Fetch all scripts once to get their content for YAML generation
            const scripts = await apiCall('/api/scripts');
            scripts.forEach(script => {
                scriptData[script.id] = script.content;
            });
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
    
    // Fix for close button
    const closeBtn = runOutputModal.querySelector('.close-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            runOutputModal.style.display = 'none';
        });
    }
});
