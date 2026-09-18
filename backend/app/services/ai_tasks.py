"""Execution functions used by dedicated AI workers."""
from app.services import DeepSeekService


def execute_ai_task(kind, payload):
    if kind == 'teacher_assistant':
        from app.routes.ai_assistant import execute_teacher_assistant
        return execute_teacher_assistant(payload['messages'], payload.get('privacy_flags', []))
    if kind == 'knowledge_deepseek':
        result = DeepSeekService._call_deepseek(
            payload['messages'], max_tokens=1000, temperature=0.2,
            timeout=45, max_retries=1)
        if not result.get('success'):
            return {
                'reply': 'AI 暂时不可用，已返回本地查询结果。\n\n' + payload['local_reply'],
                'sources': payload['sources'], 'degraded': True,
                'mode': 'local', 'can_deepen': True,
                'privacy_redacted': payload.get('privacy_flags', []),
            }
        return {
            'reply': result.get('content', ''), 'sources': payload['sources'],
            'degraded': False, 'mode': 'deepseek', 'can_deepen': False,
            'privacy_redacted': payload.get('privacy_flags', []),
        }
    if kind in ('grade_text', 'grade_python', 'overall_comment', 'parse_questions'):
        from app.services.grading_tasks import execute_grading_task
        return execute_grading_task(kind, payload)
    raise ValueError('不支持的AI任务类型')
