# 作业管理系统

基于 Python Flask 和 Vue 3 的学生、老师身份登录及作业管理在线系统。

## 项目结构

```
.
├── backend/                 # Python 后端
│   ├── app/
│   │   ├── models/         # 数据库模型
│   │   ├── routes/         # API 路由
│   │   └── utils/          # 工具函数
│   ├── config.py           # 配置文件
│   ├── requirements.txt    # Python 依赖
│   └── run.py             # 启动文件
└── frontend/               # Vue 前端
    ├── src/
    │   ├── api/           # API 接口
    │   ├── components/    # 组件
    │   ├── views/         # 页面
    │   ├── store/         # 状态管理
    │   └── router/        # 路由配置
    └── package.json       # Node 依赖
```

## 功能特性

### 学生功能
- 用户注册和登录
- 查看作业列表
- 提交作业
- 查看提交记录和批改结果

### 老师功能
- 用户注册和登录
- 创建作业
- 查看学生提交
- 批改作业（打分和评语）
- 老师 AI 助手：对话式生成作业草稿、分析批改重点、撰写作业提醒
- AI 草稿可一键应用到课程的发布作业表单，发布前由老师复核确认

## 技术栈

### 后端
- Python 3.x
- Flask - Web 框架
- Flask-SQLAlchemy - ORM
- Flask-JWT-Extended - JWT 认证
- Flask-CORS - 跨域支持
- SQLAlchemy ORM（开发环境默认 SQLite，生产环境可切换 MySQL）
- MySQL 驱动：PyMySQL

### 前端
- Vue 3 - 前端框架
- Vue Router - 路由管理
- Pinia - 状态管理
- Axios - HTTP 客户端
- Vite - 构建工具

## 快速开始

### 后端启动

1. 进入后端目录：
```bash
cd backend
```

2. 创建虚拟环境（推荐）：
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

5. 运行后端服务：
```bash
python run.py
```

后端服务将在 http://localhost:5000 启动

### 前端启动

1. 进入前端目录：
```bash
cd frontend
```

2. 安装依赖：
```bash
npm install
```

3. 运行前端开发服务器：
```bash
npm run dev
```

前端服务将在 http://localhost:3000 启动

## API 接口

### 认证接口
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/me` - 获取当前用户信息

### 作业接口
- `POST /api/assignments` - 创建作业（老师）
- `GET /api/assignments` - 获取作业列表
- `GET /api/assignments/:id` - 获取作业详情
- `POST /api/assignments/:id/submit` - 提交作业（学生）
- `GET /api/assignments/:id/submissions` - 获取作业提交（老师）
- `PUT /api/assignments/submissions/:id/grade` - 批改作业（老师）
- `GET /api/assignments/my-submissions` - 获取我的提交（学生）

### 老师 AI 助手接口
- `POST /api/ai/assistant` - 老师 AI 助手（需要教师 JWT）
- `POST /api/knowledge/agent` - 师生权限智能体（课程查询、作业进度；教师可预览并确认发布作业和发送提醒）

助手使用项目已有的 DeepSeek 配置。启动后端前，在 `backend/.env` 中配置
`DEEPSEEK_API_KEY`；助手只生成建议和可编辑草稿，不会绕过老师直接发布作业或修改成绩。

## 数据库模型

项目默认使用 SQLite，配置 `DATABASE_URL` 后可切换到 MySQL，无需修改业务模型和接口。例如：

```env
DATABASE_URL=mysql+pymysql://homework_user:密码@127.0.0.1:3306/homework?charset=utf8mb4
```

首次切换时，请先在 MySQL 中创建 `homework` 数据库，再运行：

```bash
cd backend
pip install -r requirements.txt
python migrate_sqlite_to_mysql.py
```

迁移脚本只复制数据，不会删除原来的 `backend/instance/homework.db`。文件上传内容仍保存在 `backend/app/tupian` 和 `backend/app/uploads`，需要一并保留。

### User（用户）
- id: 用户ID
- username: 用户名
- password: 密码（加密）
- email: 邮箱
- role: 角色（student/teacher）
- name: 姓名

### Assignment（作业）
- id: 作业ID
- title: 标题
- description: 描述
- due_date: 截止日期
- teacher_id: 老师ID

### Submission（提交）
- id: 提交ID
- assignment_id: 作业ID
- student_id: 学生ID
- content: 内容
- score: 分数
- feedback: 评语
- status: 状态（submitted/graded）

## 使用说明

1. 首先注册一个老师账号
2. 老师登录后创建作业
3. 注册学生账号
4. 学生登录后查看并提交作业
5. 老师查看学生提交并批改作业

## 注意事项

- 生产环境请修改 `config.py` 中的 SECRET_KEY 和 JWT_SECRET_KEY
- 建议使用 PostgreSQL 或 MySQL 替代 SQLite 用于生产环境
- 前端开发服务器已配置代理，API 请求会自动转发到后端

## 开发建议

- 可以添加文件上传功能支持附件提交
- 可以添加作业分类和标签功能
- 可以添加统计分析功能
- 可以添加通知功能
- 可以添加实时聊天功能

## 知识库扩容

知识库在未配置扩展服务时继续使用本机混合检索。生产环境可启用校内 Redis 共享缓存与限流，并启用 Qdrant 向量近邻索引，避免知识总量增长后在每次请求中扫描大量资料。部署步骤、配置参数、降级行为和隐私边界见 [知识库扩容与隐私实施说明.md](知识库扩容与隐私实施说明.md)。

## 许可证

MIT
