/**
 * 核心用户画像收集组件
 * 处理7个核心问题的强制连续收集
 */

class CoreProfiling {
    constructor(options = {}) {
        this.containerId = options.containerId || 'core-profiling-container';
        this.onComplete = options.onComplete || null;
        this.onCancel = options.onCancel || null;
        
        this.currentQuestion = null;
        this.answeredCount = 0;
        this.totalCoreQuestions = 7;
        
        this.init();
    }
    
    init() {
        // 检查容器是否存在
        if (!document.getElementById(this.containerId)) {
            this.createContainer();
        }
        
        // 检查核心问题完成状态
        this.checkCoreProgress();
    }
    
    createContainer() {
        const container = document.createElement('div');
        container.id = this.containerId;
        container.className = 'core-profiling-container';
        container.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255, 255, 255, 0.98);
            z-index: 9999;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        `;
        
        document.body.appendChild(container);
    }
    
    async checkCoreProgress() {
        const token = localStorage.getItem('token');
        if (!token) {
            // 用户未登录，显示登录提示
            this.showLoginPrompt();
            return;
        }
        
        try {
            const response = await fetch('/api/profiling/core-progress', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (response.status === 401) {
                // Token过期或无效，显示登录提示
                this.showLoginPrompt();
                return;
            }
            
            const data = await response.json();
            
            if (data.success) {
                if (data.is_completed) {
                    // 核心问题已完成，隐藏容器
                    this.hide();
                    if (this.onComplete) {
                        this.onComplete();
                    }
                } else {
                    // 有未回答的核心问题，开始收集
                    this.show();
                    this.loadNextQuestion();
                }
            }
        } catch (error) {
            console.error('检查核心问题进度失败:', error);
            this.hide();
        }
    }
    
    showLoginPrompt() {
        const container = document.getElementById(this.containerId);
        if (!container) return;
        
        container.innerHTML = `
            <div class="core-profiling-login-prompt">
                <div class="login-prompt-icon">🔐</div>
                <div class="login-prompt-title">请先登录</div>
                <div class="login-prompt-text">登录后即可开始个性化健康评估</div>
                <button class="login-prompt-btn" onclick="window.location.href='/login.html'">
                    立即登录
                </button>
                <button class="login-prompt-skip" onclick="document.getElementById('${this.containerId}').style.display='none'">
                    稍后再说
                </button>
            </div>
        `;
        container.style.display = 'flex';
    }
    
    async loadNextQuestion() {
        try {
            const response = await fetch('/api/profiling/next-question?force_new=true', {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
                }
            });
            const data = await response.json();
            
            if (data.success && data.has_question) {
                this.currentQuestion = data.question;
                this.answeredCount = data.progress.core.answered || 0;
                this.renderQuestion();
            } else {
                // 没有更多问题，可能是所有问题都已完成
                this.showCompletionScreen();
            }
        } catch (error) {
            console.error('加载下一个问题失败:', error);
        }
    }
    
    renderQuestion() {
        const container = document.getElementById(this.containerId);
        if (!container || !this.currentQuestion) return;
        
        const progressPercentage = Math.round((this.answeredCount / this.totalCoreQuestions) * 100);
        
        container.innerHTML = `
            <div class="core-profiling-card" style="
                max-width: 500px;
                width: 100%;
                background: white;
                border-radius: 16px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
                overflow: hidden;
                border: 1px solid #e9ecef;
            ">
                <!-- 进度条 -->
                <div class="progress-bar" style="
                    height: 6px;
                    background: #e9ecef;
                    position: relative;
                ">
                    <div class="progress-fill" style="
                        position: absolute;
                        top: 0;
                        left: 0;
                        height: 100%;
                        background: linear-gradient(90deg, #34c759, #00c7ff);
                        width: ${progressPercentage}%;
                        transition: width 0.3s ease;
                    "></div>
                </div>
                
                <!-- 进度文本 -->
                <div class="progress-text" style="
                    padding: 16px 24px 8px;
                    text-align: center;
                    color: #6c757d;
                    font-size: 14px;
                    font-weight: 500;
                ">
                    问题 ${this.answeredCount + 1}/${this.totalCoreQuestions}
                </div>
                
                <!-- 问题标题 -->
                <div class="question-header" style="
                    padding: 0 24px 16px;
                    text-align: center;
                ">
                    <h2 style="
                        margin: 0;
                        font-size: 20px;
                        font-weight: 600;
                        color: #212529;
                        line-height: 1.4;
                    ">
                        ${this.currentQuestion.question_text}
                    </h2>
                </div>
                
                <!-- 问题内容 -->
                <div class="question-content" style="
                    padding: 0 24px 24px;
                    min-height: 200px;
                ">
                    ${this.renderQuestionContent()}
                </div>
                
                <!-- 底部提示 -->
                <div class="question-footer" style="
                    padding: 16px 24px;
                    background: #f8f9fa;
                    border-top: 1px solid #e9ecef;
                    text-align: center;
                    color: #6c757d;
                    font-size: 13px;
                ">
                    只需1分钟，获得专属建议
                </div>
            </div>
        `;
    }
    
    renderQuestionContent() {
        if (!this.currentQuestion) return '';
        
        if (this.currentQuestion.type === 'form') {
            return this.renderFormQuestion();
        } else {
            return this.renderChoiceQuestion();
        }
    }
    
    renderFormQuestion() {
        const fields = this.currentQuestion.fields || [];
        
        let html = '<div class="form-fields" style="display: flex; flex-direction: column; gap: 16px;">';
        
        fields.forEach(field => {
            html += this.renderFormField(field);
        });
        
        html += `
            <button class="submit-form-btn" style="
                margin-top: 24px;
                padding: 14px 24px;
                background: linear-gradient(135deg, #34c759, #00c7ff);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
            " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 8px 25px rgba(52, 199, 89, 0.3)'"
            onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'"
            onclick="coreProfiling.submitFormAnswer()">
                提交
            </button>
        </div>`;
        
        return html;
    }
    
    renderFormField(field) {
        let html = `<div class="form-field" style="display: flex; flex-direction: column; gap: 8px;">`;
        html += `<label style="font-weight: 500; color: #495057; font-size: 15px;">${field.label}</label>`;
        
        if (field.input_type === 'select') {
            html += `<select class="form-select" data-field="${field.name}" style="
                padding: 12px 16px;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                font-size: 15px;
                background: white;
                color: #212529;
                transition: border-color 0.2s;
            " onfocus="this.style.borderColor='#34c759'" onblur="this.style.borderColor='#e9ecef'">`;
            
            field.options.forEach(option => {
                html += `<option value="${option.value}">${option.text}</option>`;
            });
            
            html += `</select>`;
        } else if (field.input_type === 'number') {
            html += `<div style="display: flex; align-items: center; gap: 8px;">`;
            html += `<input type="number" class="form-input" data-field="${field.name}" style="
                flex: 1;
                padding: 12px 16px;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                font-size: 15px;
                background: white;
                color: #212529;
                transition: border-color 0.2s;
            " placeholder="${field.placeholder || ''}" min="${field.min || 0}" max="${field.max || 999}"
            onfocus="this.style.borderColor='#34c759'" onblur="this.style.borderColor='#e9ecef'">`;
            
            if (field.unit) {
                html += `<span style="color: #6c757d; font-size: 15px;">${field.unit}</span>`;
            }
            
            html += `</div>`;
        }
        
        html += `</div>`;
        return html;
    }
    
    renderChoiceQuestion() {
        const options = this.currentQuestion.options || [];
        
        let html = '<div class="choice-options" style="display: flex; flex-direction: column; gap: 12px;">';
        
        options.forEach(option => {
            html += `
                <button class="choice-option" data-value="${option.value}" style="
                    padding: 16px 20px;
                    background: white;
                    border: 2px solid #e9ecef;
                    border-radius: 12px;
                    text-align: left;
                    font-size: 15px;
                    color: #212529;
                    cursor: pointer;
                    transition: all 0.2s;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                " onmouseover="this.style.borderColor='#34c759'; this.style.transform='translateY(-2px)'"
                onmouseout="this.style.borderColor='#e9ecef'; this.style.transform='translateY(0)'"
                onclick="coreProfiling.selectOption('${option.value}', '${option.text.replace(/'/g, "\\'")}')">
                    <span style="font-size: 18px;">${option.emoji || '○'}</span>
                    <span style="flex: 1;">${option.text}</span>
                </button>
            `;
        });
        
        html += `</div>`;
        return html;
    }
    
    async submitFormAnswer() {
        const formData = {};
        const selects = document.querySelectorAll('.form-select');
        const inputs = document.querySelectorAll('.form-input');
        
        // 收集选择框数据
        selects.forEach(select => {
            const fieldName = select.getAttribute('data-field');
            formData[fieldName] = select.value;
        });
        
        // 收集输入框数据
        inputs.forEach(input => {
            const fieldName = input.getAttribute('data-field');
            const value = input.value.trim();
            if (value) {
                formData[fieldName] = value;
            }
        });
        
        if (Object.keys(formData).length === 0) {
            alert('请填写所有字段');
            return;
        }
        
        try {
            const response = await fetch('/api/profiling/submit-form', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
                },
                body: JSON.stringify({
                    question_id: this.currentQuestion.id,
                    answer_value: JSON.stringify(formData)
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // 显示AI反馈
                this.showAIFeedback(data.ai_feedback || '收到！');
                
                // 延迟后加载下一个问题
                setTimeout(() => {
                    this.loadNextQuestion();
                }, 1500);
            } else {
                alert('提交失败，请重试');
            }
        } catch (error) {
            console.error('提交表单失败:', error);
            alert('网络错误，请重试');
        }
    }
    
    async selectOption(value, text) {
        try {
            const response = await fetch('/api/profiling/answer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
                },
                body: JSON.stringify({
                    question_id: this.currentQuestion.id,
                    answer_value: value,
                    answer_text: text
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // 显示AI反馈
                this.showAIFeedback(data.ai_feedback || '了解了！');
                
                // 延迟后加载下一个问题
                setTimeout(() => {
                    this.loadNextQuestion();
                }, 1500);
            } else {
                alert('提交失败，请重试');
            }
        } catch (error) {
            console.error('提交选项失败:', error);
            alert('网络错误，请重试');
        }
    }
    
    showAIFeedback(message) {
        const container = document.getElementById(this.containerId);
        if (!container) return;
        
        const card = container.querySelector('.core-profiling-card');
        if (!card) return;
        
        const feedbackDiv = document.createElement('div');
        feedbackDiv.className = 'ai-feedback';
        feedbackDiv.style.cssText = `
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(255, 255, 255, 0.95);
            padding: 24px 32px;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
            text-align: center;
            z-index: 10;
            animation: fadeIn 0.3s ease;
        `;
        
        feedbackDiv.innerHTML = `
            <div style="font-size: 48px; margin-bottom: 16px;">✨</div>
            <div style="font-size: 18px; color: #212529; font-weight: 500; line-height: 1.4;">
                ${message}
            </div>
        `;
        
        card.style.position = 'relative';
        card.appendChild(feedbackDiv);
        
        // 3秒后移除反馈
        setTimeout(() => {
            feedbackDiv.remove();
        }, 1500);
    }
    
    showCompletionScreen() {
        const container = document.getElementById(this.containerId);
        if (!container) return;
        
        container.innerHTML = `
            <div class="completion-screen" style="
                max-width: 500px;
                width: 100%;
                text-align: center;
                padding: 40px 24px;
            ">
                <div style="font-size: 64px; margin-bottom: 24px;">🎉</div>
                <h2 style="
                    margin: 0 0 16px;
                    font-size: 28px;
                    font-weight: 700;
                    color: #212529;
                ">
                    太棒了！
                </h2>
                <p style="
                    margin: 0 0 32px;
                    font-size: 16px;
                    color: #6c757d;
                    line-height: 1.6;
                ">
                    我已经足够了解你了<br>
                    现在可以开始你的健康之旅了！
                </p>
                
                <div style="
                    background: #f8f9fa;
                    border-radius: 12px;
                    padding: 24px;
                    margin-bottom: 32px;
                    text-align: left;
                ">
                    <h3 style="
                        margin: 0 0 16px;
                        font-size: 18px;
                        font-weight: 600;
                        color: #212529;
                    ">
                        👋 你好，我是小助
                    </h3>
                    <p style="
                        margin: 0 0 12px;
                        font-size: 15px;
                        color: #495057;
                        line-height: 1.5;
                    ">
                        你的专属体重管理助手
                    </p>
                    <ul style="
                        margin: 0;
                        padding-left: 20px;
                        color: #495057;
                        font-size: 14px;
                        line-height: 1.6;
                    ">
                        <li>✓ 追踪每日体重变化</li>
                        <li>✓ 记录和分析饮食</li>
                        <li>✓ 规划适合的运动</li>
                        <li>✓ 提供个性化建议</li>
                    </ul>
                </div>
                
                <div style="display: flex; flex-direction: column; gap: 12px;">
                    <button class="continue-btn" style="
                        padding: 16px 24px;
                        background: linear-gradient(135deg, #34c759, #00c7ff);
                        color: white;
                        border: none;
                        border-radius: 12px;
                        font-size: 16px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: transform 0.2s;
                    " onmouseover="this.style.transform='translateY(-2px)'"
                    onmouseout="this.style.transform='translateY(0)'"
                    onclick="coreProfiling.hide()">
                        开始体验
                    </button>
                    
                    <button class="more-questions-btn" style="
                        padding: 16px 24px;
                        background: white;
                        color: #34c759;
                        border: 2px solid #34c759;
                        border-radius: 12px;
                        font-size: 16px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.2s;
                    " onmouseover="this.style.background='#f0fff4'"
                    onmouseout="this.style.background='white'"
                    onclick="coreProfiling.showExtendedQuestions()">
                        继续了解我
                    </button>
                </div>
            </div>
        `;
    }
    
    showExtendedQuestions() {
        // 隐藏核心问题容器，让原有的随机推送逻辑接管
        this.hide();
        
        // 触发原有的画像推送
        if (typeof Profiling !== 'undefined' && typeof Profiling.forceShowQuestion === 'function') {
            setTimeout(() => {
                Profiling.forceShowQuestion();
            }, 500);
        }
    }
    
    show() {
        const container = document.getElementById(this.containerId);
        if (container) {
            container.style.display = 'flex';
        }
    }
    
    hide() {
        const container = document.getElementById(this.containerId);
        if (container) {
            container.style.display = 'none';
        }
        
        if (this.onComplete) {
            this.onComplete();
        }
    }
}

// 创建全局实例
window.coreProfiling = new CoreProfiling({
    onComplete: function() {
        console.log('核心问题收集完成');
        // 可以在这里触发其他初始化逻辑
    }
});

// 添加CSS动画
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeIn {
        from { opacity: 0; transform: translate(-50%, -50%) scale(0.9); }
        to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
    }
    
    .choice-option.selected {
        background: linear-gradient(135deg, #34c759, #00c7ff) !important;
        color: white !important;
        border-color: transparent !important;
    }
`;
document.head.appendChild(style);