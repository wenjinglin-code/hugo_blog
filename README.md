# 个人博客

这是一个基于 Hugo 构建的个人博客网站，使用了修改版的 Learn 主题。

## 功能特点

- 响应式设计，适配桌面和移动设备
- 侧边栏目录导航
- 文章目录自动生成
- Markdown 格式支持
- 标签和分类功能
- 归档页面
- 客户端搜索功能
- 易于部署到 GitHub Pages

## 本地运行

### 安装 Hugo

确保您已安装 Hugo Extended 版本：

```bash
# Windows (使用 Chocolatey)
choco install hugo-extended

# macOS (使用 Homebrew)
brew install hugo

# Linux (Ubuntu/Debian)
sudo apt-get install hugo
```

### 克隆仓库

```bash
git clone https://github.com/wenjinglin-code/hugo_blog.git
cd hugo_blog
```

### 启动本地服务器

```bash
hugo --cleanDestinationDir # 更新索引
hugo server -D
```

然后在浏览器中访问 `http://localhost:1313` 查看网站。

## 添加新内容

### 创建新文章

```bash
hugo new posts/xxx.md # 文件会创建在 content/posts 目录下，也可直接复制 md 文件到这里
```

### 导入 notion md 文件，还有点问题，需要用脚本处理
```bash
# Notion 导出包含 sub pages 的文件时，要选择包含子页，及为子页创建文件夹
python3 restructure_directories.py your_notion_output_dir 'tags' 'categories'

# 例如
python3 restructure_directories.py ./content/posts/C2000/ '"powerpc", "linux"' '"powerpc_linux"'
```

### 文章格式

新文章将具有以下格式：

```markdown
+++
title = "文章标题"
date = 2025-11-11T00:00:00+08:00
tags = ["标签1", "标签2"]
categories = ["分类"]
+++

# 文章标题

文章内容...
```
## [部署到 GitHub Pages](https://docs.github.com/zh/pages/quickstart)

>> 每次更新，需要等比较长时间才更新界面

### 方法1: 使用 GitHub Actions 自动部署到 github.io (推荐)

>> 依赖 `.github/workflows/deploy.yml` 自动编译部署配置文件

**工作原理：**
- 每次 push 代码到 `master` 分支时，GitHub Actions 会自动：
  1. 拉取代码
  2. 使用 Hugo 构建网站
  3. 将生成的静态文件推送到 `gh-pages` 分支

**配置步骤：**

1. 在博客的源码仓库的 Settings 中找到 `Actions -> General` 选项
   ```bash
   # 给 actions 提供权限
   1. Workflow permissions -> 选择 `Read and write permissions`
   2. Workflow permissions -> 选择 `Allow GitHub Actions to create and approve pull requests`
   3. 按下 `Save` 保存
   ```
2. 仓库的 Settings 中找到 `Pages` 选项
   ```bash
   # 1. Build and deployment -> Source: 选择 `GitHub Actions`
   1. Build and deployment -> Source: 选择 `Deploy from a branch`
   2. Build and deployment -> Branch: 选择 gh-pages，按下 Save 保存
   ```
3. 仓库的 Settings 中找到 `Pages` 选项中，点击 `Visit site` 就可以访问了
   一般地址为 `https://username.github.io/repostory_name/`

**手动触发部署：**
如果想手动触发部署而不 push 代码：
1. 进入仓库的 **Actions** 页面
2. 选择 "Deploy to GitHub Pages" 工作流
3. 点击 **Run workflow** -> 再次点击 **Run workflow**

**触发自动部署：**
```bash
git add .
git commit -m "更新博客内容"
git push origin master
```

### 方法2: 将静态页面部署到 github.io
1. 在 GitHub 上创建新仓库
   ```bash
   github 上新建一个仓库，名为 username.github.io，username 为你的用户名
   ```
2. 构建网站：
   ```bash
   hugo
   ```

3. 将生成的 `public` 目录推送到 GitHub：
   ```bash
   cd public
   git init
   git remote add origin git@github.com:wenjinglin-code/wenjinglin-code.github.io.git
   git pull origin  master
   git add .
   git commit -m "Deploy to GitHub Pages"
   git push --set-upstream origin master
   ```
4. 在仓库的 Settings 中找到 `Pages` 选项
   ```bash
   1. Build and deployment -> Source: 选择 `Deploy from a branch`
   2. Build and deployment -> Branch: 选择 master，按下 Save 保存
   ```
5. 访问 `https://your_username.github.io/`

## 自定义配置

### 站点配置

编辑 `hugo.toml` 文件来修改站点配置：

```toml
baseURL = 'https://example.org/'
languageCode = 'zh-cn'
defaultContentLanguage = 'zh-cn'
title = '我的个人知识库'
```

### 菜单配置

在 `hugo.toml` 中修改菜单项：

```toml
[[menu.main]]
name = "首页"
url = "/"
weight = 1
```

### 主题定制

修改 `themes/hugo-theme-learn/assets/css/main.css` 来自定义样式。

## 目录结构

```
hugo_blog/
├── archetypes/          # 内容模板
├── assets/              # 静态资源
├── content/             # 内容文件
│   ├── knowledge/       # 知识库文章
│   ├── about.md         # 关于页面
│   └── _index.md        # 首页
├── layouts/             # 页面布局
├── static/              # 静态文件
├── themes/              # 主题文件
└── hugo.toml            # 配置文件
```

## 技术栈

- [Hugo](https://gohugo.io/) - 静态网站生成器
- [Learn Theme](https://github.com/matcornic/hugo-theme-learn) - Hugo 主题（已修改）

## 许可证

本项目基于 MIT 许可证开源。
