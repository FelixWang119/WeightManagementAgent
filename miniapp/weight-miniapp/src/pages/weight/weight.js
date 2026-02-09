// 体重记录页面逻辑
const app = getApp()

Page({
  data: {
    inputWeight: '',
    inputBodyFat: '',
    inputNote: '',
    isRecording: false,
    latestWeight: null,
    weightHistory: [],
    displayHistory: [],
    showAllHistory: false,
    weightTrend: [],
    trendDirection: '',
    trendText: '',
    trendChange: 0
  },

  onLoad() {
    this.loadWeightData()
  },

  // 输入变化
  onWeightInput(e) {
    this.setData({
      inputWeight: e.detail.value
    })
  },

  onBodyFatInput(e) {
    this.setData({
      inputBodyFat: e.detail.value
    })
  },

  onNoteInput(e) {
    this.setData({
      inputNote: e.detail.value
    })
  },

  // 记录体重
  async recordWeight() {
    const weight = parseFloat(this.data.inputWeight)
    const bodyFat = this.data.inputBodyFat ? parseFloat(this.data.inputBodyFat) : null
    const note = this.data.inputNote.trim()

    if (!weight || weight <= 0 || weight > 300) {
      wx.showToast({
        title: '请输入有效的体重',
        icon: 'none'
      })
      return
    }

    this.setData({
      isRecording: true
    })

    try {
      const res = await app.request({
        url: '/api/weight/record',
        method: 'POST',
        data: {
          weight: weight,
          body_fat: bodyFat,
          note: note
        }
      })

      if (res.success) {
        wx.showToast({
          title: '记录成功',
          icon: 'success',
          duration: 2000
        })

        // 清空输入
        this.setData({
          inputWeight: '',
          inputBodyFat: '',
          inputNote: ''
        })

        // 刷新数据
        await this.loadWeightData()
      } else {
        wx.showToast({
          title: res.error || '记录失败',
          icon: 'none'
        })
      }
    } catch (err) {
      console.error('记录体重失败:', err)
      wx.showToast({
        title: '网络错误',
        icon: 'none'
      })
    }

    this.setData({
      isRecording: false
    })
  },

  // 加载体重数据
  async loadWeightData() {
    try {
      // 并行加载统计和历史记录
      const [statsRes, historyRes, trendRes] = await Promise.all([
        app.request({ url: '/api/weight/stats' }),
        app.request({ url: '/api/weight/history', data: { days: 30 } }),
        app.request({ url: '/api/weight/trend', data: { days: 7 } })
      ])

      // 处理最新体重
      if (statsRes.success && statsRes.data) {
        this.setData({
          latestWeight: statsRes.data.latest
        })
      }

      // 处理历史记录
      if (historyRes.success) {
        const history = historyRes.data.map(item => ({
          ...item,
          date: this.formatDate(item.record_date),
          time: this.formatTime(item.record_date)
        }))

        this.setData({
          weightHistory: history,
          displayHistory: history.slice(0, 5) // 默认显示5条
        })
      }

      // 处理趋势数据
      if (trendRes.success && trendRes.data) {
        const trend = trendRes.data
        this.setData({
          weightTrend: trend.weights || [],
          trendDirection: trend.trend,
          trendText: trend.trend_text,
          trendChange: trend.change || 0
        })
      }
    } catch (err) {
      console.error('加载体重数据失败:', err)
    }
  },

  // 切换历史记录显示
  toggleHistory() {
    const showAll = !this.data.showAllHistory
    this.setData({
      showAllHistory: showAll,
      displayHistory: showAll
        ? this.data.weightHistory
        : this.data.weightHistory.slice(0, 5)
    })
  },

  // 格式化日期
  formatDate(dateString) {
    const date = new Date(dateString)
    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric'
    })
  },

  // 格式化时间
  formatTime(dateString) {
    const date = new Date(dateString)
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit'
    })
  }
})
