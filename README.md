# TechPath — AI TA 求职学习检验工具

> 帮助「技术美术 / AI TA」岗位求职者系统备考：导入学习材料 → 苏格拉底式检验 → 分析岗位差距 → 监测竞品作品集

## 核心功能

- **知识库**：导入 GitHub 仓库 / 文章 URL / 纯文本 / B站视频，自动生成摘要和技术标签
- **学习中心**：项目解读、知识点讲解、个性化学习路径生成（三合一带学模式）
- **学习检验**：苏格拉底式追问 Agent，生成掌握度报告，支持技能包风格切换
- **知识网络**：可视化知识点关联图谱，掌握度热力图 + 学习推荐
- **岗位情报**：爬取 Boss 直聘 JD，提取技能频率，自动生成 Gap 分析
- **竞品监测**：采集 B站技术美术作品集，S/A/B/C 评级对标分析
- **技能包系统**：Agent 行为可插拔（米哈游面试风格 / 牛客面经 / 作品集评级标准等）

---

## 环境要求

| 依赖 | 版本 |
|------|------|
| Python | 3.11+ |
| Microsoft Edge | 任意新版（用于 B站/Boss直聘爬虫） |
| DeepSeek API Key | 必填，用于所有 AI 功能 |
| GitHub Token | 必填，用于项目解读 |
| 阿里云百炼 QWEN_API_KEY | 可选，用于 B站视频画面分析 |

---

## 安装步骤

### 1. 克隆项目

```bash
git clone https://github.com/linkq-q/techpath
cd techpath/TechPath
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# 必填
DEEPSEEK_API_KEY=your_deepseek_key_here
DEEPSEEK_MODEL=deepseek-chat
GITHUB_TOKEN=your_github_token_here

# 可选（B站视频画面分析）
QWEN_API_KEY=your_qwen_key_here
```

### 4. 验证安装（推荐）

```bash
python scripts/health_check.py
```

全部显示 ✅ 后继续下一步。

### 5. 启动应用

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

---

## 配置说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek 平台的 API Key，用于检验/讲解/情报分析 |
| `DEEPSEEK_MODEL` | 否 | 默认 `deepseek-chat`，可改为 `deepseek-reasoner` |
| `GITHUB_TOKEN` | ✅ | GitHub Personal Access Token（classic），需要 `repo` 读权限 |
| `QWEN_API_KEY` | 否 | 阿里云百炼 API Key，用于 B站视频截帧分析 |

---

## 功能使用指南

### 📚 知识库
导入学习材料。支持 GitHub 仓库 URL、文章/网页 URL、纯文本粘贴、B站视频链接。导入后系统自动生成摘要和技术标签。

### 📖 学习中心
三种带学模式：①「项目解读」输入 GitHub URL 生成7章节学习报告；②「知识点讲解」输入知识点名称获取个性化讲解；③「学习路径」设置目标岗位和周期自动规划。

### 🎯 学习检验
从知识库选择知识点开始苏格拉底式追问，Agent 会递进追问到你真正理解为止。输入「结束检验」生成掌握度报告。

### 🕸️ 知识网络
可视化展示所有知识点的关联关系。节点颜色：红=未学、橙=学过、绿=已掌握。首次使用需点击「强制重建」从历史记录提取。

### 🔍 岗位情报
刷新情报会爬取 Boss 直聘最新 JD，分析高频技能并与你的知识库对比，生成学习 Gap 报告。需要提前在浏览器窗口完成登录。

### 🏆 竞品监测
采集 B站技术美术求职作品集，自动提取技术标签并在同届样本中生成 S/A/B/C 评级。点击「我的对标」输入你的技术标签查看预估位置。

### ⚡ 技能包
管理 Agent 的专业知识模块。激活「米哈游面试风格」后，检验 Agent 会采用米哈游式追问节奏。可自定义新技能包。

---

## API Key 获取指引

| Key | 获取地址 | 费用 |
|-----|---------|------|
| DeepSeek API Key | platform.deepseek.com → API 密钥 | deepseek-chat：输入1元/百万token |
| GitHub Token | github.com → Settings → Developer settings → Personal access tokens | 免费 |
| 阿里云百炼 QWEN | dashscope.aliyun.com → API-KEY 管理 | 有免费额度 |

---

## 常见问题 FAQ

**Q1：启动后页面显示「DEEPSEEK_API_KEY 未配置」**
在项目根目录创建 `.env` 文件，添加 `DEEPSEEK_API_KEY=your_key`，然后重启 Streamlit。

**Q2：知识网络页面一直显示「暂无知识节点」**
先在学习中心讲解至少一个知识点，然后返回知识网络页面点击「强制重建」按钮。

**Q3：B站竞品监测报错或无法弹出登录窗口**
确认 Edge 浏览器安装在默认路径 `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`，且已安装 DrissionPage（`pip install DrissionPage`）。

**Q4：GitHub 项目导入失败，提示 403**
GitHub Token 可能已过期或权限不足。前往 GitHub → Settings → Developer settings 重新生成 Token，并确保勾选 `repo` 权限。

**Q5：检验时 Agent 不回复或报错**
检查 DeepSeek API Key 是否有效，以及网络是否能访问 `api.deepseek.com`。可在终端运行 `python scripts/health_check.py` 快速诊断。

---

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端框架 | Streamlit |
| AI 推理 | DeepSeek-chat（OpenAI 兼容 API） |
| 视觉分析 | 阿里云百炼 Qwen-VL |
| 记忆系统 | Mem0 |
| 知识图谱 | NetworkX + PyVis |
| 浏览器自动化 | DrissionPage + Microsoft Edge |
| 数据库 | SQLite（SQLAlchemy ORM） |
| 环境配置 | python-dotenv |

---

## 版本更新记录

### Phase 5（当前）
- 修复知识网络页面加载问题，添加 pyvis 降级方案
- 修复检验页面知识点不显示，新增标签筛选
- B站爬虫改为命令行等待登录模式（与 Boss 直聘一致）
- 新增 B站搜索结果相关性过滤
- 修复米哈游面试风格技能包显示，确认4个预置技能包全部同步
- 全局新增耗时估算提示和实际用时展示
- 全局错误处理优化，API Key 未配置时顶部警告
- 新增 API 成本统计（侧边栏显示今日/累计费用）
- 新增 `scripts/health_check.py` 安装验证脚本

### Phase 1-4
- 知识库管理（GitHub / URL / 文本 / 视频四种导入方式）
- 苏格拉底式检验 Agent（工具调用 + 掌握度报告）
- Boss 直聘 JD 爬取 + 技能频率分析
- B站竞品作品集采集 + S/A/B/C 评级系统
- 学习中心（项目解读 / 知识点讲解 / 学习路径三合一）
- 知识网络图谱（NetworkX + PyVis 可视化）
- Agent Skills 技能包系统
- Mem0 记忆系统集成
