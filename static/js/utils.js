/**
 * 工具函数模块
 * 通用工具函数集合
 */

const Utils = {
    /**
     * 日期格式化
     */
    formatDate: (date, format = 'YYYY-MM-DD') => {
        const d = new Date(date);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hours = String(d.getHours()).padStart(2, '0');
        const minutes = String(d.getMinutes()).padStart(2, '0');
        const seconds = String(d.getSeconds()).padStart(2, '0');
        
        return format
            .replace('YYYY', year)
            .replace('MM', month)
            .replace('DD', day)
            .replace('HH', hours)
            .replace('mm', minutes)
            .replace('ss', seconds);
    },
    
    /**
     * 获取今日日期
     */
    getToday: () => {
        return Utils.formatDate(new Date());
    },
    
    /**
     * 获取相对时间描述
     */
    timeAgo: (date) => {
        const now = new Date();
        const then = new Date(date);
        const diff = now - then;
        
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);
        
        if (minutes < 1) return '刚刚';
        if (minutes < 60) return `${minutes}分钟前`;
        if (hours < 24) return `${hours}小时前`;
        if (days < 7) return `${days}天前`;
        
        return Utils.formatDate(date);
    },
    
    /**
     * 防抖函数
     */
    debounce: (func, wait = 300) => {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    /**
     * 节流函数
     */
    throttle: (func, limit = 300) => {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func(...args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },
    
    /**
     * 显示提示消息
     */
    toast: (message, type = 'info', duration = 3000) => {
        // 移除现有的toast
        const existingToast = document.querySelector('.toast-notification');
        if (existingToast) {
            existingToast.remove();
        }
        
        // 创建新的toast
        const toast = document.createElement('div');
        toast.className = `toast-notification alert alert-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 80px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 9999;
            animation: slideInUp 0.3s ease;
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'fadeIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },
    
    /**
     * 显示加载中
     */
    showLoading: (container, text = '加载中...') => {
        const loadingEl = document.createElement('div');
        loadingEl.className = 'loading';
        loadingEl.innerHTML = `
            <div class="loading-spinner"></div>
            <span>${text}</span>
        `;
        
        if (typeof container === 'string') {
            document.querySelector(container).innerHTML = '';
            document.querySelector(container).appendChild(loadingEl);
        } else if (container) {
            container.innerHTML = '';
            container.appendChild(loadingEl);
        }
        
        return loadingEl;
    },
    
    /**
     * 显示空状态
     */
    showEmpty: (container, icon = '📭', title = '暂无数据', desc = '') => {
        const emptyEl = document.createElement('div');
        emptyEl.className = 'empty-state';
        emptyEl.innerHTML = `
            <div class="empty-state-icon">${icon}</div>
            <div class="empty-state-title">${title}</div>
            ${desc ? `<div class="empty-state-desc">${desc}</div>` : ''}
        `;
        
        if (typeof container === 'string') {
            document.querySelector(container).innerHTML = '';
            document.querySelector(container).appendChild(emptyEl);
        } else if (container) {
            container.innerHTML = '';
            container.appendChild(emptyEl);
        }
        
        return emptyEl;
    },
    
    /**
     * 验证表单
     */
    validateForm: (formData, rules) => {
        const errors = {};
        
        for (const [field, rule] of Object.entries(rules)) {
            const value = formData[field];
            
            if (rule.required && !value) {
                errors[field] = rule.message || `${field}不能为空`;
            } else if (rule.min && value < rule.min) {
                errors[field] = rule.message || `${field}不能小于${rule.min}`;
            } else if (rule.max && value > rule.max) {
                errors[field] = rule.message || `${field}不能大于${rule.max}`;
            } else if (rule.pattern && !rule.pattern.test(value)) {
                errors[field] = rule.message || `${field}格式不正确`;
            }
        }
        
        return {
            valid: Object.keys(errors).length === 0,
            errors
        };
    },
    
    /**
     * 复制到剪贴板
     */
    copyToClipboard: async (text) => {
        try {
            await navigator.clipboard.writeText(text);
            Utils.toast('已复制到剪贴板', 'success');
            return true;
        } catch (err) {
            Utils.toast('复制失败', 'error');
            return false;
        }
    },
    
    /**
     * 文件大小格式化
     */
    formatFileSize: (bytes) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    /**
     * 数字格式化（添加千分位）
     */
    formatNumber: (num) => {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    },
    
    /**
     * 滚动到元素
     */
    scrollToElement: (element, behavior = 'smooth') => {
        if (typeof element === 'string') {
            element = document.querySelector(element);
        }
        if (element) {
            element.scrollIntoView({ behavior, block: 'start' });
        }
    },
    
    /**
     * 生成唯一ID
     */
    generateId: () => {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    },
    
    /**
     * 存储管理（带过期时间）
     */
    storage: {
        set: (key, value, expireMinutes = null) => {
            const data = {
                value,
                timestamp: Date.now()
            };
            if (expireMinutes) {
                data.expire = expireMinutes * 60 * 1000;
            }
            localStorage.setItem(key, JSON.stringify(data));
        },

        get: (key) => {
            const data = localStorage.getItem(key);
            if (!data) return null;

            try {
                const parsed = JSON.parse(data);
                if (parsed.expire && (Date.now() - parsed.timestamp) > parsed.expire) {
                    localStorage.removeItem(key);
                    return null;
                }
                return parsed.value;
            } catch {
                return null;
            }
        },

        remove: (key) => {
            localStorage.removeItem(key);
        }
    },

    /**
     * 更新侧边栏用户信息
     */
    /**
     * 格式化用户显示名称
     * @param {Object} user - 用户对象
     * @returns {string} 格式化后的显示名称
     */
    formatUserName: (user) => {
        if (!user) return '用户';
        
        const nickname = user.nickname || user.name || '';
        
        // 如果是默认格式"用户XXXXXX"，显示为更友好的格式
        if (nickname.startsWith('用户') && nickname.length === 8) {
            const suffix = nickname.substring(2);
            return `用户 (${suffix})`;
        }
        
        return nickname || '用户';
    },

    updateSidebarUser: async () => {
        try {
            const user = Auth.getUser();
            const userNameEl = document.querySelector('.user-name');
            const userAvatarEl = document.querySelector('.user-avatar');

            if (user && userNameEl) {
                // 使用格式化后的用户名
                const displayName = Utils.formatUserName(user);
                userNameEl.textContent = displayName;

                if (userAvatarEl) {
                    const initial = displayName[0].toUpperCase();
                    userAvatarEl.textContent = initial;
                }
            }
        } catch (error) {
            console.error('更新侧边栏用户信息失败:', error);
        }
    }
};

// 导出Utils对象
window.Utils = Utils;
