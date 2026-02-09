#!/usr/bin/env python3
"""
用户端代码全面扫描工具
检查前端API调用、字段名匹配、数据路径等问题
"""

import os
import re
import ast
from pathlib import Path
from collections import defaultdict

class FrontendScanner:
    def __init__(self, base_path):
        self.base_path = Path(base_path)
        self.issues = []
        self.api_definitions = {}  # 后端API定义
        self.frontend_apis = {}    # 前端API调用
        
    def scan_all(self):
        """执行全面扫描"""
        print("🔍 开始全面扫描用户端代码...")
        print("=" * 60)
        
        # 1. 扫描后端API定义
        self.scan_backend_apis()
        
        # 2. 扫描前端API调用
        self.scan_frontend_apis()
        
        # 3. 扫描HTML文件中的JS代码
        self.scan_html_files()
        
        # 4. 检查字段名匹配
        self.check_field_matching()
        
        # 5. 检查常见错误模式
        self.check_common_patterns()
        
        # 6. 生成报告
        self.generate_report()
        
    def scan_backend_apis(self):
        """扫描后端API路由定义"""
        print("📡 扫描后端API定义...")
        
        api_dir = self.base_path / "api" / "routes"
        if not api_dir.exists():
            return
            
        for api_file in api_dir.glob("*.py"):
            with open(api_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 提取路由定义
            route_pattern = r'@router\.(get|post|put|delete)\(["\']([^"\']+)["\']'
            for match in re.finditer(route_pattern, content):
                method = match.group(1).upper()
                path = match.group(2)
                
                # 提取参数定义
                params = self.extract_backend_params(content, match.end())
                
                # 提取返回语句
                returns = self.extract_backend_returns(content)
                
                key = f"{method}:{path}"
                self.api_definitions[key] = {
                    'file': api_file.name,
                    'method': method,
                    'path': path,
                    'params': params,
                    'returns': returns
                }
                
        print(f"   找到 {len(self.api_definitions)} 个后端API")
        
    def extract_backend_params(self, content, start_pos):
        """提取后端参数定义"""
        params = []
        # 查找函数定义
        func_match = re.search(r'async def \w+\([^)]*\)', content[start_pos:start_pos+2000])
        if func_match:
            func_def = func_match.group(0)
            # 提取参数
            param_matches = re.finditer(r'(\w+):\s*(\w+)', func_def)
            for pm in param_matches:
                param_name = pm.group(1)
                param_type = pm.group(2)
                if param_name not in ['current_user', 'db']:
                    params.append({
                        'name': param_name,
                        'type': param_type
                    })
        return params
        
    def extract_backend_returns(self, content):
        """提取后端返回字段"""
        returns = {}
        # 查找return语句
        return_matches = re.finditer(r'return\s*\{([^}]+)\}', content, re.DOTALL)
        for match in return_matches:
            return_content = match.group(1)
            # 提取键值对
            kv_matches = re.finditer(r'["\'](\w+)["\']\s*:', return_content)
            for kv in kv_matches:
                key = kv.group(1)
                returns[key] = 'unknown'
        return returns
        
    def scan_frontend_apis(self):
        """扫描前端API.js文件"""
        print("📱 扫描前端API定义...")
        
        api_js = self.base_path / "static" / "js" / "api.js"
        if not api_js.exists():
            print("   ⚠️ 找不到 api.js")
            return
            
        with open(api_js, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 提取API模块定义
        module_pattern = r'const (\w+)API = \{'
        for match in re.finditer(module_pattern, content):
            module_name = match.group(1)
            module_start = match.end()
            
            # 提取模块内的方法
            methods = self.extract_frontend_methods(content, module_start)
            self.frontend_apis[module_name] = methods
            
        print(f"   找到 {len(self.frontend_apis)} 个前端API模块")
        
    def extract_frontend_methods(self, content, start_pos):
        """提取前端API方法"""
        methods = {}
        
        # 查找方法定义
        method_pattern = r'(\w+)\s*:\s*\(([^)]*)\)\s*=>\s*\{'
        bracket_count = 0
        in_method = False
        method_name = None
        method_start = 0
        
        for match in re.finditer(method_pattern, content[start_pos:start_pos+5000]):
            method_name = match.group(1)
            params = match.group(2)
            method_body_start = start_pos + match.end()
            
            # 提取方法体
            brace_count = 1
            i = method_body_start
            while i < len(content) and brace_count > 0:
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                i += 1
                
            method_body = content[method_body_start:i]
            
            # 提取API调用
            api_calls = self.extract_api_calls(method_body)
            
            methods[method_name] = {
                'params': params,
                'api_calls': api_calls
            }
            
        return methods
        
    def extract_api_calls(self, method_body):
        """提取API调用信息"""
        calls = []
        
        # 匹配 request 调用
        request_pattern = r'request\([`"\']([^`"\']+)[`"\']'
        for match in re.finditer(request_pattern, method_body):
            url = match.group(1)
            calls.append({
                'url': url,
                'method': self.detect_http_method(method_body)
            })
            
        return calls
        
    def detect_http_method(self, body):
        """检测HTTP方法"""
        if 'method:\s*[\'"]POST[\'"]' in body:
            return 'POST'
        elif 'method:\s*[\'"]PUT[\'"]' in body:
            return 'PUT'
        elif 'method:\s*[\'"]DELETE[\'"]' in body:
            return 'DELETE'
        else:
            return 'GET'
            
    def scan_html_files(self):
        """扫描HTML文件中的JS代码"""
        print("📄 扫描HTML文件...")
        
        static_dir = self.base_path / "static"
        html_files = list(static_dir.glob("*.html"))
        
        for html_file in html_files:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 检查常见问题
            self.check_html_issues(html_file.name, content)
            
    def check_html_issues(self, filename, content):
        """检查HTML文件中的问题"""
        
        # 1. 检查未定义变量
        undefined_patterns = [
            (r'\${(\w+-\w+)}', '变量名包含连字符，JS中不可用'),
            (r'document\.getElementById\([\'"](\w+)[\'"]\)', '可能未检查元素是否存在'),
        ]
        
        for pattern, desc in undefined_patterns:
            for match in re.finditer(pattern, content):
                self.issues.append({
                    'file': filename,
                    'type': '潜在错误',
                    'description': desc,
                    'match': match.group(0),
                    'line': content[:match.start()].count('\n') + 1
                })
                
        # 2. 检查API响应处理
        response_patterns = [
            (r'response\.records', f'{filename}: 使用 response.records，应检查是否为 response.data'),
            (r'response\.success', f'{filename}: 检查 success 响应'),
        ]
        
        for pattern, desc in response_patterns:
            if re.search(pattern, content):
                # 检查是否同时检查了data和records
                has_data = 'response.data' in content
                has_records = 'response.records' in content
                
                if has_records and not has_data:
                    self.issues.append({
                        'file': filename,
                        'type': '数据路径问题',
                        'description': '使用 response.records 但未检查 response.data，后端可能返回 data 字段',
                        'suggestion': '确认后端API返回的是 data 还是 records'
                    })
                    
        # 3. 检查Auth.check
        if 'Auth.check()' not in content and filename not in ['login.html', 'admin']:
            self.issues.append({
                'file': filename,
                'type': '缺少认证检查',
                'description': '页面没有调用 Auth.check() 进行登录验证',
                'suggestion': '在 DOMContentLoaded 中添加 if (!Auth.check()) window.location.href = "login.html"'
            })
            
    def check_field_matching(self):
        """检查字段名匹配问题"""
        print("🔍 检查字段名匹配...")
        
        # 对比前后端字段名
        for api_key, backend_api in self.api_definitions.items():
            # 查找对应的前端调用
            frontend_calls = self.find_matching_frontend_calls(api_key)
            
            for call in frontend_calls:
                # 检查参数名
                self.check_param_matching(api_key, backend_api, call)
                
    def find_matching_frontend_calls(self, api_key):
        """查找匹配的前端调用"""
        calls = []
        method, path = api_key.split(':', 1)
        
        for module_name, methods in self.frontend_apis.items():
            for method_name, method_info in methods.items():
                for call in method_info.get('api_calls', []):
                    if path in call['url']:
                        calls.append({
                            'module': module_name,
                            'method': method_name,
                            'call': call
                        })
                        
        return calls
        
    def check_param_matching(self, api_key, backend_api, frontend_call):
        """检查参数名匹配"""
        backend_params = [p['name'] for p in backend_api.get('params', [])]
        
        # 从前端URL中提取参数
        url = frontend_call['call']['url']
        frontend_params = re.findall(r'\?(\w+)=', url)
        frontend_params.extend(re.findall(r'&(\w+)=', url))
        
        # 检查不匹配
        for fp in frontend_params:
            if fp not in backend_params and backend_params:
                self.issues.append({
                    'file': f"api.js ({frontend_call['module']}API.{frontend_call['method']})",
                    'type': '参数名不匹配',
                    'description': f"前端参数 '{fp}' 与后端参数不匹配",
                    'backend_params': backend_params,
                    'suggestion': f"后端期望参数: {', '.join(backend_params)}"
                })
                
    def check_common_patterns(self):
        """检查常见错误模式"""
        print("🧩 检查常见错误模式...")
        
        static_dir = self.base_path / "static"
        
        # 扫描所有JS文件
        for js_file in static_dir.rglob("*.js"):
            with open(js_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 检查request函数body处理
            if 'request(' in content and 'body:' in content:
                # 检查POST请求是否有body
                post_pattern = r'method:\s*[\'"]POST[\'"][^}]*body:\s*(\w+)'
                for match in re.finditer(post_pattern, content):
                    var_name = match.group(1)
                    # 检查是否有JSON.stringify
                    if f'JSON.stringify({var_name})' not in content:
                        self.issues.append({
                            'file': js_file.name,
                            'type': 'POST请求格式问题',
                            'description': f'POST请求使用了变量 {var_name}，但未使用 JSON.stringify()',
                            'suggestion': f'应该使用 body: JSON.stringify({var_name})'
                        })
                        
    def generate_report(self):
        """生成扫描报告"""
        print("\n" + "=" * 60)
        print("📊 扫描报告")
        print("=" * 60)
        
        if not self.issues:
            print("✅ 未发现明显问题")
            return
            
        # 按类型分组
        issues_by_type = defaultdict(list)
        for issue in self.issues:
            issues_by_type[issue['type']].append(issue)
            
        # 显示问题
        for issue_type, issues in sorted(issues_by_type.items()):
            print(f"\n🔴 {issue_type} ({len(issues)}个)")
            print("-" * 60)
            
            for issue in issues:
                print(f"\n文件: {issue['file']}")
                print(f"问题: {issue['description']}")
                if 'suggestion' in issue:
                    print(f"建议: {issue['suggestion']}")
                if 'match' in issue:
                    print(f"代码: {issue['match'][:80]}")
                if 'line' in issue:
                    print(f"行号: {issue['line']}")
                    
        print(f"\n{'=' * 60}")
        print(f"总计发现 {len(self.issues)} 个潜在问题")
        print("=" * 60)
        
# 运行扫描
if __name__ == "__main__":
    import sys
    base_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/felix/open_workdspace"
    
    scanner = FrontendScanner(base_path)
    scanner.scan_all()
