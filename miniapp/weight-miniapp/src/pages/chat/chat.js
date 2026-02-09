// 对话页面逻辑
const app = getApp()

Page({
  data: {
    messages: [],
    inputValue: '',
    isSending: false,
    isTyping: false,
    scrollIntoView: '',
    agentName: '小助',
    showQuickTips: true
  },

  onLoad() {
    this.loadChatHistory()
    this.getAgentConfig()
  },

  onShow() {
    // 确保滚动到最新消息
    if (this.data.messages.length > 0) {
      this.scrollToBottom()
    }
  },

  // 加载Agent配置
  async getAgentConfig() {
    try {
      const res = await app.request({
        url: '/api/user/agent/config'
      })
      
      if (res.success) {
        this.setData({
          agentName: res.config.agent_name
        })
      }
    } catch (err) {
      console.error('加载Agent配置失败:', err)
    }
  },

  // 加载对话历史
  async loadChatHistory() {
    try {
      const res = await app.request({
        url: '/api/chat/history',
        data: {
          limit: 20
        }
      })
      
      if (res.success && res.data.length > 0) {
        // 格式化时间
        const messages = res.data.map(msg => ({
          ...msg,
          time: this.formatTime(msg.created_at)
        }))
        
        this.setData({
          messages
        })
        
        // 滚动到底部
        this.scrollToBottom()
        
        // 隐藏快捷提示
        this.setData({
          showQuickTips: false
        })
      }
    } catch (err) {
      console.error('加载对话历史失败:', err)
    }
  },

  // 输入变化
  onInput(e) {
    this.setData({
      inputValue: e.detail.value
    })
  },

  // 发送快捷提示
  sendQuickTip(e) {
    const tip = e.currentTarget.dataset.tip
    this.sendMessageToAI(tip)
  },

  // 发送消息
  async sendMessage() {
    const content = this.data.inputValue.trim()
    
    if (!content || this.data.isSending) {
      return
    }
    
    this.data.isSending = true
    
    await this.sendMessageToAI(content)
    
    // 清空输入框
    this.setData({
      inputValue: ''
    })
    
    // 隐藏快捷提示
    this.setData({
      showQuickTips: false
    })
    
    this.data.isSending = false
  },

  // 发送消息到AI
  async sendMessageToAI(content) {
    try {
      // 1. 添加到消息列表
      const userMessage = {
        id: Date.now(),
        role: 'user',
        content: content,
        time: this.formatTime(new Date().toISOString())
      }
      
      this.setData({
        messages: [...this.data.messages, userMessage]
      })
      
      // 滚动到底部
      this.scrollToBottom()
      
      // 2. 显示正在输入
      this.setData({
        isTyping: true
      })
      
      // 3. 调用API
      const res = await app.request({
        url: '/api/chat/send',
        method: 'POST',
        data: {
          content: content
        }
      })
      
      // 4. 隐藏正在输入
      this.setData({
        isTyping: false
      })
      
      if (res.success) {
        // 5. 添加助手回复
        const assistantMessage = {
          id: Date.now() + 1,
          role: 'assistant',
          content: res.data.content,
          time: this.formatTime(new Date().toISOString())
        }
        
        this.setData({
          messages: [...this.data.messages, assistantMessage]
        })
        
        // 滚动到底部
        this.scrollToBottom()
      } else {
        // 错误处理
        wx.showToast({
          title: res.error || '服务暂时不可用',
          icon: 'none',
          duration: 2000
        })
        
        const errorMessage = {
          id: Date.now() + 1,
          role: 'assistant',
          content: '抱歉，我遇到了一些问题，请稍后再试~',
          time: this.formatTime(new Date().toISOString())
        }
        
        this.setData({
          messages: [...this.data.messages, errorMessage]
        })
        
        this.scrollToBottom()
      }
      
    } catch (err) {
      console.error('发送消息失败:', err)
      
      this.setData({
        isTyping: false
      })
      
      wx.showToast({
        title: '网络错误',
        icon: 'none',
        duration: 2000
      })
    }
  },

  // 滚动到底部
  scrollToBottom() {
    const lastId = this.data.messages.length > 0 
      ? `msg-${this.data.messages[this.data.messages.length - 1].id}` 
      : ''
    
    this.setData({
      scrollIntoView: lastId
    })
  },

  // 格式化时间
  formatTime(isoString) {
    const date = new Date(isoString)
    const now = new Date()
    
    const isToday = date.toDateString() === now.toDateString()
    
    if (isToday) {
      return date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit'
      })
    } else {
      return date.toLocaleDateString('zh-CN', {
        month: 'short',
        day: 'numeric'
      })
    }
  },

  // 长按复制消息
  copyMessage(e) {
    const content = e.currentTarget.dataset.content
    
    wx.setClipboardData({
      data: content,
      success() {
        wx.showToast({
          title: '已复制',
          icon: 'success',
          duration: 1000
        })
      }
    })
  }
})
