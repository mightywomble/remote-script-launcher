document.addEventListener('DOMContentLoaded', () => {
    const DOMElements = {
        hostsCount: document.getElementById('hosts-count'),
        scriptsCount: document.getElementById('scripts-count'),
        pipelinesCount: document.getElementById('pipelines-count'),
        usersCount: document.getElementById('users-count'),
        activityLogList: document.getElementById('activity-log-list'),
    };

    const apiCall = async (url) => {
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to fetch dashboard data');
            return response.json();
        } catch (error) {
            console.error("API Call Error:", error);
            throw error;
        }
    };

    const loadDashboardData = async () => {
        try {
            const data = await apiCall('/api/dashboard-stats');

            // Populate stat cards
            DOMElements.hostsCount.textContent = data.counts.hosts;
            DOMElements.scriptsCount.textContent = data.counts.scripts;
            DOMElements.pipelinesCount.textContent = data.counts.pipelines;
            DOMElements.usersCount.textContent = data.counts.users;

            // Populate Activity Log
            DOMElements.activityLogList.innerHTML = data.logs.map(log => `
                <div class="log-item">
                    <span class="log-timestamp">${new Date(log.timestamp).toLocaleString()}</span>
                    <span class="log-user">${log.user}</span>
                    <span class="log-action">${log.action}</span>
                </div>
            `).join('') || '<div class="placeholder">No recent activity.</div>';

        } catch (error) {
            console.error("Failed to load dashboard data:", error);
        }
    };

    loadDashboardData();
});
