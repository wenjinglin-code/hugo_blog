+++
title = "Hugo 博客搭建指南"
date = 2023-11-11T00:00:00+08:00
tags = ["hugo", "静态网站", "知识库"]
categories = ["环境配置教程"]
+++

## 为什么选择 Hugo
Hugo 是一个快速、现代的静态网站生成器，非常适合搭建个人博客。

1. **速度快** - 生成网站的速度极快
2. **易于部署** - 可以轻松部署到 GitHub Pages 等平台
3. **丰富的主题** - 有大量的主题可供选择
4. **Markdown 支持** - 完美支持 Markdown 格式

## 安装 Hugo

### Windows

```powershell
choco install hugo -confirm
```

### macOS

```bash
brew install hugo
```

### Linux

```bash
sudo apt-get install hugo
```

## hugo 使用
### 创建新站点

```bash
hugo new site my-blog
cd my-blog
```

### 添加主题

```bash
git init
git submodule add https://github.com/matcornic/hugo-theme-learn.git themes/hugo-theme-learn
```

### 创建内容

```bash
hugo new posts/xxx.md # 文件会创建在 content/posts 目录下，也可直接复制 md 文件到这里
```

### 更新索引标签

```bash
hugo --cleanDestinationDir
```

### 启动服务

```bash
hugo server -D
```

## [部署到 GitHub Pages](https://docs.github.com/zh/pages/quickstart)

1. 在 GitHub 上创建新仓库
   ```bash
   github 上新建一个仓库，名为 username.github.io，username 为你的用户名
   ```
2. 构建网站：
   ```bash
   cd my-blog
   hugo
   ```
3. 将 public 目录推送到 username.github.io 仓库
4. 在仓库的 Settings 中找到 `Pages` 选项
   ```bash
   1. Build and deployment -> Source: 选择 Deploy from a branch
   2. Build and deployment -> Branch: 选择 上传代码的对应分支，按下 Save 保存
   ```
5. 访问 `https://username.github.io/`

## 最佳实践

1. 使用清晰的目录结构
2. 为每篇文章添加合适的标签和分类
3. 定期备份内容
4. 使用版本控制管理内容
