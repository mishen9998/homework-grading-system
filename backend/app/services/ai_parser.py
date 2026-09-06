import requests
import json
import re
import os
from flask import current_app


class AIQuestionParser:
    """AI题目解析服务 - 全新实现"""
    
    @staticmethod
    def get_api_config():
        """获取API配置"""
        api_key = os.environ.get('DEEPSEEK_API_KEY', '') or current_app.config.get('DEEPSEEK_API_KEY', '')
        api_url = os.environ.get('DEEPSEEK_API_URL', '') or current_app.config.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1/chat/completions')
        print(f"[AI Parser] API Key loaded: {'Yes' if api_key else 'No'}")
        print(f"[AI Parser] API URL: {api_url}")
        return api_key, api_url
    
    @staticmethod
    def call_deepseek_api(prompt, max_tokens=4000, timeout=180):
        """调用DeepSeek API"""
        api_key, api_url = AIQuestionParser.get_api_config()
        
        if not api_key or api_key == 'your-deepseek-api-key-here':
            return {
                'success': False,
                'error': 'API密钥未配置',
                'hint': '请在 backend/.env 文件中设置 DEEPSEEK_API_KEY\n获取密钥：https://platform.deepseek.com/'
            }
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'deepseek-chat',
            'messages': [
                {
                    'role': 'system',
                    'content': '你是一个专业的题目解析助手。请严格按照用户要求的格式返回JSON结果，不要添加任何其他内容。'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.1,
            'max_tokens': max_tokens
        }
        
        try:
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 401:
                return {'success': False, 'error': 'API密钥无效或已过期'}
            
            if response.status_code == 402:
                return {'success': False, 'error': 'API余额不足，请充值后使用'}
            
            if response.status_code == 429:
                return {'success': False, 'error': '请求过于频繁，请稍后重试'}
            
            if response.status_code != 200:
                return {'success': False, 'error': f'API调用失败({response.status_code})'}
            
            result = response.json()
            
            if 'choices' not in result or len(result['choices']) == 0:
                return {'success': False, 'error': 'API返回数据格式错误'}
            
            content = result['choices'][0]['message']['content']
            return {'success': True, 'content': content}
            
        except requests.exceptions.Timeout:
            return {'success': False, 'error': '请求超时，请检查网络连接'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'error': '无法连接到AI服务'}
        except Exception as e:
            return {'success': False, 'error': f'请求异常: {str(e)}'}
    
    @staticmethod
    def extract_json(text):
        """从文本中提取JSON"""
        text = text.strip()
        
        if text.startswith('{') and text.endswith('}'):
            try:
                return json.loads(text)
            except:
                pass
        
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
        
        return None
    
    @staticmethod
    def parse_questions(text):
        """解析题目文本"""
        print(f"[AI Parse] Starting to parse text, length: {len(text) if text else 0}")
        
        if not text or not text.strip():
            return {'success': False, 'error': '文本内容为空'}
        
        prompt = f"""请分析以下文本，提取所有题目并返回JSON格式结果。

【文本内容】
{text}

【要求】
1. 识别所有题目类型：单选题、多选题、判断题、填空题、简答题
2. 提取题目内容、选项、答案
3. 默认分数：单选2分、多选3分、判断2分、填空5分、简答10分

【返回格式】严格返回以下JSON，不要添加其他内容：
{{
    "questions": [
        {{
            "type": "single_choice",
            "content": "题目内容",
            "score": 2,
            "answer": "A",
            "options": {{"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"}}
        }}
    ]
}}

【type取值】single_choice(单选)、multiple_choice(多选)、true_false(判断)、fill_blank(填空)、text(简答)
【answer格式】
- 单选：单个字母如"A"
- 多选：多个字母如"A,B,C"
- 判断："true"或"false"
- 填空：答案文本
- 简答：参考答案文本
"""

        print("[AI Parse] Calling DeepSeek API...")
        result = AIQuestionParser.call_deepseek_api(prompt)
        
        if not result['success']:
            print(f"[AI Parse] API call failed: {result.get('error')}")
            return result
        
        print("[AI Parse] API call successful, extracting JSON...")
        content = result['content']
        print(f"[AI Parse] Response content length: {len(content)}")
        
        data = AIQuestionParser.extract_json(content)
        
        if not data:
            print(f"[AI Parse] Failed to extract JSON from: {content[:200]}...")
            return {'success': False, 'error': '无法解析AI返回的结果'}
        
        questions = data.get('questions', [])
        
        if not questions:
            return {'success': False, 'error': '未识别到有效题目'}
        
        print(f"[AI Parse] Found {len(questions)} questions")
        
        processed = []
        for q in questions:
            q_type = q.get('type', 'text')
            
            type_map = {
                'single_choice': 'single_choice',
                'multiple_choice': 'multiple_choice',
                'true_false': 'true_false',
                'fill_blank': 'fill_blank',
                'text': 'text'
            }
            
            processed.append({
                'question_type': type_map.get(q_type, 'text'),
                'content': q.get('content', ''),
                'score': q.get('score', 10),
                'correct_answer': q.get('answer', ''),
                'options': q.get('options', {'A': '', 'B': '', 'C': '', 'D': ''})
            })
        
        return {
            'success': True,
            'questions': processed,
            'count': len(processed)
        }
    
    @staticmethod
    def check_status():
        """检查AI服务状态"""
        api_key, api_url = AIQuestionParser.get_api_config()
        
        if not api_key or api_key == 'your-deepseek-api-key-here':
            return {
                'available': False,
                'message': 'API密钥未配置',
                'hint': '请在 backend/.env 中设置 DEEPSEEK_API_KEY\n获取密钥：https://platform.deepseek.com/'
            }
        
        return {
            'available': True,
            'message': 'AI服务已就绪'
        }
    
    @staticmethod
    def test_connection():
        """测试API连接"""
        api_key, api_url = AIQuestionParser.get_api_config()
        
        print(f"[AI Test] Testing connection with API key: {api_key[:10] if api_key else 'N/A'}...")
        
        if not api_key or api_key == 'your-deepseek-api-key-here':
            return {
                'success': False,
                'error': 'API密钥未配置',
                'hint': '请在 backend/.env 中设置 DEEPSEEK_API_KEY'
            }
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'deepseek-chat',
            'messages': [{'role': 'user', 'content': '测试'}],
            'max_tokens': 10
        }
        
        try:
            print(f"[AI Test] Sending request to: {api_url}")
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            print(f"[AI Test] Response status: {response.status_code}")
            
            if response.status_code == 200:
                return {'success': True, 'message': 'API连接正常'}
            elif response.status_code == 401:
                return {'success': False, 'error': 'API密钥无效'}
            elif response.status_code == 402:
                return {'success': False, 'error': '账户余额不足，请充值'}
            elif response.status_code == 429:
                return {'success': False, 'error': '请求过于频繁'}
            else:
                return {'success': False, 'error': f'API返回错误({response.status_code})'}
                
        except requests.exceptions.Timeout:
            return {'success': False, 'error': '连接超时，请检查网络'}
        except requests.exceptions.ConnectionError as e:
            print(f"[AI Test] Connection error: {e}")
            return {'success': False, 'error': '无法连接到DeepSeek服务'}
        except Exception as e:
            print(f"[AI Test] Exception: {e}")
            return {'success': False, 'error': str(e)}
