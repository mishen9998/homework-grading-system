from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, Schedule
from werkzeug.utils import secure_filename
import pandas as pd
import os
import io

bp = Blueprint('schedules', __name__, url_prefix='/api/schedules')

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

WEEK_DAY_MAP = {
    '周一': 1, '周二': 2, '周三': 3, '周四': 4, '周五': 5, '周六': 6, '周日': 7,
    '星期一': 1, '星期二': 2, '星期三': 3, '星期四': 4, '星期五': 5, '星期六': 6, '星期日': 7,
    '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7
}

SEMESTER_MAP = {
    '第一学期': '第一学期', '第二学期': '第二学期',
    '第1学期': '第一学期', '第2学期': '第二学期',
    '1': '第一学期', '2': '第二学期',
}

def normalize_semester_year(value):
    if not value or pd.isna(value):
        return None
    value = str(value).strip()
    if value.endswith('学年'):
        return value
    if value.endswith('年'):
        return value[:-1] + '学年'
    return value + '学年'

COLOR_MAP = {
    '蓝色': '#74b9ff',
    '橙色': '#fab1a0',
    '青绿色': '#55efc4',
    '紫色': '#a29bfe',
    '黄色': '#ffeaa7',
    '浅粉色': '#fd79a8',
    '红色': '#ff7675',
    '绿色': '#00b894',
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_week_day(value):
    if pd.isna(value):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    value_str = str(value).strip()
    return WEEK_DAY_MAP.get(value_str)

@bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_schedule():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user or user.role != 'admin':
        return jsonify({'error': '只有管理员可以上传课表'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': '只支持 Excel 文件（.xlsx, .xls）'}), 400
    
    try:
        df = pd.read_excel(file)
        
        required_columns = ['星期', '课程名称']
        for col in required_columns:
            if col not in df.columns:
                return jsonify({'error': f'Excel缺少必需列：{col}'}), 400
        
        success_count = 0
        error_list = []
        
        for index, row in df.iterrows():
            try:
                week_day = parse_week_day(row.get('星期'))
                if week_day is None or week_day < 1 or week_day > 7:
                    error_list.append(f'第{index + 2}行：星期格式错误，请使用周一~周日或1~7')
                    continue
                
                start_period = None
                end_period = None
                
                if '开始节次' in df.columns and '结束节次' in df.columns:
                    start_period = int(row['开始节次']) if pd.notna(row.get('开始节次')) else None
                    end_period = int(row['结束节次']) if pd.notna(row.get('结束节次')) else start_period
                elif '节次' in df.columns:
                    start_period = int(row['节次']) if pd.notna(row.get('节次')) else None
                    end_period = start_period
                
                if start_period is None:
                    error_list.append(f'第{index + 2}行：缺少节次信息')
                    continue
                
                if end_period is None:
                    end_period = start_period
                
                if start_period < 1 or start_period > 12 or end_period < 1 or end_period > 12:
                    error_list.append(f'第{index + 2}行：节次必须在1-12之间')
                    continue
                
                if end_period < start_period:
                    error_list.append(f'第{index + 2}行：结束节次不能小于开始节次')
                    continue
                
                color = None
                if '课程颜色标识' in df.columns and pd.notna(row.get('课程颜色标识')):
                    color_input = str(row['课程颜色标识']).strip()
                    color = COLOR_MAP.get(color_input, color_input)
                
                semester = None
                if '学期' in df.columns and pd.notna(row.get('学期')):
                    semester_input = str(row['学期']).strip()
                    semester = SEMESTER_MAP.get(semester_input, semester_input)
                
                semester_year = normalize_semester_year(row.get('学期年份'))
                
                for period in range(start_period, end_period + 1):
                    schedule = Schedule(
                        week_day=week_day,
                        period=period,
                        course_name=str(row['课程名称']),
                        teacher_name=str(row.get('教师姓名', '')) if pd.notna(row.get('教师姓名')) else None,
                        teacher_id=str(row.get('教师工号', '')) if pd.notna(row.get('教师工号')) else None,
                        class_name=str(row.get('班级', '')) if pd.notna(row.get('班级')) else None,
                        classroom=str(row.get('教室', '')) if pd.notna(row.get('教室')) else None,
                        start_week=int(row.get('开始周', 1)) if pd.notna(row.get('开始周')) else 1,
                        end_week=int(row.get('结束周', 16)) if pd.notna(row.get('结束周')) else 16,
                        semester_year=semester_year,
                        semester=semester,
                        start_period=start_period,
                        end_period=end_period,
                        color=color
                    )
                    db.session.add(schedule)
                
                success_count += 1
            except Exception as e:
                error_list.append(f'第{index + 2}行：{str(e)}')
        
        db.session.commit()
        
        return jsonify({
            'message': f'成功导入 {success_count} 条课程记录',
            'success_count': success_count,
            'errors': error_list[:10]
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'解析Excel失败：{str(e)}'}), 400

@bp.route('/student', methods=['GET'])
@jwt_required()
def get_student_schedule():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    if not user.class_name:
        return jsonify({'error': '您还没有绑定班级'}), 400
    
    schedules = Schedule.query.filter_by(class_name=user.class_name).all()
    
    course_map = {}
    for schedule in schedules:
        key = f"{schedule.week_day}-{schedule.course_name}"
        if key not in course_map:
            course_map[key] = schedule
    
    schedule_grid = {}
    for schedule in schedules:
        key = f"{schedule.week_day}-{schedule.period}"
        if key not in schedule_grid:
            schedule_grid[key] = []
        schedule_grid[key].append(schedule.to_dict())
    
    semester_info = None
    if schedules:
        first = schedules[0]
        if first.semester_year and first.semester:
            semester_info = f"{first.semester_year} {first.semester}"
    
    return jsonify({
        'class_name': user.class_name,
        'schedule_grid': schedule_grid,
        'schedules': [s.to_dict() for s in schedules],
        'semester_info': semester_info
    }), 200

@bp.route('/teacher', methods=['GET'])
@jwt_required()
def get_teacher_schedule():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    if not user.teacher_id:
        return jsonify({'error': '您还没有绑定工号'}), 400
    
    schedules = Schedule.query.filter_by(teacher_id=user.teacher_id).all()
    
    schedule_grid = {}
    for schedule in schedules:
        key = f"{schedule.week_day}-{schedule.period}"
        if key not in schedule_grid:
            schedule_grid[key] = []
        schedule_grid[key].append(schedule.to_dict())
    
    semester_info = None
    if schedules:
        first = schedules[0]
        if first.semester_year and first.semester:
            semester_info = f"{first.semester_year} {first.semester}"
    
    return jsonify({
        'teacher_id': user.teacher_id,
        'teacher_name': user.name,
        'schedule_grid': schedule_grid,
        'schedules': [s.to_dict() for s in schedules],
        'semester_info': semester_info
    }), 200

@bp.route('/clear', methods=['DELETE'])
@jwt_required()
def clear_schedule():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user or user.role != 'admin':
        return jsonify({'error': '只有管理员可以清空课表'}), 403
    
    try:
        count = Schedule.query.delete()
        db.session.commit()
        return jsonify({'message': f'已清空 {count} 条课表记录'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'清空失败：{str(e)}'}), 400

@bp.route('/template', methods=['GET'])
@jwt_required()
def get_template():
    template_data = [
        {'学期年份': '2024-2025学年', '学期': '第二学期', '星期': '周一', '开始节次': 1, '结束节次': 2, '课程名称': '数据库系统原理', '上课地点': '校友楼201', '课程颜色标识': '蓝色', '教师姓名': '张老师', '教师工号': '20260001', '班级': '计算机2401班', '开始周': 1, '结束周': 16},
        {'学期年份': '2024-2025学年', '学期': '第二学期', '星期': '周一', '开始节次': 3, '结束节次': 4, '课程名称': '数字逻辑', '上课地点': '学友楼306', '课程颜色标识': '青绿色', '教师姓名': '李老师', '教师工号': '20260002', '班级': '计算机2401班', '开始周': 1, '结束周': 16},
        {'学期年份': '2024-2025学年', '学期': '第二学期', '星期': '周二', '开始节次': 1, '结束节次': 2, '课程名称': '工程概论', '上课地点': '校友楼101', '课程颜色标识': '橙色', '教师姓名': '王老师', '教师工号': '20260003', '班级': '计算机2401班', '开始周': 1, '结束周': 16},
        {'学期年份': '2024-2025学年', '学期': '第二学期', '星期': '周二', '开始节次': 3, '结束节次': 4, '课程名称': '公共体育IV', '上课地点': '九坡体操馆', '课程颜色标识': '紫色', '教师姓名': '赵老师', '教师工号': '20260004', '班级': '计算机2401班', '开始周': 1, '结束周': 16},
        {'学期年份': '2024-2025学年', '学期': '第二学期', '星期': '周二', '开始节次': 5, '结束节次': 6, '课程名称': '习近平新时代中国特色社会主义思想概论', '上课地点': '学友楼402', '课程颜色标识': '黄色', '教师姓名': '刘老师', '教师工号': '20260005', '班级': '计算机2401班', '开始周': 1, '结束周': 16},
        {'学期年份': '2024-2025学年', '学期': '第二学期', '星期': '周三', '开始节次': 1, '结束节次': 2, '课程名称': '计算机网络编程', '上课地点': '逸夫楼702', '课程颜色标识': '蓝色', '教师姓名': '陈老师', '教师工号': '20260006', '班级': '计算机2401班', '开始周': 1, '结束周': 16},
        {'学期年份': '2024-2025学年', '学期': '第二学期', '星期': '周三', '开始节次': 3, '结束节次': 4, '课程名称': '大学英语IV', '上课地点': '国教综合大楼420', '课程颜色标识': '青绿色', '教师姓名': '周老师', '教师工号': '20260007', '班级': '计算机2401班', '开始周': 1, '结束周': 16},
        {'学期年份': '2024-2025学年', '学期': '第二学期', '星期': '周四', '开始节次': 1, '结束节次': 2, '课程名称': '工程概论', '上课地点': '学友楼306', '课程颜色标识': '紫色', '教师姓名': '王老师', '教师工号': '20260003', '班级': '计算机2401班', '开始周': 1, '结束周': 16},
        {'学期年份': '2024-2025学年', '学期': '第二学期', '星期': '周四', '开始节次': 5, '结束节次': 6, '课程名称': '数据库系统原理', '上课地点': '逸夫楼702', '课程颜色标识': '黄色', '教师姓名': '张老师', '教师工号': '20260001', '班级': '计算机2401班', '开始周': 1, '结束周': 16},
        {'学期年份': '2024-2025学年', '学期': '第二学期', '星期': '周五', '开始节次': 5, '结束节次': 6, '课程名称': '计算机网络编程', '上课地点': '逸夫楼702', '课程颜色标识': '蓝色', '教师姓名': '陈老师', '教师工号': '20260006', '班级': '计算机2401班', '开始周': 1, '结束周': 16},
    ]
    
    df = pd.DataFrame(template_data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='课表模板')
    output.seek(0)
    
    response = Response(
        output.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': 'attachment; filename=schedule_template.xlsx'
        }
    )
    return response
