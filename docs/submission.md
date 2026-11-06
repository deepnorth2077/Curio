# 交付包格式

实现 AI 必须按这个格式交付。格式固定，是为了让 Claude 能把交付物一个文件不漏地整合进仓库，并且一眼看出有没有被截断。

Claude 写的每一份提示词，最后都会附上这一节的完整内容（实现 AI 看不到仓库）。

## 格式

````
=== CURIO 交付包 ===
issue: #12
任务: act.quiz.fraction-intro-01
实现者: <模型名和版本，例如 GPT-5.1、Gemini 3 Pro>
提示词版本: v1
轮次: 1

## 文件清单
- content/activities/act.quiz.fraction-intro-01/manifest.yaml
- content/activities/act.quiz.fraction-intro-01/index.html

## 文件

### FILE: content/activities/act.quiz.fraction-intro-01/manifest.yaml
```yaml
id: act.quiz.fraction-intro-01
…
# END OF FILE
```

### FILE: content/activities/act.quiz.fraction-intro-01/index.html
```html
<!doctype html>
…
<!-- END OF FILE -->
```

## 自查
- [x] 提示词里「验收标准」的每一条
- [x] …

## 说明
- 做了哪些决定，为什么：
- 没做什么：
- 疑问（规格不清楚、互相矛盾，或者觉得不合理的地方）：

=== END ===
````

## 规则

1. **文件路径**：每个文件用 `### FILE: <路径>` 开头，路径必须和「文件清单」完全一致，也必须是提示词里指定的路径。
2. **结束标记**：每个文件的最后一行写结束标记，按文件类型用对应的注释写法：
   - YAML、Python：`# END OF FILE`
   - HTML、Markdown：`<!-- END OF FILE -->`
   - JavaScript、CSS：`/* END OF FILE */`
   - JSON 不能写注释，所以 JSON 文件不加结束标记，交付包里也不要拆成多段。
   缺了结束标记，Claude 会当作文件被截断，直接打回。
3. **完整文件**：每次都交付完整文件，不要只给改动的片段，也不要写「其余部分不变」。
4. **太长时**：一个回答放不下，就分成几次输出，每次以 `=== 续 ===` 开头，Claude 会拼起来。也可以把文件另存为附件，文件名用路径里的文件名。
5. **疑问写在「说明」里**：不要为了让自己的实现跑通，自己改规格、改字段或改消息格式。
6. **打回之后**：交付完整的新一轮交付包，「轮次」加一，并在「说明」里逐条写出改了什么。
