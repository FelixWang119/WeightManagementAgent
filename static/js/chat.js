// ========================================
// 聊天页面逻辑 - chat.js
// ========================================

// 全局变量
let isSending = false;
let messages = [];
let selectedImage = null;

// BroadcastChannel 用于跨页面通信
const dataChannel = new BroadcastChannel('weight_management_data');

// 监听数据更新
dataChannel.onmessage = (event) => {
    if (event.data.type === 'dataUpdated') {
        console.log('检测到数据更新，自动刷新热量平衡卡片...');
        loadCalorieBalance();
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    // 初始化用户画像收集（模拟企业微信主动推送）
    if (typeof Profiling !== 'undefined') {
        Profiling.init();
    }

    // 滚动到页面底部
    const container = document.getElementById('chat-messages');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }

    // 新版热量平衡卡片 - 简化加载逻辑，确保数据能够加载
    const calorieCard = document.getElementById('calorie-balance-card');
    if (calorieCard) {
        // 检查localStorage中的折叠状态
        const isExpanded = localStorage.getItem('calorieCardExpanded') === 'true';

        if (isExpanded) {
            calorieCard.classList.remove('collapsed');
        } else {
            calorieCard.classList.add('collapsed');
        }

        // 无论折叠状态如何，都尝试加载数据（但只加载一次）
        if (!calorieCard.dataset.loaded || calorieCard.dataset.loaded === 'false') {
            console.log('首次加载热量平衡数据...');
            loadCalorieBalance();
            calorieCard.dataset.loaded = 'true';
        }
    }

    // 监听饮食记录更新事件
    window.addEventListener('storage', (event) => {
        if (event.key === 'mealUpdated') {
            console.log('检测到饮食记录更新，刷新热量平衡数据');
            loadCalorieBalance();
        }
    });

    // 加载每日建议
    loadDailySuggestion();

    // 加载聊天历史
    loadChatHistory();

    // 自动调整输入框高度
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('input', () => {
            chatInput.style.height = 'auto';
            chatInput.style.height = chatInput.scrollHeight + 'px';
        });

        // 回车发送（Shift+Enter换行）
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                window.sendMessage();
            }
        });
    }
});

// ============ 图片上传功能 ============

// 处理图片选择
function handleImageSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    // 检查文件类型
    if (!file.type.startsWith('image/')) {
        Utils.toast('请选择图片文件', 'error');
        return;
    }

    // 检查文件大小（限制5MB）
    if (file.size > 5 * 1024 * 1024) {
        Utils.toast('图片大小不能超过5MB', 'error');
        return;
    }

    // 预览图片
    const reader = new FileReader();
    reader.onload = (e) => {
        selectedImage = {
            file: file,
            dataUrl: e.target.result
        };

        // 显示预览
        const preview = document.getElementById('image-preview');
        const previewImg = document.getElementById('preview-img');
        if (previewImg) previewImg.src = e.target.result;
        if (preview) preview.style.display = 'block';
    };
    reader.readAsDataURL(file);

    // 清空input，允许重复选择同一文件
    event.target.value = '';
}

// 清除已选图片
function clearImage() {
    selectedImage = null;
    const preview = document.getElementById('image-preview');
    const previewImg = document.getElementById('preview-img');
    if (preview) preview.style.display = 'none';
    if (previewImg) previewImg.src = '';
}

// 上传图片到服务器
async function uploadImage(file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('type', 'food_query');

    const response = await fetch(`${API.base}/api/chat/upload-image`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${Auth.getToken()}`
        },
        body: formData
    });

    if (!response.ok) {
        throw new Error('图片上传失败');
    }

    return await response.json();
}

// ============ 热量平衡卡片功能 ============

// 加载热量平衡数据
async function loadCalorieBalance() {
    if (!Auth.check()) {
        return;
    }
    
    const loadingEl = document.getElementById('balance-loading');
    const guideEl = document.getElementById('balance-guide');
    const detailEl = document.getElementById('balance-detail');

    if (!loadingEl || !guideEl || !detailEl) {
        console.log('热量平衡卡片元素不存在');
        return;
    }

    // 重置显示状态
    loadingEl.style.display = 'none';
    guideEl.style.display = 'none';
    detailEl.style.display = 'none';

    try {
        const response = await fetch(`${API.base}/api/calories/balance/daily?days=1`, {
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });

        if (!response.ok) {
            throw new Error('获取热量数据失败');
        }

        const result = await response.json();
        console.log('Calorie balance response:', result);

        // 检查是否有BMR数据（从 user_stats 中获取）
        if (result.success && result.user_stats) {
            console.log('BMR check:', {
                has_bmr_data: result.user_stats.has_bmr_data,
                bmr: result.user_stats.bmr,
                bmrType: typeof result.user_stats.bmr
            });

            // 更详细的调试信息
            console.log('详细BMR状态:', {
                hasBmrDataExists: result.user_stats.has_bmr_data !== undefined,
                bmrExists: result.user_stats.bmr !== undefined,
                bmrValue: result.user_stats.bmr,
                bmrIsZero: result.user_stats.bmr === 0,
                bmrIsNull: result.user_stats.bmr === null,
                bmrIsUndefined: result.user_stats.bmr === undefined
            });

            // 只有当没有BMR数据时才显示引导
            if (!result.user_stats.has_bmr_data || !result.user_stats.bmr || result.user_stats.bmr === 0) {
                console.log('显示引导：用户需要测算BMR');
                guideEl.style.display = 'block';
                updateSummary('--', '--', '需完善信息');
                return;
            }

            // 获取今日数据（注意API返回的是daily_data数组）
            if (result.daily_data && result.daily_data.length > 0) {
                const todayData = result.daily_data[result.daily_data.length - 1]; // 取最后一天（今天）
                displayCalorieBalance({
                    intake: todayData.intake,
                    exercise_burned: todayData.exercise_burned,
                    bmr: result.user_stats.bmr,
                    base_burned: todayData.base_burned, // 使用base_burned字段
                    total_burned: todayData.total_burned,
                    balance: todayData.balance
                });
            } else {
                // 没有今日数据，但显示基本信息
                guideEl.style.display = 'none';
                detailEl.style.display = 'block';
                displayCalorieBalance({
                    intake: 0,
                    exercise_burned: 0,
                    bmr: result.user_stats.bmr,
                    base_burned: result.user_stats.estimated_tdee || 1800 // 使用estimated_tdee
                });
            }
        } else {
            // API 响应异常
            guideEl.style.display = 'block';
            updateSummary('--', '--', '加载失败');
        }
    } catch (error) {
        console.error('加载热量平衡失败:', error);
        guideEl.style.display = 'block';
        updateSummary('--', '--', '加载失败');
    }
}

// 显示新版热量平衡 - 天平对比布局
function displayCalorieBalance(data) {
    const guideEl = document.getElementById('balance-guide');
    const detailEl = document.getElementById('balance-detail');
    const statusEl = document.getElementById('status-indicator');

    guideEl.style.display = 'none';
    detailEl.style.display = 'block';

    // 计算数据（兼容不同的数据格式）
    const intake = data.intake || 0;
    const exerciseBurn = data.exercise_burned || 0;
    // 使用base_burned（TDEE）作为基础消耗，如果没有则使用bmr
    const baseBurn = data.base_burned || data.bmr || 0;
    // 如果没有提供total_burned则计算
    const totalBurn = data.total_burned || (exerciseBurn + baseBurn);
    // 统一使用摄入 - 消耗的计算方式（负数表示赤字）
    const netCalorie = intake - totalBurn;

    console.log('Display new calorie balance:', { intake, exerciseBurn, baseBurn, totalBurn, netCalorie });

    // 更新天平对比布局（使用baseBurn而不是bmr）
    updateScaleComparison(intake, totalBurn, netCalorie, baseBurn, exerciseBurn);

    // 设置状态指示器
    setStatusIndicator(netCalorie);
}

// 更新天平对比布局
function updateScaleComparison(intake, totalBurn, netCalorie, bmr, exerciseBurn) {
    // 更新左右两侧数据（添加括号备注）
    document.getElementById('scale-intake').textContent = Math.round(intake) + '（饮食）';
    document.getElementById('scale-burn').textContent = Math.round(totalBurn) + '（总消耗）';

    // 更新缺口区域
    const gapValue = document.getElementById('gap-value');
    const gapStatus = document.getElementById('gap-status');

    const absGap = Math.abs(Math.round(netCalorie));
    gapValue.textContent = absGap;

    // 设置缺口状态
    if (netCalorie > 100) {
        gapStatus.textContent = '盈余';
        gapStatus.className = 'gap-status surplus';
    } else if (netCalorie > -100) {
        gapStatus.textContent = '平衡';
        gapStatus.className = 'gap-status balanced';
    } else {
        gapStatus.textContent = '缺口';
        gapStatus.className = 'gap-status deficit';
    }

    // 更新计算公式（添加括号备注）
    document.getElementById('formula-intake').textContent = Math.round(intake) + '（饮食）';
    document.getElementById('formula-bmr').textContent = Math.round(bmr) + '（基础代谢）';
    document.getElementById('formula-exercise').textContent = Math.round(exerciseBurn) + '（运动）';

    // 更新剩余可摄入量（添加括号备注）
    const remainingCalories = Math.max(0, totalBurn - intake);
    document.getElementById('remaining-calories').textContent = Math.round(remainingCalories) + '（可摄入）';

    // 根据摄入和消耗关系调整公式运算符
    const formulaOperator = document.querySelector('.formula-operator');
    if (intake < totalBurn) {
        formulaOperator.textContent = '<';
        formulaOperator.style.color = '#4caf50'; // 绿色表示符合减肥公式
    } else {
        formulaOperator.textContent = '>';
        formulaOperator.style.color = '#ff6b6b'; // 红色表示不符合减肥公式
    }
}

// 设置状态指示器
function setStatusIndicator(netCalorie) {
    const statusEl = document.getElementById('status-indicator');

    let statusText = '';
    let statusClass = '';
    let statusIcon = '';

    if (netCalorie > 500) {
        statusText = '热量盈余较多，建议适当减少摄入或增加运动';
        statusClass = 'surplus';
        statusIcon = '⚠️';
    } else if (netCalorie > 100) {
        statusText = '轻度盈余，如需减重可适当调整';
        statusClass = 'surplus';
        statusIcon = 'ℹ️';
    } else if (netCalorie > -100) {
        statusText = '热量平衡状态，非常理想！';
        statusClass = 'balanced';
        statusIcon = '🌟';
    } else if (netCalorie > -300) {
        statusText = '轻度赤字，健康减重状态';
        statusClass = 'deficit';
        statusIcon = '💪';
    } else if (netCalorie > -500) {
        statusText = '中度赤字，减重效果明显，注意营养均衡';
        statusClass = 'deficit';
        statusIcon = '🎯';
    } else {
        statusText = '大幅赤字，减重效果显著，但需注意营养补充';
        statusClass = 'deficit';
        statusIcon = '💡';
    }

    // 更新状态指示器
    statusEl.innerHTML = `<span>${statusIcon}</span><span>${statusText}</span>`;
    statusEl.className = `status-indicator ${statusClass}`;
    statusEl.style.display = 'flex';
}

// 切换折叠/展开（绑定到window全局）
window.toggleCalorieCard = function() {
    const card = document.getElementById('calorie-balance-card');
    if (!card) {
        console.error('找不到热量平衡卡片');
        return;
    }
    
    const isCollapsed = card.classList.contains('collapsed');

    if (isCollapsed) {
        // 展开
        card.classList.remove('collapsed');
        // 首次展开时加载数据
        if (!card.dataset.loaded) {
            loadCalorieBalance();
            card.dataset.loaded = 'true';
        }
    } else {
        // 折叠
        card.classList.add('collapsed');
    }

    // 保存状态到localStorage
    localStorage.setItem('calorieCardExpanded', !isCollapsed);
};

// ============ 每日建议功能 ============

// 加载每日建议
async function loadDailySuggestion(forceRefresh = false) {
    // 检查是否已登录
    if (!Auth.check()) {
        console.log('用户未登录，跳过加载每日建议');
        return;
    }
    
    const contentEl = document.getElementById('suggestion-content');
    const actionEl = document.getElementById('suggestion-action');

    if (!contentEl || !actionEl) {
        console.log('建议卡片元素不存在');
        return;
    }

    if (!forceRefresh) {
        contentEl.innerHTML = `
            <div class="suggestion-loading">
                <div class="loading-spinner" style="width: 24px; height: 24px; border-width: 2px;"></div>
                <p>AI正在生成建议...</p>
            </div>
        `;
    }

    try {
        const url = forceRefresh
            ? `${API.base}/api/chat/daily-suggestion?refresh=true`
            : `${API.base}/api/chat/daily-suggestion`;

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);

        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${Auth.getToken()}`
            },
            signal: controller.signal
        });

        clearTimeout(timeoutId);
        const result = await response.json();

        console.log('每日建议响应:', result);

        if (result.success && result.suggestion) {
            displaySuggestion(result.suggestion);
        } else {
            console.log('建议加载失败或无数据，使用默认建议');
            displayDefaultSuggestion();
        }
    } catch (error) {
        console.error('加载建议失败:', error, error.message);
        if (error.name === 'AbortError') {
            console.log('请求超时');
        }
        displayDefaultSuggestion();
    }
}

// 显示建议
function displaySuggestion(suggestion) {
    const contentEl = document.getElementById('suggestion-content');
    const actionEl = document.getElementById('suggestion-action');

    if (!contentEl || !actionEl) {
        console.error('建议卡片元素不存在');
        return;
    }

    if (!suggestion || !suggestion.content) {
        console.error('建议数据无效:', suggestion);
        return;
    }

    contentEl.textContent = suggestion.content;

    // 显示关联操作按钮
    if (suggestion.action_text && suggestion.action_text !== '知道了') {
        actionEl.innerHTML = `
            <button class="suggestion-action-btn" onclick="handleSuggestionAction('${suggestion.action_type || ''}', '${suggestion.action_target || ''}')">
                ${suggestion.action_text}
            </button>
        `;
    } else {
        actionEl.innerHTML = '';
    }
}

// 刷新建议（全局函数）
window.refreshSuggestion = async function() {
    console.log('🔄 刷新建议按钮被点击');
    const refreshBtn = document.getElementById('refresh-btn');
    if (!refreshBtn) {
        console.error('❌ 找不到刷新按钮');
        return;
    }

    refreshBtn.disabled = true;
    refreshBtn.classList.add('spinning');

    try {
        await loadDailySuggestion(true);
        console.log('✅ 建议刷新成功');
    } catch (error) {
        console.error('❌ 刷新建议失败:', error);
        if (typeof Utils !== 'undefined' && Utils.toast) {
            Utils.toast('刷新失败，请重试', 'error');
        }
    } finally {
        refreshBtn.disabled = false;
        refreshBtn.classList.remove('spinning');
    }
}

// 处理建议操作（全局函数）
window.handleSuggestionAction = function(type, target) {
    if (type === 'navigate' && target) {
        window.location.href = `/static/${target}`;
    } else if (type === 'quick_action') {
        sendQuickMessage(target);
    }
}

// 默认建议（API失败时）
async function displayDefaultSuggestion() {
    try {
        let allDefaults = [];

        // 优先从服务器获取默认建议
        try {
            const response = await fetch(`${API.base}/api/config/default-suggestions`, {
                headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
            });

            if (response.ok) {
                const result = await response.json();
                if (result.success && result.suggestions) {
                    allDefaults = result.suggestions;
                }
            }
        } catch (e) {
            console.log('获取默认建议失败');
        }

        // 如果没有服务器建议，使用内置的
        if (allDefaults.length === 0) {
            allDefaults = [
                { content: "今天别忘了记录体重哦，坚持就是胜利！💪", action_text: "记录体重", action_target: "weight.html" },
                { content: "多喝水有助于新陈代谢，建议今天喝够2000ml~", action_text: "记录饮水", action_target: "water.html" },
                { content: "运动是健康的好伙伴，今天动起来吧！", action_text: "记录运动", action_target: "exercise.html" },
                { content: "💡 蛋白质是肌肉的基石，每餐摄入20-30g有助于维持代谢", action_text: "知道了", action_target: "" },
                { content: "💡 低GI食物能让血糖更平稳，饱腹感更持久", action_text: "知道了", action_target: "" },
                { content: "💡 快走30分钟约消耗150-200kcal", action_text: "知道了", action_target: "" },
                { content: "💡 每增加1kg肌肉，每天多消耗约100kcal", action_text: "知道了", action_target: "" },
                { content: "💡 基础代谢占每日消耗的60-70%", action_text: "知道了", action_target: "" },
                { content: "每一小步都是进步，今天也在变好的路上！🌟", action_text: "记录体重", action_target: "weight.html" },
                { content: "坚持记录是减重的第一步，你已经做得很好了！", action_text: "记录数据", action_target: "index.html" }
            ];
        }

        // 随机选择一条
        const random = allDefaults[Math.floor(Math.random() * allDefaults.length)];
        displaySuggestion({
            content: random.content,
            action_text: random.action_text,
            action_type: random.action_target ? "navigate" : "none",
            action_target: random.action_target || ""
        });
    } catch (e) {
        console.error('displayDefaultSuggestion 错误:', e);
    }
}

// 加载聊天历史（只显示最近10条）
let chatHistoryOffset = 0;
const CHAT_HISTORY_LIMIT = 10;

async function loadChatHistory(loadMore = false) {
    if (!Auth.check()) {
        return;
    }
    
    try {
        const container = document.getElementById('chat-messages');
        
        if (!loadMore) {
            chatHistoryOffset = 0;
            // 只删除聊天消息元素，保留静态卡片
            const balanceCard = document.getElementById('calorie-balance-card');
            const suggestionCard = document.getElementById('daily-suggestion-card');
            
            // 删除所有 message 类元素
            const messages = container.querySelectorAll('.message');
            messages.forEach(msg => msg.remove());
            
            // 如果没有静态卡片，重新添加
            if (!balanceCard) {
                console.log('热量平衡卡片丢失，重新加载页面');
            }
        }
        
        // 加载历史记录，每次10条
        const response = await API.chat.getHistory(CHAT_HISTORY_LIMIT, chatHistoryOffset);
        
        if (response.success && response.data) {
            const newMessages = response.data;
            
            if (newMessages.length > 0) {
                const suggestionCard = document.getElementById('daily-suggestion-card');
                if (suggestionCard && chatHistoryOffset === 0) suggestionCard.style.display = 'none';
                
                // 将新消息插入到列表开头（最旧的在前）
                const container = document.getElementById('chat-messages');
                
                if (!loadMore) {
                    // 首次加载：将消息插入到静态卡片之后
                    newMessages.forEach(msg => {
                        insertMessageAt(container, null, msg.role, msg.content, false, { message_type: 'text', actions: [] }, false);
                    });
                } else {
                    // 加载更多：将消息插入到最前面
                    const firstMessage = container.querySelector('.message');
                    newMessages.forEach(msg => {
                        const tempDiv = document.createElement('div');
                        container.insertBefore(tempDiv, firstMessage);
                        insertMessageAt(container, tempDiv, msg.role, msg.content, false, { message_type: 'text', actions: [] }, false);
                    });
                }
                
                chatHistoryOffset += newMessages.length;
                
                // 如果有更多记录，显示"加载更多"按钮
                updateLoadMoreButton(newMessages.length >= CHAT_HISTORY_LIMIT);
            }
        }
    } catch (error) {
        console.error('加载聊天历史失败:', error);
    }
}

// 在指定位置插入消息
function insertMessageAt(container, insertBeforeEl, role, content, animate, messageData, enableTypewriter) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${role}`;
    if (animate) {
        messageDiv.style.animation = 'slideInUp 0.3s ease';
    }

    const avatar = role === 'user' ? '👤' : '💡';
    const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

    let contentHtml = '';
    let textContent = '';
    let hasTypewriter = false;

    if (role === 'assistant' && enableTypewriter) {
        hasTypewriter = true;
    }

    if (role === 'assistant' && messageData) {
        const messageType = messageData.message_type || 'text';
        const actions = messageData.actions || [];

        let displayContent = content;
        const jsonMatch = displayContent.match(/\{"tools":\s*\[.*?\]\}/);
        if (jsonMatch) {
            displayContent = displayContent.replace(jsonMatch[0], '').trim();
        }

        textContent = displayContent;

        if (messageType === 'card' && messageData.data) {
            contentHtml = buildCardMessage(messageData.data);
        } else if (messageType === 'quick_reply' && actions.length > 0) {
            contentHtml = `<div class="message-text">${displayContent}</div>`;
            contentHtml += `<div class="message-actions">`;
            actions.forEach(action => {
                contentHtml += `<button class="action-btn" onclick="handleMessageAction('${action.action_type}', '${action.target}')">${action.label}</button>`;
            });
            contentHtml += `</div>`;
        } else if (messageType === 'image' && messageData.image_url) {
            contentHtml = `<div class="message-image"><img src="${messageData.image_url}" alt="图片"></div>`;
            if (displayContent) {
                contentHtml += `<div class="message-text">${displayContent}</div>`;
            }
        } else {
            contentHtml = `<div class="message-text">${displayContent.replace(/\n/g, '<br>')}</div>`;
        }
    } else {
        contentHtml = `<div class="message-text">${content.replace(/\n/g, '<br>')}</div>`;
    }

    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div>
            <div class="message-time">${time}</div>
            <div class="message-content">
                ${contentHtml}
            </div>
        </div>
    `;

    container.insertBefore(messageDiv, insertBeforeEl);

    if (hasTypewriter && textContent) {
        const textElement = messageDiv.querySelector('.message-text');
        if (textElement) {
            typeWriterHTML(textElement, textContent.replace(/\n/g, '<br>'));
        }
    }
}

// 更新加载更多按钮
function updateLoadMoreButton(hasMore) {
    let btn = document.getElementById('load-more-btn');
    if (!btn && hasMore) {
        const container = document.getElementById('chat-messages');
        btn = document.createElement('div');
        btn.id = 'load-more-btn';
        btn.className = 'load-more-btn';
        btn.innerHTML = '⬇️ 加载更多';
        btn.onclick = () => loadChatHistory(true);
        container.parentNode.insertBefore(btn, container);
    }
    if (btn) {
        btn.style.display = hasMore ? 'block' : 'none';
        if (hasMore) {
            btn.innerHTML = '⬇️ 加载更多历史';
        }
    }
}

// 发送消息（全局函数，供onclick调用）
window.sendMessage = async function() {
    const input = document.getElementById('chat-input');
    const content = input.value.trim();

    // 检查是否有内容或图片
    if ((!content && !selectedImage) || isSending) return;

    // 隐藏建议卡片
    const suggestionCard = document.getElementById('daily-suggestion-card');
    if (suggestionCard) suggestionCard.style.display = 'none';

    // 构建预览内容（只显示文本，图片单独显示）
    let previewContent = content || '请帮我看看这张图片里的食物';
    appendMessage('user', previewContent);

    // 如果有图片，添加图片预览到消息区域
    if (selectedImage) {
        const container = document.getElementById('chat-messages');
        const lastMessage = container.lastElementChild;
        const imgHtml = `<img src="${selectedImage.dataUrl}" style="max-width: 200px; border-radius: 8px; margin-top: 8px; display: block;">`;
        const contentDiv = lastMessage.querySelector('.message-content');
        contentDiv.innerHTML += imgHtml;
    }

    // 清空输入框和图片
    input.value = '';
    input.style.height = 'auto';
    clearImage();

    // 显示AI思考中
    const thinkingId = showThinking();

    // 更新发送按钮状态
    const sendBtn = document.getElementById('send-btn');
    sendBtn.disabled = true;
    isSending = true;

    try {
        // 构建请求数据
        const requestData = { content: content };

        // 如果有图片，先上传再发送
        if (selectedImage) {
            const uploadResult = await uploadImage(selectedImage.file);
            if (uploadResult.success) {
                requestData.image_url = uploadResult.url;
            } else {
                throw new Error('图片上传失败');
            }
        }

        const response = await API.chat.sendMessageWithImage(requestData);

        // 移除思考中提示
        removeThinking(thinkingId);

        if (response.success) {
            // 启用打字机效果（这是最新的AI回复）
            appendMessage('assistant', response.data.content, true, response.data, true);
        } else {
            appendMessage('assistant', '抱歉，我暂时无法回复。请稍后再试。', true, { message_type: 'text', actions: [] }, true);
        }
    } catch (error) {
        // 移除思考中提示
        removeThinking(thinkingId);

        console.error('发送消息失败:', error);
        appendMessage('抱歉，发送消息失败。请检查网络连接后重试。', false, { message_type: 'text', actions: [] }, false);

        // 显示错误提示
        Utils.toast('发送失败，请重试', 'error');
    } finally {
        sendBtn.disabled = false;
        isSending = false;
    }
}

// 发送快捷消息（全局函数）
window.sendQuickMessage = function(content) {
    const input = document.getElementById('chat-input');
    input.value = content;
    window.sendMessage();
}

// 支持HTML标签的打字机效果
function typeWriterHTML(element, html, speed = 20) {
    // 创建一个临时容器来解析HTML
    const temp = document.createElement('div');
    temp.innerHTML = html;

    // 简化为纯文本打字机（保留换行）
    const plainText = temp.textContent;
    const cursor = document.createElement('span');
    cursor.className = 'typewriter-cursor';

    element.innerHTML = '';
    element.appendChild(cursor);
    element.classList.add('typewriter-content');

    // 开始打字前先滚动到底部
    const container = document.getElementById('chat-messages');
    container.scrollTop = container.scrollHeight;

    let i = 0;
    const chars = plainText.split('');

    function type() {
        if (i < chars.length) {
            const char = chars[i];
            const textNode = document.createTextNode(char);
            element.insertBefore(textNode, cursor);
            i++;

            // 自动滚动到底部
            const container = document.getElementById('chat-messages');
            container.scrollTop = container.scrollHeight;

            // 根据字符类型调整速度（标点符号稍慢）
            let delay = speed;
            if ('，。！？；：'.includes(char)) delay = speed * 3;
            if (char === '\n') delay = speed * 2;

            setTimeout(type, delay);
        } else {
            // 打字完成，恢复原始HTML格式
            element.classList.add('typewriter-complete');
            cursor.remove();
            // 最后设置完整的HTML（保留格式）
            element.innerHTML = html;
        }
    }

    type();
}

// 添加消息到聊天区域（支持富媒体）
// role: 'user' 或 'assistant'
// animate: 是否播放入场动画
// enableTypewriter: 是否启用打字机效果（仅对AI的最新回复启用）
function appendMessage(role, content, animate = true, messageData = null, enableTypewriter = false) {
    const container = document.getElementById('chat-messages');

    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${role}`;
    if (animate) {
        messageDiv.style.animation = 'slideInUp 0.3s ease';
    }

    const avatar = role === 'user' ? '👤' : '💡';
    const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

    // 构建消息内容
    let contentHtml = '';
    let textContent = ''; // 用于打字机效果的纯文本内容
    let hasTypewriter = false; // 是否需要打字机效果

    // 只有明确启用打字机且是AI消息时才启用
    if (role === 'assistant' && enableTypewriter) {
        hasTypewriter = true;
    }

    if (role === 'assistant' && messageData) {
        // AI消息，检查是否有富媒体内容
        const messageType = messageData.message_type || 'text';
        const actions = messageData.actions || [];

        // 解析内容（移除可能的工具调用JSON）
        let displayContent = content;
        const jsonMatch = displayContent.match(/\{"tools":\s*\[.*?\]\}/);
        if (jsonMatch) {
            displayContent = displayContent.replace(jsonMatch[0], '').trim();
        }

        // 检查是否是图片消息 - 图片直接显示，不使用打字机
        if (displayContent.includes('data:image/')) {
            const base64Match = displayContent.match(/data:image\/[a-zA-Z]+;base64,[A-Za-z0-9+/=]+/);
            if (base64Match) {
                contentHtml += `<img src="${base64Match[0]}" style="max-width: 200px; border-radius: 8px; margin-bottom: 8px;">`;
                displayContent = displayContent.replace(base64Match[0], '').trim();
            }
        }

        // 添加文本内容（给容器一个ID，用于打字机效果）
        if (displayContent) {
            const textId = `msg-text-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            contentHtml += `<div class="message-text" id="${textId}"></div>`;
            textContent = displayContent;
            hasTypewriter = true;
        }

        // 添加快捷操作按钮（富媒体）
        if (actions && actions.length > 0) {
            contentHtml += '<div class="message-actions">';
            actions.forEach(action => {
                if (action.type === 'button') {
                    contentHtml += `
                        <button class="message-action-btn" onclick="handleMessageAction('${action.action}', '${action.target}')">
                            ${action.text}
                        </button>
                    `;
                }
            });
            contentHtml += '</div>';
        }
    } else {
        // 用户消息或其他
        let displayContent = content;

        // 检查是否是图片消息
        if (displayContent.includes('data:image/')) {
            const base64Match = displayContent.match(/data:image\/[a-zA-Z]+;base64,[A-Za-z0-9+/=]+/);
            if (base64Match) {
                contentHtml += `<img src="${base64Match[0]}" style="max-width: 200px; border-radius: 8px; margin-bottom: 8px;">`;
                displayContent = displayContent.replace(base64Match[0], '').trim();
            }
        }

        if (displayContent) {
            contentHtml = escapeHtml(displayContent).replace(/\n/g, '<br>');
        }
    }

    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-body">
            <div class="message-content">${contentHtml}</div>
            <div class="message-time">${time}</div>
        </div>
    `;

    container.appendChild(messageDiv);

    // 如果是助手消息且有文本内容，启动打字机效果
    if (hasTypewriter && textContent) {
        const textElement = messageDiv.querySelector('.message-text');
        if (textElement) {
            // 使用打字机效果显示文本（支持HTML标签）
            typeWriterHTML(textElement, textContent.replace(/\n/g, '<br>'));
        }
    } else {
        // 非打字机效果的消息，滚动到底部
        setTimeout(() => {
            container.scrollTop = container.scrollHeight;
        }, 10);
    }
}

// 处理消息中的快捷操作
function handleMessageAction(action, target) {
    if (action === 'navigate' && target) {
        window.location.href = target;
    } else if (action === 'quick_action') {
        sendQuickMessage(target);
    }
}

// 显示思考中
function showThinking() {
    const container = document.getElementById('chat-messages');
    const id = 'thinking-' + Date.now();

    const thinkingDiv = document.createElement('div');
    thinkingDiv.id = id;
    thinkingDiv.className = 'message message-assistant';
    thinkingDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div>
            <div class="message-content">
                <div class="message-thinking">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>
    `;

    container.appendChild(thinkingDiv);
    setTimeout(() => {
        container.scrollTop = container.scrollHeight;
    }, 10);

    return id;
}

// 移除思考中
function removeThinking(id) {
    const thinking = document.getElementById(id);
    if (thinking) {
        thinking.remove();
    }
}

// HTML转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 页面级认证检查
document.addEventListener('DOMContentLoaded', () => {
    if (!Auth.check()) {
        window.location.href = 'login.html';
        return;
    }

    // 监听 localStorage 事件，自动刷新热量平衡数据
    window.addEventListener('storage', (e) => {
        if (e.key === 'mealUpdated' || e.key === 'exerciseUpdated' || e.key === 'weightUpdated') {
            console.log('检测到数据更新，自动刷新热量平衡卡片...');
            loadCalorieBalance();
        }
    });

    // 侧边栏菜单功能
    const menuToggle = document.querySelector('.menu-toggle');
    const overlay = document.querySelector('.sidebar-overlay');

    if (menuToggle) {
        menuToggle.onclick = () => {
            document.body.classList.add('menu-open');
        };
    }

    if (overlay) {
        overlay.onclick = () => {
            document.body.classList.remove('menu-open');
        };
    }

    document.onkeydown = (e) => {
        if (e.key === 'Escape') {
            document.body.classList.remove('menu-open');
        }
    };
});
