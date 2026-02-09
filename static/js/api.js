/**
 * API 封装模块
 * 统一管理所有后端API调用
 */

const API_BASE = 'http://localhost:8000';

// API 错误类
class APIError extends Error {
    constructor(message, status, data) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.data = data;
    }
}

/**
 * 通用请求函数
 */
async function request(url, options = {}) {
    const token = localStorage.getItem('token');

    const headers = {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
        ...(options.headers || {})
    };

    const finalOptions = {
        method: options.method || 'GET',
        headers: headers,
        body: options.body
    };

    // GET请求不需要body
    if (finalOptions.method === 'GET') {
        delete finalOptions.body;
    }

    try {
        const response = await fetch(`${API_BASE}${url}`, finalOptions);
        
        // 尝试解析JSON响应
        let data;
        try {
            data = await response.json();
        } catch (jsonError) {
            // 如果响应不是JSON，读取文本内容
            const text = await response.text();
            throw new APIError(
                `服务器返回了无效的JSON响应: ${text.substring(0, 100)}`,
                response.status,
                { raw: text }
            );
        }

        if (!response.ok) {
            throw new APIError(
                data.error || data.message || `HTTP ${response.status}`,
                response.status,
                data
            );
        }

        return data;
    } catch (error) {
        if (error.name === 'APIError') {
            throw error;
        }
        // 网络错误
        throw new APIError(error.message || '网络请求失败', 0, null);
    }
}

/**
 * 用户相关API
 */
const userAPI = {
    // 登录
    login: (code) => {
        return request(`/api/user/login?code=${encodeURIComponent(code)}`, {
            method: 'POST'
        });
    },
    
    // 获取用户信息
    getProfile: () => {
        return request('/api/user/profile');
    },
    
    // 更新用户信息
    updateProfile: (data) => {
        return request('/api/user/profile', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    // 获取Agent配置
    getAgentConfig: () => {
        return request('/api/user/agent/config');
    },
    
    // 更新Agent配置
    updateAgentConfig: (data) => {
        return request('/api/user/agent/config', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    // 获取助手风格列表
    getAgentStyles: () => {
        return request('/api/user/agent/styles');
    }
};

/**
 * 聊天相关API
 */
const chatAPI = {
    // 发送文本消息（旧版，非流式）
    sendMessage: (content) => {
        return request('/api/chat/send', {
            method: 'POST',
            body: JSON.stringify({ content })
        });
    },

    // 发送消息（支持图片）- 返回完整响应
    sendMessageWithImage: (data) => {
        return request('/api/chat/send', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    // 流式发送消息（新版，推荐）
    streamMessage: async (content, callbacks = {}) => {
        const token = localStorage.getItem('token');

        const response = await fetch(`${API_BASE}/api/chat/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ content })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let buffer = '';
        let fullContent = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // 解析 SSE 格式
            const lines = buffer.split('\n');
            buffer = '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));

                        if (data.done) {
                            // 流结束
                            if (callbacks.onComplete) {
                                callbacks.onComplete(fullContent);
                            }
                        } else if (data.type === 'text') {
                            // 文本内容
                            fullContent += data.content;
                            if (callbacks.onText) {
                                callbacks.onText(data.content, fullContent);
                            }
                        } else if (data.type === 'image') {
                            // 图片内容
                            if (callbacks.onImage) {
                                callbacks.onImage(data.content);
                            }
                        } else if (data.type === 'card') {
                            // 卡片内容
                            if (callbacks.onCard) {
                                callbacks.onCard(JSON.parse(data.content));
                            }
                        } else if (data.type === 'quick_actions') {
                            // 快捷操作
                            if (callbacks.onActions) {
                                callbacks.onActions(JSON.parse(data.content));
                            }
                        } else if (data.type === 'error') {
                            // 错误
                            if (callbacks.onError) {
                                callbacks.onError(data.content);
                            }
                        } else if (data.type === 'info') {
                            // 信息提示
                            if (callbacks.onInfo) {
                                callbacks.onInfo(data.content);
                            }
                        }
                    } catch (e) {
                        // 忽略解析错误
                    }
                }
            }
        }

        return fullContent;
    },

    // 获取聊天历史
    getHistory: (limit = 50) => {
        return request(`/api/chat/history?limit=${limit}`);
    },

    // 清空历史
    clearHistory: () => {
        return request('/api/chat/history', {
            method: 'DELETE'
        });
    },

    // 上传图片
    uploadImage: (file) => {
        const formData = new FormData();
        formData.append('file', file);

        return fetch(`${API_BASE}/api/chat/upload-image`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: formData
        }).then(response => response.json());
    }
};

/**
 * 体重记录API
 */
const weightAPI = {
    // 记录体重
    record: (data) => {
        const params = new URLSearchParams();
        params.append('weight', data.weight);
        if (data.bodyFat) params.append('body_fat', data.bodyFat);
        if (data.note) params.append('note', data.note);
        if (data.date) params.append('record_date', data.date);
        
        return request(`/api/weight/record?${params.toString()}`, {
            method: 'POST'
        });
    },
    
    // 获取历史记录
    getHistory: (days = 30) => {
        return request(`/api/weight/history?days=${days}`);
    },
    
    // 获取统计数据
    getStats: () => {
        return request('/api/weight/stats');
    },
    
    // 获取趋势数据
    getTrend: (days = 30) => {
        return request(`/api/weight/trend?days=${days}`);
    }
};

/**
 * 饮食记录API
 */
const mealAPI = {
    // 记录餐食
    record: (data) => {
        const params = new URLSearchParams();
        params.append('meal_type', data.mealType);
        params.append('content', data.foodName || data.content);
        if (data.calories) params.append('calories', data.calories);
        if (data.note) params.append('note', data.note);

        return request(`/api/meal/record?${params.toString()}`, {
            method: 'POST'
        });
    },

    // 获取今日餐食
    getToday: () => {
        return request('/api/meal/today');
    },

    // 获取历史记录
    getHistory: (startDate, endDate) => {
        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);

        return request(`/api/meal/history?${params.toString()}`);
    },

    // 搜索食物
    searchFood: (keyword) => {
        return request(`/api/meal/search?keyword=${encodeURIComponent(keyword)}`);
    },

    // 分析图片 - 使用fetch直接调用，因为要上传文件
    analyzeImage: (file, mealType) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('meal_type', mealType);

        return fetch(`${API_BASE}/api/meal/analyze`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: formData
        }).then(response => response.json());
    }
};

/**
 * 运动记录API
 */
const exerciseAPI = {
    // 记录运动
    record: (data) => {
        const params = new URLSearchParams();
        params.append('exercise_type', data.exerciseType);
        params.append('duration', data.duration);
        if (data.calories) params.append('calories_burned', data.calories);
        if (data.intensity) params.append('intensity', data.intensity);
        if (data.note) params.append('note', data.note);
        
        return request(`/api/exercise/record?${params.toString()}`, {
            method: 'POST'
        });
    },
    
    // 获取今日运动
    getToday: () => {
        return request('/api/exercise/today');
    },
    
    // 获取运动类型列表
    getTypes: () => {
        return request('/api/exercise/types');
    }
};

/**
 * 饮水记录API
 */
const waterAPI = {
    // 记录饮水
    record: (amount) => {
        return request(`/api/water/record?amount_ml=${amount}`, {
            method: 'POST'
        });
    },
    
    // 获取今日饮水
    getToday: () => {
        return request('/api/water/today');
    },
    
    // 获取统计数据
    getStats: () => {
        return request('/api/water/stats');
    }
};

/**
 * 睡眠记录API
 */
const sleepAPI = {
    record: (data) => {
        const params = new URLSearchParams();
        params.append('bed_time', data.bedtime);
        params.append('bed_period', data.bedPeriod);
        params.append('wake_time', data.waketime);
        params.append('wake_period', data.wakePeriod);
        params.append('sleep_date', data.date);
        if (data.quality) {
            const qualityMap = { poor: 2, medium: 3, good: 4 };
            params.append('quality', qualityMap[data.quality] || 3);
        }

        return request(`/api/sleep/record?${params.toString()}`, {
            method: 'POST'
        });
    },

    overwrite: (recordId, data) => {
        const params = new URLSearchParams();
        params.append('bed_time', data.bedtime);
        params.append('bed_period', data.bedPeriod);
        params.append('wake_time', data.waketime);
        params.append('wake_period', data.wakePeriod);
        params.append('sleep_date', data.date);
        if (data.quality) {
            const qualityMap = { poor: 2, medium: 3, good: 4 };
            params.append('quality', qualityMap[data.quality] || 3);
        }

        return request(`/api/sleep/overwrite/${recordId}?${params.toString()}`, {
            method: 'PUT'
        });
    },

    getHistory: (days = 7) => {
        return request(`/api/sleep/history?days=${days}`);
    },

    getStats: () => {
        return request('/api/sleep/stats');
    }
};

/**
 * 报告API
 */
const reportAPI = {
    // 获取周报
    getWeekly: (date) => {
        const url = date 
            ? `/api/report/weekly?date=${date}`
            : '/api/report/weekly';
        return request(url);
    },
    
    // 生成周报
    generate: (date) => {
        const params = new URLSearchParams();
        if (date) params.append('date', date);
        
        return request(`/api/report/generate?${params.toString()}`, {
            method: 'POST'
        });
    }
};

/**
 * 提醒API
 */
const reminderAPI = {
    // 获取提醒设置
    getSettings: () => {
        return request('/api/reminder/settings');
    },

    // 更新提醒设置（单个）
    updateSetting: (type, data) => {
        return request(`/api/reminder/settings/${type}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    // 批量更新提醒设置
    updateSettings: (data) => {
        return request('/api/reminder/settings/batch', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }
};

/**
 * 目标管理API
 */
const goalsAPI = {
    // 获取当前目标
    getCurrent: () => {
        return request('/api/goals/current');
    },

    // 创建目标
    create: (data) => {
        return request('/api/goals', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    // 获取目标详情
    getDetail: (goalId) => {
        return request(`/api/goals/${goalId}`);
    },

    // 更新目标
    update: (goalId, data) => {
        return request(`/api/goals/${goalId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    // 放弃目标
    abandon: (goalId) => {
        return request(`/api/goals/${goalId}/abandon`, {
            method: 'POST'
        });
    },

    // 完成目标
    complete: (goalId) => {
        return request(`/api/goals/${goalId}/complete`, {
            method: 'POST'
        });
    },

    // 获取历史目标
    getHistory: () => {
        return request('/api/goals/history/list');
    },

    // 获取进度统计
    getProgressStats: () => {
        return request('/api/goals/progress/stats');
    }
};

/**
 * 热量计算API
 */
const caloriesAPI = {
    // 计算BMR和TDEE
    calculate: (data) => {
        return request('/api/calories/calculate', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    // 计算热量平衡
    calculateBalance: (data) => {
        return request('/api/calories/balance', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    // 计算减重目标热量
    calculateWeightLossTarget: (data) => {
        return request('/api/calories/weight-loss-target', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    // 获取活动水平列表
    getActivityLevels: () => {
        return request('/api/calories/activity-levels');
    },

    // 获取每日热量数据
    getDailyBalance: (days = 7) => {
        return request(`/api/calories/balance/daily?days=${days}`);
    },

    // 获取热量分布数据
    getDistribution: (days = 7) => {
        return request(`/api/calories/balance/distribution?days=${days}`);
    }
};

/**
 * 健康检查API
 */
const healthAPI = {
    check: () => {
        return request('/health');
    }
};

// 导出API对象
window.API = {
    Error: APIError,
    base: API_BASE,
    user: userAPI,
    chat: chatAPI,
    weight: weightAPI,
    meal: mealAPI,
    exercise: exerciseAPI,
    water: waterAPI,
    sleep: sleepAPI,
    report: reportAPI,
    reminder: reminderAPI,
    goals: goalsAPI,
    calories: caloriesAPI,
    health: healthAPI
};
