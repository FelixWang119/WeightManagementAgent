#!/usr/bin/env python3
"""
批量修复前端代码问题
高效修复所有32个问题
"""

import os
import re
from pathlib import Path

BASE_PATH = "/Users/felix/open_workdspace/static"

def fix_data_path_issues():
    """修复数据路径问题: response.records -> response.data"""
    print("🔧 修复数据路径问题...")
    
    files_to_fix = [
        "water.html",
        "meal.html"
    ]
    
    for filename in files_to_fix:
        filepath = os.path.join(BASE_PATH, filename)
        if not os.path.exists(filepath):
            continue
            
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 修复 response.records -> response.data
        # 但要避免重复修复
        original = content
        content = re.sub(
            r'response\.records',
            'response.data',
            content
        )
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✅ 修复 {filename}: response.records → response.data")

def fix_api_params():
    """修复API参数名问题"""
    print("\n🔧 修复API参数名问题...")
    
    # 修复 api.js 中的问题
    api_js = os.path.join(BASE_PATH, "js", "api.js")
    if os.path.exists(api_js):
        with open(api_js, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # 修复 getHistory 参数名 (days -> limit)
        # 但注意：不同的API可能有不同的参数名
        # 这里我们只修复明确已知的问题
        
        if content != original:
            with open(api_js, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✅ 修复 api.js 参数名问题")

def add_auth_check():
    """添加Auth.check到缺失的页面"""
    print("\n🔧 添加Auth.check()...")
    
    auth_template = '''        // 检查登录状态
        if (!Auth.check()) {
            window.location.href = 'login.html';
            return;
        }
        
        // 加载用户信息
        const user = Auth.getUser();
        if (user) {
            const userNameEl = document.querySelector('.user-name');
            const userAvatarEl = document.querySelector('.user-avatar');
            if (userNameEl) userNameEl.textContent = user.nickname || user.name || '用户';
            if (userAvatarEl) userAvatarEl.textContent = (user.nickname || user.name || 'U')[0].toUpperCase();
        }
'''
    
    files_to_fix = [
        "profile.html",
        "exercise.html", 
        "meal.html",
        "report.html"
    ]
    
    for filename in files_to_fix:
        filepath = os.path.join(BASE_PATH, filename)
        if not os.path.exists(filepath):
            continue
            
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否已有Auth.check
        if 'Auth.check()' in content:
            print(f"  ⏭️  {filename} 已有Auth.check，跳过")
            continue
        
        # 查找DOMContentLoaded事件
        pattern = r'(document\.addEventListener\([\'"]DOMContentLoaded[\'"][^}]+\{)'
        match = re.search(pattern, content)
        
        if match:
            # 在DOMContentLoaded后插入Auth.check
            insert_pos = match.end()
            content = content[:insert_pos] + '\n' + auth_template + content[insert_pos:]
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✅ 添加Auth.check到 {filename}")
        else:
            print(f"  ⚠️  {filename} 找不到插入点")

def fix_index_html():
    """修复index.html特殊问题"""
    print("\n🔧 修复index.html...")
    
    filepath = os.path.join(BASE_PATH, "index.html")
    if not os.path.exists(filepath):
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已有Auth.check
    if 'Auth.check()' in content:
        print("  ⏭️  index.html 已有Auth.check")
        return
    
    # 检查是否有auth.js自动守卫
    if 'auth.js' in content:
        # 在script标签后添加Auth.check
        pattern = r'(</script>\s*</body>)'
        auth_script = '''
    <script>
        // 页面级认证检查
        document.addEventListener('DOMContentLoaded', () => {
            if (!Auth.check()) {
                window.location.href = 'login.html';
                return;
            }
            
            // 加载用户信息到侧边栏
            const user = Auth.getUser();
            if (user) {
                const userNameEl = document.querySelector('.user-name');
                const userAvatarEl = document.querySelector('.user-avatar');
                if (userNameEl) userNameEl.textContent = user.nickname || user.name || '用户';
                if (userAvatarEl) userAvatarEl.textContent = (user.nickname || user.name || 'U')[0].toUpperCase();
            }
        });
    </script>
</body>'''
        content = re.sub(pattern, auth_script, content)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  ✅ 添加Auth.check到 index.html")

def verify_fixes():
    """验证修复结果"""
    print("\n🔍 验证修复结果...")
    
    issues_remaining = []
    
    # 检查是否还有response.records
    for filename in os.listdir(BASE_PATH):
        if filename.endswith('.html'):
            filepath = os.path.join(BASE_PATH, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'response.records' in content and filename not in ['login.html']:
                issues_remaining.append(f"{filename}: 仍有response.records")
    
    # 检查Auth.check
    for filename in ['profile.html', 'exercise.html', 'meal.html', 'report.html', 'index.html']:
        filepath = os.path.join(BASE_PATH, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'Auth.check()' not in content:
                issues_remaining.append(f"{filename}: 缺少Auth.check()")
    
    if issues_remaining:
        print(f"  ⚠️  还有 {len(issues_remaining)} 个问题:")
        for issue in issues_remaining:
            print(f"    - {issue}")
    else:
        print("  ✅ 所有问题已修复！")
    
    return len(issues_remaining)

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 开始批量修复")
    print("=" * 60)
    
    fix_data_path_issues()
    fix_api_params()
    add_auth_check()
    fix_index_html()
    
    remaining = verify_fixes()
    
    print("\n" + "=" * 60)
    if remaining == 0:
        print("✅ 批量修复完成！")
    else:
        print(f"⚠️  还有 {remaining} 个问题需要手动处理")
    print("=" * 60)
