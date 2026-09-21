document.addEventListener('DOMContentLoaded', () => {
  // 1. Notification Dropdown Fetcher
  const notifBtn = document.getElementById('notifDropdownBtn');
  const notifBadge = document.getElementById('notifBadge');
  const notifList = document.getElementById('notifDropdownList');

  function updateNotifications() {
    fetch('/api/notifications')
      .then(res => res.json())
      .then(data => {
        if (data.unread_count > 0) {
          if (notifBadge) {
            notifBadge.textContent = data.unread_count;
            notifBadge.classList.remove('d-none');
          }
        } else {
          if (notifBadge) notifBadge.classList.add('d-none');
        }

        if (notifList && data.notifications) {
          if (data.notifications.length === 0) {
            notifList.innerHTML = '<li class="p-3 text-center text-muted small">No notifications yet.</li>';
          } else {
            notifList.innerHTML = data.notifications.map(n => `
              <li>
                <a class="dropdown-item py-2 border-bottom ${n.read_flag ? 'text-muted' : 'fw-bold bg-light'}" href="${n.link || '#'}">
                  <div class="small">${n.message}</div>
                  <div class="text-muted" style="font-size: 0.75rem;">${n.created_at}</div>
                </a>
              </li>
            `).join('') + `
              <li><button class="dropdown-item text-center small text-primary py-2 fw-semibold" id="markAllReadBtn">Mark all as read</button></li>
            `;

            const markBtn = document.getElementById('markAllReadBtn');
            if (markBtn) {
              markBtn.addEventListener('click', (e) => {
                e.preventDefault();
                fetch('/api/notifications/mark-read', {
                  method: 'POST',
                  headers: { 'X-Requested-With': 'XMLHttpRequest' }
                }).then(() => updateNotifications());
              });
            }
          }
        }
      })
      .catch(() => {});
  }

  if (notifBtn) {
    updateNotifications();
    setInterval(updateNotifications, 10000);
  }

  // 2. Real-time Workflow Status Polling
  const liveWorkflowEl = document.getElementById('liveWorkflowTracker');
  if (liveWorkflowEl) {
    const workflowId = liveWorkflowEl.dataset.workflowId;
    if (workflowId) {
      const pollInterval = setInterval(() => {
        fetch(`/api/workflow/${workflowId}/status`)
          .then(res => res.json())
          .then(data => {
            // Update Progress Bar
            const progBar = document.getElementById('workflowProgressBar');
            if (progBar) {
              progBar.style.width = `${data.progress_pct}%`;
              progBar.textContent = `${data.progress_pct}%`;
            }

            // Update Status Badge
            const statusBadge = document.getElementById('workflowStatusBadge');
            if (statusBadge) {
              statusBadge.textContent = data.status.toUpperCase();
              statusBadge.className = `badge bg-${data.status === 'completed' ? 'success' : (data.status === 'failed' ? 'danger' : 'primary')}`;
            }

            // Update Steps UI
            if (data.steps) {
              data.steps.forEach(s => {
                const stepEl = document.getElementById(`step-${s.id}`);
                if (stepEl) {
                  const icon = stepEl.querySelector('.timeline-step-icon');
                  const statusText = stepEl.querySelector('.step-status-text');
                  const resultText = stepEl.querySelector('.step-result-text');

                  if (icon) {
                    icon.className = `timeline-step-icon bg-${s.status}`;
                    icon.innerHTML = s.status === 'done' ? '✓' : (s.status === 'failed' ? '✗' : (s.status === 'in_progress' ? '⟳' : '•'));
                  }
                  if (statusText) {
                    statusText.textContent = s.status.replace('_', ' ').toUpperCase();
                    statusText.className = `badge bg-${s.status} step-status-text`;
                  }
                  if (resultText && s.result_text) {
                    resultText.textContent = s.result_text;
                  }
                }
              });
            }

            // Stop polling if completed or failed
            if (data.status === 'completed' || data.status === 'failed' || data.status === 'partially_failed') {
              clearInterval(pollInterval);
            }
          })
          .catch(() => {});
      }, 3000);
    }
  }
});
