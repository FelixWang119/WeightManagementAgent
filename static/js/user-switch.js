// ============ 用户切换功能（调试用） ============

const UserSwitch = {
    // 缓存用户列表
    cachedUsers: null,

    // 常用测试登录码（与管理端一致）
    testCodes: [
        { code: 'user001', avatar: 'U1' },
        { code: 'user002', avatar: 'U2' },
        { code: 'user003', avatar: 'U3' },
        { code: 'test123', avatar: 'T1' },
        { code: 'demo', avatar: 'D1' },
    ],

    async loadAllUsers() {
        try {
            // 从服务器获取所有用户列表（需要管理员权限）
            const response = await fetch('http://localhost:8000/api/admin/users', {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('admin_token')}`
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.cachedUsers = data.users || [];
                return this.cachedUsers;
            }
        } catch (error) {
            console.log('无法获取用户列表，使用登录码模式');
        }

        // 降级：使用预定义的登录码
        return this.testCodes.map(item => ({
            id: null,
            nickname: `登录码: ${item.code}`,
            openid: item.code,
            avatar: item.avatar,
            isCodeMode: true
        }));
    },

    async show() {
        const modal = document.getElementById('user-switch-modal');
        const list = document.getElementById('user-switch-list');
        const currentUser = Auth.getUser();

        // 加载用户列表
        const users = await this.loadAllUsers();

        // 生成用户列表HTML
        list.innerHTML = users.map((user) => {
            const isActive = currentUser &&
                ((user.isCodeMode && user.openid === currentUser.id) || (!user.isCodeMode && user.id === currentUser.id));

            // 改进显示逻辑
            let displayName, subText;
            if (user.isCodeMode) {
                // 测试用户：显示更友好的名称
                const code = user.openid;
                if (code === 'user001') displayName = '测试用户 1';
                else if (code === 'user002') displayName = '测试用户 2';
                else if (code === 'user003') displayName = '测试用户 3';
                else if (code === 'test123') displayName = '测试用户 (test123)';
                else if (code === 'demo') displayName = '演示用户';
                else displayName = `测试用户: ${code}`;
                subText = `登录码: ${user.openid}`;
            } else {
                // 真实用户：如果昵称是默认格式，显示更友好
                if (user.nickname && user.nickname.startsWith('用户') && user.nickname.length === 8) {
                    // 默认格式"用户XXXXXX"，显示为"用户 (XXXXXX)"
                    const suffix = user.nickname.substring(2);
                    displayName = `用户 (${suffix})`;
                } else {
                    displayName = user.nickname || `用户 ${user.id}`;
                }
                subText = `ID: ${user.id}`;
            }
            
            const clickAction = user.isCodeMode ? `UserSwitch.switch('${user.openid}')` : `UserSwitch.switchById(${user.id})`;

            return `
                <div class="user-switch-item ${isActive ? 'active' : ''}" onclick="${clickAction}">
                    <div class="user-switch-avatar">${user.avatar || displayName[0].toUpperCase()}</div>
                    <div class="user-switch-info">
                        <div class="user-switch-name">${displayName}</div>
                        <div class="user-switch-id">${subText}</div>
                    </div>
                    ${isActive ? '<span class="user-switch-check">✓</span>' : ''}
                </div>
            `;
        }).join('');
        
        modal.classList.add('show');
    },
    
    hide() {
        document.getElementById('user-switch-modal').classList.remove('show');
    },
    
    async switch(code) {
        this.hide();
        Utils.toast(`正在切换到 ${code}...`, 'info');

        try {
            // 清除当前登录状态
            Auth.setToken(null);
            Auth.setUser(null);

            // 使用新code登录
            const result = await Auth.login(code);

            if (result.success) {
                Utils.toast(`✅ 已切换到: ${result.user.nickname}`, 'success');
                // 刷新页面以加载新用户数据
                setTimeout(() => {
                    window.location.reload();
                }, 500);
            } else {
                throw new Error(result.error || '切换失败');
            }
        } catch (error) {
            console.error('切换用户失败:', error);
            Utils.toast('❌ 切换失败: ' + error.message, 'error');
            // 恢复登录页跳转
            setTimeout(() => {
                window.location.href = 'login.html';
            }, 1500);
        }
    },

    // 通过用户ID切换（使用用户的OpenID登录）
    async switchById(userId) {
        this.hide();

        try {
            // 从缓存的用户列表中找到该用户的OpenID
            const targetUser = this.cachedUsers.find(u => u.id === userId);
            if (!targetUser) {
                throw new Error('用户不存在');
            }

            // 使用OpenID作为登录码
            const code = targetUser.openid;
            Utils.toast(`正在切换到 ${targetUser.nickname}...`, 'info');

            // 清除当前登录状态
            Auth.setToken(null);
            Auth.setUser(null);

            // 使用新code登录
            const result = await Auth.login(code);

            if (result.success) {
                Utils.toast(`✅ 已切换到: ${result.user.nickname}`, 'success');
                // 刷新页面以加载新用户数据
                setTimeout(() => {
                    window.location.reload();
                }, 500);
            } else {
                throw new Error(result.error || '切换失败');
            }
        } catch (error) {
            console.error('切换用户失败:', error);
            Utils.toast('❌ 切换失败: ' + error.message, 'error');
        }
    },
    
    async switchToNew() {
        // 生成随机code
        const randomCode = 'user_' + Math.random().toString(36).substring(2, 8);
        await this.switch(randomCode);
    }
};

// 点击弹窗外部关闭
document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('user-switch-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target.id === 'user-switch-modal') {
                UserSwitch.hide();
            }
        });
    }
});