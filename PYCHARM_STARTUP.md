# PyCharm 一键启动使用说明

## 快速启动

### 方法一：直接运行 Python 脚本
1. 在 PyCharm 中打开项目
2. 找到项目根目录下的 `start_all.py` 文件
3. 右键点击该文件，选择 "Run 'start_all'"
4. 等待脚本自动完成环境检查、依赖安装和服务启动
5. 浏览器会自动打开前端页面

### 方法二：在终端运行
1. 在 PyCharm 底部打开 Terminal
2. 运行命令：`python start_all.py`
3. 等待启动完成

## 脚本功能

`start_all.py` 脚本会自动完成以下操作：

1. **环境检查**
   - 检查 Python 版本（需要 3.8+）
   - 检查 Node.js/npm 是否安装

2. **环境准备**
   - 自动创建 Python 虚拟环境（如果不存在）
   - 安装后端依赖包
   - 安装前端依赖包（如果 node_modules 不存在）

3. **服务启动**
   - 启动 Flask 后端服务（端口 5000）
   - 启动 Vue3 前端开发服务器（端口 5173）
   - 自动打开浏览器访问前端页面

4. **优雅退出**
   - 按 Ctrl+C 可以同时停止前后端服务

## 服务地址

- **后端 API**：http://localhost:5000
- **前端页面**：http://localhost:5173

## 测试账号

- **老师账号**：用户名 `teacher1`，密码 `123456`
- **学生账号**：用户名 `student1`，密码 `123456`

## 注意事项

1. 确保已安装 Python 3.8 或更高版本
2. 确保已安装 Node.js 和 npm
3. 首次运行会自动安装依赖，可能需要较长时间
4. 如果端口被占用，请先关闭占用端口的程序

## 常见问题

### Q: 提示 Python 版本不符合要求
A: 请安装 Python 3.8 或更高版本，并确保已添加到系统 PATH

### Q: 提示未找到 npm
A: 请先安装 Node.js（包含 npm），下载地址：https://nodejs.org/

### Q: 依赖安装失败
A: 检查网络连接，或使用国内镜像源：
   - 后端：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple`
   - 前端：`npm install --registry=https://registry.npmmirror.com`

### Q: 服务启动失败
A: 检查端口 5000 和 5173 是否被其他程序占用
