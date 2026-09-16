"""Owner-scoped polling endpoints for background AI work."""
from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity

from app.services.ai_jobs import get_ai_job, queue_status
from app.utils.decorators import role_required


bp = Blueprint('ai_jobs', __name__, url_prefix='/api/ai/jobs')


@bp.get('/<job_id>')
@role_required('student', 'teacher', 'admin')
def job_status(job_id):
    job = get_ai_job(job_id)
    if not job or int(job.get('user_id') or 0) != int(get_jwt_identity()):
        return jsonify(error='AI任务不存在或已过期'), 404
    body = {'job_id': job_id, 'status': job.get('status', 'unknown')}
    if job.get('status') == 'completed':
        body['result'] = job.get('result') or {}
    elif job.get('status') == 'failed':
        body['error'] = job.get('error') or 'AI任务执行失败'
    return jsonify(body)


@bp.get('/queue/status')
@role_required('admin')
def admin_queue_status():
    return jsonify(queue_status())
