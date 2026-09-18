from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, ChatMessage, Friendship
from werkzeug.utils import secure_filename
import os
from datetime import datetime

bp = Blueprint('chats', __name__, url_prefix='/api/chats')

UPLOAD_FOLDER = 'uploads/chat_files'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/conversations', methods=['GET'])
@jwt_required()
def get_conversations():
    user_id = get_jwt_identity()
    
    sent_friendships = Friendship.query.filter_by(user_id=user_id, status='accepted').all()
    received_friendships = Friendship.query.filter_by(friend_id=user_id, status='accepted').all()
    
    friends = []
    for f in sent_friendships:
        last_message = ChatMessage.query.filter(
            ((ChatMessage.sender_id == user_id) & (ChatMessage.receiver_id == f.friend_id)) |
            ((ChatMessage.sender_id == f.friend_id) & (ChatMessage.receiver_id == user_id))
        ).order_by(ChatMessage.created_at.desc()).first()
        
        unread_count = ChatMessage.query.filter_by(
            sender_id=f.friend_id,
            receiver_id=user_id,
            is_read=False
        ).count()
        
        friends.append({
            'friend': f.friend.to_dict(),
            'last_message': last_message.to_dict() if last_message else None,
            'unread_count': unread_count
        })
    
    for f in received_friendships:
        last_message = ChatMessage.query.filter(
            ((ChatMessage.sender_id == user_id) & (ChatMessage.receiver_id == f.user_id)) |
            ((ChatMessage.sender_id == f.user_id) & (ChatMessage.receiver_id == user_id))
        ).order_by(ChatMessage.created_at.desc()).first()
        
        unread_count = ChatMessage.query.filter_by(
            sender_id=f.user_id,
            receiver_id=user_id,
            is_read=False
        ).count()
        
        friends.append({
            'friend': f.user.to_dict(),
            'last_message': last_message.to_dict() if last_message else None,
            'unread_count': unread_count
        })
    
    friends.sort(key=lambda x: x['last_message']['created_at'] if x['last_message'] else '1970-01-01', reverse=True)
    
    return jsonify({'conversations': friends}), 200

@bp.route('/messages/<int:friend_id>', methods=['GET'])
@jwt_required()
def get_messages(friend_id):
    user_id = get_jwt_identity()
    
    friendship = Friendship.query.filter(
        ((Friendship.user_id == user_id) & (Friendship.friend_id == friend_id) & (Friendship.status == 'accepted')) |
        ((Friendship.user_id == friend_id) & (Friendship.friend_id == user_id) & (Friendship.status == 'accepted'))
    ).first()
    
    if not friendship:
        return jsonify({'error': '你们不是好友关系'}), 400
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    messages = ChatMessage.query.filter(
        ((ChatMessage.sender_id == user_id) & (ChatMessage.receiver_id == friend_id)) |
        ((ChatMessage.sender_id == friend_id) & (ChatMessage.receiver_id == user_id))
    ).order_by(ChatMessage.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    ChatMessage.query.filter_by(
        sender_id=friend_id,
        receiver_id=user_id,
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    
    return jsonify({
        'messages': [m.to_dict() for m in messages.items[::-1]],
        'has_more': messages.has_next,
        'total': messages.total
    }), 200

@bp.route('/send', methods=['POST'])
@jwt_required()
def send_message():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    receiver_id = data.get('receiver_id')
    content = data.get('content', '').strip()
    
    if not receiver_id:
        return jsonify({'error': '请指定接收者'}), 400
    
    if not content:
        return jsonify({'error': '消息内容不能为空'}), 400
    
    friendship = Friendship.query.filter(
        ((Friendship.user_id == user_id) & (Friendship.friend_id == receiver_id) & (Friendship.status == 'accepted')) |
        ((Friendship.user_id == receiver_id) & (Friendship.friend_id == user_id) & (Friendship.status == 'accepted'))
    ).first()
    
    if not friendship:
        return jsonify({'error': '你们不是好友关系'}), 400
    
    message = ChatMessage(
        sender_id=user_id,
        receiver_id=receiver_id,
        content=content
    )
    
    db.session.add(message)
    db.session.commit()
    
    return jsonify({
        'message': '发送成功',
        'chat_message': message.to_dict()
    }), 201

@bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_file():
    user_id = get_jwt_identity()
    
    if 'file' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400
    
    file = request.files['file']
    receiver_id = request.form.get('receiver_id')
    
    if not receiver_id:
        return jsonify({'error': '请指定接收者'}), 400
    
    try:
        receiver_id = int(receiver_id)
    except ValueError:
        return jsonify({'error': '接收者ID无效'}), 400
    
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': '不支持的文件类型'}), 400
    
    friendship = Friendship.query.filter(
        ((Friendship.user_id == user_id) & (Friendship.friend_id == receiver_id) & (Friendship.status == 'accepted')) |
        ((Friendship.user_id == receiver_id) & (Friendship.friend_id == user_id) & (Friendship.status == 'accepted'))
    ).first()
    
    if not friendship:
        return jsonify({'error': '你们不是好友关系'}), 400
    
    original_filename = file.filename
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f"{timestamp}_{filename}"
    
    upload_dir = os.path.join(current_app.root_path, UPLOAD_FOLDER)
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)
    
    file_size = os.path.getsize(file_path)
    
    message = ChatMessage(
        sender_id=int(user_id),
        receiver_id=receiver_id,
        content='[文件]',
        message_type='file',
        file_url=f"/{UPLOAD_FOLDER}/{filename}",
        file_name=original_filename,
        file_size=file_size
    )
    
    db.session.add(message)
    db.session.commit()
    
    return jsonify({
        'message': '文件发送成功',
        'chat_message': message.to_dict()
    }), 201

@bp.route('/download/<int:message_id>', methods=['GET'])
@jwt_required()
def download_file(message_id):
    user_id = get_jwt_identity()
    
    message = ChatMessage.query.get(message_id)
    
    if not message:
        return jsonify({'error': '消息不存在'}), 404
    
    if not message.file_url:
        return jsonify({'error': '该消息没有文件'}), 400
    
    if message.sender_id != int(user_id) and message.receiver_id != int(user_id):
        return jsonify({'error': '无权下载此文件'}), 403
    
    from flask import send_from_directory
    
    directory = os.path.join(current_app.root_path, UPLOAD_FOLDER)
    filename = message.file_url.split('/')[-1]
    
    return send_from_directory(directory, filename, as_attachment=True, download_name=message.file_name)

@bp.route('/unread-count', methods=['GET'])
@jwt_required()
def get_unread_count():
    user_id = get_jwt_identity()
    
    count = ChatMessage.query.filter_by(
        receiver_id=user_id,
        is_read=False
    ).count()
    
    return jsonify({'unread_count': count}), 200
