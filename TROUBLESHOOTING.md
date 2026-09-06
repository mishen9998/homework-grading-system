# 登录失败问题诊断和解决方案

## 问题分析

经过检查，发现以下问题：

### 1. 后端服务未运行
- 端口5000没有被占用
- 后端Flask服务没有启动

### 2. 数据库文件不存在
- backend目录下没有homework.db文件
- 测试账号没有被创建

### 3. Python环境问题
- Python命令执行失败（错误代码9009）
- 可能是Python路径配置问题

## 解决方案

### 方案一：手动安装Python（推荐）

#### 步骤1：下载并安装Python
1. 访问：https://www.python.org/downloads/
2. 下载Python 3.8或更高版本
3. **重要**：安装时勾选"Add Python to PATH"
4. 完成安装后重启命令行

#### 步骤2：验证Python安装
打开新的命令行窗口，运行：
```bash
python --version
```
应该显示Python版本号，如：Python 3.11.0

#### 步骤3：安装后端依赖
```bash
cd backend
pip install -r requirements.txt
```

#### 步骤4：创建测试账号
```bash
python init_test_accounts.py
```

#### 步骤5：启动后端
```bash
python run.py
```

应该看到类似输出：
```
 * Running on http://0.0.0.0:5000
```

#### 步骤6：启动前端（新开命令行窗口）
```bash
cd frontend
npm run dev
```

### 方案二：使用虚拟环境

#### 步骤1：创建虚拟环境
```bash
cd backend
python -m venv venv
```

#### 步骤2：激活虚拟环境
Windows:
```bash
venv\Scripts\activate
```

#### 步骤3：安装依赖
```bash
pip install -r requirements.txt
```

#### 步骤4：初始化数据库和账号
```bash
python init_test_accounts.py
```

#### 步骤5：启动后端
```bash
python run.py
```

### 方案三：使用一键启动脚本

1. 双击运行 `start.bat`
2. 脚本会自动完成所有步骤
3. 如果失败，请查看错误信息

## 验证步骤

### 1. 检查Python是否正常
```bash
python --version
```

### 2. 检查依赖是否安装
```bash
pip list | findstr Flask
```

应该看到Flask相关包

### 3. 检查后端是否运行
```bash
netstat -ano | findstr :5000
```

应该看到端口5000被占用

### 4. 检查数据库文件
```bash
cd backend
dir *.db
```

应该看到homework.db文件

### 5. 测试后端API
打开浏览器访问：http://localhost:5000

应该看到Flask欢迎页面或404错误（说明服务在运行）

## 常见错误和解决

### 错误1：'python' 不是内部或外部命令
**原因**：Python没有添加到PATH环境变量

**解决**：
1. 重新安装Python，确保勾选"Add Python to PATH"
2. 或手动添加Python到PATH：
   - 右键"此电脑" → 属性 → 高级系统设置
   - 环境变量 → 系统变量 → Path
   - 添加Python安装路径（如：C:\Python311\）

### 错误2：ModuleNotFoundError: No module named 'flask'
**原因**：Flask包没有安装

**解决**：
```bash
pip install Flask==3.0.0
```

### 错误3：端口5000已被占用
**原因**：其他程序占用了5000端口

**解决**：
1. 查找占用端口的进程：
   ```bash
   netstat -ano | findstr :5000
   ```
2. 结束进程：
   ```bash
   taskkill /PID <进程ID> /F
   ```
3. 或修改后端端口（config.py）

### 错误4：数据库锁定错误
**原因**：数据库文件被其他进程占用

**解决**：
1. 停止所有Python进程
2. 删除homework.db文件
3. 重新运行init_test_accounts.py

## 完整测试流程

### 1. 确保后端运行
- 访问 http://localhost:5000
- 确保没有错误信息

### 2. 确保前端运行
- 访问 http://localhost:3000
- 确保看到登录页面

### 3. 测试老师登录
1. 点击"老师"按钮
2. 输入用户名：teacher1
3. 输入密码：123456
4. 点击登录
5. 应该跳转到老师仪表板

### 4. 测试学生登录
1. 点击"学生"按钮
2. 输入用户名：student1
3. 输入密码：123456
4. 点击登录
5. 应该跳转到学生仪表板

## 调试技巧

### 查看后端日志
后端运行时会显示详细的日志信息，包括：
- 请求信息
- 错误信息
- 数据库操作

### 查看前端控制台
1. 按F12打开开发者工具
2. 切换到Console标签
3. 查看JavaScript错误和网络请求

### 使用curl测试API
```bash
curl -X POST http://localhost:5000/api/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"teacher1\",\"password\":\"123456\"}"
```

## 如果问题仍然存在

1. **完全重新安装Python**
   - 卸载现有Python
   - 重新安装，确保勾选"Add to PATH"

2. **使用不同的Python版本**
   - 尝试Python 3.9、3.10、3.11

3. **检查防火墙设置**
   - 确保端口5000和3000没有被阻止

4. **查看系统日志**
   - Windows事件查看器
   - 查找Python相关错误

## 联系支持

如果以上方案都无法解决问题，请提供：
1. Python版本：`python --version` 的输出
2. pip版本：`pip --version` 的输出
3. 错误信息：完整的错误堆栈
4. 操作系统版本
