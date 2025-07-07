document.addEventListener('DOMContentLoaded', () => {
    const DOMElements = {
        groupList: document.getElementById('group-list'),
        userList: document.getElementById('user-list'),
        userListHeader: document.getElementById('user-list-header'),
        addGroupBtn: document.getElementById('add-group-btn'),
        addUserBtn: document.getElementById('add-user-btn'),
        addGroupModal: document.getElementById('add-group-modal'),
        addUserModal: document.getElementById('add-user-modal'),
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

    const loadUsersForGroup = async (groupId) => {
        selectedGroupId = groupId;
        DOMElements.userList.innerHTML = '<div class="placeholder"><i class="fas fa-spinner fa-spin"></i></div>';
        try {
            const users = await apiCall(`/api/groups/${groupId}/users`);
            DOMElements.userList.innerHTML = users.map(user => `
                <div class="management-item" data-user-id="${user.id}">
                    <span><i class="fas fa-user"></i> ${user.username}</span>
                    <button class="delete-user-btn icon-btn" title="Delete User">&times;</button>
                </div>
            `).join('') || '<div class="placeholder">This group has no users.</div>';
            
            const groupName = document.querySelector(`.management-item[data-group-id='${groupId}'] span`).textContent.trim();
            DOMElements.userListHeader.textContent = `Users in ${groupName}`;
            DOMElements.addUserBtn.style.display = 'inline-flex';
        } catch (e) { console.error("Failed to load users:", e); }
    };

    // Event Handlers
    DOMElements.groupList.addEventListener('click', async (e) => {
        const groupItem = e.target.closest('.management-item');
        if (!groupItem) return;

        if (e.target.closest('.delete-group-btn')) {
            const groupId = groupItem.dataset.groupId;
            if (confirm(`Are you sure you want to delete this group? This will also delete all users within it.`)) {
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
            loadUsersForGroup(groupItem.dataset.groupId);
        }
    });

    DOMElements.userList.addEventListener('click', async (e) => {
        if (e.target.closest('.delete-user-btn')) {
            const userItem = e.target.closest('.management-item');
            const userId = userItem.dataset.userId;
            if (confirm(`Are you sure you want to delete user "${userItem.querySelector('span').textContent.trim()}"?`)) {
                await apiCall(`/api/users/${userId}`, { method: 'DELETE' });
                showToast('User deleted.');
                loadUsersForGroup(selectedGroupId);
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
        loadUsersForGroup(selectedGroupId);
    });

    // Initial Load
    loadGroups();
    document.querySelectorAll('.modal .close-btn').forEach(btn => btn.addEventListener('click', (e) => e.target.closest('.modal').style.display = 'none'));
});
