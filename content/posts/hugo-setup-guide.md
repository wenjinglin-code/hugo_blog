+++
title = "Hugo 知识库搭建指南"
date = 2023-11-11T00:00:00+08:00
tags = ["Hugo", "静态网站", "知识库"]
categories = ["技术文档"]
+++

# Hugo 知识库搭建指南

Hugo 是一个快速、现代的静态网站生成器，非常适合搭建个人知识库。

## 为什么选择 Hugo

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

## 创建新站点

```bash
hugo new site my-knowledge-base
cd my-knowledge-base
```

## 添加主题

```bash
git init
git submodule add https://github.com/matcornic/hugo-theme-learn.git themes/hugo-theme-learn
```

## 创建内容

```bash
cp xxx.md content/posts/
```

## 更新内容

```bash
hugo --cleanDestinationDir
```

## 启动服务

```bash
hugo server -D

# hugo server --disableFastRender
```

## 部署到 GitHub Pages

1. 在 GitHub 上创建新仓库
2. 构建网站：
   ```bash
   hugo
   ```
3. 将 public 目录推送到 GitHub Pages

## 最佳实践

1. 使用清晰的目录结构
2. 为每篇文章添加合适的标签和分类
3. 定期备份内容
4. 使用版本控制管理内容
