/** 通知轮询系统 - 用于前端实时获取待处理通知 */
class NotificationPoller {
    constructor(options = {}) {
        this.options = {
            interval: 30000, // 30秒
            onNotification: null,
            ...options
        };
        
        this.timer = null;
        this.isRunning = false;
        this.lastCheckTime = null;
        this.processedNotifications = new Set();
        
        // 启动轮询
        this.start();
        
        // 监听页面可见性变化
        this.handleVisibilityChange = this.handleVisibilityChange.bind(this);
        document.addEventListener('visibilitychange', this.handleVisibilityChange);
    }
    
    start() {
        if (this.isRunning) return;
        
        this.isRunning = true;
        this.poll(); // 立即执行一次
        this.timer = setInterval(() => this.poll(), this.options.interval);
        
        console.log('[NotificationPoller] 轮询已启动');
    }
    
    stop() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
        this.isRunning = false;
        console.log('[NotificationPoller] 轮询已停止');
    }
    
    handleVisibilityChange() {
        if (document.hidden) {
            this.stop();
        } else {
            this.poll();
            this.start();
        }
    }
    
    async poll() {
        try {
            const token = localStorage.getItem('token');
            if (!token) return;
            
            const response = await fetch('/api/notifications/pending', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            const data = await response.json();
            
            if (data.success && data.count > 0) {
                const newNotifications = data.notifications.filter(
                    n => !this.processedNotifications.has(n.id)
                );
                
                if (newNotifications.length > 0) {
                    console.log(`[NotificationPoller] 收到 ${newNotifications.length} 条新通知`);
                    
                    newNotifications.forEach(notification => {
                        this.processedNotifications.add(notification.id);
                        this.renderNotification(notification);
                    });
                    
                    if (this.options.onNotification) {
                        this.options.onNotification(newNotifications);
                    }
                }
            }
            
            this.lastCheckTime = new Date();
        } catch (error) {
            console.error('[NotificationPoller] 轮询错误:', error);
        }
    }
    
    renderNotification(notification) {
        const chatContainer = document.querySelector('.chat-messages') || 
                             document.querySelector('.messages-container') ||
                             document.getElementById('chat-messages');
        
        if (!chatContainer) {
            console.warn('[NotificationPoller] 未找到对话容器');
            return;
        }
        
        const notificationEl = document.createElement('div');
        notificationEl.className = 'notification-message-card';
        notificationEl.id = `notification-${notification.id}`;
        notificationEl.style.cssText = `
            margin: 12px 16px;
            padding: 0;
            border-radius: 12px;
            background: linear-gradient(135deg, ${notification.color}15 0%, ${notification.color}08 100%);
            border-left: 4px solid ${notification.color};
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            animation: notificationSlideIn 0.3s ease-out;
            overflow: hidden;
        `;
        
        const priorityClass = notification.priority === 'high' ? 'notification-priority-high' : '';
        
        notificationEl.innerHTML = `
            <div class="notification-content-wrapper ${priorityClass}" style="padding: 16px;">
                <div class="notification-header" style="display: flex; align-items: center; margin-bottom: 10px;">
                    <span class="notification-icon" style="font-size: 1.5rem; margin-right: 10px;">${notification.icon}</span>
                    <span class="notification-title" style="font-weight: 600; font-size: 1rem; color: #333; flex: 1;">${notification.title}</span>
                    ${notification.priority === 'high' ? '<span class="priority-badge" style="background: #ff3b30; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem;">重要</span>' : ''}
                </div>
                <div class="notification-body" style="color: #666; font-size: 0.95rem; line-height: 1.5; margin-bottom: 12px;">
                    ${notification.content}
                </div>
                <div class="notification-actions" style="display: flex; gap: 10px; justify-content: flex-end;">
                    ${notification.action_url ? `
                        <a href="${notification.action_url}" 
                           class="notification-action-btn primary" 
                           style="background: ${notification.color}; color: white; padding: 8px 16px; border-radius: 20px; text-decoration: none; font-size: 0.9rem; font-weight: 500; transition: opacity 0.2s;"
                           onclick="window.notificationPoller.handleAction(${notification.id}, 'click', event)">
                            ${notification.action_text} →
                        </a>
                    ` : ''}
                    <button class="notification-action-btn dismiss" 
                            style="background: transparent; color: #999; border: 1px solid #ddd; padding: 8px 16px; border-radius: 20px; font-size: 0.9rem; cursor: pointer; transition: all 0.2s;"
                            onclick="window.notificationPoller.handleAction(${notification.id}, 'dismiss')">
                        忽略
                    </button>
                </div>
            </div>
        `;
        
        chatContainer.appendChild(notificationEl);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        
        if (notification.priority === 'high') {
            this.playNotificationSound();
        }
    }
    
    async handleAction(notificationId, action, event) {
        if (event && action === 'click') {
            event.preventDefault();
            const href = event.target.getAttribute('href');
            await this.acknowledge(notificationId, 'click');
            this.removeNotificationCard(notificationId);
            if (href) window.location.href = href;
        } else if (action === 'dismiss') {
            await this.acknowledge(notificationId, 'dismiss');
            this.removeNotificationCard(notificationId);
        }
    }
    
    async acknowledge(notificationId, action) {
        try {
            const token = localStorage.getItem('token');
            if (!token) return;
            
            await fetch(`/api/notifications/${notificationId}/acknowledge?action=${action}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
        } catch (error) {
            console.error('[NotificationPoller] 确认通知失败:', error);
        }
    }
    
    removeNotificationCard(notificationId) {
        const card = document.getElementById(`notification-${notificationId}`);
        if (card) {
            card.style.animation = 'notificationSlideOut 0.3s ease-out';
            setTimeout(() => card.remove(), 300);
        }
    }
    
    playNotificationSound() {
        // 可选：播放提示音
    }
}

window.NotificationPoller = NotificationPoller;
