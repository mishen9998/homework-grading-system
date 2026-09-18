# 启动指南

## 前端状态
✅ 前端已成功启动在：http://localhost:3000

## 后端启动说明

由于系统Python环境配置问题，请按照以下步骤手动启动后端：

### 方法1：使用Python安装包（推荐）

1. 下载并安装Python 3.8+：https://www.python.org/downloads/
2. 安装时勾选"Add Python to PATH"
3. 打开新的命令行窗口，进入backend目录：
   ```bash
   cd backend
   ```
4. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
5. 启动后端：
   ```bash
   python run.py
   ```

### 方法2：使用虚拟环境

1. 进入backend目录：
   ```bash
   cd backend
   ```
2. 创建虚拟环境：
   ```bash
   python -m venv venv
   ```
3. 激活虚拟环境：
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - Linux/Mac:
     ```bash
     source venv/bin/activate
     ```
4. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
5. 启动后端：
   ```bash
   python run.py
   ```

## 测试账号

### 老师账号
- 用户名：teacher1
- 密码：123456
- 邮箱：teacher1@example.com
- 姓名：张老师

### 学生账号
- 用户名：student1
- 密码：123456
- 邮箱：student1@example.com
- 姓名：李同学

## 测试步骤

1. **启动后端**（按照上述方法）
   - 后端将在 http://localhost:5000 运行
   - 确保看到类似输出：`Running on http://0.0.0.0:5000`

2. **访问前端**
   - 打开浏览器访问：http://localhost:3000
   - 前端应该显示登录页面

3. **注册老师账号**
   - 点击"立即注册"
   - 填写老师账号信息：
     - 用户名：teacher1
     - 姓名：张老师
     - 邮箱：teacher1@example.com
     - 密码：123456
     - 角色：选择"老师"
   - 点击"注册"

4. **老师登录**
   - 使用注册的账号登录
   - 应该跳转到老师仪表板

5. **创建作业**
   - 在老师仪表板点击"创建作业"标签
   - 填写作业信息：
     - 标题：第一次作业
     - 描述：请完成第一章的练习题
     - 截止日期：选择未来的日期
   - 点击"创建作业"

6. **注册学生账号**
   - 点击右上角"退出登录"
   - 点击"立即注册"
   - 填写学生账号信息：
     - 用户名：student1
     - 姓名：李同学
     - 邮箱：student1@example.com
     - 密码：123456
     - 角色：选择"学生"
   - 点击"注册"

7. **学生登录**
   - 使用注册的学生账号登录
   - 应该跳转到学生仪表板

8. **提交作业**
   - 在学生仪表板查看作业列表
   - 点击"提交作业"
   - 填写作业内容
   - 点击"提交"

9. **老师批改作业**
   - 退出学生账号，登录老师账号
   - 在老师仪表板点击作业的"查看提交"按钮
   - 查看学生提交的作业
   - 输入分数（0-100）和评语
   - 点击"提交批改"

10. **学生查看批改结果**
    - 退出老师账号，登录学生账号
    - 切换到"我的提交"标签
    - 查看作业的分数和评语

## 故障排除

### 后端无法启动
- 确保Python已正确安装：`python --version`
- 确保依赖已安装：`pip list | findstr Flask`
- 检查端口5000是否被占用：`netstat -ano | findstr :5000`

### 前端无法连接后端
- 确保后端正在运行
- 检查浏览器控制台是否有错误信息
- 确认CORS配置正确

### 数据库问题
- 删除backend目录下的homework.db文件
- 重新启动后端，会自动创建新的数据库

## API测试

可以使用Postman或curl测试API：

### 注册用户
```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","name":"测试","email":"test@example.com","password":"123456","role":"student"}'
```

### 登录
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"123456"}'
```

### 创建作业（需要token）
```bash
curl -X POST http://localhost:5000/api/assignments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"title":"测试作业","description":"作业描述","due_date":"2026-12-31T23:59:59"}'
```

## 下一步

系统基础框架已完成，可以考虑添加以下功能：
- 文件上传功能
- 作业分类和标签
- 统计分析功能
- 邮件通知
- 实时聊天
- 作业模板
- 批量导入学生
- 成绩导出
