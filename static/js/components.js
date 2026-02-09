/**
 * 通用组件模块
 * 封装可复用的UI组件
 */

const Components = {
    /**
     * 初始化侧边栏导航
     */
    initSidebar: () => {
        const menuToggle = document.querySelector('.menu-toggle');
        const sidebarOverlay = document.querySelector('.sidebar-overlay');
        const currentPage = window.location.pathname.split('/').pop() || 'index.html';
        
        // 打开菜单
        if (menuToggle) {
            menuToggle.addEventListener('click', () => {
                document.body.classList.toggle('menu-open');
            });
        }
        
        // 点击遮罩关闭
        if (sidebarOverlay) {
            sidebarOverlay.addEventListener('click', () => {
                document.body.classList.remove('menu-open');
            });
        }
        
        // 高亮当前页面
        document.querySelectorAll('.nav-item').forEach(item => {
            const href = item.getAttribute('href');
            if (href && href.includes(currentPage)) {
                item.classList.add('active');
            }
        });
        
        // ESC键关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                document.body.classList.remove('menu-open');
            }
        });
    },
    
    /**
     * 渲染用户信息到侧边栏
     */
    renderUserInfo: async () => {
        const userNameEl = document.querySelector('.user-name');
        const userAvatarEl = document.querySelector('.user-avatar');
        
        if (!userNameEl) return;
        
        // 先尝试从本地存储获取
        let user = Auth.getUser();
        
        // 如果没有或已过期，从服务器获取
        if (!user) {
            user = await Auth.updateUserInfo();
        }
        
        if (user) {
            userNameEl.textContent = user.nickname || user.name || '用户';
            if (userAvatarEl) {
                userAvatarEl.textContent = (user.nickname || '用').charAt(0);
            }
        }
    },
    
    /**
     * 创建确认对话框
     */
    confirm: (options = {}) => {
        return new Promise((resolve) => {
            const {
                title = '确认',
                message = '确定执行此操作？',
                confirmText = '确定',
                cancelText = '取消',
                type = 'warning'
            } = options;
            
            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-header">
                        <h3>${title}</h3>
                        <button class="modal-close">&times;</button>
                    </div>
                    <div class="modal-body">
                        <p>${message}</p>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary cancel-btn">${cancelText}</button>
                        <button class="btn btn-${type} confirm-btn">${confirmText}</button>
                    </div>
                </div>
            `;
            
            // 添加样式
            modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
            `;
            
            const dialog = modal.querySelector('.modal-dialog');
            dialog.style.cssText = `
                background: white;
                border-radius: 12px;
                width: 90%;
                max-width: 400px;
                animation: slideInUp 0.3s ease;
            `;
            
            document.body.appendChild(modal);
            
            // 事件处理
            const close = (result) => {
                modal.remove();
                resolve(result);
            };
            
            modal.querySelector('.cancel-btn').addEventListener('click', () => close(false));
            modal.querySelector('.confirm-btn').addEventListener('click', () => close(true));
            modal.querySelector('.modal-close').addEventListener('click', () => close(false));
            modal.addEventListener('click', (e) => {
                if (e.target === modal) close(false);
            });
        });
    },
    
    /**
     * 创建模态框
     */
    modal: (options = {}) => {
        const {
            title = '',
            content = '',
            width = '500px',
            onClose = null
        } = options;
        
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-dialog" style="width: 90%; max-width: ${width};">
                <div class="modal-header" style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 16px 20px;
                    border-bottom: 1px solid #e0e0e0;
                ">
                    <h3 style="margin: 0; font-size: 1.125rem;">${title}</h3>
                    <button class="modal-close" style="
                        background: none;
                        border: none;
                        font-size: 1.5rem;
                        cursor: pointer;
                        color: #7f8c8d;
                    ">&times;</button>
                </div>
                <div class="modal-body" style="padding: 20px;">
                    ${content}
                </div>
            </div>
        `;
        
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            animation: fadeIn 0.3s ease;
        `;
        
        document.body.appendChild(modal);
        
        const close = () => {
            modal.style.animation = 'fadeIn 0.3s ease reverse';
            setTimeout(() => {
                modal.remove();
                if (onClose) onClose();
            }, 300);
        };
        
        modal.querySelector('.modal-close').addEventListener('click', close);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) close();
        });
        
        return {
            close,
            element: modal
        };
    },
    
    /**
     * 初始化底部快捷栏
     */
    initBottomBar: () => {
        const currentPage = window.location.pathname.split('/').pop() || 'index.html';
        
        document.querySelectorAll('.quick-action').forEach(action => {
            const href = action.getAttribute('href');
            if (href && href.includes(currentPage)) {
                action.classList.add('active');
            }
        });
    },
    
    /**
     * 自动调整文本域高度
     */
    autoResizeTextarea: (textarea) => {
        if (typeof textarea === 'string') {
            textarea = document.querySelector(textarea);
        }
        
        if (!textarea) return;
        
        const resize = () => {
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        };
        
        textarea.addEventListener('input', resize);
        // 初始化一次
        resize();
    },
    
    /**
     * 初始化图表容器
     */
    initChart: (canvasId, type, data, options = {}) => {
        const ctx = document.getElementById(canvasId)?.getContext('2d');
        if (!ctx) return null;
        
        const defaultOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                }
            }
        };
        
        return new Chart(ctx, {
            type,
            data,
            options: { ...defaultOptions, ...options }
        });
    },
    
    /**
     * 格式化并显示错误
     */
    showError: (error, container) => {
        const message = error.message || '操作失败';
        
        if (container) {
            if (typeof container === 'string') {
                container = document.querySelector(container);
            }
            container.innerHTML = `
                <div class="alert alert-error">
                    <strong>错误</strong>: ${message}
                </div>
            `;
        } else {
            Utils.toast(message, 'error');
        }
    }
};

// 导出Components对象
window.Components = Components;

// 页面加载完成后自动初始化
document.addEventListener('DOMContentLoaded', () => {
    Components.initSidebar();
    Components.initBottomBar();
    Components.renderUserInfo();
});
