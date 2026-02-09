# 体重管理助手 - 微信小程序开发指南

## 📱 项目结构

```
miniapp/weight-miniapp/
├── app.js                  # 小程序全局逻辑
├── app.json                # 小程序配置
├── app.wxss                # 全局样式
├── sitemap.json            # 站点地图
├── src/
│   ├── pages/              # 页面目录
│   │   ├── index/          # 首页
│   │   ├── chat/           # 对话页面
│   │   ├── weight/         # 体重记录
│   │   ├── meal/           # 餐食记录
│   │   ├── exercise/       # 运动记录
│   │   ├── water/          # 饮水记录
│   │   ├── sleep/          # 睡眠记录
│   │   └── profile/        # 个人中心
│   ├── components/         # 组件目录
│   ├── utils/              # 工具函数
│   └── assets/             # 静态资源
│       └── icons/          # 图标文件
```

## 🚀 快速开始

### 1. 安装微信开发者工具

下载并安装 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)

### 2. 创建小程序账号

1. 访问 [微信公众平台](https://mp.weixin.qq.com/)
2. 注册小程序账号
3. 获取 AppID

### 3. 导入项目

1. 打开微信开发者工具
2. 选择 "导入项目"
3. 选择 `miniapp/weight-miniapp` 目录
4. 填写你的 AppID
5. 点击 "导入"

### 4. 配置后端接口

修改 `app.js` 中的 `apiBaseUrl`：

```javascript
globalData: {
  apiBaseUrl: 'http://localhost:8000',  // 开发环境
  // 生产环境: 'https://your-domain.com'
}
```

### 5. 开发调试

1. 点击 "编译" 按钮
2. 使用模拟器预览
3. 扫码真机调试

## 📄 页面说明

### 已完成页面

#### 1. 首页 (index)
- **功能**: 数据总览、快捷操作
- **展示**: 今日体重、摄入热量、运动时长、饮水量
- **交互**: 点击卡片跳转到对应页面

### 待开发页面

#### 2. 对话页面 (chat)
```javascript
// pages/chat/chat.js
Page({
  data: {
    messages: [],
    inputValue: ''
  },
  
  async sendMessage() {
    // 调用后端 /api/chat/send
    // 展示 AI 回复
  }
})
```

#### 3. 体重记录 (weight)
```javascript
// pages/weight/weight.js
Page({
  data: {
    weight: '',
    history: []
  },
  
  async recordWeight() {
    // POST /api/weight/record
  },
  
  async loadHistory() {
    // GET /api/weight/history
  }
})
```

#### 4. 餐食记录 (meal)
- 文字记录
- 拍照上传（AI识别）
- 食物搜索

#### 5. 运动/饮水/睡眠记录
- 参考体重记录页面
- 调用对应 API

#### 6. 个人中心 (profile)
- 用户信息
- Agent设置
- 提醒设置
- 周报查看

## 🔌 API 对接

### 封装请求方法

```javascript
// utils/request.js
const app = getApp()

export const request = (options) => {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.apiBaseUrl}${options.url}`,
      method: options.method || 'GET',
      data: options.data,
      header: {
        'Authorization': `Bearer ${app.globalData.token}`,
        'Content-Type': 'application/json'
      },
      success: resolve,
      fail: reject
    })
  })
}
```

### 使用示例

```javascript
import { request } from '../../utils/request'

Page({
  async onLoad() {
    const res = await request({
      url: '/api/user/profile'
    })
    console.log(res.data)
  }
})
```

## 🎨 UI 组件建议

### 1. 使用 Vant Weapp

```bash
# 安装 Vant Weapp
npm i @vant/weapp -S --production
```

在 `app.json` 中配置：
```json
{
  "usingComponents": {
    "van-button": "@vant/weapp/button/index",
    "van-cell": "@vant/weapp/cell/index",
    "van-field": "@vant/weapp/field/index"
  }
}
```

### 2. 推荐组件
- `van-button` - 按钮
- `van-cell` - 单元格
- `van-field` - 输入框
- `van-datetime-picker` - 日期选择
- `van-dialog` - 弹窗
- `van-toast` - 轻提示

## 📱 真机调试

### 1. 配置合法域名

在微信公众平台配置服务器域名：
- request 合法域名: `https://your-domain.com`
- uploadFile 合法域名: `https://your-domain.com`

### 2. 开发阶段跳域名校验

在微信开发者工具中：
- 设置 -> 项目设置 -> 不校验合法域名

### 3. 真机预览

1. 点击 "预览" 按钮
2. 扫码在手机上查看
3. 打开调试模式查看 console

## 🔐 登录流程

```javascript
// 微信登录示例
Page({
  async login() {
    // 1. 获取微信登录凭证
    const { code } = await wx.login()
    
    // 2. 发送给后端
    const res = await request({
      url: '/api/user/login',
      method: 'POST',
      data: { code }
    })
    
    // 3. 保存 token
    if (res.success) {
      wx.setStorageSync('token', res.token)
      app.globalData.token = res.token
    }
  }
})
```

## 📝 注意事项

1. **图片资源**：添加图标到 `assets/icons/` 目录
2. **域名配置**：生产环境必须配置 HTTPS
3. **代码体积**：控制代码包大小（不超过 2MB）
4. **权限申请**：如需相机、相册权限，需在 `app.json` 中声明

## 🎁 开发建议

### Phase 1: 基础功能
- [x] 首页框架
- [ ] 登录页面
- [ ] 体重记录
- [ ] 对话页面

### Phase 2: 记录功能
- [ ] 餐食记录（文字）
- [ ] 运动记录
- [ ] 饮水记录
- [ ] 睡眠记录

### Phase 3: 高级功能
- [ ] 餐食拍照识别
- [ ] 周报展示
- [ ] 数据图表
- [ ] 提醒设置

### Phase 4: 优化体验
- [ ] 加载动画
- [ ] 错误处理
- [ ] 离线缓存
- [ ] 性能优化

## 📚 参考文档

- [微信小程序开发文档](https://developers.weixin.qq.com/miniprogram/dev/framework/)
- [Taro 文档](https://taro.jd.com/)
- [Vant Weapp 文档](https://vant-contrib.gitee.io/vant-weapp/)

## 🆘 常见问题

### Q: 请求后端 API 失败？
A: 检查：
1. 后端服务是否启动
2. `apiBaseUrl` 配置是否正确
3. Token 是否有效
4. 域名是否加入白名单

### Q: 如何上传图片？
```javascript
wx.chooseImage({
  success: (res) => {
    wx.uploadFile({
      url: 'https://api.example.com/upload',
      filePath: res.tempFilePaths[0],
      name: 'file',
      success: (uploadRes) => {
        console.log(uploadRes.data)
      }
    })
  }
})
```

---

**祝你开发顺利！** 🎉
