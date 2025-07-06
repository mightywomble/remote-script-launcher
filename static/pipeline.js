document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('pipeline-canvas');
    const saveBtn = document.getElementById('save-pipeline-btn');
    const runBtn = document.getElementById('run-pipeline-btn');
    const dryRunBtn = document.getElementById('dry-run-pipeline-btn');
    const pipelineNameInput = document.getElementById('pipeline-name');
    const yamlOutput = document.getElementById('yaml-output');
    const runOutputModal = document.getElementById('run-output-modal');
    const runOutputLog = document.getElementById('run-output-log');
    const localScriptListContainer = document.getElementById('local-script-list-grouped');
    const githubScriptListContainer = document.getElementById('github-script-list-grouped');

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
            return response.json();
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
    
    const generateYaml = async () => {
        const pipelineName = pipelineNameInput.value || 'unnamed-pipeline';
        const yamlObject = { name: pipelineName, on: 'workflow_dispatch', jobs: {} };
        const hostNodes = nodes.filter(n => n.type === 'host');
        
        for (const hostNode of hostNodes) {
            const jobKey = `run-on-${hostNode.name.replace(/\s+/g, '-').toLowerCase()}`;
            const job = { 'runs-on': hostNode.name, steps: [] };

            const findSteps = async (startNodeId) => {
                const connectedEdges = edges.filter(e => e.from === startNodeId);
                for (const edge of connectedEdges) {
                    const nextNode = nodes.find(n => n.id === edge.to);
                    if (nextNode) {
                        let step = {};
                        if (nextNode.type === 'script') {
                            let scriptContent = scriptContentCache[nextNode.scriptId] || scriptContentCache[nextNode.scriptPath];
                            if (!scriptContent && nextNode.scriptPath) {
                                try {
                                    const data = await apiCall(`/api/github/script-content?path=${nextNode.scriptPath}`);
                                    scriptContent = data.content;
                                    scriptContentCache[nextNode.scriptPath] = scriptContent;
                                } catch (e) {
                                    scriptContent = `# Failed to load script: ${nextNode.name}`;
                                }
                            }
                            step = { name: `Run ${nextNode.name}`, run: scriptContent || 'Script content not found.' };
                        } else if (nextNode.type.startsWith('ai') || nextNode.type.startsWith('discord') || nextNode.type.startsWith('email')) {
                            step = { name: nextNode.name, uses: `actions/${nextNode.type}@v1` };
                        }
                        if (Object.keys(step).length > 0) job.steps.push(step);
                        await findSteps(nextNode.id);
                    }
                }
            };
            await findSteps(hostNode.id);
            if (job.steps.length > 0) yamlObject.jobs[jobKey] = job;
        }

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
        const logContainer = document.createElement('div');
        logContainer.className = 'log-entry';

        const header = document.createElement('div');
        header.className = `log-line ${data.type}`;
        
        let iconClass = 'fa-info-circle';
        if (data.type === 'success') iconClass = 'fa-check-circle';
        if (data.type === 'error') iconClass = 'fa-times-circle';
        
        header.innerHTML = `<span class="icon"><i class="fas ${iconClass}"></i></span><span>${escapeHtml(data.message)}</span>`;
        logContainer.appendChild(header);

        if (data.type === 'output' || data.type === 'error') {
            const outputContent = document.createElement('div');
            outputContent.className = 'log-content';
            outputContent.innerHTML = `<pre>${escapeHtml(data.message)}</pre>`;
            logContainer.appendChild(outputContent);
            header.classList.add('expandable');
            header.querySelector('.icon').classList.add('fa-chevron-right');

            header.addEventListener('click', () => {
                const isOpen = header.classList.toggle('open');
                outputContent.style.display = isOpen ? 'block' : 'none';
                header.querySelector('.icon').classList.toggle('fa-chevron-right');
                header.querySelector('.icon').classList.toggle('fa-chevron-down');
            });
        }
        
        if (data.message.startsWith('Executing step:')) {
            const progressContainer = document.createElement('div');
            progressContainer.className = 'progress-bar-container';
            const progressBar = document.createElement('div');
            progressBar.className = 'progress-bar';
            logContainer.appendChild(progressContainer);
            setTimeout(() => { progressBar.style.width = '90%'; }, 100);
        }
        
        if (data.type === 'success' || data.type === 'error') {
            const allProgress = runOutputLog.querySelectorAll('.progress-bar');
            const lastProgressBar = allProgress[allProgress.length - 1];
            if (lastProgressBar && lastProgressBar.style.width !== '100%') {
                lastProgressBar.style.width = '100%';
                lastProgressBar.classList.add(data.type);
            }
        }
        
        runOutputLog.appendChild(logContainer);
        runOutputLog.scrollTop = runOutputLog.scrollHeight;
    });

    const escapeHtml = (unsafe) => unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");

    const renderGroupedScripts = (scripts, targetElement, isGitHub) => {
        const typeMap = {
            'bash-command': { name: 'Bash Commands', icon: 'fa-terminal', items: [] },
            'bash-script': { name: 'Bash Scripts', icon: 'fa-scroll', items: [] },
            'python-script': { name: 'Python Scripts', icon: 'fab fa-python', items: [] },
            'ansible-playbook': { name: 'Ansible Playbooks', icon: 'fa-play-circle', items: [] },
            'bash_scripts': { name: 'Bash Scripts', icon: 'fa-scroll', items: [] },
            'python_scripts': { name: 'Python Scripts', icon: 'fab fa-python', items: [] },
            'ansible_playbooks': { name: 'Ansible Playbooks', icon: 'fa-play-circle', items: [] },
        };

        scripts.forEach(script => {
            const type = script.script_type || script.type;
            if (typeMap[type]) {
                typeMap[type].items.push(script);
            }
        });

        targetElement.innerHTML = '';
        for (const key in typeMap) {
            const group = typeMap[key];
            if (group.items.length > 0) {
                const section = document.createElement('div');
                section.className = 'component-sub-section';

                const header = document.createElement('div');
                header.className = 'sub-section-header';
                header.innerHTML = `<h5><i class="fas ${group.icon}"></i> ${group.name}</h5><i class="fas fa-chevron-down"></i>`;
                
                const content = document.createElement('div');
                content.className = 'sub-section-content';
                group.items.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'draggable-item script-node-item';
                    div.draggable = true;
                    div.dataset.nodeType = 'script';
                    div.dataset.id = item.id || `gh-${item.sha}`;
                    div.dataset.name = item.name;
                    div.dataset.scriptPath = item.path || '';
                    div.innerHTML = `<i class="fas fa-file-code"></i><strong>${item.name}</strong>`;
                    content.appendChild(div);
                });

                section.appendChild(header);
                section.appendChild(content);
                targetElement.appendChild(section);

                header.addEventListener('click', () => {
                    section.classList.toggle('open');
                    content.style.display = section.classList.contains('open') ? 'block' : 'none';
                });
            }
        }
    };
    
    const setupSidebarAccordion = () => {
        document.querySelectorAll('.pipeline-sidebar .component-section').forEach(section => {
            const header = section.querySelector('.component-header');
            if (header) {
                header.addEventListener('click', () => {
                    const content = section.querySelector('.component-content');
                    const isOpen = section.classList.toggle('open');
                    content.style.display = isOpen ? 'block' : 'none';
                });
            }
        });
    };

    // --- Initial Load ---
    const initializeEditor = async () => {
        try {
            const [localScripts, githubScripts] = await Promise.all([
                apiCall('/api/scripts'),
                apiCall('/api/github/scripts')
            ]);
            
            localScripts.forEach(script => { scriptContentCache[script.id] = script.content; });
            renderGroupedScripts(localScripts, localScriptListContainer);

            if (githubScripts && githubScripts.length > 0) {
                renderGroupedScripts(githubScripts, githubScriptListContainer);
            } else {
                githubScriptListContainer.innerHTML = '<div class="placeholder">No GitHub scripts.</div>';
            }

            if (PIPELINE_ID) {
                loadPipeline(PIPELINE_ID);
            }
            setupSidebarAccordion();
        } catch (e) {
            console.error("Failed to initialize editor:", e);
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
