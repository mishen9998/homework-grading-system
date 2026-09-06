from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, Friendship

bp = Blueprint('friends', __name__, url_prefix='/api/friends')

@bp.route('/list', methods=['GET'])
@jwt_required()
def get_friends():
    user_id = get_jwt_identity()
    
    sent_friendships = Friendship.query.filter_by(user_id=user_id, status='accepted').all()
    received_friendships = Friendship.query.filter_by(friend_id=user_id, status='accepted').all()
    
    friends = []
    for f in sent_friendships:
        friends.append({
            'id': f.id,
            'friendship_id': f.id,
            'user': f.friend.to_dict(),
            'created_at': f.created_at.isoformat() if f.created_at else None
        })
    for f in received_friendships:
        friends.append({
            'id': f.id,
            'friendship_id': f.id,
            'user': f.user.to_dict(),
            'created_at': f.created_at.isoformat() if f.created_at else None
        })
    
    return jsonify({'friends': friends}), 200

@bp.route('/pending', methods=['GET'])
@jwt_required()
def get_pending_requests():
    user_id = get_jwt_identity()
    
    pending = Friendship.query.filter_by(friend_id=user_id, status='pending').all()
    
    requests = []
    for f in pending:
        requests.append({
            'id': f.id,
            'user': f.user.to_dict(),
            'created_at': f.created_at.isoformat() if f.created_at else None
        })
    
    return jsonify({'requests': requests}), 200

@bp.route('/add', methods=['POST'])
@jwt_required()
def add_friend():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    friend_code = data.get('friend_code')
    if not friend_code:
        return jsonify({'error': '请输入好友代码'}), 400
    
    friend = User.query.filter_by(friend_code=friend_code.upper()).first()
    if not friend:
        return jsonify({'error': '未找到该好友代码对应的用户'}), 404
    
    if friend.id == int(user_id):
        return jsonify({'error': '不能添加自己为好友'}), 400
    
    existing = Friendship.query.filter(
        ((Friendship.user_id == user_id) & (Friendship.friend_id == friend.id)) |
        ((Friendship.user_id == friend.id) & (Friendship.friend_id == user_id))
    ).first()
    
    if existing:
        if existing.status == 'accepted':
            return jsonify({'error': '你们已经是好友了'}), 400
        elif existing.status == 'pending':
            if existing.user_id == int(user_id):
                return jsonify({'error': '已发送好友请求，等待对方确认'}), 400
            else:
                return jsonify({'error': '对方已向你发送好友请求，请查看待处理请求'}), 400
    
    friendship = Friendship(user_id=user_id, friend_id=friend.id, status='pending')
    db.session.add(friendship)
    db.session.commit()
    
    return jsonify({
        'message': '好友请求已发送',
        'friend': friend.to_dict()
    }), 201

@bp.route('/accept/<int:request_id>', methods=['POST'])
@jwt_required()
def accept_friend(request_id):
    user_id = get_jwt_identity()
    
    friendship = Friendship.query.filter_by(id=request_id, friend_id=user_id, status='pending').first()
    
    if not friendship:
        return jsonify({'error': '好友请求不存在'}), 404
    
    friendship.status = 'accepted'
    db.session.commit()
    
    return jsonify({
        'message': '已接受好友请求',
        'friend': friendship.user.to_dict()
    }), 200

@bp.route('/reject/<int:request_id>', methods=['POST'])
@jwt_required()
def reject_friend(request_id):
    user_id = get_jwt_identity()
    
    friendship = Friendship.query.filter_by(id=request_id, friend_id=user_id, status='pending').first()
    
    if not friendship:
        return jsonify({'error': '好友请求不存在'}), 404
    
    db.session.delete(friendship)
    db.session.commit()
    
    return jsonify({'message': '已拒绝好友请求'}), 200

@bp.route('/remove/<int:friendship_id>', methods=['DELETE'])
@jwt_required()
def remove_friend(friendship_id):
    user_id = get_jwt_identity()
    
    friendship = Friendship.query.filter(
        ((Friendship.id == friendship_id) & 
         ((Friendship.user_id == user_id) | (Friendship.friend_id == user_id)))
    ).first()
    
    if not friendship:
        return jsonify({'error': '好友关系不存在'}), 404
    
    db.session.delete(friendship)
    db.session.commit()
    
    return jsonify({'message': '已删除好友'}), 200

@bp.route('/search', methods=['GET'])
@jwt_required()
def search_user_by_code():
    user_id = get_jwt_identity()
    friend_code = request.args.get('code', '').upper()
    
    if not friend_code:
        return jsonify({'error': '请输入好友代码'}), 400
    
    user = User.query.filter_by(friend_code=friend_code).first()
    
    if not user:
        return jsonify({'error': '未找到该用户'}), 404
    
    if user.id == int(user_id):
        return jsonify({'error': '这是你自己的好友代码'}), 400
    
    return jsonify({'user': user.to_dict()}), 200
