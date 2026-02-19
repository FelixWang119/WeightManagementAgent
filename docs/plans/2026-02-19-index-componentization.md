# Index.html 组件化重构计划

> **执行说明**: 这是一个完整的重构计划，建议在新会话中按步骤执行。
> **备份位置**: `static/backup/index.html.backup.20260219`

---

## 目标

将 `static/index.html` (410行/24KB) 重构为组件化结构，目标精简到 ~120行/8KB。

## 最终目录结构

```
static/
├── index.html                           # 精简后的主文件
├── components/                          # HTML模板片段
│   ├── sidebar.html
│   ├── calorie-balance.html
│   ├── daily-suggestion.html
│   ├── chat-toolbar.html
│   ├── chat-input.html
│   ├── quick-actions-bar.html
│   └── user-switch-modal.html
├── js/
│   ├── components/                      # 组件化JS
│   │   ├── Sidebar.js
│   │   ├── CalorieBalance.js
│   │   ├── DailySuggestion.js
│   │   ├── ChatToolbar.js
│   │   ├── ChatInput.js
│   │   └── QuickActionsBar.js
│   ├── app.js                           # 应用初始化器
│   └── main.js                          # 入口文件
└── backup/
    └── index.html.backup.20260219       # 原文件备份
```

---

## 执行步骤

### Phase 1: 创建HTML模板组件 (30分钟)

#### Step 1.1: 创建 Sidebar 模板
**创建文件**: `static/components/sidebar.html`

```html
<!-- 侧边栏导航组件 -->
<div class="sidebar-overlay" id="sidebar-overlay"></div>

<aside class="sidebar" id="sidebar">
    <div class="sidebar-header">
        <div class="user-avatar">用</div>
        <div class="user-info">
            <div class="user-name">加载中...</div>
            <div class="user-status">在线</div>
        </div>
    </div>

    <nav class="sidebar-nav">
        <div class="nav-section">
            <div class="nav-section-title">主要功能</div>
            <ul class="nav-list">
                <li>
                    <a href="index.html" class="nav-item active">
                        <span class="nav-item-icon">🤖</span>
                        <span class="nav-item-text">AI助手</span>
                    </a>
                </li>
                <li>
                    <a href="weight.html" class="nav-item">
                        <span class="nav-item-icon">⚖️</span>
                        <span class="nav-item-text">体重记录</span>
                    </a>
                </li>
                <li>
                    <a href="meal.html" class="nav-item">
                        <span class="nav-item-icon">🍽️</span>
                        <span class="nav-item-text">饮食记录</span>
                    </a>
                </li>
                <li>
                    <a href="exercise.html" class="nav-item">
                        <span class="nav-item-icon">🏃</span>
                        <span class="nav-item-text">运动记录</span>
                    </a>
                </li>
            </ul>
        </div>

        <div class="nav-section">
            <div class="nav-section-title">健康管理</div>
            <ul class="nav-list">
                <li>
                    <a href="water.html" class="nav-item">
                        <span class="nav-item-icon">💧</span>
                        <span class="nav-item-text">饮水记录</span>
                    </a>
                </li>
                <li>
                    <a href="sleep.html" class="nav-item">
                        <span class="nav-item-icon">😴</span>
                        <span class="nav-item-text">睡眠记录</span>
                    </a>
                </li>
                <li>
                    <a href="report.html" class="nav-item">
                        <span class="nav-item-icon">📊</span>
                        <span class="nav-item-text">数据报告</span>
                    </a>
                </li>
                <li>
                    <a href="goals.html" class="nav-item">
                        <span class="nav-item-icon">🎯</span>
                        <span class="nav-item-text">目标管理</span>
                    </a>
                </li>
                <li>
                    <a href="calculator.html" class="nav-item">
                        <span class="nav-item-icon">🔥</span>
                        <span class="nav-item-text">热量计算</span>
                    </a>
                </li>
                <li>
                    <a href="reminders.html" class="nav-item">
                        <span class="nav-item-icon">🔔</span>
                        <span class="nav-item-text">提醒设置</span>
                    </a>
                </li>
            </ul>
        </div>
    </nav>

    <div class="sidebar-footer">
        <button class="sidebar-switch-btn" onclick="UserSwitch.show()">
            <span>🔄</span>
            <span>切换用户（调试）</span>
        </button>
        <a href="profile.html" class="nav-item">
            <span class="nav-item-icon">⚙️</span>
            <span class="nav-item-text">个人设置</span>
        </a>
        <button class="logout-btn" onclick="Auth.logout()">
            <span>🚪</span>
            <span>退出登录</span>
        </button>
    </div>
</aside>
```

#### Step 1.2: 创建热量平衡卡片模板
**创建文件**: `static/components/calorie-balance.html`

```html
<!-- 热量平衡卡片组件 -->
<div class="calorie-balance-card" id="calorie-balance-card">
    <div class="balance-card-header" onclick="CalorieBalance.toggle()">
        <div class="balance-header-left">
            <span class="balance-icon">🔥</span>
            <span class="balance-title">今日热量平衡</span>
            <span class="date-indicator" id="balance-date">今日</span>
        </div>
        <div class="balance-header-right">
            <span class="collapse-indicator">▼</span>
        </div>
    </div>

    <div class="balance-card-content" id="balance-content">
        <!-- 无BMR引导 -->
        <div class="balance-guide" id="balance-guide" style="display: none;">
            <div class="guide-icon">📊</div>
            <div class="guide-text">
                完善基础信息，开启热量追踪<br>
                基础代谢是计算热量平衡的重要数据<br>
                只需1分钟即可完成测算
            </div>
            <button class="guide-btn" onclick="window.location.href='calculator.html'">立即测算</button>
        </div>

        <!-- 加载中 -->
        <div class="balance-loading" id="balance-loading">
            <div class="loading-spinner balance-loading-spinner"></div>
            <p>加载热量数据中...</p>
        </div>

        <!-- 天平对比布局 -->
        <div class="balance-detail" id="balance-detail" style="display: none;">
            <div class="scale-comparison">
                <div class="scale-side intake-side">
                    <div class="scale-card">
                        <div class="scale-icon">🍽️</div>
                        <div class="scale-label">饮食摄入</div>
                        <div class="scale-value" id="scale-intake">0</div>
                        <div class="scale-unit">kcal</div>
                    </div>
                </div>

                <div class="scale-connector">
                    <div class="scale-line"></div>
                    <div class="scale-gap" id="scale-gap">
                        <div class="gap-icon">⚖️</div>
                        <div class="gap-value" id="gap-value">0</div>
                        <div class="gap-unit">kcal</div>
                        <div class="gap-status" id="gap-status">平衡</div>
                    </div>
                    <div class="scale-line"></div>
                </div>

                <div class="scale-side burn-side">
                    <div class="scale-card">
                        <div class="scale-icon">🔥</div>
                        <div class="scale-label">热量消耗</div>
                        <div class="scale-value" id="scale-burn">0</div>
                        <div class="scale-unit">kcal</div>
                    </div>
                </div>
            </div>

            <div class="formula-area">
                <div class="formula-label">计算公式（减肥公式：饮食摄入 &lt; 基础代谢 + 运动消耗）</div>
                <div class="formula-content">
                    <span class="formula-intake" id="formula-intake">0</span>
                    <span class="formula-operator">&lt;</span>
                    <span class="formula-bmr" id="formula-bmr">0</span>
                    <span class="formula-operator">+</span>
                    <span class="formula-exercise" id="formula-exercise">0</span>
                </div>
                <div class="formula-result" id="formula-result">
                    <span class="result-icon">💡</span>
                    <span class="result-text">还可以吃 <span id="remaining-calories">0</span> kcal</span>
                </div>
            </div>

            <div class="status-indicator" id="status-indicator" style="display: none;">
                <span>💡</span>
                <span>状态提示信息</span>
            </div>
        </div>
    </div>
</div>
```

#### Step 1.3: 创建每日建议卡片模板
**创建文件**: `static/components/daily-suggestion.html`

```html
<!-- 每日建议卡片组件 -->
<div class="daily-suggestion-card" id="daily-suggestion-card">
    <div class="suggestion-header">
        <span class="suggestion-icon">💡</span>
        <span class="suggestion-title">今日建议</span>
        <button class="refresh-btn" id="refresh-btn" onclick="DailySuggestion.refresh()" title="换一条">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="23 4 23 10 17 10"></polyline>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
            </svg>
        </button>
    </div>

    <div class="suggestion-content" id="suggestion-content">
        <div class="suggestion-loading">
            <div class="loading-spinner" style="width: 24px; height: 24px; border-width: 2px;"></div>
            <p>AI正在生成建议...</p>
        </div>
    </div>

    <div class="suggestion-action" id="suggestion-action"></div>
</div>
```

#### Step 1.4: 创建聊天工具栏模板
**创建文件**: `static/components/chat-toolbar.html`

```html
<!-- 快捷工具栏组件 -->
<div class="chat-toolbar">
    <button class="toolbar-btn" onclick="ChatToolbar.sendQuickMessage('记录体重')">⚖️ 记体重</button>
    <button class="toolbar-btn" onclick="ChatToolbar.sendQuickMessage('记录早餐')">🍽️ 记饮食</button>
    <button class="toolbar-btn" onclick="ChatToolbar.sendQuickMessage('记录运动')">🏃 记运动</button>
    <button class="toolbar-btn" onclick="ChatToolbar.sendQuickMessage('记录饮水')">💧 记饮水</button>
</div>
```

#### Step 1.5: 创建聊天输入区域模板
**创建文件**: `static/components/chat-input.html`

```html
<!-- 聊天输入区域组件 -->
<div class="chat-input-area">
    <div class="chat-input-wrapper">
        <button class="chat-image-btn" onclick="document.getElementById('image-input').click()" title="上传图片">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                <polyline points="21 15 16 10 5 21"></polyline>
            </svg>
        </button>
        <input type="file" id="image-input" accept="image/*" style="display: none;" onchange="ChatInput.handleImageSelect(event)">
        <textarea id="chat-input" class="chat-input" placeholder="输入消息...（支持上传图片询问食物）" rows="1"></textarea>
        <button class="chat-send-btn" id="send-btn" onclick="ChatInput.sendMessage()">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
        </button>
    </div>
    <div id="image-preview" class="image-preview" style="display: none;">
        <div class="preview-item">
            <img id="preview-img" src="" alt="预览">
            <button class="preview-remove" onclick="ChatInput.clearImage()">×</button>
        </div>
    </div>
</div>
```

#### Step 1.6: 创建底部快捷栏模板
**创建文件**: `static/components/quick-actions-bar.html`

```html
<!-- 底部快捷栏（移动端） -->
<div class="quick-actions-bar">
    <a href="weight.html" class="quick-action-item">
        <span>⚖️</span>
        <span>体重</span>
    </a>
    <a href="meal.html" class="quick-action-item">
        <span>🍽️</span>
        <span>饮食</span>
    </a>
    <a href="exercise.html" class="quick-action-item">
        <span>🏃</span>
        <span>运动</span>
    </a>
    <a href="water.html" class="quick-action-item">
        <span>💧</span>
        <span>饮水</span>
    </a>
</div>
```

#### Step 1.7: 创建用户切换弹窗模板
**创建文件**: `static/components/user-switch-modal.html`

```html
<!-- 用户切换弹窗组件 -->
<div class="user-switch-modal" id="user-switch-modal">
    <div class="user-switch-content">
        <div class="user-switch-header">
            <h3 class="user-switch-title">🔧 调试：切换用户</h3>
            <button class="user-switch-close" onclick="UserSwitch.hide()">×</button>
        </div>
        <div class="user-switch-list" id="user-switch-list"></div>
        <div class="user-switch-footer">
            <button class="user-switch-btn secondary" onclick="UserSwitch.hide()">取消</button>
            <button class="user-switch-btn primary" onclick="UserSwitch.switchToNew()">+ 新用户</button>
        </div>
    </div>
</div>
```

---

### Phase 2: 创建组件化JS (60分钟)

#### Step 2.1: 创建 Sidebar 组件
**创建文件**: `static/js/components/Sidebar.js`

```javascript
/**
 * 侧边栏导航组件
 */
class Sidebar {
    constructor() {
        this.sidebar = null;
        this.overlay = null;
        this.toggleBtn = null;
        this.init();
    }

    init() {
        // 绑定事件
        document.addEventListener('DOMContentLoaded', () => {
            this.sidebar = document.getElementById('sidebar');
            this.overlay = document.getElementById('sidebar-overlay');
            this.toggleBtn = document.getElementById('menu-toggle');

            if (this.toggleBtn) {
                this.toggleBtn.addEventListener('click', () => this.toggle());
            }

            if (this.overlay) {
                this.overlay.addEventListener('click', () => this.close());
            }
        });
    }

    toggle() {
        if (this.sidebar) {
            this.sidebar.classList.toggle('active');
            if (this.overlay) {
                this.overlay.classList.toggle('active');
            }
        }
    }

    open() {
        if (this.sidebar) {
            this.sidebar.classList.add('active');
            if (this.overlay) {
                this.overlay.classList.add('active');
            }
        }
    }

    close() {
        if (this.sidebar) {
            this.sidebar.classList.remove('active');
            if (this.overlay) {
                this.overlay.classList.remove('active');
            }
        }
    }
}

// 导出全局实例
window.Sidebar = Sidebar;
```

#### Step 2.2: 创建 CalorieBalance 组件
**创建文件**: `static/js/components/CalorieBalance.js`

```javascript
/**
 * 热量平衡卡片组件
 */
class CalorieBalance {
    constructor() {
        this.isExpanded = true;
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.loadData();
        });
    }

    static toggle() {
        const content = document.getElementById('balance-content');
        const indicator = document.querySelector('.collapse-indicator');
        
        if (content) {
            const isHidden = content.style.display === 'none';
            content.style.display = isHidden ? 'block' : 'none';
            if (indicator) {
                indicator.textContent = isHidden ? '▼' : '▶';
            }
        }
    }

    async loadData() {
        // 从原chat.js中提取的加载逻辑
        try {
            const response = await fetch('/api/calories/balance/daily', {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });

            const data = await response.json();

            if (data.success) {
                this.updateUI(data.data);
            }
        } catch (error) {
            console.error('[CalorieBalance] 加载数据失败:', error);
        }
    }

    updateUI(data) {
        // 更新UI元素
        const elements = {
            intake: document.getElementById('scale-intake'),
            burn: document.getElementById('scale-burn'),
            gap: document.getElementById('gap-value'),
            status: document.getElementById('gap-status'),
            formulaIntake: document.getElementById('formula-intake'),
            formulaBmr: document.getElementById('formula-bmr'),
            formulaExercise: document.getElementById('formula-exercise'),
            remaining: document.getElementById('remaining-calories')
        };

        if (elements.intake) elements.intake.textContent = data.intake || 0;
        if (elements.burn) elements.burn.textContent = data.burn || 0;
        if (elements.gap) elements.gap.textContent = data.gap || 0;
        if (elements.status) elements.status.textContent = data.status || '平衡';
        if (elements.formulaIntake) elements.formulaIntake.textContent = data.intake || 0;
        if (elements.formulaBmr) elements.formulaBmr.textContent = data.bmr || 0;
        if (elements.formulaExercise) elements.formulaExercise.textContent = data.exercise || 0;
        if (elements.remaining) elements.remaining.textContent = data.remaining || 0;

        // 隐藏加载状态，显示详情
        const loading = document.getElementById('balance-loading');
        const detail = document.getElementById('balance-detail');
        
        if (loading) loading.style.display = 'none';
        if (detail) detail.style.display = 'block';
    }
}

window.CalorieBalance = CalorieBalance;
```

#### Step 2.3: 创建 DailySuggestion 组件
**创建文件**: `static/js/components/DailySuggestion.js`

```javascript
/**
 * 每日建议卡片组件
 */
class DailySuggestion {
    constructor() {
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.loadSuggestion();
        });
    }

    static async refresh() {
        const instance = new DailySuggestion();
        await instance.loadSuggestion(true);
    }

    async loadSuggestion(forceRefresh = false) {
        const content = document.getElementById('suggestion-content');
        const action = document.getElementById('suggestion-action');

        if (content && !forceRefresh) {
            // 首次加载显示加载状态已在HTML中
        }

        try {
            const url = `/api/chat/daily-suggestion${forceRefresh ? '?refresh=true' : ''}`;
            const response = await fetch(url, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });

            const data = await response.json();

            if (data.success && content) {
                content.innerHTML = `<p>${data.suggestion || '暂无建议'}</p>`;
                
                if (action && data.action) {
                    action.innerHTML = `<button class="btn-primary" onclick="${data.action.onclick}">${data.action.text}</button>`;
                }
            }
        } catch (error) {
            console.error('[DailySuggestion] 加载建议失败:', error);
            if (content) {
                content.innerHTML = '<p>获取建议失败，请稍后重试</p>';
            }
        }
    }
}

window.DailySuggestion = DailySuggestion;
```

#### Step 2.4: 创建 ChatToolbar 组件
**创建文件**: `static/js/components/ChatToolbar.js`

```javascript
/**
 * 聊天工具栏组件
 */
class ChatToolbar {
    static sendQuickMessage(message) {
        // 调用聊天输入组件的发送方法
        if (window.ChatInput) {
            window.ChatInput.sendMessage(message);
        } else {
            console.warn('[ChatToolbar] ChatInput 未初始化');
        }
    }
}

window.ChatToolbar = ChatToolbar;
```

#### Step 2.5: 创建 ChatInput 组件
**创建文件**: `static/js/components/ChatInput.js`

```javascript
/**
 * 聊天输入区域组件
 */
class ChatInput {
    constructor() {
        this.selectedImage = null;
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.bindEvents();
        });
    }

    bindEvents() {
        const textarea = document.getElementById('chat-input');
        
        if (textarea) {
            textarea.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });

            // 自动调整高度
            textarea.addEventListener('input', () => {
                textarea.style.height = 'auto';
                textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
            });
        }
    }

    static handleImageSelect(event) {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            const preview = document.getElementById('image-preview');
            const img = document.getElementById('preview-img');
            
            if (preview && img) {
                img.src = e.target.result;
                preview.style.display = 'block';
            }
            
            // 保存到实例
            if (window.chatInputInstance) {
                window.chatInputInstance.selectedImage = file;
            }
        };
        reader.readAsDataURL(file);
    }

    static clearImage() {
        const preview = document.getElementById('image-preview');
        const img = document.getElementById('preview-img');
        const input = document.getElementById('image-input');
        
        if (preview) preview.style.display = 'none';
        if (img) img.src = '';
        if (input) input.value = '';
        
        if (window.chatInputInstance) {
            window.chatInputInstance.selectedImage = null;
        }
    }

    static async sendMessage(text = null) {
        const textarea = document.getElementById('chat-input');
        const message = text || (textarea ? textarea.value.trim() : '');
        
        if (!message && !window.chatInputInstance?.selectedImage) {
            return;
        }

        // 清空输入
        if (textarea && !text) {
            textarea.value = '';
            textarea.style.height = 'auto';
        }

        // 这里应该调用聊天核心逻辑
        // 暂时保持与原来相同的行为
        if (window.sendMessage) {
            await window.sendMessage(message);
        }

        // 清除图片
        if (window.chatInputInstance?.selectedImage) {
            ChatInput.clearImage();
        }
    }
}

// 创建全局实例
window.ChatInput = ChatInput;
window.chatInputInstance = new ChatInput();
```

#### Step 2.6: 创建 QuickActionsBar 组件
**创建文件**: `static/js/components/QuickActionsBar.js`

```javascript
/**
 * 底部快捷栏组件（移动端）
 */
class QuickActionsBar {
    constructor() {
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.checkMobile();
        });

        window.addEventListener('resize', () => {
            this.checkMobile();
        });
    }

    checkMobile() {
        const bar = document.querySelector('.quick-actions-bar');
        if (!bar) return;

        const isMobile = window.innerWidth <= 768;
        bar.style.display = isMobile ? 'flex' : 'none';
    }
}

window.QuickActionsBar = QuickActionsBar;
```

---

### Phase 3: 重构主HTML文件 (30分钟)

#### Step 3.1: 重写精简版 index.html
**替换文件**: `static/index.html`

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI助手 - 体重管理助手</title>
    
    <!-- 样式文件 -->
    <link rel="stylesheet" href="css/base.css">
    <link rel="stylesheet" href="css/components.css">
    <link rel="stylesheet" href="css/layout.css">
    <link rel="stylesheet" href="css/user-switch.css">
    <link rel="stylesheet" href="css/chat.css">
    <link rel="stylesheet" href="css/core-profiling.css">
</head>
<body>
    <div class="page">
        <!-- 顶部导航 -->
        <header class="page-header">
            <div class="header-brand">
                <span class="header-brand-icon">🤖</span>
                <span>AI助手</span>
            </div>
            <div class="header-actions">
                <button class="btn-icon" onclick="if(typeof Profiling !== 'undefined') Profiling.forceShowQuestion()" title="测试画像问答" style="margin-right: 8px; font-size: 1.25rem;">❓</button>
                <button class="menu-toggle" id="menu-toggle" title="打开菜单">
                    <span></span>
                </button>
            </div>
        </header>

        <!-- 页面内容 -->
        <div class="page-content">
            <!-- 侧边栏 -->
            <div id="sidebar-container"></div>

            <!-- 主内容区 -->
            <main class="page-main" style="padding: 0;">
                <div class="chat-page">
                    <!-- 聊天消息区域 -->
                    <div class="chat-container" id="chat-messages">
                        <!-- 组件容器 -->
                        <div id="calorie-balance-container"></div>
                        <div id="daily-suggestion-container"></div>
                    </div>

                    <!-- 快捷工具栏 -->
                    <div id="chat-toolbar-container"></div>

                    <!-- 输入区域 -->
                    <div id="chat-input-container"></div>

                    <!-- 底部快捷栏（移动端） -->
                    <div id="quick-actions-container"></div>
                </div>
            </main>
        </div>
    </div>

    <!-- 用户切换弹窗 -->
    <div id="user-switch-container"></div>

    <!-- 脚本 -->
    <script src="https://unpkg.com/chart.js@3.9.1/dist/chart.min.js"></script>
    
    <!-- 基础脚本 -->
    <script src="js/api.js"></script>
    <script src="js/auth.js"></script>
    <script src="js/utils.js"></script>
    <script src="js/components.js"></script>
    <script src="js/profiling.js"></script>
    <script src="js/user-switch.js"></script>
    <script src="js/chat.js"></script>
    <script src="js/components/CoreProfiling.js"></script>
    
    <!-- 新组件脚本 -->
    <script src="js/components/Sidebar.js"></script>
    <script src="js/components/CalorieBalance.js"></script>
    <script src="js/components/DailySuggestion.js"></script>
    <script src="js/components/ChatToolbar.js"></script>
    <script src="js/components/ChatInput.js"></script>
    <script src="js/components/QuickActionsBar.js"></script>
    
    <!-- 核心功能 -->
    <script src="js/core-profiling.js"></script>
    <script src="js/notification-poller.js"></script>
    
    <!-- 应用初始化 -->
    <script src="js/app.js"></script>
</body>
</html>
```

#### Step 3.2: 创建 App 初始化器
**创建文件**: `static/js/app.js`

```javascript
/**
 * 应用初始化器
 * 负责加载组件模板和初始化各模块
 */
class App {
    constructor() {
        this.components = {};
    }

    async init() {
        try {
            // 加载所有HTML组件模板
            await this.loadComponents();
            
            // 初始化各组件
            this.initComponents();
            
            // 初始化核心功能
            this.initCoreFeatures();
            
            console.log('[App] 应用初始化完成');
        } catch (error) {
            console.error('[App] 初始化失败:', error);
        }
    }

    async loadComponents() {
        const components = [
            { id: 'sidebar-container', file: 'components/sidebar.html' },
            { id: 'calorie-balance-container', file: 'components/calorie-balance.html' },
            { id: 'daily-suggestion-container', file: 'components/daily-suggestion.html' },
            { id: 'chat-toolbar-container', file: 'components/chat-toolbar.html' },
            { id: 'chat-input-container', file: 'components/chat-input.html' },
            { id: 'quick-actions-container', file: 'components/quick-actions-bar.html' },
            { id: 'user-switch-container', file: 'components/user-switch-modal.html' }
        ];

        for (const comp of components) {
            try {
                const response = await fetch(comp.file);
                const html = await response.text();
                const container = document.getElementById(comp.id);
                if (container) {
                    container.innerHTML = html;
                }
            } catch (error) {
                console.warn(`[App] 加载组件 ${comp.file} 失败:`, error);
            }
        }
    }

    initComponents() {
        // 初始化侧边栏
        if (typeof Sidebar !== 'undefined') {
            this.components.sidebar = new Sidebar();
        }

        // 初始化热量平衡卡片
        if (typeof CalorieBalance !== 'undefined') {
            this.components.calorieBalance = new CalorieBalance();
        }

        // 初始化每日建议
        if (typeof DailySuggestion !== 'undefined') {
            this.components.dailySuggestion = new DailySuggestion();
        }

        // 初始化底部快捷栏
        if (typeof QuickActionsBar !== 'undefined') {
            this.components.quickActionsBar = new QuickActionsBar();
        }
    }

    initCoreFeatures() {
        // 初始化核心问题收集
        if (typeof CoreProfiling !== 'undefined') {
            window.coreProfiling = new CoreProfiling({
                onComplete: () => {
                    console.log('核心问题收集完成');
                }
            });
        }

        // 初始化通知轮询系统
        if (typeof NotificationPoller !== 'undefined') {
            window.notificationPoller = new NotificationPoller({
                interval: 30000,
                onNotification: (notifications) => {
                    console.log('收到新通知:', notifications);
                }
            });
        }
    }
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
    window.app.init();
});
```

---

### Phase 4: 测试验证 (30分钟)

#### Step 4.1: 验证文件完整性
**检查命令**:
```bash
# 检查所有文件是否已创建
ls -la static/components/
ls -la static/js/components/
ls -la static/js/app.js
ls -la static/index.html
```

#### Step 4.2: 浏览器测试清单

- [ ] 页面能正常加载，无404错误
- [ ] 侧边栏能正常展开/收起
- [ ] 热量平衡卡片显示正常，数据加载正确
- [ ] 每日建议卡片显示正常，刷新按钮工作
- [ ] 聊天工具栏按钮能正常发送快捷消息
- [ ] 聊天输入框能正常输入和发送消息
- [ ] 移动端底部快捷栏正常显示
- [ ] 用户切换弹窗正常弹出
- [ ] 核心问题收集系统正常工作
- [ ] 通知轮询系统正常工作

#### Step 4.3: 性能检查

打开浏览器开发者工具，检查：
- Network面板：所有组件模板是否正确加载
- Console面板：无JavaScript错误
- Performance面板：首屏加载时间是否有改善

---

## 回滚方案

如果重构出现问题，快速回滚：

```bash
# 恢复备份文件
cp static/backup/index.html.backup.20260219 static/index.html

# 清理新创建的文件（可选）
rm -rf static/components/
rm -rf static/js/components/
rm static/js/app.js
```

---

## 文件修改统计

| 类型 | 数量 | 说明 |
|------|------|------|
| 新建HTML组件 | 7个 | sidebar, calorie-balance等 |
| 新建JS组件 | 6个 | Sidebar.js, CalorieBalance.js等 |
| 修改主文件 | 1个 | index.html 精简重构 |
| 新建JS文件 | 1个 | app.js 应用初始化器 |

**预计重构后**:
- `index.html`: 410行 → ~120行 (减少70%)
- 单个组件文件: 20-60行，易于维护
- 职责分离清晰，便于团队协作
