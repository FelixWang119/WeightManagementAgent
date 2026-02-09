// 小程序全局逻辑
App({
  globalData: {
    userInfo: null,
    token: null,
    apiBaseUrl: 'http://localhost:8000'  // 开发环境
  },

  onLaunch() {
    console.log('App Launch')
    // 检查登录状态
    this.checkLoginStatus()
  },

  // 检查登录状态
  checkLoginStatus() {
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
      console.log('已登录，token:', token.substring(0, 20) + '...')
    } else {
      console.log('未登录，需要登录')
      // 这里可以跳转到登录页
    }
  },

  // 封装请求方法
  request(options) {
    const { url, method = 'GET', data, header = {} } = options
    const { apiBaseUrl, token } = this.globalData

    return new Promise((resolve, reject) => {
      wx.request({
        url: `${apiBaseUrl}${url}`,
        method,
        data,
        header: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` }),
          ...header
        },
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(res.data)
          } else {
            console.error('请求失败:', res)
            reject(res)
          }
        },
        fail: (err) => {
          console.error('请求错误:', err)
          wx.showToast({
            title: '网络错误',
            icon: 'none'
          })
          reject(err)
        }
      })
    })
  }
})
