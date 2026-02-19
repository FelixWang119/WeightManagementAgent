/**
 * 增强图表组件
 * 支持体重趋势、营养摄入、运动进度等可视化
 */

class EnhancedCharts {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container #${containerId} not found`);
            return;
        }
        
        this.options = {
            theme: 'light',
            responsive: true,
            animation: true,
            ...options
        };
        
        this.charts = {};
        this.dataCache = {};
    }
    
    /**
     * 初始化图表容器
     */
    init() {
        this.container.innerHTML = '';
        this.container.classList.add('enhanced-charts-container');
        
        if (this.options.responsive) {
            this.container.style.position = 'relative';
            this.container.style.width = '100%';
        }
        
        return this;
    }
    
    /**
     * 创建体重趋势图表
     */
    async createWeightTrendChart(data, chartId = 'weight-trend') {
        const canvas = this._createCanvas(chartId);
        
        const chartData = {
            labels: data.labels || [],
            datasets: [
                {
                    label: '体重 (kg)',
                    data: data.datasets?.[0]?.data || [],
                    borderColor: '#4CAF50',
                    backgroundColor: 'rgba(76, 175, 80, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                }
            ]
        };
        
        const options = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: (context) => {
                            return `${context.dataset.label}: ${context.parsed.y}kg`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        maxRotation: 45
                    }
                },
                y: {
                    beginAtZero: false,
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    title: {
                        display: true,
                        text: '体重 (kg)'
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'nearest'
            }
        };
        
        // 如果有趋势线，添加第二个数据集
        if (data.datasets?.length > 1) {
            chartData.datasets.push({
                label: '趋势线',
                data: data.datasets[1].data || [],
                borderColor: '#FF9800',
                backgroundColor: 'transparent',
                borderWidth: 3,
                borderDash: [5, 5],
                fill: false,
                pointRadius: 0,
                tension: 0.4,
            });
        }
        
        this.charts[chartId] = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: chartData,
            options: options
        });
        
        return this.charts[chartId];
    }
    
    /**
     * 创建热量摄入图表
     */
    async createCalorieChart(data, chartId = 'calorie-chart') {
        const canvas = this._createCanvas(chartId);
        
        const chartData = {
            labels: data.labels || [],
            datasets: [
                {
                    label: '实际摄入',
                    data: data.datasets?.[0]?.data || [],
                    backgroundColor: 'rgba(54, 162, 235, 0.6)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1,
                }
            ]
        };
        
        const options = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: (context) => {
                            return `${context.dataset.label}: ${context.parsed.y}千卡`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    title: {
                        display: true,
                        text: '热量 (千卡)'
                    }
                }
            }
        };
        
        // 添加目标热量线
        if (data.target_calories) {
            chartData.datasets.push({
                label: '目标热量',
                data: Array(data.labels?.length || 0).fill(data.target_calories),
                type: 'line',
                borderColor: '#FF5722',
                borderWidth: 2,
                fill: false,
                pointRadius: 0,
                borderDash: [5, 5],
            });
        }
        
        this.charts[chartId] = new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: chartData,
            options: options
        });
        
        return this.charts[chartId];
    }
    
    /**
     * 创建运动进度图表
     */
    async createExerciseChart(data, chartId = 'exercise-chart') {
        const canvas = this._createCanvas(chartId);
        
        const chartData = {
            labels: data.labels || [],
            datasets: [
                {
                    label: '运动时长 (分钟)',
                    data: data.datasets?.[0]?.data || [],
                    backgroundColor: 'rgba(255, 99, 132, 0.6)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1,
                    yAxisID: 'y',
                }
            ]
        };
        
        const options = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                }
            },
            scales: {
                x: {
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: '运动时长 (分钟)'
                    },
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: '消耗热量 (千卡)'
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                }
            }
        };
        
        // 添加消耗热量线
        if (data.datasets?.length > 1) {
            chartData.datasets.push({
                label: '消耗热量',
                data: data.datasets[1].data || [],
                type: 'line',
                borderColor: '#9C27B0',
                backgroundColor: 'transparent',
                borderWidth: 2,
                fill: false,
                pointRadius: 0,
                yAxisID: 'y1',
            });
        }
        
        this.charts[chartId] = new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: chartData,
            options: options
        });
        
        return this.charts[chartId];
    }
    
    /**
     * 创建饮水进度图表
     */
    async createWaterChart(data, chartId = 'water-chart') {
        const canvas = this._createCanvas(chartId);
        
        const chartData = {
            labels: data.labels || [],
            datasets: [
                {
                    label: '饮水量 (ml)',
                    data: data.datasets?.[0]?.data || [],
                    backgroundColor: 'rgba(33, 150, 243, 0.6)',
                    borderColor: 'rgba(33, 150, 243, 1)',
                    borderWidth: 1,
                }
            ]
        };
        
        const options = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: (context) => {
                            return `${context.dataset.label}: ${context.parsed.y}ml`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    title: {
                        display: true,
                        text: '饮水量 (ml)'
                    }
                }
            }
        };
        
        // 添加目标饮水线
        if (data.target_water) {
            chartData.datasets.push({
                label: '目标饮水量',
                data: Array(data.labels?.length || 0).fill(data.target_water),
                type: 'line',
                borderColor: '#2196F3',
                borderWidth: 2,
                fill: false,
                pointRadius: 0,
                borderDash: [5, 5],
            });
        }
        
        this.charts[chartId] = new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: chartData,
            options: options
        });
        
        return this.charts[chartId];
    }
    
    /**
     * 创建习惯完成率图表
     */
    async createHabitChart(data, chartId = 'habit-chart') {
        const canvas = this._createCanvas(chartId);
        
        const chartData = {
            labels: data.labels || [],
            datasets: [
                {
                    label: '完成率 (%)',
                    data: data.datasets?.[0]?.data || [],
                    borderColor: 'rgba(156, 39, 176, 0.8)',
                    backgroundColor: 'rgba(156, 39, 176, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                }
            ]
        };
        
        const options = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: (context) => {
                            return `${context.dataset.label}: ${context.parsed.y}%`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    title: {
                        display: true,
                        text: '完成率 (%)'
                    },
                    ticks: {
                        callback: (value) => `${value}%`
                    }
                }
            }
        };
        
        // 添加移动平均线
        if (data.datasets?.length > 1) {
            chartData.datasets.push({
                label: '移动平均',
                data: data.datasets[1].data || [],
                borderColor: '#FF9800',
                backgroundColor: 'transparent',
                borderWidth: 3,
                fill: false,
                pointRadius: 0,
                tension: 0.4,
            });
        }
        
        // 添加目标线
        chartData.datasets.push({
            label: '目标线',
            data: Array(data.labels?.length || 0).fill(100),
            borderColor: '#4CAF50',
            borderWidth: 1,
            fill: false,
            pointRadius: 0,
            borderDash: [5, 5],
        });
        
        this.charts[chartId] = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: chartData,
            options: options
        });
        
        return this.charts[chartId];
    }
    
    /**
     * 创建健康指标雷达图
     */
    async createHealthRadarChart(data, chartId = 'health-radar') {
        const canvas = this._createCanvas(chartId);
        
        const chartData = {
            labels: data.labels || ['体重', '营养', '运动', '饮水', '睡眠', '习惯'],
            datasets: [
                {
                    label: '健康指标',
                    data: data.datasets?.[0]?.data || [75, 80, 65, 90, 70, 85],
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    pointBackgroundColor: 'rgba(54, 162, 235, 1)',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: 'rgba(54, 162, 235, 1)',
                }
            ]
        };
        
        const options = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            return `${context.label}: ${context.raw}分`;
                        }
                    }
                }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        stepSize: 20,
                        callback: (value) => `${value}分`
                    },
                    pointLabels: {
                        font: {
                            size: 12
                        }
                    }
                }
            }
        };
        
        this.charts[chartId] = new Chart(canvas.getContext('2d'), {
            type: 'radar',
            data: chartData,
            options: options
        });
        
        return this.charts[chartId];
    }
    
    /**
     * 创建成就进度饼图
     */
    async createAchievementChart(data, chartId = 'achievement-chart') {
        const canvas = this._createCanvas(chartId);
        
        const chartData = {
            labels: data.labels || [],
            datasets: [
                {
                    label: '成就进度',
                    data: data.datasets?.[0]?.data || [],
                    backgroundColor: [
                        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
                        '#9966FF', '#FF9F40', '#8AC926', '#1982C4'
                    ],
                    borderWidth: 1,
                }
            ]
        };
        
        const options = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'right',
                },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const label = context.label || '';
                            const value = context.raw || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = Math.round((value / total) * 100);
                            return `${label}: ${value}个 (${percentage}%)`;
                        }
                    }
                }
            }
        };
        
        this.charts[chartId] = new Chart(canvas.getContext('2d'), {
            type: 'doughnut',
            data: chartData,
            options: options
        });
        
        return this.charts[chartId];
    }
    
    /**
     * 从API加载图表数据
     */
    async loadChartData(endpoint, chartType, chartId, params = {}) {
        try {
            const url = new URL(endpoint, window.location.origin);
            Object.keys(params).forEach(key => {
                url.searchParams.append(key, params[key]);
            });
            
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (!result.success) {
                throw new Error(result.error || '加载数据失败');
            }
            
            this.dataCache[chartId] = result.data;
            
            // 根据图表类型创建图表
            switch (chartType) {
                case 'weight':
                    return await this.createWeightTrendChart(result.data, chartId);
                case 'calorie':
                    return await this.createCalorieChart(result.data, chartId);
                case 'exercise':
                    return await this.createExerciseChart(result.data, chartId);
                case 'water':
                    return await this.createWaterChart(result.data, chartId);
                case 'habit':
                    return await this.createHabitChart(result.data, chartId);
                case 'radar':
                    return await this.createHealthRadarChart(result.data, chartId);
                case 'achievement':
                    return await this.createAchievementChart(result.data, chartId);
                default:
                    throw new Error(`未知的图表类型: ${chartType}`);
            }
            
        } catch (error) {
            console.error(`加载图表数据失败 (${chartId}):`, error);
            this._showError(chartId, error.message);
            return null;
        }
    }
    
    /**
     * 更新图表数据
     */
    updateChart(chartId, newData) {
        if (!this.charts[chartId]) {
            console.error(`图表 ${chartId} 不存在`);
            return;
        }
        
        this.charts[chartId].data = newData;
        this.charts[chartId].update();
        this.dataCache[chartId] = newData;
    }
    
    /**
     * 刷新图表
     */
    refreshChart(chartId) {
        if (!this.charts[chartId]) {
            console.error(`图表 ${chartId} 不存在`);
            return;
        }
        
        this.charts[chartId].update();
    }
    
    /**
     * 销毁图表
     */
    destroyChart(chartId) {
        if (this.charts[chartId]) {
            this.charts[chartId].destroy();
            delete this.charts[chartId];
            delete this.dataCache[chartId];
        }
    }
    
    /**
     * 销毁所有图表
     */
    destroyAll() {
        Object.keys(this.charts).forEach(chartId => {
            this.destroyChart(chartId);
        });
        this.container.innerHTML = '';
    }
    
    /**
     * 获取图表数据
     */
    getChartData(chartId) {
        return this.dataCache[chartId] || null;
    }
    
    /**
     * 导出图表为图片
     */
    exportChartAsImage(chartId, format = 'png') {
        if (!this.charts[chartId]) {
            console.error(`图表 ${chartId} 不存在`);
            return null;
        }
        
        const canvas = this.charts[chartId].canvas;
        const imageUrl = canvas.toDataURL(`image/${format}`);
        
        // 创建下载链接
        const link = document.createElement('a');
        link.download = `chart-${chartId}-${new Date().toISOString().slice(0, 10)}.${format}`;
        link.href = imageUrl;
        link.click();
        
        return imageUrl;
    }
    
    /**
     * 创建Canvas元素
     */
    _createCanvas(chartId) {
        const chartContainer = document.createElement('div');
        chartContainer.className = 'chart-container';
        chartContainer.id = `container-${chartId}`;
        chartContainer.style.position = 'relative';
        chartContainer.style.height = '400px';
        chartContainer.style.marginBottom = '20px';
        
        const canvas = document.createElement('canvas');
        canvas.id = chartId;
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        
        chartContainer.appendChild(canvas);
        this.container.appendChild(chartContainer);
        
        return canvas;
    }
    
    /**
     * 显示错误信息
     */
    _showError(chartId, message) {
        const container = document.getElementById(`container-${chartId}`);
        if (!container) return;
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'chart-error';
        errorDiv.style.cssText = `
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
            color: #f44336;
            padding: 20px;
            background: rgba(244, 67, 54, 0.1);
            border-radius: 8px;
            max-width: 80%;
        `;
        
        errorDiv.innerHTML = `
            <i class="material-icons" style="font-size: 48px; margin-bottom: 10px;">error_outline</i>
            <p style="margin: 0; font-size: 14px;">${message}</p>
        `;
        
        container.appendChild(errorDiv);
    }
}

// 导出为全局变量
if (typeof window !== 'undefined') {
    window.EnhancedCharts = EnhancedCharts;
}

export default EnhancedCharts;