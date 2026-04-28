---
name: AI_TA核心知识
description: AI TA岗位的核心技术考察标准，包含扩散模型、LoRA、ComfyUI、Shader的深度考察点
trigger_keywords: ["LoRA", "扩散模型", "ComfyUI", "Shader", "AI TA", "技术美术", "微调", "AIGC"]
level: 2
---

## 扩散模型考察重点

- **前向过程（Forward Process）**：理解马尔可夫链加噪过程，$q(x_t|x_{t-1})$ 的数学含义，为什么选择高斯噪声
- **逆向过程（Reverse Process）**：参数化 $p_\theta(x_{t-1}|x_t)$，UNet 网络预测噪声 vs 预测原图的区别
- **噪声 Schedule**：线性 schedule 与余弦 schedule 的差异，对训练稳定性的影响
- **DDPM vs DDIM**：DDIM 的确定性采样原理，为何能在更少步数下获得相近质量，step 数对生成速度/质量的权衡

## LoRA 考察重点

- **低秩分解原理**：$W = W_0 + \Delta W = W_0 + BA$，rank 参数决定 $B$ 和 $A$ 的维度，参数量计算方式
- **rank 参数选择依据**：style LoRA 建议 rank 4-16，concept LoRA 建议 rank 16-64，rank 过高过低的副作用
- **与全量微调的对比**：显存占用对比（LoRA 通常仅需 6-12GB）、过拟合风险对比、训练速度对比
- **实际训练流程**：数据集准备（20-50 张打标图）→ kohya_ss / SimpleTuner 配置 → loss 曲线监控 → 合并权重 → 效果验证

## ComfyUI 考察重点

- **节点类型**：CLIP 文本编码节点 / KSampler 采样节点 / VAE 编解码节点 / ControlNet 条件控制节点 / 自定义 Python 节点
- **工作流设计**：如何串联 IP-Adapter + ControlNet + LoRA 实现多条件控制，工作流导出为 JSON 的结构
- **与 SD WebUI 的区别**：ComfyUI 图结构 vs WebUI 线性流程，ComfyUI 对显存的细粒度控制优势，ComfyUI API 接口调用方式
- **自定义节点开发**：继承 `NODE_CLASS_MAPPINGS`，定义 `INPUT_TYPES` 和 `RETURN_TYPES`，注册到 ComfyUI 节点列表

## Shader 考察重点

- **渲染管线各阶段**：顶点着色器 → 几何着色器（可选）→ 光栅化 → 片元着色器 → 帧缓冲输出，每阶段可读写的数据
- **PBR 原理**：金属度/粗糙度工作流，Cook-Torrance BRDF 的组成（D/F/G 项），能量守恒的实现
- **常见优化手段**：减少 overdraw（Early-Z / 不透明物体前向排序）、合批（GPU Instancing / SRP Batcher / Static Batching）、LOD 系统设计
- **Unity vs UE 的差异**：Unity ShaderLab 结构 vs UE Material Graph，两者的 custom function 节点对比，移动端 Shader 的精度问题（half vs float）

## 面试常见追问方向

- **从原理到工程实现**：「你知道 DDIM 加速采样的原理，那如果让你在 ComfyUI 中实现自定义采样器节点，你会怎么设计？」
- **从工具使用到背后机制**：「你用过 LoRA 训练，那为什么 rank=4 的 LoRA 有时候比 rank=64 效果更稳定？」
- **从单点到系统设计**：「如果让你为一个游戏项目搭建 AI 辅助纹理生成的完整流程，从美术输入到最终输出，你会怎么设计？」
