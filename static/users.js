document.addEventListener('DOMContentLoaded', () => {
    const DOMElements = {
        groupList: document.getElementById('group-list'),
        userList: document.getElementById('user-list'),
        apiTokenList: document.getElementById('api-token-list'),
        userListHeader: document.getElementById('user-list-header'),
        addGroupBtn: document.getElementById('add-group-btn'),
        addUserBtn: document.getElementById('add-user-btn'),
        addTokenForm: document.getElementById('add-token-form'),
        addGroupModal: document.getElementById('add-group-modal'),
        addUserModal: document.getElementById('add-user-modal'),
        newTokenModal: document.getElementById('new-token-modal'),
        newTokenDisplay: document.getElementById('new-token-display'),
        copyTokenBtn: document.getElementById('copy-token-btn'),
        closeTokenModalBtn: document.getElementById('close-token-modal-btn'),
        addGroupForm: document.getElementById('add-group-form'),
        addUserForm: document.getElementById('add-user-form'),
        toast: document.getElementById('toast-notification'),
    };

    let selectedGroupId = null;

    const apiCall = async (url, options = {}) => {
        try {
            const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
            if (!response.ok) throw new Error((await response.json()).message || `HTTP ${response.status}`);
            return response.json();
        } catch (error) {
            showToast(error.message, 'error');
            throw error;
        }
    };

    const showToast = (message, type = 'success') => {
        DOMElements.toast.textContent = message;
        DOMElements.toast.className = `show ${type}`;
        setTimeout(() => { DOMElements.toast.className = ''; }, 3000);
    };
    
    const setupModals = () => {
        document.querySelectorAll('.modal').forEach(modal => {
            const closeBtn = modal.querySelector('.close-btn');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => modal.style.display = 'none');
            }
        });
    };

    const loadGroups = async () => {
        try {
            const groups = await apiCall('/api/groups');
            DOMElements.groupList.innerHTML = groups.map(group => `
                <div class="management-item" data-group-id="${group.id}">
                    <span><i class="fas fa-users"></i> ${group.name}</span>
                    <button class="delete-group-btn icon-btn" title="Delete Group">&times;</button>
                </div>
            `).join('') || '<div class="placeholder">No groups found.</div>';
        } catch (e) { console.error("Failed to load groups:", e); }
    };

    const loadUsersAndTokens = async (groupId) => {
        selectedGroupId = groupId;
        DOMElements.userList.innerHTML = '<div class="placeholder"><i class="fas fa-spinner fa-spin"></i></div>';
        DOMElements.apiTokenList.innerHTML = '<div class="placeholder"><i class="fas fa-spinner fa-spin"></i></div>';
        try {
            const [users, tokens] = await Promise.all([
                apiCall(`/api/groups/${groupId}/users`),
                apiCall(`/api/api-tokens?group_id=${groupId}`)
            ]);
            
            DOMElements.userList.innerHTML = users.map(user => `
                <div class="management-item" data-user-id="${user.id}">
                    <span><i class="fas fa-user"></i> ${user.username} (${user.role})</span>
                    <button class="delete-user-btn icon-btn" title="Delete User">&times;</button>
                </div>
            `).join('') || '<div class="placeholder">This group has no users.</div>';
            
            DOMElements.apiTokenList.innerHTML = tokens.map(token => `
                <div class="token-item" data-token-id="${token.id}">
                    <span><i class="fas fa-key"></i> ${token.description} (<b>${token.token_prefix}...</b>)</span>
                    <button class="delete-token-btn icon-btn" title="Delete Token">&times;</button>
                </div>
            `).join('') || '<div class="placeholder">No API tokens for this group.</div>';

            const groupName = document.querySelector(`.management-item[data-group-id='${groupId}'] span`).textContent.trim();
            DOMElements.userListHeader.textContent = `Users in ${groupName}`;
            DOMElements.addUserBtn.style.display = 'inline-flex';
        } catch (e) { console.error("Failed to load users/tokens:", e); }
    };

    // --- Event Handlers ---
    DOMElements.groupList.addEventListener('click', async (e) => {
        const groupItem = e.target.closest('.management-item');
        if (!groupItem) return;

        if (e.target.closest('.delete-group-btn')) {
            const groupId = groupItem.dataset.groupId;
            if (confirm(`Are you sure you want to delete this group? This will also delete all users and associated items within it.`)) {
                await apiCall(`/api/groups/${groupId}`, { method: 'DELETE' });
                showToast('Group deleted.');
                loadGroups();
                DOMElements.userList.innerHTML = '<div class="placeholder">Select a group.</div>';
                DOMElements.userListHeader.textContent = 'Select a Group';
                DOMElements.addUserBtn.style.display = 'none';
            }
        } else {
            document.querySelectorAll('.management-item.active').forEach(el => el.classList.remove('active'));
            groupItem.classList.add('active');
            loadUsersAndTokens(groupItem.dataset.groupId);
        }
    });

    DOMElements.userList.addEventListener('click', async (e) => {
        if (e.target.closest('.delete-user-btn')) {
            const userItem = e.target.closest('.management-item');
            const userId = userItem.dataset.userId;
            if (confirm(`Are you sure you want to delete user "${userItem.querySelector('span').textContent.trim()}"?`)) {
                await apiCall(`/api/users/${userId}`, { method: 'DELETE' });
                showToast('User deleted.');
                loadUsersAndTokens(selectedGroupId);
            }
        }
    });

    DOMElements.addGroupBtn.addEventListener('click', () => {
        DOMElements.addGroupForm.reset();
        DOMElements.addGroupModal.style.display = 'flex';
    });

    DOMElements.addGroupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(DOMElements.addGroupForm);
        await apiCall('/api/groups', { method: 'POST', body: JSON.stringify(Object.fromEntries(formData)) });
        showToast('Group created successfully.');
        DOMElements.addGroupModal.style.display = 'none';
        loadGroups();
    });

    DOMElements.addUserBtn.addEventListener('click', () => {
        DOMElements.addUserForm.reset();
        DOMElements.addUserForm.querySelector('input[name="group_id"]').value = selectedGroupId;
        DOMElements.addUserModal.style.display = 'flex';
    });

    DOMElements.addUserForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(DOMElements.addUserForm);
        await apiCall('/api/users', { method: 'POST', body: JSON.stringify(Object.fromEntries(formData)) });
        showToast('User added successfully.');
        DOMElements.addUserModal.style.display = 'none';
        loadUsersAndTokens(selectedGroupId);
    });
    
    DOMElements.addTokenForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!selectedGroupId) {
            showToast('Please select a group first.', 'error');
            return;
        }
        const formData = new FormData(DOMElements.addTokenForm);
        const payload = { description: formData.get('description') };
        try {
            const result = await apiCall(`/api/api-tokens?group_id=${selectedGroupId}`, { method: 'POST', body: JSON.stringify(payload) });
            DOMElements.newTokenDisplay.value = result.token;
            DOMElements.newTokenModal.style.display = 'flex';
            DOMElements.addTokenForm.reset();
            loadUsersAndTokens(selectedGroupId);
        } catch (e) {}
    });

    DOMElements.apiTokenList.addEventListener('click', async (e) => {
        if(e.target.closest('.delete-token-btn')) {
            const tokenItem = e.target.closest('.token-item');
            const tokenId = tokenItem.dataset.tokenId;
            if(confirm('Are you sure you want to delete this API token?')) {
                await apiCall(`/api/api-tokens/${tokenId}`, { method: 'DELETE' });
                showToast('API Token deleted.');
                loadUsersAndTokens(selectedGroupId);
            }
        }
    });
    
    DOMElements.copyTokenBtn.addEventListener('click', () => {
        DOMElements.newTokenDisplay.select();
        document.execCommand('copy');
        showToast('Token copied to clipboard!');
    });
    
    DOMElements.closeTokenModalBtn.addEventListener('click', () => {
        DOMElements.newTokenModal.style.display = 'none';
    });

    // Initial Load
    setupModals();
    loadGroups();
});
