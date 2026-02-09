/**
 * 认证管理模块
 * 处理登录状态、Token管理、路由守卫
 */

const AUTH_KEY = 'token';
const USER_KEY = 'user';

/**
 * 认证管理器
 */
const Auth = {
    /**
     * 获取Token
     */
    getToken() {
        return localStorage.getItem(AUTH_KEY);
    },

    /**
     * 设置Token
     */
    setToken(token) {
        if (token) {
            localStorage.setItem(AUTH_KEY, token);
        } else {
            localStorage.removeItem(AUTH_KEY);
        }
    },

    /**
     * 获取用户信息
     */
    getUser() {
        const userData = localStorage.getItem(USER_KEY);
        return userData ? JSON.parse(userData) : null;
    },

    /**
     * 设置用户信息
     */
    setUser(user) {
        if (user) {
            localStorage.setItem(USER_KEY, JSON.stringify(user));
        } else {
            localStorage.removeItem(USER_KEY);
        }
    },

    /**
     * 检查是否已登录 (别名)
     */
    check() {
        return !!this.getToken();
    },

    /**
     * 检查是否已登录
     */
    isLoggedIn() {
        return !!this.getToken();
    },
    
    /**
     * 登录
     */
    async login(code) {
        try {
            const response = await API.user.login(code);
            
            if (response.success && response.token) {
                this.setToken(response.token);
                this.setUser(response.user);
                return {
                    success: true,
                    user: response.user,
                    isNew: response.is_new
                };
            } else {
                return {
                    success: false,
                    error: response.error || '登录失败'
                };
            }
        } catch (error) {
            return {
                success: false,
                error: error.message || '登录请求失败'
            };
        }
    },
    
    /**
     * 登出
     */
    logout() {
        this.setToken(null);
        this.setUser(null);
        window.location.href = '/static/login.html';
    },
    
    /**
     * 路由守卫 - 检查登录状态
     */
    guard() {
        // 排除登录页
        if (window.location.pathname.includes('login.html')) {
            // 已登录则跳转到首页
            if (this.isLoggedIn()) {
                window.location.href = '/static/index.html';
            }
            return;
        }
        
        // 其他页面需要登录
        if (!this.isLoggedIn()) {
            // 保存当前URL以便登录后返回
            sessionStorage.setItem('redirect_url', window.location.href);
            window.location.href = '/static/login.html';
        }
    },
    
    /**
     * 获取重定向URL
     */
    getRedirectUrl() {
        const url = sessionStorage.getItem('redirect_url') || '/static/index.html';
        sessionStorage.removeItem('redirect_url');
        return url;
    },
    
    /**
     * 更新用户信息
     */
    async updateUserInfo() {
        try {
            const response = await API.user.getProfile();
            if (response.success && response.data) {
                this.setUser(response.data.user);
                return response.data.user;
            }
        } catch (error) {
            console.error('更新用户信息失败:', error);
        }
        return null;
    }
};

// 导出Auth对象
window.Auth = Auth;

// 页面加载时执行路由守卫
document.addEventListener('DOMContentLoaded', () => {
    Auth.guard();
});
