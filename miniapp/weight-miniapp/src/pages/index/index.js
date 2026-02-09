// 首页逻辑
const app = getApp()

Page({
  data: {
    userInfo: {},
    agentName: '小助',
    todayData: {
      weight: 65.5,
      calories: 800,
      exerciseMinutes: 30,
      water: 250
    },
    weightChange: 0,
    waterProgress: 12,
    weeklyGoal: {
      current: 0,
      target: 0.5
    },
    goalProgress: 0,
    latestReport: null
  },

  onLoad() {
    this.loadUserInfo()
    this.loadTodayData()
    this.loadWeeklyGoal()
    this.loadLatestReport()
  },

  onShow() {
    // 每次显示页面时刷新数据
    this.loadTodayData()
  },

  // 加载用户信息
  async loadUserInfo() {
    try {
      const res = await app.request({
        url: '/api/user/profile'
      })
      
      if (res.success) {
        this.setData({
          userInfo: res.user,
          agentName: res.agent_config?.name || '小助'
        })
      }
    } catch (err) {
      console.error('加载用户信息失败:', err)
    }
  },

  // 加载今日数据
  async loadTodayData() {
    try {
      // 并行加载各类数据
      const [weightRes, mealRes, exerciseRes, waterRes] = await Promise.all([
        app.request({ url: '/api/weight/stats' }),
        app.request({ url: '/api/meal/today' }),
        app.request({ url: '/api/exercise/stats' }),
        app.request({ url: '/api/water/today' })
      ])

      const todayData = {
        weight: weightRes.data?.latest?.weight || 0,
        calories: mealRes.total_calories || 0,
        exerciseMinutes: exerciseRes.data?.this_week?.duration_minutes || 0,
        water: waterRes.current_ml || 0
      }

      this.setData({
        todayData,
        waterProgress: Math.min(100, Math.round((todayData.water / 2000) * 100))
      })
    } catch (err) {
      console.error('加载今日数据失败:', err)
    }
  },

  // 加载周目标
  async loadWeeklyGoal() {
    try {
      const res = await app.request({
        url: '/api/goal/current'
      })
      
      if (res.success && res.data) {
        const progress = (res.data.current_weight - res.data.target_weight) / 
                        (res.data.start_weight - res.data.target_weight) * 100
        
        this.setData({
          weeklyGoal: {
            current: res.data.current_weight,
            target: res.data.target_weight
          },
          goalProgress: Math.max(0, Math.min(100, progress))
        })
      }
    } catch (err) {
      console.error('加载目标失败:', err)
    }
  },

  // 加载最新周报
  async loadLatestReport() {
    try {
      const res = await app.request({
        url: '/api/report/latest'
      })
      
      if (res.success && res.data) {
        this.setData({
          latestReport: {
            summary: res.data.summary.substring(0, 100) + '...',
            highlights: res.data.highlights || []
          }
        })
      }
    } catch (err) {
      console.error('加载周报失败:', err)
    }
  },

  // 快捷记录
  quickRecord(e) {
    const type = e.currentTarget.dataset.type
    const urls = {
      weight: '/pages/weight/weight',
      meal: '/pages/meal/meal',
      water: '/pages/water/water',
      exercise: '/pages/exercise/exercise'
    }
    
    wx.navigateTo({
      url: urls[type]
    })
  },

  // 页面跳转
  goToWeight() {
    wx.navigateTo({ url: '/pages/weight/weight' })
  },
  
  goToMeal() {
    wx.navigateTo({ url: '/pages/meal/meal' })
  },
  
  goToExercise() {
    wx.navigateTo({ url: '/pages/exercise/exercise' })
  },
  
  goToWater() {
    wx.navigateTo({ url: '/pages/water/water' })
  },

  viewReport() {
    wx.navigateTo({ url: '/pages/report/report' })
  }
})
