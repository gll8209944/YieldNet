> 自动同步自 Notion，同步时间: 2026-04-15
> 页面 ID: `343a4400-33e1-8077-b469-ecb92e5589e1`
> 原始链接: https://www.notion.so/343a440033e18077b469ecb92e5589e1

# FleetGuard · 多机避撞协同系统

> 🤖 **FleetGuard — 多机避撞协同系统**
楼宇讲解机器人同楼层多机避撞协调方案 · CycloneDDS + domain_bridge + Nav2 行为树集成

---

## 项目概述

解决同楼层 2~3 台讲解机器人在走廊、T 字路口等狭窄区域的碰撞风险。通过 DDS 机间通信 + 去中心化优先级协商 + Nav2 行为树原生集成，实现零碰撞、低延迟、低带宽的多机避让协调。

| **维度** | **指标** |
| --- | --- |
| 支持台数 | 2~3 台（架构支持 N 台扩展） |
| 通信方式 | CycloneDDS 双 Domain + domain_bridge 桥接 |
| Nav2 集成 | 自定义行为树节点（CheckFleetConflict / WaitForYieldClear / AdjustSpeedForFleet） |
| 无线带宽 | ≤ 3.2 KB/s（3 台） |
| 让行延迟 | ≤ 15s / 次 |

---

## 文档导航

- [多机避撞协同系统 · PRD](https://www.notion.so/多机避撞协同系统-·-PRD-6fa035862f2a46e38e8a93b821e9bf28)

- [多机避撞协同系统 · 系统架构设计](https://www.notion.so/多机避撞协同系统-·-系统架构设计-6cf06f260cd54c68914a45869511d87c)

- [Test Requirements: 多机避撞协同系统](https://www.notion.so/Test-Requirements:-多机避撞协同系统-343a440033e181d7940fcc57a14bcdaa)

- [Document Review: 多机避撞协同系统](https://www.notion.so/Document-Review:-多机避撞协同系统-343a440033e181b7b558ca5714e181b2)

- [Document Review: 多机避撞协同系统](https://www.notion.so/Document-Review:-多机避撞协同系统-343a440033e181f39647f967772ceca9)

- [Test Requirements: 多机避撞协同系统](https://www.notion.so/Test-Requirements:-多机避撞协同系统-343a440033e181fb95f1ff89a601931c)

- [Document Review: 多机避撞协同系统](https://www.notion.so/Document-Review:-多机避撞协同系统-343a440033e181cb9cfcd04f16348811)
