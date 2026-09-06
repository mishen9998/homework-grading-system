import requests
import json
import time
from flask import current_app


class DeepSeekService:
    """DeepSeek AI 服务封装。

    通过公共方法 _call_deepseek 统一处理 API 调用、重试、错误捕获，
    各业务方法只负责构造 prompt 与解析结果，消除重复代码。
    """

    @staticmethod
    def _call_deepseek(messages, max_tokens, temperature, timeout=30, max_retries=1):
        """调用 DeepSeek API 的公共方法。

        返回:
            成功: {'success': True, 'content': str}
            失败: {'success': False, 'error': str}
        """
        api_key = current_app.config.get('DEEPSEEK_API_KEY')
        api_url = current_app.config.get('DEEPSEEK_API_URL')

        if not api_key:
            return {
                'success': False,
                'error': 'DeepSeek API密钥未配置，请联系管理员配置DEEPSEEK_API_KEY'
            }

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': 'deepseek-chat',
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens
        }

        retry_count = 0
        while True:
            try:
                response = requests.post(
                    api_url, headers=headers, json=payload, timeout=timeout
                )

                if response.status_code == 429:
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(5 * retry_count)
                        continue
                    return {'success': False, 'error': 'API请求频率过高，请稍后重试'}

                if response.status_code == 402:
                    return {
                        'success': False,
                        'error': 'DeepSeek账户余额不足，请前往 https://platform.deepseek.com/ 充值后再使用'
                    }

                if response.status_code == 401:
                    return {'success': False, 'error': 'API密钥无效或已过期，请检查DEEPSEEK_API_KEY配置'}

                if response.status_code != 200:
                    return {
                        'success': False,
                        'error': f'DeepSeek API调用失败: {response.status_code} - {response.text[:200]}'
                    }

                result = response.json()
                if 'choices' not in result or len(result['choices']) == 0:
                    return {'success': False, 'error': 'DeepSeek API返回结果格式错误'}

                return {'success': True, 'content': result['choices'][0]['message']['content']}

            except requests.exceptions.Timeout:
                retry_count += 1
                if retry_count < max_retries:
                    continue
                return {'success': False, 'error': 'DeepSeek API请求超时，请稍后重试'}
            except requests.exceptions.ConnectionError:
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2)
                    continue
                return {'success': False, 'error': '无法连接到AI服务，请检查网络连接'}
            except requests.exceptions.RequestException as e:
                return {'success': False, 'error': f'DeepSeek API请求失败: {str(e)}'}
            except Exception as e:
                return {'success': False, 'error': f'调用过程发生错误: {str(e)}'}

    @staticmethod
    def _parse_json(content):
        """从可能包含 markdown 代码块的响应中提取 JSON，失败返回 None。"""
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return None

    @staticmethod
    def grade_python_code(question_content, question_score, reference_answer, student_code, requirements=None):
        prompt = f"""你是一位经验丰富的Python编程老师，请帮我批改以下Python编程作业。

【题目要求】
{question_content}

【满分】
{question_score}分

【参考答案/评分标准】
{reference_answer if reference_answer else '无参考答案，请根据题目要求合理评分'}

【学生提交的Python代码】
```python
{student_code if student_code else '学生未提交代码'}
```

【额外要求】
{requirements if requirements else '无额外要求'}

【评分要求】
1. 检查代码是否能正确解决题目要求的问题
2. 检查代码逻辑是否正确、清晰
3. 检查代码风格是否规范（变量命名、注释、缩进等）
4. 检查是否有潜在的bug或边界情况处理不当
5. 检查代码效率是否合理
6. 如果学生未提交代码或代码完全错误，给0分
7. 如果代码部分正确，根据正确程度给部分分数
8. 如果代码完全正确且风格良好，给满分

请只返回一个JSON格式的结果，不要包含其他内容：
{{
    "score": <0到{question_score}之间的整数>,
    "feedback": "<简短的评语，说明为什么给这个分数>",
    "code_analysis": {{
        "correctness": "<代码正确性分析>",
        "logic": "<代码逻辑分析>",
        "style": "<代码风格评价>",
        "bugs": "<潜在问题或bug>",
        "suggestions": "<改进建议>"
    }},
    "improved_code": "<如果有问题，给出改进后的代码示例，如果代码正确则为空字符串>"
}}
"""

        messages = [
            {'role': 'system', 'content': '你是一位专业的Python编程教师，擅长批改编程作业。请严格按照评分标准进行评分，给出详细的代码分析和改进建议。'},
            {'role': 'user', 'content': prompt}
        ]

        resp = DeepSeekService._call_deepseek(messages, max_tokens=2000, temperature=0.3, timeout=60)
        if not resp['success']:
            return resp

        content = resp['content']
        grade_result = DeepSeekService._parse_json(content)
        if grade_result is None:
            return {'success': False, 'error': '无法解析DeepSeek返回的评分结果', 'raw_response': content}

        score = max(0, min(int(grade_result.get('score', 0)), question_score))
        return {
            'success': True,
            'score': score,
            'feedback': grade_result.get('feedback', ''),
            'code_analysis': grade_result.get('code_analysis', {}),
            'improved_code': grade_result.get('improved_code', ''),
            'raw_response': content
        }

    @staticmethod
    def grade_text_question(question_content, question_score, reference_answer, student_answer):
        prompt = f"""你是一位经验丰富的老师，请帮我批改以下非选择题。

【题目内容】
{question_content}

【满分】
{question_score}分

【参考答案/评分标准】
{reference_answer if reference_answer else '无参考答案，请根据题目内容合理评分'}

【学生答案】
{student_answer if student_answer else '学生未作答'}

【评分要求】
1. 请仔细阅读题目和学生的答案
2. 根据学生答案的完整性、准确性、逻辑性进行评分
3. 满分为{question_score}分
4. 如果学生未作答或答案完全错误，给0分
5. 如果答案部分正确，根据正确程度给部分分数
6. 如果答案完全正确，给满分

请只返回一个JSON格式的结果，不要包含其他内容：
{{
    "score": <0到{question_score}之间的整数>,
    "feedback": "<简短的评语，说明为什么给这个分数>",
    "analysis": "<答案分析，指出学生的优点和不足>"
}}
"""

        messages = [
            {'role': 'system', 'content': '你是一位专业的教师助手，擅长批改各类非选择题。请严格按照评分标准进行评分，并给出合理的评语。'},
            {'role': 'user', 'content': prompt}
        ]

        resp = DeepSeekService._call_deepseek(messages, max_tokens=1000, temperature=0.3, timeout=30)
        if not resp['success']:
            return resp

        content = resp['content']
        grade_result = DeepSeekService._parse_json(content)
        if grade_result is None:
            return {'success': False, 'error': '无法解析DeepSeek返回的评分结果', 'raw_response': content}

        score = max(0, min(int(grade_result.get('score', 0)), question_score))
        return {
            'success': True,
            'score': score,
            'feedback': grade_result.get('feedback', ''),
            'analysis': grade_result.get('analysis', ''),
            'raw_response': content
        }

    @staticmethod
    def generate_overall_comment(assignment_title, student_name, total_score, max_score, question_results):
        questions_summary = ""
        for i, q in enumerate(question_results, 1):
            questions_summary += f"\n第{i}题（{q.get('type', '未知题型')}，{q.get('score', 0)}/{q.get('max_score', 0)}分）："
            if q.get('feedback'):
                questions_summary += f"\n  评语：{q.get('feedback')}"

        prompt = f"""你是一位经验丰富、和蔼可亲的老师，请根据学生的作业完成情况，生成一段总评语。

【作业信息】
作业标题：{assignment_title}
学生姓名：{student_name if student_name else '该同学'}

【成绩概况】
总分：{total_score}/{max_score}分
得分率：{round(total_score/max_score*100, 1) if max_score > 0 else 0}%

【各题得分情况】
{questions_summary if questions_summary else '无详细题目信息'}

【要求】
1. 总评语要温暖、有鼓励性，体现老师的关怀
2. 肯定学生的优点和进步
3. 针对不足之处给出具体的改进建议
4. 语言要亲切自然，避免过于生硬
5. 字数控制在100-200字左右
6. 不要使用markdown格式，直接输出纯文本

请直接输出总评语内容，不要包含其他内容。"""

        messages = [
            {'role': 'system', 'content': '你是一位温暖、有爱心的老师，善于发现学生的闪光点，同时也能给出建设性的指导意见。'},
            {'role': 'user', 'content': prompt}
        ]

        # 总评直接返回纯文本，无需 JSON 解析
        resp = DeepSeekService._call_deepseek(messages, max_tokens=500, temperature=0.7, timeout=30)
        if not resp['success']:
            return resp

        return {'success': True, 'comment': resp['content'].strip()}

    @staticmethod
    def parse_questions_from_text(text):
        if not text or not text.strip():
            return {'success': False, 'error': '文本内容不能为空'}

        prompt = f"""你是一位专业的教育工作者，请帮我从以下文本中解析出题目，并返回结构化的JSON数据。

【原始文本】
{text}

【解析要求】
1. 识别所有题目，包括选择题、多选题、判断题、填空题、大题/简答题/编程题
2. 提取题目内容、选项（如果有）、正确答案、分数
3. 如果原文没有明确分数，请根据题型设置默认分数：
   - 单选题：2分
   - 多选题：3分
   - 判断题：2分
   - 填空题：5分
   - 大题：10分
4. 正确答案格式要求：
   - 单选题：单个字母，如 "A"
   - 多选题：多个字母用逗号分隔，如 "A,B,C"
   - 判断题：使用 "true" 或 "false"
   - 填空题：答案文本，多个答案用 | 分隔
   - 大题：参考答案文本

请只返回一个JSON格式的结果，不要包含其他内容：
{{
    "questions": [
        {{
            "question_type": "<single_choice/multiple_choice/true_false/fill_blank/text>",
            "content": "<题目内容>",
            "score": <分数>,
            "correct_answer": "<正确答案>",
            "options": {{
                "A": "<选项A内容>",
                "B": "<选项B内容>",
                "C": "<选项C内容>",
                "D": "<选项D内容>"
            }}
        }}
    ]
}}

注意：
1. question_type 只能是以下值之一：single_choice, multiple_choice, true_false, fill_blank, text
2. 如果不是选择题，options可以都设为空字符串
3. 确保正确答案与题目匹配
4. 保持题目内容的完整性，包括题号后的文字"""

        messages = [
            {'role': 'system', 'content': '你是一位专业的教育工作者，擅长从文本中提取和整理题目。请严格按照要求返回JSON格式的结果。'},
            {'role': 'user', 'content': prompt}
        ]

        # 题目解析耗时较长，启用 3 次重试与 120s 超时
        resp = DeepSeekService._call_deepseek(
            messages, max_tokens=4000, temperature=0.1, timeout=120, max_retries=3
        )
        if not resp['success']:
            return resp

        content = resp['content']
        parse_result = DeepSeekService._parse_json(content)
        if parse_result is None:
            return {
                'success': False,
                'error': '无法解析API返回的结果，请检查题目格式',
                'raw_response': content[:500]
            }

        questions = parse_result.get('questions', [])

        default_scores = {
            'single_choice': 2,
            'multiple_choice': 3,
            'true_false': 2,
            'fill_blank': 5,
            'text': 10
        }
        for q in questions:
            if 'options' not in q:
                q['options'] = {'A': '', 'B': '', 'C': '', 'D': ''}
            if 'score' not in q or q['score'] <= 0:
                q['score'] = default_scores.get(q.get('question_type', 'text'), 10)

        return {
            'success': True,
            'questions': questions,
            'count': len(questions)
        }
