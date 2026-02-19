/**
 * 用户画像收集模块
 * 支持交互式问答，模拟企业微信主动推送
 */

const Profiling = {
    // 当前问题
    currentQuestion: null,
    
    // 初始化
    init() {
        // 页面加载后不立即显示，等用户有交互后再推送
        // 模拟企业微信的"适时推送"
        setTimeout(() => {
            this.checkAndShowQuestion();
        }, 3000); // 3秒后检查
        
        // 每5分钟检查一次是否需要推送新问题
        setInterval(() => {
            this.checkAndShowQuestion();
        }, 5 * 60 * 1000);
    },
    
    // 检查并显示问题
    async checkAndShowQuestion() {
        // 如果已经有问题在显示，不再推送
        if (document.getElementById('profiling-question-card')) {
            return;
        }
        
        // 检查核心问题是否已完成
        try {
            const coreResponse = await fetch(`${API.base}/api/profiling/core-progress`, {
                headers: {
                    'Authorization': `Bearer ${Auth.getToken()}`
                }
            });
            
            const coreResult = await coreResponse.json();
            
            // 如果核心问题未完成，不进行随机推送
            if (coreResult.success && !coreResult.is_completed) {
                return;
            }
        } catch (error) {
            console.error('检查核心问题进度失败:', error);
        }
        
        try {
            const response = await fetch(`${API.base}/api/profiling/next-question`, {
                headers: {
                    'Authorization': `Bearer ${Auth.getToken()}`
                }
            });
            
            const result = await response.json();
            
            if (result.success && result.has_question && result.should_push) {
                this.showQuestion(result.question);
            }
        } catch (error) {
            console.error('获取画像问题失败:', error);
        }
    },
    
    // 显示问题卡片
    showQuestion(question) {
        if (!question || (!question.options && !question.fields)) {
            console.error('Invalid question data:', question);
            return;
        }

        // 创建问题卡片
        const card = document.createElement('div');
        card.id = 'profiling-question-card';
        card.className = 'profiling-question-card animate-slide-in-up';

        let contentHtml = '';

        // 表单类型问题（使用fields）
        if (question.type === 'form' && question.fields) {
            contentHtml = question.fields.map(field => `
                <div class="profiling-field" data-name="${field.name}">
                    <label class="profiling-field-label">${field.label || field.name}</label>
                    ${this._renderFieldInput(field)}
                </div>
            `).join('');
        } else {
            // 选择题类型（使用options）
            const optionsHtml = question.options.map((opt, index) => `
                <button class="profiling-option-btn" onclick="Profiling.submitAnswer('${question.id}', '${opt.value}', '${opt.text}')" style="animation-delay: ${index * 0.1}s">
                    <span class="option-emoji">${opt.emoji || ''}</span>
                    <span class="option-text">${opt.text}</span>
                </button>
            `).join('');
            contentHtml = `
                <p class="profiling-question">${question.question_text}</p>
                <div class="profiling-options">
                    ${optionsHtml}
                </div>
            `;
        }

        card.innerHTML = `
            <div class="profiling-header">
                <span class="profiling-icon">💬</span>
                <span class="profiling-title">小调查</span>
                <button class="profiling-close" onclick="Profiling.dismissQuestion()" title="稍后再说">✕</button>
            </div>
            <div class="profiling-content">
                ${contentHtml}
            </div>
            ${question.type === 'form' ? `
            <div class="profiling-footer">
                <button class="btn btn-primary" onclick="Profiling.submitFormAnswer('${question.id}')" style="width: 100%;">提交</button>
            </div>
            ` : `
            <div class="profiling-footer">
                <span class="profiling-progress">了解你 ${question.progress?.percentage || 0}%</span>
                <button class="profiling-skip" onclick="Profiling.skipQuestion()">跳过</button>
            </div>
            `}
        `;
        
        // 插入到聊天区域顶部
        const chatContainer = document.getElementById('chat-messages');
        if (chatContainer) {
            // 如果有每日建议卡片，插入在它后面
            const suggestionCard = document.getElementById('daily-suggestion-card');
            if (suggestionCard && suggestionCard.nextSibling) {
                chatContainer.insertBefore(card, suggestionCard.nextSibling);
            } else {
                chatContainer.insertBefore(card, chatContainer.firstChild);
            }
        }
        
        this.currentQuestion = question;
        
        // 3秒后自动滚动到问题卡片
        setTimeout(() => {
            card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 500);
    },
    
    // 渲染表单字段输入框
    _renderFieldInput(field) {
        const placeholder = field.placeholder || '';
        const min = field.min || '';
        const max = field.max || '';

        if (field.input_type === 'select' && field.options) {
            return `
                <select class="profiling-field-input" data-name="${field.name}">
                    <option value="">请选择${field.label}</option>
                    ${field.options.map(opt => `
                        <option value="${opt.value}">${opt.text}</option>
                    `).join('')}
                </select>
            `;
        } else {
            return `
                <input type="${field.input_type || 'text'}"
                       class="profiling-field-input"
                       data-name="${field.name}"
                       placeholder="${placeholder}"
                       ${min ? `min="${min}"` : ''}
                       ${max ? `max="${max}"` : ''}
                       ${field.unit ? `data-unit="${field.unit}"` : ''}>
            `;
        }
    },

    // 提交表单答案 - 使用简化版API
    async submitFormAnswer(questionId) {
        const card = document.getElementById('profiling-question-card');
        if (!card) {
            console.error('Card not found');
            return;
        }

        const fields = card.querySelectorAll('.profiling-field');
        const answers = {};

        fields.forEach(fieldEl => {
            const name = fieldEl.dataset.name;
            const input = fieldEl.querySelector('input, select');
            if (input) {
                answers[name] = input.value;
            }
        });

        console.log('Submitting form answers:', answers);

        // 验证必填
        for (const [key, value] of Object.entries(answers)) {
            if (!value) {
                Utils.toast('请填写完整信息', 'error');
                return;
            }
        }

        try {
            console.log('Using simplified API...');
            const response = await fetch(`${API.base}/api/profiling/submit-form`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${Auth.getToken()}`
                },
                body: JSON.stringify({
                    question_id: questionId,
                    answer_value: JSON.stringify(answers)
                })
            });

            console.log('Response status:', response.status);
            const result = await response.json();
            console.log('Response data:', result);

            if (result.success) {
                this.showFeedback(result.ai_feedback);
                setTimeout(() => {
                    this.removeQuestionCard();
                }, 2000);
            } else {
                throw new Error(result.detail || result.message || '提交失败');
            }
        } catch (error) {
            console.error('提交表单失败:', error);
            Utils.toast('提交失败，请重试', 'error');
        }
    },

    // 提交回答
    async submitAnswer(questionId, answerValue, answerText) {
        const card = document.getElementById('profiling-question-card');
        if (!card) {
            console.error('Card not found');
            return;
        }

        // 显示提交中状态
        const options = card.querySelectorAll('.profiling-option-btn');
        options.forEach(btn => btn.disabled = true);

        try {
            console.log('Submitting answer:', { questionId, answerValue, answerText });
            const response = await fetch(`${API.base}/api/profiling/answer`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${Auth.getToken()}`
                },
                body: JSON.stringify({
                    question_id: questionId,
                    answer_value: answerValue,
                    answer_text: answerText
                })
            });

            console.log('Response status:', response.status);
            const result = await response.json();
            console.log('Response data:', result);

            if (result.success) {
                // 显示AI反馈
                this.showFeedback(result.ai_feedback);

                // 2秒后移除卡片
                setTimeout(() => {
                    this.removeQuestionCard();

                    // 如果还有下一个问题，延迟后显示
                    if (result.next_action && Math.random() > 0.5) {
                        setTimeout(() => {
                            this.checkAndShowQuestion();
                        }, 2000);
                    }
                }, 2000);
            } else {
                throw new Error(result.message || '提交失败');
            }
        } catch (error) {
            console.error('提交回答失败:', error);
            Utils.toast('提交失败，请重试', 'error');
            options.forEach(btn => btn.disabled = false);
        }
    },
    
    // 显示AI反馈
    showFeedback(feedback) {
        const card = document.getElementById('profiling-question-card');
        if (!card) return;
        
        const content = card.querySelector('.profiling-content');
        const options = card.querySelector('.profiling-options');
        const footer = card.querySelector('.profiling-footer');
        
        // 隐藏选项和footer
        if (options) options.style.display = 'none';
        if (footer) footer.style.display = 'none';
        
        // 添加反馈消息
        const feedbackEl = document.createElement('div');
        feedbackEl.className = 'profiling-feedback animate-fade-in';
        feedbackEl.innerHTML = `
            <div class="feedback-bubble">
                <span class="feedback-icon">🤖</span>
                <span class="feedback-text">${feedback}</span>
            </div>
        `;
        content.appendChild(feedbackEl);
    },
    
    // 跳过问题
    skipQuestion() {
        this.removeQuestionCard();
        // 记录跳过，避免立即再次推送
        Utils.toast('好的，我们稍后再聊~', 'info');
    },
    
    // 关闭问题
    dismissQuestion() {
        this.removeQuestionCard();
    },
    
    // 移除问题卡片
    removeQuestionCard() {
        const card = document.getElementById('profiling-question-card');
        if (card) {
            card.style.animation = 'slideInUp 0.3s ease reverse';
            setTimeout(() => card.remove(), 300);
        }
        this.currentQuestion = null;
    },
    
    // 手动触发获取问题（用于测试）
    async forceShowQuestion() {
        // 检查核心问题是否已完成
        try {
            const coreResponse = await fetch(`${API.base}/api/profiling/core-progress`, {
                headers: {
                    'Authorization': `Bearer ${Auth.getToken()}`
                }
            });
            
            const coreResult = await coreResponse.json();
            
            // 如果核心问题未完成，显示核心问题收集界面
            if (coreResult.success && !coreResult.is_completed) {
                if (typeof coreProfiling !== 'undefined') {
                    coreProfiling.show();
                    return;
                }
            }
        } catch (error) {
            console.error('检查核心问题进度失败:', error);
        }
        
        try {
            const response = await fetch(`${API.base}/api/profiling/next-question?force_new=true`, {
                headers: {
                    'Authorization': `Bearer ${Auth.getToken()}`
                }
            });
            
            const result = await response.json();
            
            if (result.success && result.has_question) {
                // 如果已有问题在显示，先移除
                this.removeQuestionCard();
                setTimeout(() => this.showQuestion(result.question), 300);
            } else if (!result.has_question) {
                Utils.toast('太棒了！我已经足够了解你了~', 'success');
            }
        } catch (error) {
            console.error('获取问题失败:', error);
            Utils.toast('获取失败，请重试', 'error');
        }
    },
    
    // 获取画像进度
    async getProgress() {
        try {
            const response = await fetch(`${API.base}/api/profiling/progress`, {
                headers: {
                    'Authorization': `Bearer ${Auth.getToken()}`
                }
            });
            
            const result = await response.json();
            return result;
        } catch (error) {
            console.error('获取进度失败:', error);
            return null;
        }
    }
};

// 导出
window.Profiling = Profiling;
