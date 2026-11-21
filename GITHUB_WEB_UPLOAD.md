# 只用 GitHub 网页版：发布 GLI COMPASS

不需要安装 Git。全程浏览器操作，约 10 分钟。

> 这是一个新网站，仓库名建议 `gli-compass`。
>
> 完成后网址：`https://zeraray929418798.github.io/gli-compass/`

## 1. 下载并解压

下载 `gli-compass-upload.zip`，右键 → **全部解压缩**。

里面应该有：

```text
.github
data
scripts
site
README.md
requirements.txt
serve.py
```

## 2. 新建仓库

打开 [github.com/new](https://github.com/new)：

- Repository name：`gli-compass`
- 选 **Public**
- 不要勾选 Add a README / .gitignore / license
- 点 **Create repository**

## 3. 上传内容

1. 进入新仓库，点 **uploading an existing file**。
2. 打开解压后的文件夹，按 **Ctrl + A** 全选里面的内容。
3. 直接拖进浏览器上传框。
4. Commit message 填 `initial upload`。
5. 点 **Commit changes**。

> 不要上传外面的 `gli-compass` 文件夹本身，否则会多套一层。

## 4. 开启 Pages

仓库 **Settings → Pages**：

- **Build and deployment → Source = GitHub Actions**

## 5. 运行一次

仓库顶部 **Actions** → 左侧 **Update GLI data and deploy** → **Run workflow** → 分支 `main` → 绿色按钮。

首次会下载 16 个行情序列并构建，约 2–3 分钟。

## 6. 打开网站

**Settings → Pages** 顶部会出现 **Visit site**，或直接打开：

```text
https://zeraray929418798.github.io/gli-compass/
```

## 以后

- 每天早上 **7:30 左右（北京时间）** 自动更新；周末数据不变。
- 想立刻更新：**Actions → Update GLI data and deploy → Run workflow**。
- 修改代码后手动 Run 一次即可重新部署。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| Pages 404 | 确认 Source = GitHub Actions，等首次部署完成 |
| Actions 没有工作流 | 检查 `.github/workflows/update-and-deploy.yml` 是否上传 |
| 运行失败 403 | Settings → Actions → General → Workflow permissions → Read and write |
| 页面空白 | 检查 `site/data/gli.js` 是否存在；F12 看 404 |
| 页面显示旧数据 | Ctrl + F5 强制刷新 |

## 提醒

- 不要把 GitHub 密码、验证码发给任何人。
- 不需要 API key，不需要付费。
- GLI 是市场代理版，不是央行资产负债表完整核算，不构成投资建议。
