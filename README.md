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

### 导入 notion md 文件，还有点问题
```bash
1. Notion 导出包含 sub pages 的文件时，要选择包含子页，及为子页创建文件夹
2. 导出的 md 文件，要去掉文件名后面的 md5 值，以及引用这个文件的对应地方也要改
3. 父级目录里面用到的资源要去掉第一级目录，注意引用 md 文件不用去除
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

   ```

## [部署到 GitHub Pages](https://docs.github.com/zh/pages/quickstart)

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
   git remote add origin https://github.com/your-username/your_username.github.io.git
   git add .
   git commit -m "Deploy to GitHub Pages"
   git push -u origin
   ```
4. 在仓库的 Settings 中找到 `Pages` 选项
   ```bash
   1. Build and deployment -> Source: 选择 Deploy from a branch
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
