import os
import re
import sqlite3
import secrets
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import pandas as pd

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

DATABASE = 'tiku.db'
UPLOAD_FOLDER = 'uploads'
EXPORT_FOLDER = 'exports'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXPORT_FOLDER, exist_ok=True)

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_type TEXT NOT NULL,
            content TEXT NOT NULL,
            score REAL,
            answer TEXT,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def parse_text_questions(text):
    questions = []
    lines = text.strip().split('\n')
    
    type_mapping = {
        '选择题': '单选题',
        '单选题': '单选题',
        '多选题': '多选题',
        '判断题': '判断题',
        '填空题': '填空题',
        '大题': '大题',
        '综合题': '大题',
        '综合大题': '大题',
        '简答题': '大题',
        '论述题': '大题',
        '编程题': '大题',
    }
    
    type_pattern = r'^#+\s*[一二三四五六七八九十]+[、.．]\s*(.+?题|.+?选择|.+?判断|.+?填空|.+?大题|.+?编程)'
    question_pattern = r'^(\d+)[.、．]\s*(.+)$'
    single_option_pattern = r'^([A-D])[.、．)]\s*(.+)$'
    inline_option_pattern = r'([A-D])[.、．)]\s*([^A-D]+?)(?=\s+[A-D][.、．)]|$)'
    answer_section_pattern = r'^#+\s*参考答案|^参考答案'
    answer_type_pattern = r'^#+\s*[一二三四五六七八九十]+[、.．]\s*(.+?题|.+?选择|.+?判断|.+?填空)'
    sub_title_pattern = r'^###\s*(题目|题目要求|示例|要求)'
    
    current_type = '单选题'
    current_question = None
    in_answer_section = False
    current_answer_type = ''
    answers = {}
    big_question_counter = 0
    in_big_question = False
    in_code_block = False
    
    for i, line in enumerate(lines):
        original_line = line
        line = line.strip()
        
        if line.startswith('```'):
            in_code_block = not in_code_block
            continue
        
        if in_code_block:
            continue
        
        if not line or line == '---':
            continue
        
        if re.match(answer_section_pattern, line, re.IGNORECASE):
            in_answer_section = True
            if current_question:
                questions.append(current_question)
                current_question = None
            continue
        
        if in_answer_section:
            type_match = re.match(answer_type_pattern, line)
            if type_match:
                type_name = type_match.group(1).strip()
                for key, value in type_mapping.items():
                    if key in type_name:
                        current_answer_type = value
                        break
                continue
            
            multi_ans_pattern = r'(\d+)[.、．]\s*(\S+)'
            multi_matches = re.findall(multi_ans_pattern, line)
            
            if multi_matches and len(multi_matches) >= 1:
                for q_num, ans_content in multi_matches:
                    ans_content = ans_content.strip()
                    
                    if current_answer_type == '判断题':
                        if '√' in ans_content or '对' in ans_content or 'T' in ans_content.upper():
                            ans_content = '正确'
                        elif '×' in ans_content or '错' in ans_content or 'F' in ans_content.upper():
                            ans_content = '错误'
                    elif current_answer_type in ['单选题', '多选题']:
                        letter_match = re.match(r'^([A-D]+)', ans_content, re.IGNORECASE)
                        if letter_match:
                            ans_content = letter_match.group(1).upper()
                    
                    key = f"{current_answer_type}_{q_num}"
                    answers[key] = ans_content
            continue
        
        type_match = re.match(type_pattern, line)
        if type_match:
            if current_question:
                questions.append(current_question)
                current_question = None
            
            type_name = type_match.group(1).strip()
            for key, value in type_mapping.items():
                if key in type_name:
                    current_type = value
                    break
            
            if current_type == '大题':
                in_big_question = True
                big_question_counter += 1
                current_question = {
                    '题型': '大题',
                    '题目内容': '',
                    '分数': 10,
                    '正确答案': '',
                    '选项A': '',
                    '选项B': '',
                    '选项C': '',
                    '选项D': '',
                    '_num': str(big_question_counter)
                }
            else:
                in_big_question = False
            continue
        
        if in_big_question and current_question:
            if re.match(sub_title_pattern, line, re.IGNORECASE):
                continue
            
            if current_question['题目内容']:
                current_question['题目内容'] += '\n' + line
            else:
                current_question['题目内容'] = line
            continue
        
        q_match = re.match(question_pattern, line)
        if q_match and not in_big_question:
            if current_question:
                questions.append(current_question)
            
            content = q_match.group(2).strip()
            content = re.sub(r'（\s*）|\(\s*\)|【\s*】', '', content)
            content = content.strip()
            
            current_question = {
                '题型': current_type,
                '题目内容': content,
                '分数': 2 if current_type in ['单选题', '判断题'] else 3 if current_type == '多选题' else 5,
                '正确答案': '',
                '选项A': '',
                '选项B': '',
                '选项C': '',
                '选项D': '',
                '_num': q_match.group(1)
            }
            continue
        
        if current_question and not in_big_question:
            inline_opts = re.findall(inline_option_pattern, line)
            if inline_opts and len(inline_opts) >= 2:
                for opt_letter, opt_content in inline_opts:
                    opt_content = opt_content.strip()
                    if opt_content:
                        current_question[f'选项{opt_letter}'] = opt_content
            else:
                single_opt_match = re.match(single_option_pattern, line)
                if single_opt_match:
                    opt_letter = single_opt_match.group(1)
                    opt_content = single_opt_match.group(2).strip()
                    current_question[f'选项{opt_letter}'] = opt_content
    
    if current_question:
        questions.append(current_question)
    
    for q in questions:
        q_num = q.get('_num', '')
        q_type = q['题型']
        key = f"{q_type}_{q_num}"
        
        if key in answers:
            q['正确答案'] = answers[key]
        
        if '_num' in q:
            del q['_num']
    
    return questions

def parse_excel_file(filepath):
    try:
        df = pd.read_excel(filepath)
        required_columns = ['题型', '题目内容', '分数', '正确答案']
        
        for col in required_columns:
            if col not in df.columns:
                return None, f"缺少必需列: {col}"
        
        questions = []
        for _, row in df.iterrows():
            question = {
                '题型': str(row['题型']) if pd.notna(row['题型']) else '',
                '题目内容': str(row['题目内容']) if pd.notna(row['题目内容']) else '',
                '分数': float(row['分数']) if pd.notna(row['分数']) else 0,
                '正确答案': str(row['正确答案']) if pd.notna(row['正确答案']) else '',
                '选项A': str(row['选项A']) if '选项A' in df.columns and pd.notna(row['选项A']) else '',
                '选项B': str(row['选项B']) if '选项B' in df.columns and pd.notna(row['选项B']) else '',
                '选项C': str(row['选项C']) if '选项C' in df.columns and pd.notna(row['选项C']) else '',
                '选项D': str(row['选项D']) if '选项D' in df.columns and pd.notna(row['选项D']) else '',
            }
            if question['题型'] and question['题目内容']:
                questions.append(question)
        
        return questions, None
    except Exception as e:
        return None, str(e)

def save_questions(questions):
    conn = get_db()
    cursor = conn.cursor()
    success_count = 0
    
    for q in questions:
        try:
            cursor.execute('''
                INSERT INTO questions (question_type, content, score, answer, option_a, option_b, option_c, option_d)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (q['题型'], q['题目内容'], q['分数'], q['正确答案'], 
                  q.get('选项A', ''), q.get('选项B', ''), q.get('选项C', ''), q.get('选项D', '')))
            success_count += 1
        except Exception as e:
            print(f"Error inserting question: {e}")
    
    conn.commit()
    conn.close()
    return success_count

def generate_excel(questions):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'题库导入_{timestamp}.xlsx'
    filepath = os.path.join(EXPORT_FOLDER, filename)
    
    df_data = []
    for q in questions:
        df_data.append({
            '题型': q['题型'],
            '题目内容': q['题目内容'],
            '分数': q['分数'],
            '正确答案': q['正确答案'],
            '选项A': q.get('选项A', ''),
            '选项B': q.get('选项B', ''),
            '选项C': q.get('选项C', ''),
            '选项D': q.get('选项D', '')
        })
    
    df = pd.DataFrame(df_data)
    df.to_excel(filepath, index=False, engine='openpyxl')
    
    return filename

@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        token = secrets.token_hex(16)
        return jsonify({
            'success': True,
            'message': '登录成功',
            'token': token
        })
    else:
        return jsonify({
            'success': False,
            'message': '账号或密码错误'
        }), 401

@app.route('/api/import/text', methods=['POST'])
def import_text():
    data = request.get_json()
    text = data.get('text', '')
    
    if not text.strip():
        return jsonify({'success': False, 'message': '文本内容不能为空'}), 400
    
    questions = parse_text_questions(text)
    
    if not questions:
        return jsonify({'success': False, 'message': '未能识别出有效题目，请检查格式'}), 400
    
    count = save_questions(questions)
    excel_file = generate_excel(questions)
    return jsonify({
        'success': True,
        'message': f'成功导入 {count} 道题目',
        'questions': questions,
        'excel_file': excel_file
    })

@app.route('/api/import/excel', methods=['POST'])
def import_excel():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择文件'}), 400
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': '请上传Excel文件(.xlsx或.xls)'}), 400
    
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)
    
    questions, error = parse_excel_file(filepath)
    
    if error:
        return jsonify({'success': False, 'message': f'解析失败: {error}'}), 400
    
    count = save_questions(questions)
    excel_file = generate_excel(questions)
    return jsonify({
        'success': True,
        'message': f'成功导入 {count} 道题目',
        'questions': questions,
        'excel_file': excel_file
    })

@app.route('/api/import/file', methods=['POST'])
def import_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择文件'}), 400
    
    if not file.filename.endswith('.txt'):
        return jsonify({'success': False, 'message': '请上传文本文件(.txt)'}), 400
    
    try:
        content = file.read().decode('utf-8')
    except UnicodeDecodeError:
        try:
            content = file.read().decode('gbk')
        except:
            return jsonify({'success': False, 'message': '文件编码不支持，请使用UTF-8或GBK编码'}), 400
    
    questions = parse_text_questions(content)
    
    if not questions:
        return jsonify({'success': False, 'message': '未能识别出有效题目，请检查格式'}), 400
    
    count = save_questions(questions)
    excel_file = generate_excel(questions)
    return jsonify({
        'success': True,
        'message': f'成功导入 {count} 道题目',
        'questions': questions,
        'excel_file': excel_file
    })

@app.route('/api/questions', methods=['GET'])
def get_questions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM questions ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()
    
    questions = []
    for row in rows:
        questions.append({
            'id': row['id'],
            '题型': row['question_type'],
            '题目内容': row['content'],
            '分数': row['score'],
            '正确答案': row['answer'],
            '选项A': row['option_a'],
            '选项B': row['option_b'],
            '选项C': row['option_c'],
            '选项D': row['option_d'],
            '创建时间': row['created_at']
        })
    
    return jsonify({'success': True, 'questions': questions})

@app.route('/api/questions/<int:question_id>', methods=['DELETE'])
def delete_question(question_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM questions WHERE id = ?', (question_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': '删除成功'})

@app.route('/api/questions/clear', methods=['POST'])
def clear_questions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM questions')
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': '已清空所有题目'})

@app.route('/api/download/<filename>')
def download_excel(filename):
    filepath = os.path.join(EXPORT_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    else:
        return jsonify({'success': False, 'message': '文件不存在'}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
