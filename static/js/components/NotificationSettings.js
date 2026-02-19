/**
 * 通知设置组件 - 核心功能
 * 管理用户通知偏好和提醒设置
 */

class NotificationSettings {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container #${containerId} not found`);
            return;
        }
        
        this.options = {
            apiBaseUrl: '/api/notification',
            theme: 'light',
            ...options
        };
        
        this.preferences = {};
        this.reminders = [];
        this.notifications = [];
        
        this.init();
    }
    
    /**
     * 初始化组件
     */
    async init() {
        try {
            // 加载数据
            await this.loadPreferences();
            await this.loadReminders();
            
            // 渲染界面
            this.render();
            
        } catch (error) {
            console.error('初始化通知设置失败:', error);
            this.showError('加载通知设置失败');
        }
    }
    
    /**
     * 加载通知偏好设置
     */
    async loadPreferences() {
        try {
            const response = await fetch(`${this.options.apiBaseUrl}/preferences`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '加载偏好设置失败');
            }
            
            this.preferences = result.data || {};
            return this.preferences;
            
        } catch (error) {
            console.error('加载通知偏好失败:', error);
            throw error;
        }
    }
    
    /**
     * 加载提醒设置
     */
    async loadReminders() {
        try {
            const response = await fetch(`${this.options.apiBaseUrl}/reminders`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '加载提醒设置失败');
            }
            
            this.reminders = result.data || [];
            return this.reminders;
            
        } catch (error) {
            console.error('加载提醒设置失败:', error);
            throw error;
        }
    }
    
    /**
     * 渲染组件
     */
    render() {
        this.container.innerHTML = '';
        
        // 创建标签页容器
        const tabsContainer = document.createElement('div');
        tabsContainer.className = 'notification-settings-tabs';
        tabsContainer.style.cssText = `
            display: flex;
            border-bottom: 1px solid #e0e0e0;
            margin-bottom: 20px;
        `;
        
        // 标签页
        const tabs = [
            { id: 'preferences', label: '偏好设置', icon: 'settings' },
            { id: 'reminders', label: '提醒设置', icon: 'notifications' },
        ];
        
        tabs.forEach(tab => {
            const tabElement = document.createElement('button');
            tabElement.className = 'notification-tab';
            tabElement.dataset.tab = tab.id;
            tabElement.innerHTML = `
                <i class="material-icons" style="vertical-align: middle; margin-right: 8px;">${tab.icon}</i>
                ${tab.label}
            `;
            tabElement.style.cssText = `
                padding: 12px 24px;
                background: none;
                border: none;
                border-bottom: 3px solid transparent;
                cursor: pointer;
                font-size: 14px;
                color: #666;
                transition: all 0.3s;
                display: flex;
                align-items: center;
            `;
            
            if (tab.id === 'preferences') {
                tabElement.style.borderBottomColor = '#4CAF50';
                tabElement.style.color = '#4CAF50';
                tabElement.style.fontWeight = 'bold';
            }
            
            tabElement.addEventListener('click', () => this.switchTab(tab.id));
            tabsContainer.appendChild(tabElement);
        });
        
        this.container.appendChild(tabsContainer);
        
        // 内容容器
        const contentContainer = document.createElement('div');
        contentContainer.id = 'notification-content';
        contentContainer.style.cssText = `
            min-height: 400px;
            padding: 20px;
        `;
        this.container.appendChild(contentContainer);
        
        // 渲染默认标签页
        this.renderPreferencesTab();
    }
    
    /**
     * 切换标签页
     */
    switchTab(tabId) {
        // 更新标签页样式
        const tabs = this.container.querySelectorAll('.notification-tab');
        tabs.forEach(tab => {
            if (tab.dataset.tab === tabId) {
                tab.style.borderBottomColor = '#4CAF50';
                tab.style.color = '#4CAF50';
                tab.style.fontWeight = 'bold';
            } else {
                tab.style.borderBottomColor = 'transparent';
                tab.style.color = '#666';
                tab.style.fontWeight = 'normal';
            }
        });
        
        // 渲染对应内容
        const contentContainer = document.getElementById('notification-content');
        contentContainer.innerHTML = '';
        
        switch (tabId) {
            case 'preferences':
                this.renderPreferencesTab();
                break;
            case 'reminders':
                this.renderRemindersTab();
                break;
        }
    }
    
    /**
     * 渲染偏好设置标签页
     */
    renderPreferencesTab() {
        const contentContainer = document.getElementById('notification-content');
        
        const form = document.createElement('form');
        form.id = 'notification-preferences-form';
        form.style.cssText = `
            max-width: 600px;
            margin: 0 auto;
        `;
        
        // 全局开关
        const globalSwitch = this.createSwitch(
            'enabled',
            '启用通知',
            '接收所有系统通知',
            this.preferences.enabled !== false
        );
        form.appendChild(globalSwitch);
        
        // 通知类型设置
        const notificationTypes = [
            { key: 'enable_time_based', label: '时间提醒', description: '固定时间提醒（如三餐、运动）' },
            { key: 'enable_event_based', label: '事件提醒', description: '基于事件触发（如未记录体重）' },
            { key: 'enable_achievement', label: '成就通知', description: '成就达成通知' },
            { key: 'enable_goal_progress', label: '目标进度', description: '目标进度更新通知' },
            { key: 'enable_data_anomaly', label: '数据异常', description: '数据异常提醒（如体重波动大）' },
        ];
        
        const typesSection = this.createSection('通知类型设置');
        notificationTypes.forEach(type => {
            const switchElement = this.createSwitch(
                type.key,
                type.label,
                type.description,
                this.preferences[type.key] !== false
            );
            typesSection.appendChild(switchElement);
        });
        form.appendChild(typesSection);
        
        // 具体提醒设置
        const reminderTypes = [
            { key: 'enable_weight_reminder', label: '体重记录提醒', description: '提醒记录每日体重' },
            { key: 'enable_breakfast_reminder', label: '早餐记录提醒', description: '提醒记录早餐' },
            { key: 'enable_lunch_reminder', label: '午餐记录提醒', description: '提醒记录午餐' },
            { key: 'enable_dinner_reminder', label: '晚餐记录提醒', description: '提醒记录晚餐' },
            { key: 'enable_daily_report', label: '日报提醒', description: '每日健康报告生成提醒' },
            { key: 'enable_weekly_report', label: '周报提醒', description: '每周报告生成提醒' },
        ];
        
        const remindersSection = this.createSection('具体提醒设置');
        reminderTypes.forEach(reminder => {
            const switchElement = this.createSwitch(
                reminder.key,
                reminder.label,
                reminder.description,
                this.preferences[reminder.key] !== false
            );
            remindersSection.appendChild(switchElement);
        });
        form.appendChild(remindersSection);
        
        // 通知渠道设置
        const channelsSection = this.createSection('通知渠道');
        const channelSelect = this.createSelect(
            'preferred_channel',
            '首选通知渠道',
            [
                { value: 'chat', label: '聊天界面' },
                { value: 'push', label: '推送通知' },
                { value: 'email', label: '邮件' },
                { value: 'sms', label: '短信' },
            ],
            this.preferences.preferred_channel || 'chat'
        );
        channelsSection.appendChild(channelSelect);
        form.appendChild(channelsSection);
        
        // 免打扰时段
        const quietHoursSection = this.createSection('免打扰时段');
        
        const quietStart = this.createTimeInput(
            'quiet_hours_start',
            '开始时间',
            this.preferences.quiet_hours_start || '22:00'
        );
        quietHoursSection.appendChild(quietStart);
        
        const quietEnd = this.createTimeInput(
            'quiet_hours_end',
            '结束时间',
            this.preferences.quiet_hours_end || '08:00'
        );
        quietHoursSection.appendChild(quietEnd);
        
        form.appendChild(quietHoursSection);
        
        // 通知频率
        const frequencySection = this.createSection('通知频率');
        const frequencySelect = this.createSelect(
            'notification_frequency',
            '通知频率',
            [
                { value: 'minimal', label: '最少通知（仅重要提醒）' },
                { value: 'normal', label: '正常频率（推荐）' },
                { value: 'frequent', label: '频繁通知（所有提醒）' },
            ],
            this.preferences.notification_frequency || 'normal'
        );
        frequencySection.appendChild(frequencySelect);
        form.appendChild(frequencySection);
        
        // 保存按钮
        const saveButton = document.createElement('button');
        saveButton.type = 'button';
        saveButton.textContent = '保存设置';
        saveButton.style.cssText = `
            background: #4CAF50;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            margin-top: 20px;
            width: 100%;
            transition: background 0.3s;
        `;
        saveButton.addEventListener('mouseenter', () => {
            saveButton.style.background = '#45a049';
        });
        saveButton.addEventListener('mouseleave', () => {
            saveButton.style.background = '#4CAF50';
        });
        saveButton.addEventListener('click', () => this.savePreferences());
        
        form.appendChild(saveButton);
        contentContainer.appendChild(form);
    }
    
    /**
     * 渲染提醒设置标签页
     */
    renderRemindersTab() {
        const contentContainer = document.getElementById('notification-content');
        
        const header = document.createElement('div');
        header.style.cssText = `
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        `;
        
        const title = document.createElement('h3');
        title.textContent = '提醒设置';
        title.style.margin = '0';
        
        const addButton = document.createElement('button');
        addButton.textContent = '添加提醒';
        addButton.style.cssText = `
            background: #4CAF50;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        `;
        addButton.addEventListener('click', () => this.showAddReminderModal());
        
        header.appendChild(title);
        header.appendChild(addButton);
        contentContainer.appendChild(header);
        
        // 提醒列表
        if (this.reminders.length === 0) {
            const emptyState = document.createElement('div');
            emptyState.style.cssText = `
                text-align: center;
                padding: 40px;
                color: #999;
            `;
            emptyState.innerHTML = `
                <i class="material-icons" style="font-size: 48px; margin-bottom: 16px;">notifications_off</i>
                <p>暂无提醒设置</p>
                <button id="add-default-reminders" style="
                    background: #4CAF50;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    cursor: pointer;
                    margin-top: 16px;
                ">添加默认提醒</button>
            `;
            contentContainer.appendChild(emptyState);
            
            document.getElementById('add-default-reminders').addEventListener('click', () => {
                this.addDefaultReminders();
            });
        } else {
            const remindersList = document.createElement('div');
            remindersList.className = 'reminders-list';
            
            this.reminders.forEach(reminder => {
                const reminderCard = this.createReminderCard(reminder);
                remindersList.appendChild(reminderCard);
            });
            
            contentContainer.appendChild(remindersList);
        }
    }
    
    /**
     * 创建开关组件
     */
    createSwitch(id, label, description, checked = true) {
        const container = document.createElement('div');
        container.style.cssText = `
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #f0f0f0;
        `;
        
        const labelContainer = document.createElement('div');
        labelContainer.style.flex = '1';
        
        const labelElement = document.createElement('div');
        labelElement.textContent = label;
        labelElement.style.fontWeight = '500';
        labelElement.style.marginBottom = '4px';
        
        const descElement = document.createElement('div');
        descElement.textContent = description;
        descElement.style.fontSize = '12px';
        descElement.style.color = '#666';
        
        labelContainer.appendChild(labelElement);
        labelContainer.appendChild(descElement);
        
        const switchContainer = document.createElement('label');
        switchContainer.className = 'switch';
        switchContainer.style.cssText = `
            position: relative;
            display: inline-block;
            width: 60px;
            height: 34px;
        `;
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = id;
        checkbox.checked = checked;
        checkbox.style.cssText = `
            opacity: 0;
            width: 0;
            height: 0;
        `;
        
        const slider = document.createElement('span');
        slider.className = 'slider';
        slider.style.cssText = `
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: .4s;
            border-radius: 34px;
        `;
        
        const sliderBefore = document.createElement('span');
        sliderBefore.style.cssText = `
            position: absolute;
            content: "";
            height: 26px;
            width: 26px;
            left: 4px;
            bottom: 4px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        `;
        
        slider.appendChild(sliderBefore);
        
        // 切换样式
        checkbox.addEventListener('change', () => {
            if (checkbox.checked) {
                slider.style.backgroundColor = '#4CAF50';
                sliderBefore.style.transform = 'translateX(26px)';
            } else {
                slider.style.backgroundColor = '#ccc';
                sliderBefore.style.transform = 'translateX(0)';
            }
        });
        
        // 初始样式
        if (checked) {
            slider.style.backgroundColor = '#4CAF50';
            sliderBefore.style.transform = 'translateX(26px)';
        }
        
        switchContainer.appendChild(checkbox);
        switchContainer.appendChild(slider);
        
        container.appendChild(labelContainer);
        container.appendChild(switchContainer);
        
        return container;
    }
    
    /**
     * 创建选择框组件
     */
    createSelect(id, label, options, selectedValue) {
        const container = document.createElement('div');
        container.style.cssText = `
            margin-bottom: 16px;
        `;
        
        const labelElement = document.createElement('label');
        labelElement.htmlFor = id;
        labelElement.textContent = label;
        labelElement.style.cssText = `
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
        `;
        
        const select = document.createElement('select');
        select.id = id;
        select.name = id;
        select.style.cssText = `
            width: 100%;
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            background: white;
        `;
        
        options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option.value;
            optionElement.textContent = option.label;
            if (option.value === selectedValue) {
                optionElement.selected = true;
            }
            select.appendChild(optionElement);
        });
        
        container.appendChild(labelElement);
        container.appendChild(select);
        
        return container;
    }
    
    /**
     * 创建时间输入组件
     */
    createTimeInput(id, label, value) {
        const container = document.createElement('div');
        container.style.cssText = `
            margin-bottom: 16px;
        `;
        
        const labelElement = document.createElement('label');
        labelElement.htmlFor = id;
        labelElement.textContent = label;
        labelElement.style.cssText = `
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
        `;
        
        const input = document.createElement('input');
        input.type = 'time';
        input.id = id;
        input.name = id;
        input.value = value;
        input.style.cssText = `
            width: 100%;
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        `;
        
        container.appendChild(labelElement);
        container.appendChild(input);
        
        return container;
    }
    
    /**
     * 创建分区标题
     */
    createSection(title) {
        const section = document.createElement('div');
        section.style.cssText = `
            margin: 24px 0 16px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid #4CAF50;
        `;
        
        const titleElement = document.createElement('h4');
        titleElement.textContent = title;
        titleElement.style.cssText = `
            margin: 0;
            color: #4CAF50;
            font-size: 16px;
        `;
        
        section.appendChild(titleElement);
        return section;
    }
    
    /**
     * 创建提醒卡片
     */
    createReminderCard(reminder) {
        const card = document.createElement('div');
        card.className = 'reminder-card';
        card.style.cssText = `
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: box-shadow 0.3s;
        `;
        
        card.addEventListener('mouseenter', () => {
            card.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.boxShadow = 'none';
        });
        
        // 提醒信息
        const info = document.createElement('div');
        info.style.flex = '1';
        
        const title = document.createElement('div');
        title.style.cssText = `
            font-weight: 500;
            margin-bottom: 4px;
            display: flex;
            align-items: center;
        `;
        
        const icon = document.createElement('i');
        icon.className = 'material-icons';
        icon.textContent = this.getReminderIcon(reminder.reminder_type);
        icon.style.cssText = `
            margin-right: 8px;
            color: #4CAF50;
            font-size: 20px;
        `;
        
        const titleText = document.createElement('span');
        titleText.textContent = this.getReminderName(reminder.reminder_type);
        
        title.appendChild(icon);
        title.appendChild(titleText);
        
        const details = document.createElement('div');
        details.style.cssText = `
            font-size: 12px;
            color: #666;
        `;
        
        if (reminder.reminder_time) {
            details.textContent = `时间: ${reminder.reminder_time} ${reminder.weekdays_only ? '(仅工作日)' : ''}`;
        } else {
            details.textContent = '事件触发';
        }
        
        info.appendChild(title);
        info.appendChild(details);
        
        // 开关和操作按钮
        const actions = document.createElement('div');
        actions.style.cssText = `
            display: flex;
            align-items: center;
            gap: 8px;
        `;
        
        // 启用开关
        const switchContainer = document.createElement('label');
        switchContainer.className = 'switch';
        switchContainer.style.cssText = `
            position: relative;
            display: inline-block;
            width: 50px;
            height: 28px;
        `;
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = reminder.enabled;
        checkbox.style.cssText = `
            opacity: 0;
            width: 0;
            height: 0;
        `;
        
        const slider = document.createElement('span');
        slider.className = 'slider';
        slider.style.cssText = `
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: ${reminder.enabled ? '#4CAF50' : '#ccc'};
            transition: .4s;
            border-radius: 34px;
        `;
        
        const sliderBefore = document.createElement('span');
        sliderBefore.style.cssText = `
            position: absolute;
            content: "";
            height: 20px;
            width: 20px;
            left: 4px;
            bottom: 4px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
            transform: ${reminder.enabled ? 'translateX(22px)' : 'translateX(0)'};
        `;
        
        slider.appendChild(sliderBefore);
        
        checkbox.addEventListener('change', () => {
            this.updateReminder(reminder.reminder_type, { enabled: checkbox.checked });
        });
        
        switchContainer.appendChild(checkbox);
        switchContainer.appendChild(slider);
        
        // 删除按钮
        const deleteButton = document.createElement('button');
        deleteButton.innerHTML = '<i class="material-icons">delete</i>';
        deleteButton.style.cssText = `
            background: none;
            border: none;
            color: #f44336;
            cursor: pointer;
            padding: 4px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        
        deleteButton.addEventListener('click', () => {
            if (confirm('确定要删除这个提醒吗？')) {
                this.deleteReminder(reminder.reminder_type);
            }
        });
        
        actions.appendChild(switchContainer);
        actions.appendChild(deleteButton);
        
        card.appendChild(info);
        card.appendChild(actions);
        
        return card;
    }
    
    /**
     * 保存偏好设置
     */
    async savePreferences() {
        try {
            const form = document.getElementById('notification-preferences-form');
            const formData = new FormData(form);
            
            const preferences = {};
            formData.forEach((value, key) => {
                if (key.startsWith('enable_')) {
                    preferences[key] = value === 'on';
                } else if (key === 'enabled') {
                    preferences[key] = value === 'on';
                } else {
                    preferences[key] = value;
                }
            });
            
            // 处理开关元素
            const switches = form.querySelectorAll('input[type="checkbox"]');
            switches.forEach(switchElement => {
                if (!preferences.hasOwnProperty(switchElement.id)) {
                    preferences[switchElement.id] = switchElement.checked;
                }
            });
            
            const response = await fetch(`${this.options.apiBaseUrl}/preferences`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(preferences),
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '保存设置失败');
            }
            
            this.showSuccess('设置已保存');
            this.preferences = preferences;
            
        } catch (error) {
            console.error('保存偏好设置失败:', error);
            this.showError('保存设置失败');
        }
    }
    
    /**
     * 更新提醒设置
     */
    async updateReminder(reminderType, updates) {
        try {
            const params = new URLSearchParams();
            params.append('reminder_type', reminderType);
            
            if (updates.enabled !== undefined) {
                params.append('enabled', updates.enabled);
            }
            
            const response = await fetch(`${this.options.apiBaseUrl}/reminders?${params.toString()}`, {
                method: 'POST',
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '更新提醒失败');
            }
            
            // 刷新提醒列表
            await this.loadReminders();
            this.renderRemindersTab();
            
        } catch (error) {
            console.error('更新提醒失败:', error);
            this.showError('更新提醒失败');
        }
    }
    
    /**
     * 删除提醒
     */
    async deleteReminder(reminderType) {
        try {
            const response = await fetch(`${this.options.apiBaseUrl}/reminders/${reminderType}`, {
                method: 'DELETE',
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '删除提醒失败');
            }
            
            // 刷新提醒列表
            await this.loadReminders();
            this.renderRemindersTab();
            
            this.showSuccess('提醒已删除');
            
        } catch (error) {
            console.error('删除提醒失败:', error);
            this.showError('删除提醒失败');
        }
    }
    
    /**
     * 添加默认提醒
     */
    async addDefaultReminders() {
        try {
            const defaultReminders = [
                { type: 'weight', time: '08:00', enabled: true },
                { type: 'breakfast', time: '08:30', enabled: true },
                { type: 'lunch', time: '12:30', enabled: true },
                { type: 'dinner', time: '18:30', enabled: true },
                { type: 'exercise', time: '19:00', enabled: true },
                { type: 'water', time: '10:00', enabled: true, interval_minutes: 120 },
            ];
            
            for (const reminder of defaultReminders) {
                const params = new URLSearchParams();
                params.append('reminder_type', reminder.type);
                params.append('reminder_time', reminder.time);
                params.append('enabled', reminder.enabled.toString());
                
                if (reminder.interval_minutes) {
                    params.append('interval_minutes', reminder.interval_minutes.toString());
                }
                
                await fetch(`${this.options.apiBaseUrl}/reminders?${params.toString()}`, {
                    method: 'POST',
                });
            }
            
            // 刷新提醒列表
            await this.loadReminders();
            this.renderRemindersTab();
            
            this.showSuccess('默认提醒已添加');
            
        } catch (error) {
            console.error('添加默认提醒失败:', error);
            this.showError('添加默认提醒失败');
        }
    }
    
    /**
     * 显示添加提醒模态框
     */
    showAddReminderModal() {
        alert('添加提醒功能开发中...');
    }
    
    /**
     * 获取提醒图标
     */
    getReminderIcon(reminderType) {
        const icons = {
            'weight': 'monitor_weight',
            'breakfast': 'breakfast_dining',
            'lunch': 'lunch_dining',
            'dinner': 'dinner_dining',
            'snack': 'bakery_dining',
            'exercise': 'fitness_center',
            'water': 'local_drink',
            'sleep': 'bedtime',
            'weekly': 'summarize',
            'test': 'notifications',
        };
        return icons[reminderType] || 'notifications';
    }
    
    /**
     * 获取提醒名称
     */
    getReminderName(reminderType) {
        const names = {
            'weight': '体重记录',
            'breakfast': '早餐记录',
            'lunch': '午餐记录',
            'dinner': '晚餐记录',
            'snack': '零食记录',
            'exercise': '运动提醒',
            'water': '饮水提醒',
            'sleep': '睡眠提醒',
            'weekly': '周报提醒',
            'test': '测试提醒',
        };
        return names[reminderType] || reminderType;
    }
    
    /**
     * 显示成功消息
     */
    showSuccess(message) {
        this.showMessage(message, 'success');
    }
    
    /**
     * 显示错误消息
     */
    showError(message) {
        this.showMessage(message, 'error');
    }
    
    /**
     * 显示消息
     */
    showMessage(message, type = 'info') {
        const messageDiv = document.createElement('div');
        messageDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 4px;
            color: white;
            font-size: 14px;
            z-index: 1000;
            animation: slideIn 0.3s ease-out;
        `;
        
        if (type === 'success') {
            messageDiv.style.backgroundColor = '#4CAF50';
        } else if (type === 'error') {
            messageDiv.style.backgroundColor = '#f44336';
        } else {
            messageDiv.style.backgroundColor = '#2196F3';
        }
        
        messageDiv.textContent = message;
        document.body.appendChild(messageDiv);
        
        // 3秒后自动消失
        setTimeout(() => {
            messageDiv.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => {
                document.body.removeChild(messageDiv);
            }, 300);
        }, 3000);
    }
}

// 导出为全局变量
if (typeof window !== 'undefined') {
    window.NotificationSettings = NotificationSettings;
}

export default NotificationSettings;