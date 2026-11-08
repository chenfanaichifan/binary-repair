# 135 · file:// 隐藏上传的真机证据（2026-11-08）

## 0. 一句话

`UPLOAD_AVAILABLE` 的 file:// 分支不再是「只有源码断言」，
现在有真实浏览器的 DOM 证据。

## 1. 方法（关键是让协议真的变成 file:）

1. 从 http 页面拿渲染后的 DOM（此时按钮**没有** `hidden`）
2. 把 `/static/...` 改成 `./static/...`，静态资源复制到同目录
3. 用 Edge 以 `file:///C:/ptreview/static-site/index.html` 打开
4. `--dump-dom` 读取重新执行过 agent.js 的 DOM

这样对比的是同一份 HTML，只有协议不同，排除了模板差异。

## 2. 结果

http（对照，来自源 DOM）：

```html
<button id="agent-deliverable-upload" type="button" class="btn ghost"
        data-testid="agent-deliverable-upload">
```

file://（重新执行 agent.js 后）：

```html
<button id="agent-deliverable-upload" type="button" class="btn ghost"
        data-testid="agent-deliverable-upload" hidden="">

<input id="agent-deliverable-input" type="file" accept=".elf,application/x-elf"
       data-testid="agent-deliverable-input" hidden="">
```

两个控件都被加上 `hidden`，与 `UPLOAD_AVAILABLE` 的判断一致。

## 3. 这条为什么值得单独记

它验证的不是「文案对不对」，而是「能力是否被正确关掉」。
如果只写源码断言，有人改回 `if (false)` 之类的写法也能骗过文本匹配；
换成真实协议打开，`hidden` 是浏览器执行后的结果，改不动。

## 4. 边界

- 静态副本里 API 请求全部失败，页面其他区域显示错误态 —— 这是预期的，
  本条只验证上传控件的可见性，不验证数据加载。
- 没有测 https：本地没有证书，https 与 http 走同一分支（`||`），
  源码断言已覆盖。

## 5. 复现

```powershell
# 1) 拿 http 渲染后的 DOM
msedge --headless=new --virtual-time-budget=8000 --dump-dom ^
  "http://127.0.0.1:8123/agent/<job>?token=<token>" > agent-dom.html

# 2) 改相对路径并复制 static
# 3) 以 file:// 打开再 dump
msedge --headless=new --allow-file-access-from-files ^
  --virtual-time-budget=6000 --dump-dom ^
  "file:///C:/ptreview/static-site/index.html" > file-dom.html
```
