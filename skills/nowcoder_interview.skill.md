---
name: 牛客面经精华
description: 从牛客网爬取的技术美术/AI TA真实面试考察点汇总
trigger_keywords: ["面经", "牛客", "考察", "八股", "真题", "高频"]
level: 2
---

## 高频考察知识点（出现频率 > 60%）

### 渲染方向

- **渲染管线细节**：顶点着色器输出 clip space 坐标后，光栅化如何插值 varying 变量
- **PBR 原理**：金属度/粗糙度工作流，IBL（Image Based Lighting）的实现，为什么 PBR 在不同光照条件下表现一致
- **Shader 优化**：纹理采样数量控制、尽量避免 `if` 分支（改用 `step/lerp`）、精度限定符（half/float 的选用）

### AI 生成方向

- **LoRA 训练参数**：epoch 数、learning rate、network_dim（rank）的选择经验，loss 曲线正常/异常的判断
- **扩散模型推理加速**：DDIM/DPM-Solver/LCM 的适用场景，量化（FP16/INT8）对质量的影响，TensorRT 加速流程

### 工具链方向

- **ComfyUI 自定义节点**：如何编写一个接收图像输入输出处理结果的自定义节点
- **Python 脚本自动化**：批处理 AI 生图任务、自动化资产管线脚本

## 常见追问（出现频率 40-60%）

- **Draw Call 优化**：GPU Instancing 的原理和使用限制，SRP Batcher 的工作机制，Static Batching vs Dynamic Batching 的选择
- **GPU Instancing**：`MaterialPropertyBlock` 的使用，Instancing 对 Skinned Mesh Renderer 的限制
- **模型量化方法**：FP32 → FP16 → INT8 精度损失分析，GPTQ/AWQ/GGUF 量化方案对比
- **ComfyUI 自定义节点进阶**：如何在节点中调用外部 Python 库、节点间如何传递非标准数据类型

## 加分回答要素

1. **结合实际项目经验**：「我在 X 项目中用这个知识点解决了 Y 问题，具体是...」
2. **能说出具体数据**：「优化前 Draw Call 有 800 个，通过 GPU Instancing 降到了 120 个，帧率从 35fps 提升到 58fps」
3. **知道局限性**：「GPU Instancing 在 Unity 中不能直接用于 Skinned Mesh Renderer，需要用 Shader Graph 的 Compute Shader 方案绕过」
4. **展示学习路径**：「我最近在研究 X，是因为在 Y 上遇到了问题...」

## 面试前 48 小时速查清单

- [ ] 说清楚自己最熟悉的一个项目，能描述完整技术决策过程
- [ ] 准备好「踩坑故事」：遇到了什么问题，怎么排查，最终怎么解决
- [ ] 复习 PBR 公式（Cook-Torrance BRDF）和渲染管线各阶段
- [ ] 能流畅说出 LoRA 训练的完整流程和关键参数含义
- [ ] 了解当前最新的 AI 生图工具链进展（每月至少关注一次）
