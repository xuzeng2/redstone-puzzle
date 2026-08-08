#!/usr/bin/env python3
"""
红石逻辑解谜游戏生成器
用法: python gen_redstone_game.py <关卡定义文件.json> [输出文件.html]
如果不指定输出文件，默认输出 redstone-puzzle.html

关卡定义文件格式 (JSON):
{
  "levels": [
    {
      "name": "关卡名称",
      "desc": "关卡描述",
      "cols": 12, "rows": 8,
      "input": {"x": 1, "y": 4, "duration": 10, "strength": 15},
      "output": {"x": 10, "y": 4},
      "target": {"delay": 4, "duration": 10},
      "components": ["dust", "repeater"],
      "limits": {"repeater": 2},
      "hint": "提示文字",
      "par": 10,
      "logic": "not"          // 可选, "not"/"or"/"and"
    },
    // 多输入关卡用 "inputs" 代替 "input":
    {
      "name": "或门",
      "desc": "两路汇合",
      "cols": 12, "rows": 8,
      "inputs": [
        {"x": 1, "y": 2, "duration": 10, "strength": 15, "delay": 0},
        {"x": 1, "y": 6, "duration": 10, "strength": 15, "delay": 5}
      ],
      "output": {"x": 10, "y": 4},
      "target": {"delay": 10, "duration": 15},
      "components": ["dust"],
      "hint": "...",
      "par": 14,
      "logic": "or"
    }
  ]
}

字段说明:
  name        关卡名称 (必填)
  desc        关卡描述 (必填)
  cols/rows   网格列数/行数 (必填)
  input       单输入配置 {x, y, duration, strength} (单输入关卡必填)
  inputs      多输入数组 [{x, y, duration, strength, delay}] (多输入关卡必填, 与input二选一)
  output      输出点 {x, y} (必填)
  target      目标 {delay, duration} (必填)
  components  可用元件列表 (必填), 可选值: dust/block/torch/repeater/comparator/observer/stone/piston
  limits      元件数量限制 {元件类型: 数量} (可选)
  hint        通关提示 (必填)
  par         推荐元件数 (可选, 默认10)
  logic       逻辑门类型 (可选) "not"/"or"/"and", 设置后会显示对应逻辑门介绍
  preplaced   预放置元件数组 (可选), 玩家无法移除这些元件
              格式: [{"x": 5, "y": 3, "type": "block", "direction": 0, "delay": 1, "mode": "compare"}]
              type 必填, direction/delay/mode 可选 (有方向的元件需指定 direction: 0=右 1=下 2=左 3=上)
"""

import json
import sys
import os


# ============================================================
#  HTML 模板（固定部分：CSS + JS 引擎）
#  关卡数据会注入到 LEVELS 占位符位置
# ============================================================
HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>红石逻辑解谜 — Redstone Logic Puzzle</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    background:#1a1a2e; color:#e0e0e0; font-family:'Segoe UI',sans-serif;
    display:flex; flex-direction:column; align-items:center; min-height:100vh;
    user-select:none;
  }
  #header {
    width:100%; max-width:900px; padding:10px 16px;
    display:flex; justify-content:space-between; align-items:center;
    background:#16213e; border-bottom:3px solid #0f3460;
  }
  #header h1 { font-size:18px; color:#e94560; letter-spacing:1px; }
  #levelSelector { display:flex; gap:4px; flex-wrap:wrap; }
  .level-btn {
    width:28px; height:28px; border:2px solid #0f3460; background:#1a1a2e;
    color:#aaa; font-size:12px; cursor:pointer; border-radius:3px;
    display:flex; align-items:center; justify-content:center;
  }
  .level-btn:hover { border-color:#e94560; color:#e94560; }
  .level-btn.current { background:#e94560; color:#fff; border-color:#e94560; }
  .level-btn.completed { background:#0f3460; color:#4ecca3; border-color:#4ecca3; }
  .level-btn.current.completed { background:#0f3460; color:#4ecca3; border-color:#e94560; box-shadow:0 0 8px rgba(233,69,96,.7); }
  .level-btn.locked { opacity:.3; cursor:not-allowed; }
  #infoBar {
    width:100%; max-width:900px; padding:8px 16px;
    background:#0f3460; display:flex; gap:20px; flex-wrap:wrap;
    font-size:13px; align-items:center;
  }
  #infoBar .label { color:#888; }
  #infoBar .target { color:#e94560; font-weight:bold; }
  #infoBar .current { color:#4ecca3; font-weight:bold; }
  #infoBar .matched { color:#ffd700; font-weight:bold; }
  #infoBar .level-desc { color:#ccc; flex:1; min-width:200px; }
  #canvasWrap {
    margin:10px 0; border:4px solid #0f3460; border-radius:4px;
    background:#0d1117; box-shadow:0 0 20px rgba(233,69,96,.2);
  }
  canvas { display:block; cursor:pointer; image-rendering:pixelated; }
  #controls {
    width:100%; max-width:900px; padding:8px 16px;
    background:#16213e; display:flex; gap:8px; align-items:center; flex-wrap:wrap;
  }
  .btn {
    padding:6px 14px; border:2px solid #0f3460; background:#1a1a2e;
    color:#e0e0e0; cursor:pointer; border-radius:4px; font-size:13px;
    display:flex; align-items:center; gap:4px;
  }
  .btn:hover { border-color:#e94560; color:#e94560; }
  .btn:active { transform:scale(.95); }
  .btn.primary { background:#e94560; color:#fff; border-color:#e94560; }
  .btn.primary:hover { background:#ff5570; }
  #componentBar {
    width:100%; max-width:900px; padding:8px 16px;
    background:#0f3460; display:flex; gap:6px; flex-wrap:wrap; align-items:center;
  }
  #componentBar .label { color:#888; font-size:12px; margin-right:4px; }
  .comp-btn {
    width:52px; height:52px; border:2px solid #1a1a2e; background:#16213e;
    cursor:pointer; border-radius:4px; display:flex; flex-direction:column;
    align-items:center; justify-content:center; gap:2px; position:relative;
  }
  .comp-btn canvas { pointer-events:none; }
  .comp-btn:hover { border-color:#e94560; }
  .comp-btn.selected { border-color:#4ecca3; box-shadow:0 0 8px rgba(78,204,163,.5); }
  .comp-btn .count { position:absolute; top:0; right:2px; font-size:10px; color:#4ecca3; }
  .comp-btn .name { font-size:8px; color:#888; }
  #hint {
    width:100%; max-width:900px; padding:6px 16px;
    background:#0d1117; color:#888; font-size:12px; text-align:center;
  }
  /* 过关弹窗 */
  #winModal {
    display:none; position:fixed; top:0; left:0; width:100%; height:100%;
    background:rgba(0,0,0,.7); z-index:100; justify-content:center; align-items:center;
  }
  #winModal.show { display:flex; }
  #winModal .panel {
    background:#16213e; border:4px solid #4ecca3; border-radius:12px;
    padding:48px 60px; text-align:center; max-width:520px;
    box-shadow:0 0 40px rgba(78,204,163,.4);
    animation:winPop .4s ease-out;
  }
  @keyframes winPop {
    0% { transform:scale(0.5); opacity:0; }
    70% { transform:scale(1.05); }
    100% { transform:scale(1); opacity:1; }
  }
  #winModal h2 { color:#4ecca3; font-size:42px; margin-bottom:20px; letter-spacing:4px; }
  #winModal p { color:#ccc; margin-bottom:24px; line-height:1.8; font-size:18px; }
  #winModal .stars { font-size:52px; margin-bottom:24px; color:#ffd700; letter-spacing:8px; }
  #winModal .btn { margin:0 6px; font-size:16px; padding:10px 24px; }
  /* 元件介绍弹窗 */
  #introModal {
    display:none; position:fixed; top:0; left:0; width:100%; height:100%;
    background:rgba(0,0,0,.8); z-index:110; justify-content:center; align-items:center;
  }
  #introModal.show { display:flex; }
  #introModal .panel {
    background:#16213e; border:3px solid #e94560; border-radius:8px;
    padding:24px 32px; text-align:center; max-width:440px;
  }
  #introModal h2 { color:#e94560; font-size:20px; margin-bottom:6px; }
  #introModal .subtitle { color:#888; font-size:12px; margin-bottom:14px; }
  #introModal .intro-icon { margin:0 auto 14px; }
  #introModal .intro-icon canvas { display:block; margin:0 auto; }
  #introModal .intro-desc { color:#ccc; font-size:14px; line-height:1.7; margin-bottom:16px; text-align:left; }
  #introModal .intro-desc b { color:#4ecca3; }
  #introModal .intro-tip { color:#ffd700; font-size:12px; margin-bottom:14px; }
  #introModal .btn { margin:0 auto; }
  /* 引导提示 */
  #tip {
    display:none; position:fixed; bottom:20px; left:50%; transform:translateX(-50%);
    background:#16213e; border:2px solid #e94560; border-radius:6px;
    padding:8px 16px; color:#e94560; font-size:13px; z-index:300;
    animation:fadeIn .3s;
  }
  #tip.show { display:block; }
  @keyframes fadeIn { from{opacity:0} to{opacity:1} }
  /* 全通关弹窗 */
  #finalModal {
    display:none; position:fixed; top:0; left:0; width:100%; height:100%;
    background:rgba(0,0,0,.85); z-index:120; justify-content:center; align-items:center;
  }
  #finalModal.show { display:flex; }
  #finalModal .panel {
    background:#16213e; border:5px solid #ffd700; border-radius:16px;
    padding:60px 80px; text-align:center; max-width:640px;
    box-shadow:0 0 60px rgba(255,215,0,.5);
    animation:finalPop .5s ease-out;
  }
  @keyframes finalPop {
    0% { transform:scale(0.3); opacity:0; }
    60% { transform:scale(1.08); }
    100% { transform:scale(1); opacity:1; }
  }
  #finalModal h2 { color:#ffd700; font-size:56px; margin-bottom:28px; letter-spacing:8px; text-shadow:0 0 20px rgba(255,215,0,.6); }
  #finalModal p { color:#ccc; margin-bottom:28px; line-height:2; font-size:22px; }
  #finalModal .stars { font-size:72px; margin-bottom:32px; color:#ffd700; letter-spacing:12px; }
  #finalModal .btn { margin:0 auto; font-size:18px; padding:12px 32px; }
  /* 失败弹窗 */
  #failModal {
    display:none; position:fixed; top:0; left:0; width:100%; height:100%;
    background:rgba(0,0,0,.7); z-index:100; justify-content:center; align-items:center;
  }
  #failModal.show { display:flex; }
  #failModal .panel {
    background:#16213e; border:4px solid #e94560; border-radius:12px;
    padding:40px 50px; text-align:center; max-width:480px;
    box-shadow:0 0 40px rgba(233,69,96,.4);
    animation:failPop .4s ease-out;
  }
  @keyframes failPop {
    0% { transform:scale(0.5); opacity:0; }
    70% { transform:scale(1.05); }
    100% { transform:scale(1); opacity:1; }
  }
  #failModal h2 { color:#e94560; font-size:36px; margin-bottom:20px; letter-spacing:4px; }
  #failModal p { color:#ccc; margin-bottom:24px; line-height:1.8; font-size:16px; }
  #failModal .btn { margin:0 6px; font-size:16px; padding:10px 24px; }
  /* 主页 */
  #homePage {
    display:flex; position:fixed; top:0; left:0; width:100%; height:100%;
    background:linear-gradient(135deg, #0d1117 0%, #16213e 50%, #0f3460 100%);
    z-index:200; justify-content:center; align-items:center; flex-direction:column;
  }
  #homePage.hide { display:none; }
  #homePage .home-title {
    font-size:48px; color:#e94560; letter-spacing:6px; margin-bottom:8px;
    text-shadow:0 0 30px rgba(233,69,96,.5);
  }
  #homePage .home-subtitle {
    font-size:16px; color:#888; margin-bottom:32px; letter-spacing:2px;
  }
  #homePage .home-progress {
    font-size:18px; color:#4ecca3; margin-bottom:24px;
  }
  #homePage .home-progress-bar {
    width:300px; height:8px; background:#1a1a2e; border-radius:4px; margin-bottom:32px;
    overflow:hidden; border:1px solid #0f3460;
  }
  #homePage .home-progress-fill {
    height:100%; background:linear-gradient(90deg, #4ecca3, #e94560); transition:width .5s;
  }
  #homePage .home-levels {
    display:flex; gap:8px; flex-wrap:wrap; justify-content:center; max-width:500px; margin-bottom:32px;
  }
  #homePage .home-level-btn {
    width:48px; height:48px; border:2px solid #0f3460; background:#1a1a2e;
    color:#aaa; font-size:18px; cursor:pointer; border-radius:6px;
    display:flex; align-items:center; justify-content:center; transition:all .2s;
  }
  #homePage .home-level-btn:hover { border-color:#e94560; color:#e94560; transform:scale(1.1); }
  #homePage .home-level-btn.completed { background:#0f3460; color:#4ecca3; border-color:#4ecca3; }
  #homePage .home-level-btn.locked { opacity:.3; cursor:not-allowed; }
  #homePage .home-level-btn.locked:hover { transform:none; border-color:#0f3460; color:#aaa; }
  #homePage .home-start {
    padding:14px 48px; font-size:20px; border:3px solid #e94560; background:#e94560;
    color:#fff; cursor:pointer; border-radius:8px; letter-spacing:4px;
    box-shadow:0 0 20px rgba(233,69,96,.4); transition:all .2s;
  }
  #homePage .home-start:hover { background:#ff5570; box-shadow:0 0 30px rgba(233,69,96,.6); transform:scale(1.05); }
  #homePage .home-free {
    padding:12px 36px; font-size:16px; border:2px solid #4ecca3; background:transparent;
    color:#4ecca3; cursor:pointer; border-radius:8px; letter-spacing:2px; margin-top:16px;
    transition:all .2s;
  }
  #homePage .home-free:hover { background:#4ecca3; color:#0d1117; box-shadow:0 0 20px rgba(78,204,163,.5); transform:scale(1.05); }
  /* 联机弹窗 */
  #onlineModal {
    display:none; position:fixed; top:0; left:0; width:100%; height:100%;
    background:rgba(0,0,0,.8); z-index:130; justify-content:center; align-items:center;
  }
  #onlineModal.show { display:flex; }
  #onlineModal .panel {
    background:#16213e; border:3px solid #0f3460; border-radius:10px;
    padding:28px 36px; text-align:center; max-width:560px; width:90%;
  }
  #onlineModal h2 { color:#4ecca3; font-size:22px; margin-bottom:6px; }
  #onlineModal .mp-subtitle { color:#888; font-size:12px; margin-bottom:18px; }
  #onlineModal .mp-status {
    padding:8px 16px; border-radius:6px; margin-bottom:16px; font-size:13px;
    background:#16213e; color:#888; border:1px solid #0f3460;
  }
  #onlineModal .mp-status.online { background:#0f3460; color:#4ecca3; border-color:#4ecca3; }
  #onlineModal .mp-btns { display:flex; gap:10px; justify-content:center; margin-bottom:16px; }
  #onlineModal .mp-btn {
    padding:12px 28px; border:2px solid #0f3460; background:#1a1a2e;
    color:#e0e0e0; cursor:pointer; border-radius:6px; font-size:14px; flex:1; max-width:200px;
  }
  #onlineModal .mp-btn:hover { border-color:#e94560; color:#e94560; }
  #onlineModal .mp-btn.host { border-color:#4ecca3; color:#4ecca3; }
  #onlineModal .mp-btn.host:hover { background:#4ecca3; color:#1a1a2e; }
  #onlineModal .mp-btn.join { border-color:#e94560; color:#e94560; }
  #onlineModal .mp-btn.join:hover { background:#e94560; color:#fff; }
  #onlineModal .mp-section { margin-bottom:14px; text-align:left; }
  #onlineModal .mp-section .mp-label { color:#888; font-size:11px; margin-bottom:4px; }
  #onlineModal .mp-section textarea {
    width:100%; height:70px; background:#0d1117; color:#4ecca3;
    border:1px solid #0f3460; border-radius:4px; padding:8px;
    font-family:monospace; font-size:11px; resize:none;
  }
  #onlineModal .mp-section .mp-copy-btn {
    margin-top:4px; padding:4px 12px; border:1px solid #0f3460; background:#1a1a2e;
    color:#aaa; cursor:pointer; border-radius:3px; font-size:11px;
  }
  #onlineModal .mp-section .mp-copy-btn:hover { border-color:#4ecca3; color:#4ecca3; }
  #onlineModal .mp-zone-info {
    display:flex; gap:12px; justify-content:center; margin-bottom:14px;
  }
  #onlineModal .mp-zone-info .zone-card {
    flex:1; padding:10px; border-radius:6px; text-align:center; font-size:13px;
  }
  #onlineModal .mp-zone-info .zone-left { background:rgba(233,69,96,.15); border:1px solid #e94560; color:#e94560; }
  #onlineModal .mp-zone-info .zone-right { background:rgba(78,204,163,.15); border:1px solid #4ecca3; color:#4ecca3; }
  #onlineModal .mp-zone-info .zone-card.active { box-shadow:0 0 12px rgba(255,255,255,.2); }
  #onlineModal .mp-close-btn {
    padding:8px 24px; border:2px solid #0f3460; background:#1a1a2e;
    color:#888; cursor:pointer; border-radius:4px; font-size:13px; margin-top:8px;
  }
  #onlineModal .mp-close-btn:hover { border-color:#e94560; color:#e94560; }
  #onlineModal .mp-disconnect-btn {
    padding:8px 24px; border:2px solid #e94560; background:#e94560;
    color:#fff; cursor:pointer; border-radius:4px; font-size:13px; margin-top:8px;
  }
  #mpIndicator {
    display:none; padding:4px 12px; border-radius:4px; font-size:12px;
    background:#0f3460; color:#4ecca3; border:1px solid #4ecca3;
  }
  #mpIndicator.show { display:inline-block; }
  /* 联机聊天区 */
  #chatPanel {
    display:none; position:fixed; left:max(0px, calc(50vw - 690px)); top:0;
    width:240px; height:100vh; background:#0d1117;
    border-right:2px solid #0f3460; flex-direction:column; z-index:90;
    transition:left 0.3s ease, top 0.3s ease, height 0.3s ease;
  }
  #chatPanel.show { display:flex; }
  #chatPanel .chat-header {
    padding:10px 14px; background:#16213e; border-bottom:2px solid #0f3460;
    font-size:14px; color:#4ecca3; font-weight:bold; display:flex; align-items:center; gap:6px;
  }
  #chatPanel .chat-messages {
    flex:1; overflow-y:auto; padding:8px; display:flex; flex-direction:column; gap:6px;
  }
  #chatPanel .chat-messages::-webkit-scrollbar { width:4px; }
  #chatPanel .chat-messages::-webkit-scrollbar-thumb { background:#0f3460; border-radius:2px; }
  #chatPanel .chat-msg {
    max-width:85%; padding:6px 10px; border-radius:8px; font-size:12px;
    word-break:break-word; line-height:1.5; animation:chatFadeIn .2s;
  }
  @keyframes chatFadeIn { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:translateY(0)} }
  #chatPanel .chat-msg.self {
    align-self:flex-end; background:#0f3460; color:#4ecca3; border:1px solid #4ecca3;
  }
  #chatPanel .chat-msg.other {
    align-self:flex-start; background:#1a1a2e; color:#e94560; border:1px solid #e94560;
  }
  #chatPanel .chat-msg.system {
    align-self:center; background:none; color:#555; font-size:11px; border:none;
  }
  #chatPanel .chat-input-area {
    padding:8px; border-top:1px solid #0f3460; display:flex; gap:6px;
  }
  #chatPanel .chat-input {
    flex:1; background:#16213e; border:1px solid #0f3460; border-radius:4px;
    color:#e0e0e0; padding:6px 8px; font-size:12px; outline:none;
  }
  #chatPanel .chat-input:focus { border-color:#4ecca3; }
  #chatPanel .chat-send-btn {
    padding:6px 12px; background:#0f3460; border:1px solid #4ecca3;
    color:#4ecca3; border-radius:4px; cursor:pointer; font-size:12px; white-space:nowrap;
  }
  #chatPanel .chat-send-btn:hover { background:#4ecca3; color:#0d1117; }
  #chatPanel .chat-mic-btn {
    padding:6px 8px; background:#0f3460; border:1px solid #e94560;
    color:#e94560; border-radius:4px; cursor:pointer; font-size:14px; line-height:1;
    transition: all 0.2s;
  }
  #chatPanel .chat-mic-btn:hover { background:#e94560; color:#fff; }
  #chatPanel .chat-mic-btn.recording {
    background:#e94560; color:#fff; animation:micPulse 1s infinite;
  }
  @keyframes micPulse { 0%,100%{opacity:1} 50%{opacity:.5} }
  #chatPanel .chat-msg.voice {
    display:flex; align-items:center; gap:6px; cursor:pointer;
  }
  #chatPanel .chat-msg.voice .voice-icon { font-size:16px; }
  #chatPanel .chat-msg.voice .voice-duration { font-size:11px; opacity:.8; }
  #chatPanel .chat-msg.voice.playing .voice-icon { animation:micPulse .6s infinite; }
  #chatPanel .chat-recording-hint {
    display:none; padding:4px 8px; background:rgba(233,69,96,.15);
    color:#e94560; font-size:11px; text-align:center;
  }
  #chatPanel .chat-recording-hint.show { display:block; }
  body.chat-open { padding-left:min(240px, max(0px, calc(1380px - 100vw))); }
  body { transition: padding-left 0.3s ease; }
</style>
</head>
<body>

<!-- 联机聊天区 -->
<div id="chatPanel">
  <div class="chat-header">&#128172; 联机聊天</div>
  <div class="chat-messages" id="chatMessages"></div>
  <div class="chat-recording-hint" id="chatRecordingHint">&#128308; 录音中... 点击麦克风停止并发送</div>
  <div class="chat-input-area">
    <input type="text" class="chat-input" id="chatInput" placeholder="输入消息..." maxlength="200">
    <button class="chat-mic-btn" id="chatMicBtn" title="语音消息">&#127908;</button>
    <button class="chat-send-btn" id="chatSendBtn">发送</button>
  </div>
</div>

<div id="homePage" class="hide">
  <div class="home-title">红石逻辑解谜</div>
  <div class="home-subtitle">Redstone Logic Puzzle</div>
  <div class="home-progress" id="homeProgress">0 / 10 关卡完成</div>
  <div class="home-progress-bar"><div class="home-progress-fill" id="homeProgressFill" style="width:0%"></div></div>
  <div class="home-levels" id="homeLevels"></div>
  <button class="home-start" id="homeStartBtn">开始游戏</button>
  <button class="home-free" id="homeFreeBtn">自由模式</button>
</div>

<div id="header">
  <h1>红石逻辑解谜</h1>
  <span id="mpIndicator"></span>
  <div id="levelSelector"></div>
</div>

<div id="infoBar">
  <span class="level-desc" id="levelDesc"></span>
  <span><span class="label">目标延迟:</span> <span class="target" id="targetDelay">-</span></span>
  <span><span class="label">目标持续:</span> <span class="target" id="targetDuration">-</span></span>
  <span id="targetStrengthInfo" style="display:none"><span class="label">目标强度:</span> <span class="target" id="targetStrength">-</span></span>
  <span><span class="label">当前延迟:</span> <span class="current" id="currentDelay">-</span></span>
  <span><span class="label">当前持续:</span> <span class="current" id="currentDuration">-</span></span>
  <span id="currentStrengthInfo" style="display:none"><span class="label">当前强度:</span> <span class="current" id="currentStrength">-</span></span>
  <span><span class="label">Tick:</span> <span class="current" id="tickDisplay">0</span></span>
</div>

<div id="canvasWrap">
  <canvas id="game" width="864" height="540"></canvas>
</div>

<div id="controls">
  <button class="btn primary" id="playBtn">&#9654; 播放</button>
  <button class="btn" id="resetBtn">&#8634; 重置</button>
  <button class="btn" id="stepBtn">&#9193; 单步</button>
  <button class="btn" id="rotateBtn">&#10227; 旋转(R)</button>
  <span style="width:10px"></span>
  <button class="btn" id="saveBtn">&#128190; 存档</button>
  <button class="btn" id="loadBtn">&#128194; 读档</button>
  <button class="btn" id="soundBtn">&#128266; 音效</button>
  <button class="btn" id="onlineBtn">&#128279; 联机</button>
  <button class="btn" id="homeBtn">&#127968; 主页</button>
  <input type="file" id="fileInput" accept=".json" style="display:none">
  <span style="flex:1"></span>
  <span style="font-size:12px;color:#888">左键放置 | 右键移除 | R键旋转</span>
</div>

<div id="componentBar">
  <span class="label">元件:</span>
</div>

<div id="hint" id="hintText"></div>

<div id="winModal">
  <div class="panel">
    <h2>过关!</h2>
    <div class="stars" id="winStars">★ ★ ★</div>
    <p id="winInfo"></p>
    <div style="display:flex;justify-content:center;gap:16px">
      <button class="btn" id="retryBtn">重试</button>
      <button class="btn primary" id="nextBtn">下一关 →</button>
    </div>
  </div>
</div>

<div id="failModal">
  <div class="panel">
    <h2>挑战失败</h2>
    <p id="failInfo"></p>
    <div style="display:flex;justify-content:center;gap:16px">
      <button class="btn primary" id="failRetryBtn">重试</button>
      <button class="btn" id="failCloseBtn">关闭</button>
    </div>
  </div>
</div>

<div id="tip"></div>

<div id="finalModal">
  <div class="panel">
    <h2>全部通关!</h2>
    <div class="stars" id="finalStars">★ ★ ★ ★ ★</div>
    <p id="finalInfo">恭喜你完成了所有关卡！<br>你已经掌握了红石逻辑的精髓！</p>
    <button class="btn primary" id="finalCloseBtn">再来一次</button>
  </div>
</div>

<div id="introModal">
  <div class="panel">
    <div class="subtitle" id="introSubtitle">新元件解锁</div>
    <h2 id="introTitle"></h2>
    <div class="intro-icon"><canvas id="introIcon" width="48" height="48"></canvas></div>
    <div class="intro-desc" id="introDesc"></div>
    <div class="intro-tip" id="introTip"></div>
    <button class="btn primary" id="introStartBtn">开始挑战</button>
  </div>
</div>

<!-- 联机弹窗 -->
<div id="onlineModal">
  <div class="panel">
    <h2>&#128279; 联机模式</h2>
    <div class="mp-subtitle">双人协作 — 各自负责左/右半区</div>
    <div class="mp-status" id="mpStatus">&#9888; 未连接</div>
    <div class="mp-zone-info">
      <div class="zone-card zone-left" id="zoneCardLeft">
        <b>P1 左区</b><br><span style="font-size:11px;color:#888">主机</span>
      </div>
      <div class="zone-card zone-right" id="zoneCardRight">
        <b>P2 右区</b><br><span style="font-size:11px;color:#888">加入方</span>
      </div>
    </div>
    <div class="mp-btns" id="mpRoleBtns">
      <button class="mp-btn host" id="mpHostBtn">&#127918; 创建房间（左区）</button>
      <button class="mp-btn join" id="mpJoinBtn">&#128279; 加入房间（右区）</button>
    </div>
    <!-- 主机：生成邀请码 -->
    <div class="mp-section" id="mpOfferSection" style="display:none">
      <div class="mp-label">&#128203; 邀请码（复制发给队友）</div>
      <textarea id="mpOfferCode" readonly></textarea>
      <button class="mp-copy-btn" id="mpCopyOfferBtn">&#128203; 复制邀请码</button>
    </div>
    <!-- 主机：粘贴应答码 -->
    <div class="mp-section" id="mpAnswerInputSection" style="display:none">
      <div class="mp-label">粘贴队友的应答码</div>
      <textarea id="mpAnswerInput" placeholder="粘贴应答码..."></textarea>
      <button class="mp-btn join" id="mpConfirmAnswerBtn" style="margin-top:4px;width:100%;max-width:none">确认应答码</button>
    </div>
    <!-- 加入方：粘贴邀请码 -->
    <div class="mp-section" id="mpJoinSection" style="display:none">
      <div class="mp-label">粘贴队友的邀请码</div>
      <textarea id="mpJoinInput" placeholder="粘贴邀请码..."></textarea>
      <button class="mp-btn host" id="mpSendJoinBtn" style="margin-top:4px;width:100%;max-width:none">连接</button>
    </div>
    <!-- 加入方：生成应答码 -->
    <div class="mp-section" id="mpAnswerSection" style="display:none">
      <div class="mp-label">&#128203; 应答码（复制发给主机）</div>
      <textarea id="mpAnswerCode" readonly></textarea>
      <button class="mp-copy-btn" id="mpCopyAnswerBtn">&#128203; 复制应答码</button>
    </div>
    <button class="mp-close-btn" id="mpCloseBtn">关闭</button>
    <button class="mp-disconnect-btn" id="mpDisconnectBtn" style="display:none">断开连接</button>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/simple-peer@9.11.1/simplepeer.min.js"></script>
<script>
// ============================================================
//  音效系统 (Web Audio API)
// ============================================================
let audioCtx = null;
let soundEnabled = true;
function getAudio() { if (!audioCtx) { try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e) { soundEnabled = false; } } return audioCtx; }
function playTone(freq, dur, type, vol) {
  if (!soundEnabled) return;
  let ctx = getAudio(); if (!ctx) return;
  let osc = ctx.createOscillator(), gain = ctx.createGain();
  osc.type = type || 'square'; osc.frequency.value = freq;
  gain.gain.setValueAtTime(0, ctx.currentTime);
  gain.gain.linearRampToValueAtTime(vol || 0.15, ctx.currentTime + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
  osc.connect(gain); gain.connect(ctx.destination);
  osc.start(); osc.stop(ctx.currentTime + dur);
}
function playPlace() { playTone(440, 0.08, 'square', 0.12); }
function playRemove() { playTone(220, 0.08, 'sawtooth', 0.10); }
function playRotate() { playTone(330, 0.06, 'triangle', 0.10); }
function playClick() { playTone(600, 0.05, 'square', 0.08); }
function playWin() {
  let notes = [523, 659, 784, 1047];
  notes.forEach((f, i) => setTimeout(() => playTone(f, 0.15, 'square', 0.15), i * 100));
}
function playFinalWin() {
  let notes = [523, 659, 784, 1047, 1319, 1568];
  notes.forEach((f, i) => setTimeout(() => playTone(f, 0.2, 'square', 0.18), i * 120));
}
function playSignal() { playTone(880, 0.03, 'sine', 0.05); }
function playFail() {
  let notes = [400, 350, 300, 250];
  notes.forEach((f, i) => setTimeout(() => playTone(f, 0.12, 'sawtooth', 0.12), i * 80));
}

// ============================================================
//  联机系统 (P2P / WebRTC via simple-peer)
// ============================================================
let MP = {
  enabled: false,         // 联机模式已开启
  peer: null,             // SimplePeer 实例
  isHost: false,          // 是否主机（左区）
  connected: false,       // 连接已建立
  myZone: null,           // 'left' | 'right'
  boundary: 0,            // 分界线 x 坐标（>= boundary 为右区）
  remoteCursor: { x: -1, y: -1 }, // 队友光标
  syncing: false,         // 正在处理远端同步（防止回环）
};

// --- 区域判定 ---
function calcBoundary() { MP.boundary = Math.floor(G.cols / 2); }
function isInMyZone(x) {
  if (!MP.enabled || !MP.connected) return true;
  if (MP.myZone === 'left') return x < MP.boundary;
  return x >= MP.boundary;
}
function getZoneOf(x) {
  if (!MP.enabled) return null;
  return x < MP.boundary ? 'left' : 'right';
}

// --- 发送消息 ---
function sendToPeer(msg) {
  if (MP.connected && MP.peer && !MP.syncing) {
    try { MP.peer.send(JSON.stringify(msg)); } catch(e) { console.error('send error', e); }
  }
}

// --- 更新联机状态指示 ---
function updateMPIndicator() {
  let el = document.getElementById('mpIndicator');
  if (!MP.enabled) { el.classList.remove('show'); el.textContent = ''; return; }
  el.classList.add('show');
  if (MP.connected) {
    let zone = MP.myZone === 'left' ? '左区(P1)' : '右区(P2)';
    el.textContent = '\uD83D\uDFE2 联机中 · ' + zone;
    el.style.borderColor = '#4ecca3'; el.style.color = '#4ecca3'; el.style.background = '#0f3460';
  } else {
    el.textContent = '\uD83D\uDFE1 联机模式 · 未连接';
    el.style.borderColor = '#e94560'; el.style.color = '#e94560'; el.style.background = '#1a1a2e';
  }
}

// --- 更新弹窗状态 ---
function setMPStatus(text, online) {
  let el = document.getElementById('mpStatus');
  el.textContent = text;
  el.className = 'mp-status' + (online ? ' online' : '');
}
function hideMPSections() {
  ['mpOfferSection','mpAnswerInputSection','mpJoinSection','mpAnswerSection'].forEach(id => {
    document.getElementById(id).style.display = 'none';
  });
}

// --- 检查 SimplePeer 是否加载 ---
function checkSimplePeer() {
  if (typeof SimplePeer === 'undefined') {
    setMPStatus('❌ 联机库未加载，请检查网络连接', false);
    showTip('联机库加载失败，请刷新页面重试');
    return false;
  }
  return true;
}

// --- 创建房间（主机 / 左区） ---
function mpStartHost() {
  if (!checkSimplePeer()) return;
  if (MP.peer) { setMPStatus('⚠ 已有连接，请先断开', false); return; }
  MP.isHost = true; MP.myZone = 'left';
  setMPStatus('🟡 正在生成邀请码...', false);
  document.getElementById('mpRoleBtns').style.display = 'none';
  document.getElementById('zoneCardLeft').classList.add('active');
  document.getElementById('zoneCardRight').classList.remove('active');

  MP.peer = new SimplePeer({ initiator: true, trickle: false });
  MP.peer.on('signal', function(data) {
    document.getElementById('mpOfferCode').value = JSON.stringify(data);
    document.getElementById('mpOfferSection').style.display = 'block';
    document.getElementById('mpAnswerInputSection').style.display = 'block';
    setMPStatus('🟡 邀请码已生成，等待队友应答', false);
  });
  MP.peer.on('connect', onPeerConnect);
  MP.peer.on('data', onPeerData);
  MP.peer.on('error', onPeerError);
  MP.peer.on('close', onPeerClose);
}

// --- 加入房间（加入方 / 右区） ---
function mpStartJoin() {
  if (MP.peer) { setMPStatus('⚠ 已有连接，请先断开', false); return; }
  MP.isHost = false; MP.myZone = 'right';
  document.getElementById('mpRoleBtns').style.display = 'none';
  hideMPSections();
  document.getElementById('mpJoinSection').style.display = 'block';
  document.getElementById('zoneCardRight').classList.add('active');
  document.getElementById('zoneCardLeft').classList.remove('active');
  setMPStatus('🟡 请粘贴队友的邀请码', false);
  document.getElementById('mpJoinInput').value = '';
  document.getElementById('mpJoinInput').focus();
}

// --- 加入方：发送邀请码并生成应答码 ---
function mpSendJoin() {
  if (!checkSimplePeer()) return;
  let code = document.getElementById('mpJoinInput').value.trim();
  if (!code) { setMPStatus('⚠ 请粘贴邀请码', false); return; }
  let signal;
  try { signal = JSON.parse(code); } catch(e) { setMPStatus('❌ 无效的邀请码', false); return; }

  setMPStatus('🟡 正在连接主机...', false);
  MP.peer = new SimplePeer({ initiator: false, trickle: false });
  MP.peer.on('signal', function(data) {
    document.getElementById('mpAnswerCode').value = JSON.stringify(data);
    document.getElementById('mpAnswerSection').style.display = 'block';
    document.getElementById('mpJoinSection').style.display = 'none';
    setMPStatus('🟡 应答码已生成，请复制发给主机', false);
  });
  MP.peer.on('connect', onPeerConnect);
  MP.peer.on('data', onPeerData);
  MP.peer.on('error', onPeerError);
  MP.peer.on('close', onPeerClose);
  MP.peer.signal(signal);
}

// --- 主机：确认应答码 ---
function mpConfirmAnswer() {
  let code = document.getElementById('mpAnswerInput').value.trim();
  if (!code) { setMPStatus('⚠ 请粘贴应答码', false); return; }
  let signal;
  try { signal = JSON.parse(code); } catch(e) { setMPStatus('❌ 无效的应答码', false); return; }
  setMPStatus('🟡 正在建立连接...', false);
  MP.peer.signal(signal);
}

// --- 连接建立 ---
function onPeerConnect() {
  MP.connected = true;
  MP.enabled = true;
  setMPStatus('🟢 连接成功！', true);
  hideMPSections();
  document.getElementById('mpRoleBtns').style.display = 'none';
  document.getElementById('mpDisconnectBtn').style.display = 'inline-block';
  updateMPIndicator();
  calcBoundary();
  render();
  // 主机同步当前状态给加入方
  if (MP.isHost) {
    setTimeout(() => { syncFullState(); }, 300);
  }
  showTip(MP.myZone === 'left' ? '你是 P1 左区主机' : '你是 P2 右区加入方');
  // 显示聊天面板
  showChatPanel();
  addChatSystem('—— 联机已连接 ——');
}

// --- 连接错误 ---
function onPeerError(err) {
  setMPStatus('❌ 错误: ' + err.message, false);
  console.error('peer error', err);
}

// --- 连接关闭 ---
function onPeerClose() {
  let wasConnected = MP.connected;
  // 停止录音
  if (voiceRecorder && voiceRecorder.state === 'recording') {
    try { voiceRecorder.stop(); } catch(e){}
  }
  MP.connected = false;
  MP.peer = null;
  // 隐藏聊天面板
  hideChatPanel();
  if (wasConnected) {
    setMPStatus('⚪ 连接已断开', false);
    updateMPIndicator();
    render();
    showTip('队友已断开');
  } else {
    setMPStatus('⚪ 连接失败，请重试', false);
  }
  document.getElementById('mpDisconnectBtn').style.display = 'none';
  document.getElementById('mpRoleBtns').style.display = 'flex';
  hideMPSections();
  document.getElementById('zoneCardLeft').classList.remove('active');
  document.getElementById('zoneCardRight').classList.remove('active');
}

// --- 断开连接 ---
function mpDisconnect() {
  // 停止录音
  if (voiceRecorder && voiceRecorder.state === 'recording') {
    try { voiceRecorder.stop(); } catch(e){}
  }
  if (MP.peer) { try { MP.peer.destroy(); } catch(e){} MP.peer = null; }
  MP.connected = false; MP.enabled = false; MP.myZone = null;
  MP.remoteCursor = { x: -1, y: -1 };
  // 隐藏聊天面板并清空消息
  hideChatPanel();
  document.getElementById('chatMessages').innerHTML = '';
  setMPStatus('⚪ 未连接', false);
  updateMPIndicator();
  document.getElementById('mpDisconnectBtn').style.display = 'none';
  document.getElementById('mpRoleBtns').style.display = 'flex';
  hideMPSections();
  document.getElementById('zoneCardLeft').classList.remove('active');
  document.getElementById('zoneCardRight').classList.remove('active');
  render();
}

// --- 全状态同步（任一方可发起） ---
function syncFullState() {
  if (!MP.connected) return;
  let layout = [];
  for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) {
    let c = G.grid[x][y];
    if (c.type === T.EMPTY || c.type === T.INPUT || c.type === T.OUTPUT) continue;
    let item = { x, y, type: c.type, direction: c.direction, delay: c.delay, mode: c.mode };
    if (c.type === T.LEVER) item.leverOn = c.leverOn;
    layout.push(item);
  }
  sendToPeer({ t: 'fullSync', levelIdx: G.levelIdx, layout: layout });
}

// --- 处理远端数据 ---
function onPeerData(data) {
  // simple-peer 浏览器版可能将字符串转为 Uint8Array/Buffer，需先尝试解码为文本
  let str;
  if (typeof data === 'string') {
    str = data;
  } else if (data instanceof ArrayBuffer) {
    str = new TextDecoder('utf-8').decode(new Uint8Array(data));
  } else if (data instanceof Uint8Array) {
    str = new TextDecoder('utf-8').decode(data);
  } else {
    return;
  }
  let msg;
  try { msg = JSON.parse(str); } catch(e) {
    // 不是JSON，当作语音二进制数据处理
    playVoiceMessage(data);
    return;
  }
  MP.syncing = true;
  switch (msg.t) {
    case 'place': {
      let c = G.grid[msg.x][msg.y];
      if (c.type === T.EMPTY) {
        c.type = msg.comp; c.direction = msg.dir; c.delay = msg.delay || 1; c.mode = msg.mode || 'compare';
        c.outputActive=false; c.prevInput=false; c.eventQueue=[]; c.extinguished=false;
        c.pulsing=false; c.pulseTimer=0; c.prevFrontSignal=0; c.outputStrength=0; c.cooldown=0;
        c.extended=false; c.pushedBlockType=null; c.pistonCooldown=0;
        c.buttonActive=false; c.buttonTimer=0; c.leverOn=false;
        G.compCounts[msg.comp] = (G.compCounts[msg.comp] || 0) + 1;
        resetSimulation(); updateInfoBar(); render();
      }
      break;
    }
    case 'remove': {
      let c = G.grid[msg.x][msg.y];
      if (c.type !== T.EMPTY && c.type !== T.INPUT && c.type !== T.OUTPUT) {
        retractAllPistons();
        G.compCounts[c.type] = Math.max(0, (G.compCounts[c.type] || 1) - 1);
        c.type = T.EMPTY; c.direction = 0; c.delay = 1;
        resetSimulation(); updateInfoBar(); render();
      }
      break;
    }
    case 'modify': {
      let c = G.grid[msg.x][msg.y];
      if (c.type === msg.comp) {
        retractAllPistons();
        if (msg.dir !== undefined) c.direction = msg.dir;
        if (msg.delay !== undefined) c.delay = msg.delay;
        if (msg.mode !== undefined) c.mode = msg.mode;
        resetSimulation(); render();
      }
      break;
    }
    case 'reset': { resetSimulation(); break; }
    case 'play': { if (!G.running) startSimulation(); break; }
    case 'pause': { if (G.running) pauseSimulation(); break; }
    case 'step': { stepSimulation(); break; }
    case 'level': {
      if (msg.idx >= 0 && msg.idx < LEVELS.length && msg.idx !== G.levelIdx) {
        loadLevel(msg.idx);
      }
      break;
    }
    case 'fullSync': {
      if (msg.levelIdx !== undefined && msg.levelIdx !== G.levelIdx) {
        G.levelIdx = msg.levelIdx; G.level = LEVELS[msg.levelIdx]; G.selectedComp = null;
        initGrid(G.level);
      } else {
        // 同关卡清空自定义元件再重建
        for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) {
          let c = G.grid[x][y];
          if (c.type !== T.INPUT && c.type !== T.OUTPUT) {
            c.type = T.EMPTY; c.direction = 0; c.delay = 1;
          }
        }
        G.compCounts = {};
      }
      // 应用远端布局（不调用 restoreLayout，完全以远端为准）
      if (msg.layout) {
        for (let item of msg.layout) {
          if (item.x < 0 || item.x >= G.cols || item.y < 0 || item.y >= G.rows) continue;
          let c = G.grid[item.x][item.y];
          if (c.type === T.INPUT || c.type === T.OUTPUT) continue;
          c.type = item.type; c.direction = item.direction || 0;
          c.delay = item.delay || 1; c.mode = item.mode || 'compare';
          c.outputActive=false; c.prevInput=false; c.eventQueue=[]; c.extinguished=false;
          c.pulsing=false; c.pulseTimer=0; c.prevFrontSignal=0; c.outputStrength=0; c.cooldown=0;
          c.buttonActive=false; c.buttonTimer=0; c.leverOn=item.leverOn||false;
          G.compCounts[item.type] = (G.compCounts[item.type] || 0) + 1;
        }
      }
      calcBoundary();
      buildComponentBar(); buildLevelSelector(); updateInfoBar();
      document.getElementById('hint').textContent = '提示: ' + (G.level.hint || '');
      pauseSimulation(); resizeCanvas(); render();
      break;
    }
    case 'cursor': { MP.remoteCursor = { x: msg.x, y: msg.y }; render(); break; }
    case 'chat': { addChatMessage(msg.text, 'other'); break; }
    case 'buttonActivate': {
      let c = G.grid[msg.x][msg.y];
      if (c.type === T.BUTTON) {
        c.buttonActive = true; c.buttonTimer = 5;
        if (!G.running) { initRestingSignals(); startButtonRestTimer(); render(); }
        else render();
      }
      break;
    }
    case 'leverToggle': {
      let c = G.grid[msg.x][msg.y];
      if (c.type === T.LEVER) {
        c.leverOn = msg.on;
        if (!G.running) { initRestingSignals(); render(); }
        else render();
      }
      break;
    }
  }
  MP.syncing = false;
}

// --- 聊天功能 ---
function sendChatMessage() {
  let input = document.getElementById('chatInput');
  let text = input.value.trim();
  if (!text) return;
  if (!MP.connected) { showTip('未连接到队友'); return; }
  sendToPeer({ t: 'chat', text: text });
  addChatMessage(text, 'self');
  input.value = '';
}

function addChatMessage(text, who) {
  let container = document.getElementById('chatMessages');
  let div = document.createElement('div');
  div.className = 'chat-msg ' + who;
  if (who === 'self') {
    div.textContent = text;
  } else {
    div.textContent = '队友: ' + text;
  }
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function addChatSystem(text) {
  let container = document.getElementById('chatMessages');
  let div = document.createElement('div');
  div.className = 'chat-msg system';
  div.textContent = text;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function positionChatPanel() {
  let chatPanel = document.getElementById('chatPanel');
  let header = document.getElementById('header');
  let hint = document.getElementById('hint');
  if (!header || !hint || !chatPanel) return;
  let top = header.getBoundingClientRect().top;
  let bottom = hint.getBoundingClientRect().bottom;
  chatPanel.style.top = top + 'px';
  chatPanel.style.height = (bottom - top) + 'px';
}

function showChatPanel() {
  positionChatPanel();
  document.getElementById('chatPanel').classList.add('show');
  document.body.classList.add('chat-open');
}

function hideChatPanel() {
  document.getElementById('chatPanel').classList.remove('show');
  document.body.classList.remove('chat-open');
  let chatPanel = document.getElementById('chatPanel');
  chatPanel.style.top = '';
  chatPanel.style.height = '';
}

window.addEventListener('resize', () => {
  let chatPanel = document.getElementById('chatPanel');
  if (chatPanel && chatPanel.classList.contains('show')) {
    positionChatPanel();
  }
});

// --- 语音消息功能 ---
let voiceRecorder = null;
let voiceChunks = [];
let voiceStartTime = 0;
let voiceTimer = null;

async function toggleVoiceRecording() {
  let micBtn = document.getElementById('chatMicBtn');
  let hint = document.getElementById('chatRecordingHint');

  if (voiceRecorder && voiceRecorder.state === 'recording') {
    voiceRecorder.stop();
    return;
  }

  if (!MP.connected) { showTip('未连接到队友'); return; }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showTip('浏览器不支持语音功能'); return;
  }

  try {
    let stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    voiceChunks = [];
    voiceRecorder = new MediaRecorder(stream);
    voiceRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) voiceChunks.push(e.data);
    };
    voiceRecorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      micBtn.classList.remove('recording');
      hint.classList.remove('show');
      clearTimeout(voiceTimer);
      let duration = Math.round((Date.now() - voiceStartTime) / 1000);

      if (voiceChunks.length === 0) { showTip('录音为空'); return; }

      let blob = new Blob(voiceChunks, { type: 'audio/webm' });
      blob.arrayBuffer().then(buf => {
        let header = new ArrayBuffer(8);
        let dv = new DataView(header);
        dv.setUint32(0, 0x564F4943);
        dv.setUint32(4, duration);
        let combined = new Uint8Array(8 + buf.byteLength);
        combined.set(new Uint8Array(header), 0);
        combined.set(new Uint8Array(buf), 8);
        try {
          MP.peer.send(combined);
        } catch(e) {
          showTip('发送失败: ' + e.message);
          return;
        }
        addVoiceMessage(duration, blob, 'self');
        playClick();
      });
    };

    voiceRecorder.start();
    voiceStartTime = Date.now();
    micBtn.classList.add('recording');
    hint.classList.add('show');

    voiceTimer = setTimeout(() => {
      if (voiceRecorder && voiceRecorder.state === 'recording') {
        voiceRecorder.stop();
      }
    }, 60000);

  } catch(e) {
    showTip('无法访问麦克风: ' + (e.message || '权限被拒绝'));
  }
}

function playVoiceMessage(data) {
  let arr = new Uint8Array(data);
  if (arr.length < 8) return;
  let dv = new DataView(arr.buffer);
  let magic = dv.getUint32(0);
  if (magic !== 0x564F4943) return;
  let duration = dv.getUint32(4);
  let audioData = arr.slice(8);
  let blob = new Blob([audioData], { type: 'audio/webm' });
  addVoiceMessage(duration, blob, 'other');
}

function addVoiceMessage(duration, blob, who) {
  let container = document.getElementById('chatMessages');
  let div = document.createElement('div');
  div.className = 'chat-msg voice ' + who;

  let icon = document.createElement('span');
  icon.className = 'voice-icon';
  icon.innerHTML = who === 'self' ? '&#128483;' : '&#128253;';

  let dur = document.createElement('span');
  dur.className = 'voice-duration';
  dur.textContent = duration + 's';

  div.appendChild(icon);
  div.appendChild(dur);

  if (who === 'other') {
    let label = document.createElement('span');
    label.style.fontSize = '11px';
    label.style.opacity = '0.7';
    label.textContent = '队友';
    div.insertBefore(label, icon);
  }

  div.onclick = () => {
    let audio = new Audio(URL.createObjectURL(blob));
    div.classList.add('playing');
    audio.onended = () => { div.classList.remove('playing'); };
    audio.play();
  };

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;

  if (who === 'other') {
    let audio = new Audio(URL.createObjectURL(blob));
    audio.play().catch(() => {});
  }
}

// --- 打开/关闭联机弹窗 ---
function openOnlineModal() {
  document.getElementById('onlineModal').classList.add('show');
}
function closeOnlineModal() {
  document.getElementById('onlineModal').classList.remove('show');
}

// --- 复制到剪贴板 ---
function mpCopyText(text, label) {
  if (!text) { showTip('没有可复制的内容'); return; }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      showTip('已复制' + (label||'') + '！');
    }).catch(() => {
      mpFallbackCopy(text, label);
    });
  } else {
    mpFallbackCopy(text, label);
  }
}
function mpFallbackCopy(text, label) {
  let ta = document.createElement('textarea');
  ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
  document.body.appendChild(ta); ta.select();
  try { document.execCommand('copy'); showTip('已复制' + (label||'') + '！'); }
  catch(e) { showTip('复制失败，请手动复制'); }
  ta.remove();
}

// --- 绑定联机UI事件 ---
document.getElementById('onlineBtn').onclick = () => { playClick(); openOnlineModal(); };
document.getElementById('mpCloseBtn').onclick = () => { playClick(); closeOnlineModal(); };
document.getElementById('mpHostBtn').onclick = () => { playClick(); mpStartHost(); };
document.getElementById('mpJoinBtn').onclick = () => { playClick(); mpStartJoin(); };
document.getElementById('mpSendJoinBtn').onclick = () => { playClick(); mpSendJoin(); };
document.getElementById('mpConfirmAnswerBtn').onclick = () => { playClick(); mpConfirmAnswer(); };
document.getElementById('mpDisconnectBtn').onclick = () => { playClick(); mpDisconnect(); };
document.getElementById('mpCopyOfferBtn').onclick = () => { mpCopyText(document.getElementById('mpOfferCode').value, '邀请码'); };
document.getElementById('mpCopyAnswerBtn').onclick = () => { mpCopyText(document.getElementById('mpAnswerCode').value, '应答码'); };

// --- 聊天事件绑定 ---
document.getElementById('chatSendBtn').onclick = () => { playClick(); sendChatMessage(); };
document.getElementById('chatInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); sendChatMessage(); }
});
document.getElementById('chatMicBtn').onclick = () => { toggleVoiceRecording(); };

// ============================================================
//  常量定义
// ============================================================
const CELL = 48;
const TICK_MS = 120;
const DIRECTIONS = [
  { dx: 1, dy: 0 },
  { dx: 0, dy: 1 },
  { dx: -1, dy: 0 },
  { dx: 0, dy: -1 },
];

const T = {
  EMPTY: 'empty', DUST: 'dust', BLOCK: 'block', TORCH: 'torch',
  REPEATER: 'repeater', COMPARATOR: 'comparator', OBSERVER: 'observer',
  INPUT: 'input', OUTPUT: 'output', STONE: 'stone', PISTON: 'piston', LAMP: 'lamp',
  BUTTON: 'button', LEVER: 'lever',
};

const COMP_NAMES = {
  dust: '红石粉', block: '红石块', torch: '红石火把',
  repeater: '中继器', comparator: '比较器', observer: '侦测器', stone: '石头', piston: '粘性活塞', lamp: '红石灯',
  button: '按钮', lever: '拉杆',
};

const COMP_INTROS = {
  dust: {
    title: '红石粉',
    desc: '最基础的信号传输元件。信号每经过1格红石粉<b>衰减1点</b>（从15开始），同时产生<b>1tick延迟</b>。信号会向所有相连的方向传播，摆放成路径即可连接输入和输出。',
    tip: '左键放置 | 右键移除 | 按R键可旋转有方向的元件',
  },
  repeater: {
    title: '中继器',
    desc: '<b>单向</b>信号传输元件，只从背面输入、正面输出。点击可调节延迟档位（1~4tick），能将信号<b>恢复到15点</b>并增加精确延迟。延迟 = 档位值 + 1tick。',
    tip: '放置后点击可切换延迟档位(1~4)，按R键旋转方向',
  },
  observer: {
    title: '侦测器',
    desc: '检测<b>前方</b>格子的信号变化。当检测到信号<b>上升沿</b>（从无到有）时，从背面输出一个<b>2tick短脉冲</b>信号（强度15）。常用于将长信号转换为短脉冲。',
    tip: '侦测器"脸"朝信号来源方向，背面输出脉冲。按R键旋转',
  },
  torch: {
    title: '红石火把',
    desc: '<b>信号反相器</b>。当火把<b>背面</b>有信号时火把熄灭（输出0）；背面无信号时火把点亮（输出15）。可用于构建逻辑非门。注意：火把是单向元件，只从背面输入。',
    tip: '火把头指向输出方向，杆部连接输入。按R键旋转',
  },
  block: {
    title: '红石块',
    desc: '<b>永久信号源</b>。红石块始终输出满强度信号（15点），无需任何输入即可供电。可作为常亮电源使用，也能传导信号。',
    tip: '无需输入，始终输出信号强度15',
  },
  stone: {
    title: '石头',
    desc: '<b>可充能方块</b>。石头本身不产生信号，但当<b>中继器正面朝向石头</b>时，石头被充能为信号强度15。充能后的石头可以给相邻的红石粉、中继器（输入端朝向石头）、比较器（输入端朝向石头）提供信号。',
    tip: '将中继器正面（输出端）对准石头即可充能，石头向所有相邻方向输出信号',
  },
  piston: {
    title: '粘性活塞',
    desc: '<b>可推拉方块的机械元件</b>。当活塞<b>任意相邻方向有信号</b>时，活塞伸出，将正前方的<b>石头或红石块</b>向前推一格；信号消失时活塞缩回，将方块<b>拉回</b>原位。活塞本身不导电也不产生信号，但被推拉的方块在新位置会正常工作。',
    tip: '活塞正面朝向要推的方块，给活塞相邻的任意红石粉供电即可激活。按R键旋转方向',
  },
  comparator: {
    title: '比较器',
    desc: '<b>信号处理</b>元件。背面为主输入，左右两侧为侧输入。<b>比较模式</b>：主输入≥侧输入时直通信号；<b>减法模式</b>：输出 = 主输入 - 侧输入。点击可切换模式，按R键旋转方向。',
    tip: '三角尖端为输出方向，背面为主输入。点击切换比较/减法模式',
  },
  lamp: {
    title: '红石灯',
    desc: '<b>信号指示灯</b>。当任意相邻方向有红石信号时，灯泡<b>亮起</b>发出橙色光芒；信号消失时熄灭。红石灯不导电也不产生信号，仅用于<b>可视化信号状态</b>。',
    tip: '放在红石粉旁边即可，有信号就亮，无信号就灭',
  },
  button: {
    title: '按钮',
    desc: '<b>瞬时信号源</b>。点击按钮后，它会输出<b>强度15</b>的信号，持续<b>5tick</b>后自动关闭。按钮向所有相邻方向输出信号，适合触发短脉冲。',
    tip: '点击已放置的按钮即可激活，信号持续5tick后自动消失',
  },
  lever: {
    title: '拉杆',
    desc: '<b>持久信号源</b>。拉杆有<b>开启</b>和<b>关闭</b>两种状态。开启时持续输出<b>强度15</b>的信号，关闭时不输出。点击拉杆可切换状态。',
    tip: '点击已放置的拉杆切换开/关，开启时持续输出信号',
  },
};

// ============================================================
//  关卡数据（由生成器注入）
// ============================================================
const LEVELS = __LEVELS_PLACEHOLDER__;

// ============================================================
//  随机关卡生成（第19关）
// ============================================================
function generateRandomLevel() {
  for (let attempt = 0; attempt < 50; attempt++) {
    let lv = tryGenerateRandomLevel();
    if (lv) return lv;
  }
  // 保底：简单直线关卡
  return {
    name: '随机挑战', desc: '随机生成的关卡——每次都不一样！',
    cols: 12, rows: 6,
    input: { x: 1, y: 3, duration: 15, strength: 15 },
    output: { x: 10, y: 3 },
    target: { delay: 8, duration: 15 },
    components: ['dust', 'repeater'], limits: { dust: 12, repeater: 2 },
    hint: '随机关卡：随机元件和目标，已通过模拟验证', par: 8, preplaced: []
  };
}

function tryGenerateRandomLevel() {
  let cols = 10 + Math.floor(Math.random() * 7);
  let rows = 6 + Math.floor(Math.random() * 5);
  let inY = 1 + Math.floor(Math.random() * (rows - 2));
  let outY = 1 + Math.floor(Math.random() * (rows - 2));
  let inputDur = 10 + Math.floor(Math.random() * 11);
  let input = { x: 1, y: inY, duration: inputDur, strength: 15 };
  let output = { x: cols - 2, y: outY };

  // 生成L形路径（确保所有单元格正交相邻）
  let path = [];
  let cx = input.x + 1, cy = input.y;
  let midX = input.x + 2 + Math.floor(Math.random() * Math.max(1, output.x - input.x - 4));
  midX = Math.min(midX, output.x - 2);
  // Phase 1: 向右到midX（含）
  while (cx <= midX) { path.push({x: cx, y: cy, dir: 0}); cx++; }
  cx = midX;
  // Phase 2: 垂直到outY
  while (cy !== outY) {
    if (cy < outY) { cy++; path.push({x: cx, y: cy, dir: 1}); }
    else { cy--; path.push({x: cx, y: cy, dir: 3}); }
  }
  // Phase 3: 向右到output前一格
  cx = midX + 1;
  while (cx <= output.x - 1) { path.push({x: cx, y: cy, dir: 0}); cx++; }

  if (path.length < 3) return null;

  // 随机选择可用元件
  let components = ['dust'];
  let limits = { dust: path.length + 8 };
  let useRep = Math.random() < 0.7;
  let useObs = Math.random() < 0.4;
  if (useRep) { components.push('repeater'); limits.repeater = 1 + Math.floor(Math.random() * 3); }
  if (useObs) { components.push('observer'); limits.observer = 1 + Math.floor(Math.random() * 2); }

  // 构建解法
  let solution = [];
  let repCount = 0;
  let dustSinceRep = 0;
  let needRep = useRep && path.length > 12;
  let repInterval = needRep ? Math.floor(path.length / 3) : 999;

  for (let i = 0; i < path.length; i++) {
    let cell = path[i];
    let isLast = (i === path.length - 1);
    if (isLast && useObs && path.length > 2) {
      solution.push({ x: cell.x, y: cell.y, type: 'observer', direction: (cell.dir + 2) % 4 });
    } else if (needRep && repCount < limits.repeater && dustSinceRep >= repInterval && !isLast && cell.dir === 0) {
      let delay = 1 + Math.floor(Math.random() * 3);
      solution.push({ x: cell.x, y: cell.y, type: 'repeater', direction: 0, delay: delay });
      repCount++; dustSinceRep = 0;
    } else {
      solution.push({ x: cell.x, y: cell.y, type: 'dust' });
      dustSinceRep++;
    }
  }

  let level = {
    name: '随机挑战', desc: '随机生成的关卡——每次都不一样！',
    cols, rows, input, output,
    components: components, limits: limits,
    hint: '随机关卡：随机元件和目标，已通过模拟验证可解',
    par: path.length, preplaced: solution
  };

  let result = validateSolution(level);
  if (!result.valid) return null;

  level.target = { delay: result.delay, duration: result.duration };
  if (result.strength > 0 && result.strength < 15) level.target.strength = result.strength;
  level.preplaced = [];
  return level;
}

function validateSolution(level) {
  G.validating = true;
  let savedLevel = G.level, savedIdx = G.levelIdx, savedGrid = G.grid, savedSig = G.signals;
  let savedTick = G.tick, savedInputActive = G.inputActive, savedInputRem = G.inputRemaining;
  let savedOutput = { p: G.outputPowered, a: G.outputArrivalTick, d: G.outputDepartureTick,
    dur: G.outputDuration, del: G.outputDelay, str: G.outputMaxStrength, pc: G.pulseChecked, w: G.won };
  let savedInputStates = G.inputStates, savedCompCounts = G.compCounts;
  let savedCols = G.cols, savedRows = G.rows;

  G.level = level; G.levelIdx = -999;
  initGrid(level);

  if (G.inputStates.length > 0) { for (let s of G.inputStates) { s.remaining = s.duration; s.delay = s.origDelay; s.active = false; } }
  else { G.inputRemaining = level.input.duration; }
  G.inputActive = false; G.tick = 0; G.pulseChecked = false; G.won = false;

  let maxDuration = G.inputStates.length > 0 ? Math.max(...G.inputStates.map(s => (s.origDelay||0) + s.duration)) : level.input.duration;
  let maxTicks = maxDuration + 60;

  for (let i = 0; i < maxTicks; i++) {
    tickUpdate();
    if (G.outputDuration > 0) break;
  }

  let result = {
    valid: G.outputDelay >= 0 && G.outputDuration > 0,
    delay: G.outputDelay, duration: G.outputDuration, strength: G.outputMaxStrength
  };

  // 恢复状态
  G.level = savedLevel; G.levelIdx = savedIdx; G.grid = savedGrid; G.signals = savedSig;
  G.tick = savedTick; G.inputActive = savedInputActive; G.inputRemaining = savedInputRem;
  G.outputPowered = savedOutput.p; G.outputArrivalTick = savedOutput.a;
  G.outputDepartureTick = savedOutput.d; G.outputDuration = savedOutput.dur;
  G.outputDelay = savedOutput.del; G.outputMaxStrength = savedOutput.str; G.pulseChecked = savedOutput.pc; G.won = savedOutput.w;
  G.inputStates = savedInputStates; G.compCounts = savedCompCounts;
  G.cols = savedCols; G.rows = savedRows;
  G.validating = false;

  return result;
}

// 生成随机关卡（在G初始化后调用）
// LEVELS.push(generateRandomLevel()); — 移至G定义后

// ============================================================
//  游戏状态
// ============================================================
let G = {
  grid: [], signals: [], cols: 0, rows: 0,
  levelIdx: 0, level: null, tick: 0,
  running: false, timer: null,
  selectedComp: null, selectedRotate: 0,
  inputActive: false, inputRemaining: 0,
  outputPowered: false, outputArrivalTick: -1,
  outputDepartureTick: -1, outputDuration: 0, outputDelay: -1, outputMaxStrength: 0, pulseChecked: false, won: false,
  hoverX: -1, hoverY: -1,
  validating: false,
  completed: new Set((() => {
    let ver = localStorage.getItem('rs_version');
    if (ver !== '5') {
      localStorage.removeItem('rs_completed');
      localStorage.removeItem('rs_intro_seen');
      localStorage.setItem('rs_version', '5');
    }
    return JSON.parse(localStorage.getItem('rs_completed') || '[]');
  })()),
  compCounts: {}, animFrame: 0, pistonAnimRequested: false,
  inputStates: [], logicResult: null, levelLayouts: {},
};

function initGrid(level) {
  G.cols = level.cols; G.rows = level.rows;
  G.grid = []; G.signals = [];
  for (let x = 0; x < G.cols; x++) {
    G.grid[x] = []; G.signals[x] = [];
    for (let y = 0; y < G.rows; y++) {
      G.grid[x][y] = { type: T.EMPTY, direction: 0, delay: 1, mode: 'compare',
        outputActive: false, prevInput: false, eventQueue: [],
        extinguished: false, pulsing: false, pulseTimer: 0,
        prevFrontSignal: 0, outputStrength: 0, cooldown: 0,
        extended: false, pushedBlockType: null, pistonCooldown: 0, pistonAnim: 0,
        buttonActive: false, buttonTimer: 0, leverOn: false };
      G.signals[x][y] = 0;
    }
  }
  if (level.input) { G.grid[level.input.x][level.input.y].type = T.INPUT; }
  if (level.inputs) {
    G.inputStates = level.inputs.map(inp => ({
      x: inp.x, y: inp.y, duration: inp.duration,
      delay: inp.delay || 0, origDelay: inp.delay || 0,
      strength: inp.strength || 15, remaining: 0, active: false,
    }));
    for (let s of G.inputStates) G.grid[s.x][s.y].type = T.INPUT;
  } else { G.inputStates = []; }
  if (level.output) { G.grid[level.output.x][level.output.y].type = T.OUTPUT; }
  if (level.preplaced) {
    for (let p of level.preplaced) {
      let c = G.grid[p.x][p.y]; c.type = p.type;
      if (p.direction !== undefined) c.direction = p.direction;
      if (p.delay !== undefined) c.delay = p.delay;
      if (p.mode !== undefined) c.mode = p.mode;
    }
  }
  G.compCounts = {};
  calcBoundary();
  resetSimulation();
}

function isSignalSource(cell) { return [T.BLOCK,T.TORCH,T.REPEATER,T.COMPARATOR,T.OBSERVER,T.INPUT,T.STONE,T.BUTTON,T.LEVER].includes(cell.type); }
function isConductive(cell) { return [T.DUST,T.BLOCK,T.TORCH,T.REPEATER,T.COMPARATOR,T.OBSERVER,T.INPUT,T.STONE,T.BUTTON,T.LEVER].includes(cell.type); }
function isDirectionalSource(cell) { return [T.REPEATER,T.COMPARATOR,T.OBSERVER,T.TORCH].includes(cell.type); }
function getOutputDir(cell) { let d=DIRECTIONS[cell.direction]; return cell.type===T.OBSERVER?{dx:-d.dx,dy:-d.dy}:d; }
function getNeighborSignal(nx,ny,x,y) { let n=G.grid[nx][ny]; if(!isConductive(n))return 0; if(isDirectionalSource(n)){let o=getOutputDir(n); if(nx+o.dx!==x||ny+o.dy!==y)return 0;} return G.signals[nx][ny]; }
function getInputSignal(x,y,dir) { let ix=x-dir.dx,iy=y-dir.dy; if(ix<0||ix>=G.cols||iy<0||iy>=G.rows)return 0; let n=G.grid[ix][iy]; if(!isConductive(n))return 0; if(isDirectionalSource(n)){let o=getOutputDir(n); if(ix+o.dx!==x||iy+o.dy!==y)return 0;} return G.signals[ix][iy]; }
function getOutputPower(cell,x,y) {
  switch(cell.type){
    case T.BLOCK: return 15;
    case T.INPUT: { if(G.inputStates.length>0){for(let s of G.inputStates){if(s.x===x&&s.y===y)return s.active?s.strength:0;}return 0;} return G.inputActive?(G.level.input.strength||15):0; }
    case T.TORCH: return cell.extinguished?0:15;
    case T.REPEATER: return cell.outputActive?15:0;
    case T.COMPARATOR: return cell.outputActive?(cell.outputStrength||0):0;
    case T.OBSERVER: return cell.pulsing?15:0;
    case T.STONE: { let p=0; for(let i=0;i<4;i++){let d=DIRECTIONS[i]; let nx=x+d.dx,ny=y+d.dy; if(nx<0||nx>=G.cols||ny<0||ny>=G.rows)continue; let n=G.grid[nx][ny]; if(n.type===T.REPEATER){let o=getOutputDir(n); if(nx+o.dx===x&&ny+o.dy===y){let s=G.signals[nx][ny]; if(s>p)p=s;}}} return p; }
    case T.BUTTON: return cell.buttonActive ? 15 : 0;
    case T.LEVER: return cell.leverOn ? 15 : 0;
    default: return 0;
  }
}

function tickUpdate() {
  G.animFrame++;
  if (G.inputStates.length > 0) {
    for (let s of G.inputStates) {
      if (s.delay > 0) { s.delay--; s.active = false; }
      else if (s.remaining > 0) { s.active = true; s.remaining--; }
      else { s.active = false; }
    }
    G.inputActive = G.inputStates.some(s => s.active);
  } else {
    if (G.inputRemaining > 0) { G.inputActive = true; G.inputRemaining--; }
    else { G.inputActive = false; }
  }
  for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) {
    let cell = G.grid[x][y];
    switch(cell.type){
      case T.REPEATER: { let d=DIRECTIONS[cell.direction]; let ip=getInputSignal(x,y,d)>0; if(ip&&!cell.prevInput)cell.eventQueue.push({tick:G.tick+cell.delay,state:true}); if(!ip&&cell.prevInput)cell.eventQueue.push({tick:G.tick+cell.delay,state:false}); cell.prevInput=ip; while(cell.eventQueue.length>0&&cell.eventQueue[0].tick<=G.tick)cell.outputActive=cell.eventQueue.shift().state; break; }
      case T.TORCH: { let d=DIRECTIONS[cell.direction]; cell.extinguished=getInputSignal(x,y,d)>0; break; }
      case T.COMPARATOR: { let d=DIRECTIONS[cell.direction]; let mp=getInputSignal(x,y,d); let sp=0; let ps=[{dx:d.dy,dy:d.dx},{dx:-d.dy,dy:-d.dx}]; for(let p of ps){let sx=x+p.dx,sy=y+p.dy; if(sx>=0&&sx<G.cols&&sy>=0&&sy<G.rows){let ns=getNeighborSignal(sx,sy,x,y); if(ns>sp)sp=ns;}} if(cell.mode==='compare'){if(mp>=sp&&mp>0){cell.outputActive=true;cell.outputStrength=mp;}else{cell.outputActive=false;cell.outputStrength=0;}}else{let r=Math.max(0,mp-sp);cell.outputActive=r>0;cell.outputStrength=r;} break; }
      case T.OBSERVER: { let d=DIRECTIONS[cell.direction]; let fx=x+d.dx,fy=y+d.dy; let fs=0; if(fx>=0&&fx<G.cols&&fy>=0&&fy<G.rows)fs=G.signals[fx][fy]||0; if(fs>0&&cell.prevFrontSignal===0){cell.pulsing=true;cell.pulseTimer=2;}else if(cell.pulseTimer>0){cell.pulseTimer--;if(cell.pulseTimer<=0)cell.pulsing=false;} cell.prevFrontSignal=fs; break; }
      case T.BUTTON: { if(cell.buttonActive){cell.buttonTimer--; if(cell.buttonTimer<=0)cell.buttonActive=false;} break; }
    }
  }
  // 粘性活塞推拉逻辑
  for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) {
    let cell = G.grid[x][y];
    if (cell.type !== T.PISTON) continue;
    if (cell.pistonCooldown > 0) { cell.pistonCooldown--; continue; }
    let dir = DIRECTIONS[cell.direction];
    let fx = x + dir.dx, fy = y + dir.dy;
    let bx = fx + dir.dx, by = fy + dir.dy;
    if (fx < 0 || fx >= G.cols || fy < 0 || fy >= G.rows) continue;
    if (bx < 0 || bx >= G.cols || by < 0 || by >= G.rows) continue;
    let powered = false;
    for (let i = 0; i < 4; i++) { if (i === cell.direction) continue; let d = DIRECTIONS[i]; let nx = x + d.dx, ny = y + d.dy; if (nx < 0 || nx >= G.cols || ny < 0 || ny >= G.rows) continue; if (G.signals[nx][ny] > 0) { powered = true; break; } }
    let frontCell = G.grid[fx][fy];
    let beyondCell = G.grid[bx][by];
    if (powered && !cell.extended) {
      if ((frontCell.type === T.STONE || frontCell.type === T.BLOCK) && beyondCell.type === T.EMPTY) {
        beyondCell.type = frontCell.type; beyondCell.direction = frontCell.direction; beyondCell.delay = frontCell.delay; beyondCell.mode = frontCell.mode;
        beyondCell.outputActive=false; beyondCell.prevInput=false; beyondCell.eventQueue=[]; beyondCell.extinguished=false; beyondCell.pulsing=false; beyondCell.pulseTimer=0; beyondCell.prevFrontSignal=0; beyondCell.outputStrength=0; beyondCell.cooldown=0; beyondCell.extended=false; beyondCell.pushedBlockType=null;
        frontCell.type = T.EMPTY; frontCell.direction = 0; frontCell.delay = 1; frontCell.mode = 'compare';
        cell.extended = true; cell.pushedBlockType = beyondCell.type; cell.pistonCooldown = 2;
      }
    } else if (!powered && cell.extended) {
      if (frontCell.type === T.EMPTY && beyondCell.type === cell.pushedBlockType) {
        frontCell.type = beyondCell.type; frontCell.direction = beyondCell.direction; frontCell.delay = beyondCell.delay; frontCell.mode = beyondCell.mode;
        frontCell.outputActive=false; frontCell.prevInput=false; frontCell.eventQueue=[]; frontCell.extinguished=false; frontCell.pulsing=false; frontCell.pulseTimer=0; frontCell.prevFrontSignal=0; frontCell.outputStrength=0; frontCell.cooldown=0; frontCell.extended=false; frontCell.pushedBlockType=null;
        beyondCell.type = T.EMPTY; beyondCell.direction = 0; beyondCell.delay = 1; beyondCell.mode = 'compare';
        cell.extended = false; cell.pushedBlockType = null; cell.pistonCooldown = 2;
      }
    }
  }
  let newSig = [];
  for (let x = 0; x < G.cols; x++) {
    newSig[x] = [];
    for (let y = 0; y < G.rows; y++) {
      newSig[x][y] = 0;
      let cell = G.grid[x][y];
      if (isSignalSource(cell)) { newSig[x][y] = getOutputPower(cell, x, y); }
      else if (cell.type === T.DUST) {
        let prevSig = G.signals[x][y];
        if (cell.cooldown > 0) { cell.cooldown--; newSig[x][y] = 0; }
        else if (prevSig > 0) {
          let mx = 0;
          for (let i = 0; i < 4; i++) { let d=DIRECTIONS[i]; let nx=x+d.dx,ny=y+d.dy; if(nx<0||nx>=G.cols||ny<0||ny>=G.rows)continue; let s=getNeighborSignal(nx,ny,x,y); if(s>mx)mx=s; }
          if (mx > prevSig) newSig[x][y] = mx - 1;
          else { newSig[x][y] = 0; cell.cooldown = 2; }
        } else {
          let mx = 0;
          for (let i = 0; i < 4; i++) { let d=DIRECTIONS[i]; let nx=x+d.dx,ny=y+d.dy; if(nx<0||nx>=G.cols||ny<0||ny>=G.rows)continue; let s=getNeighborSignal(nx,ny,x,y); if(s>mx)mx=s; }
          newSig[x][y] = mx > 0 ? mx - 1 : 0;
        }
      }
    }
  }
  G.signals = newSig;
  let hasActiveSignal = false;
  for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) { if (newSig[x][y] > 0) { hasActiveSignal = true; break; } }
  if (hasActiveSignal && !G.validating) playSignal();
  if (G.level.output) checkOutput();
  if (!G.validating) updateInfoBar();
  G.tick++;
  if (G.level.freeMode) {
    let anySignal = false, anyEvent = false;
    for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) { if (G.signals[x][y] > 0) anySignal = true; if (G.grid[x][y].eventQueue && G.grid[x][y].eventQueue.length > 0) anyEvent = true; }
    if (!anySignal && !anyEvent && G.tick > 10) endSimulation();
    return;
  }
  let maxDuration = G.inputStates.length > 0 ? Math.max(...G.inputStates.map(s => (s.origDelay||0) + s.duration)) : G.level.input.duration;
  if (!G.inputActive && G.tick > maxDuration + 10) {
    let anySignal = false, anyEvent = false;
    for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) { if (G.signals[x][y] > 0) anySignal = true; if (G.grid[x][y].eventQueue && G.grid[x][y].eventQueue.length > 0) anyEvent = true; }
    if (!anySignal && !anyEvent && !G.outputPowered) endSimulation();
  }
  if (G.tick > maxDuration + 50) endSimulation();
}

function endSimulation() {
  pauseSimulation();
  if (G.validating) return;
  if (G.level.freeMode) return;
  if (!G.won) showFailModal();
}

function checkOutput() {
  let out = G.level.output; let hasSignal = false; let maxStr = 0;
  for (let d of DIRECTIONS) { let nx=out.x+d.dx,ny=out.y+d.dy; if(nx<0||nx>=G.cols||ny<0||ny>=G.rows)continue; if(G.signals[nx][ny]>0){hasSignal=true; if(G.signals[nx][ny]>maxStr)maxStr=G.signals[nx][ny];} }
  if (hasSignal && !G.outputPowered && !G.pulseChecked) { G.outputPowered = true; G.outputArrivalTick = G.tick; G.outputDelay = G.tick; G.outputMaxStrength = maxStr; }
  if (hasSignal && G.outputPowered && maxStr > G.outputMaxStrength) G.outputMaxStrength = maxStr;
  if (!hasSignal && G.outputPowered) { G.outputPowered = false; G.outputDepartureTick = G.tick; G.outputDuration = G.outputDepartureTick - G.outputArrivalTick; G.pulseChecked = true; let won = checkWin(); if (!won && !G.validating) endSimulation(); }
}

function checkWin() {
  if (G.validating) return false;
  let target = G.level.target;
  let strengthOk = target.strength === undefined || G.outputMaxStrength === target.strength;
  if (G.outputDelay === target.delay && G.outputDuration === target.duration && strengthOk) {
    G.completed.add(G.levelIdx);
    localStorage.setItem('rs_completed', JSON.stringify([...G.completed]));
    G.won = true;
    pauseSimulation(); showWinModal();
    return true;
  }
  return false;
}

function startSimulation() {
  if (G.running) return;
  if (G.tick === 0) {
    if (G.inputStates.length > 0) { for (let s of G.inputStates) { s.remaining = s.duration; s.delay = s.origDelay; s.active = false; } }
    else if (G.level.input) { G.inputRemaining = G.level.input.duration; }
  }
  G.running = true;
  document.getElementById('playBtn').textContent = '\u23F8 暂停';
  G.timer = setInterval(() => { tickUpdate(); render(); }, TICK_MS);
}
function pauseSimulation() { G.running = false; if (G.timer) { clearInterval(G.timer); G.timer = null; } if (!G.validating) document.getElementById('playBtn').textContent = '\u25B6 播放'; }

// 静止状态下按钮实时倒计时
let buttonRestTimer = null;
function startButtonRestTimer() {
  if (buttonRestTimer) return;
  buttonRestTimer = setInterval(() => {
    let anyActive = false;
    for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) {
      let c = G.grid[x][y];
      if (c.type === T.BUTTON && c.buttonActive) {
        c.buttonTimer--;
        if (c.buttonTimer <= 0) c.buttonActive = false;
        else anyActive = true;
      }
    }
    if (!anyActive) { clearInterval(buttonRestTimer); buttonRestTimer = null; }
    if (!G.running) { initRestingSignals(); render(); }
  }, TICK_MS);
}
function initRestingSignals() {
  // 迭代计算静止信号状态：火把/红石块/中继器/比较器/石头点亮红石粉，火把收到输入信号则熄灭
  let changed = true, iter = 0;
  while (changed && iter < 50) {
    changed = false; iter++;
    for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) G.signals[x][y] = 0;
    // 设置信号源（含中继器、比较器、石头）
    for (let x = 0; x < G.cols; x++) {
      for (let y = 0; y < G.rows; y++) {
        let cell = G.grid[x][y];
        if (cell.type === T.TORCH && !cell.extinguished) G.signals[x][y] = 15;
        else if (cell.type === T.BLOCK) G.signals[x][y] = 15;
        else if (cell.type === T.REPEATER) {
          let d=DIRECTIONS[cell.direction]; let ip=getInputSignal(x,y,d)>0;
          cell.outputActive=ip; cell.prevInput=ip;
          if(ip) G.signals[x][y]=15;
        }
        else if (cell.type === T.COMPARATOR) {
          let d=DIRECTIONS[cell.direction]; let mp=getInputSignal(x,y,d); let sp=0;
          let ps=[{dx:d.dy,dy:d.dx},{dx:-d.dy,dy:-d.dx}];
          for(let p of ps){let sx=x+p.dx,sy=y+p.dy; if(sx>=0&&sx<G.cols&&sy>=0&&sy<G.rows){let ns=getNeighborSignal(sx,sy,x,y); if(ns>sp)sp=ns;}}
          if(cell.mode==='compare'){if(mp>=sp&&mp>0){cell.outputActive=true;cell.outputStrength=mp;G.signals[x][y]=mp;}else{cell.outputActive=false;cell.outputStrength=0;}}
          else{let r=Math.max(0,mp-sp);cell.outputActive=r>0;cell.outputStrength=r;if(r>0)G.signals[x][y]=r;}
        }
        else if (cell.type === T.STONE) {
          let p=0; for(let i=0;i<4;i++){let d=DIRECTIONS[i]; let nx=x+d.dx,ny=y+d.dy; if(nx<0||nx>=G.cols||ny<0||ny>=G.rows)continue; let n=G.grid[nx][ny]; if(n.type===T.REPEATER){let o=getOutputDir(n); if(nx+o.dx===x&&ny+o.dy===y){let s=G.signals[nx][ny]; if(s>p)p=s;}}}
          if(p>0) G.signals[x][y]=p;
        }
        else if (cell.type === T.BUTTON && cell.buttonActive) G.signals[x][y] = 15;
        else if (cell.type === T.LEVER && cell.leverOn) G.signals[x][y] = 15;
      }
    }
    // 红石粉传播 + 中继器/比较器/石头 交叉传播（确保中继器激活后红石粉能再次传播）
    let innerChanged = true, innerIter = 0;
    while (innerChanged && innerIter < 30) {
      innerChanged = false; innerIter++;
      let dustChanged = true, dustIter = 0;
      while (dustChanged && dustIter < 30) {
        dustChanged = false; dustIter++;
        for (let x = 0; x < G.cols; x++) {
          for (let y = 0; y < G.rows; y++) {
            if (G.grid[x][y].type === T.DUST) {
              let mx = 0;
              for (let i = 0; i < 4; i++) {
                let d = DIRECTIONS[i];
                let nx = x + d.dx, ny = y + d.dy;
                if (nx < 0 || nx >= G.cols || ny < 0 || ny >= G.rows) continue;
                let s = getNeighborSignal(nx, ny, x, y);
                if (s > mx) mx = s;
              }
              let newVal = mx > 0 ? mx - 1 : 0;
              if (newVal !== G.signals[x][y]) { G.signals[x][y] = newVal; dustChanged = true; }
            }
          }
        }
      }
      // 红石粉传播后重新检查中继器/比较器/石头
      for (let x = 0; x < G.cols; x++) {
        for (let y = 0; y < G.rows; y++) {
          let cell = G.grid[x][y];
          if (cell.type === T.REPEATER) {
            let d=DIRECTIONS[cell.direction]; let ip=getInputSignal(x,y,d)>0;
            if(ip!==cell.outputActive){cell.outputActive=ip;cell.prevInput=ip;G.signals[x][y]=ip?15:0;innerChanged=true;changed=true;}
          }
          else if (cell.type === T.COMPARATOR) {
            let d=DIRECTIONS[cell.direction]; let mp=getInputSignal(x,y,d); let sp=0;
            let ps=[{dx:d.dy,dy:d.dx},{dx:-d.dy,dy:-d.dx}];
            for(let p of ps){let sx=x+p.dx,sy=y+p.dy; if(sx>=0&&sx<G.cols&&sy>=0&&sy<G.rows){let ns=getNeighborSignal(sx,sy,x,y); if(ns>sp)sp=ns;}}
            let na,ns; if(cell.mode==='compare'){if(mp>=sp&&mp>0){na=true;ns=mp;}else{na=false;ns=0;}}else{let r=Math.max(0,mp-sp);na=r>0;ns=r;}
            if(na!==cell.outputActive||ns!==cell.outputStrength){cell.outputActive=na;cell.outputStrength=ns;G.signals[x][y]=na?ns:0;innerChanged=true;changed=true;}
          }
          else if (cell.type === T.STONE) {
            let p=0; for(let i=0;i<4;i++){let d=DIRECTIONS[i]; let nx=x+d.dx,ny=y+d.dy; if(nx<0||nx>=G.cols||ny<0||ny>=G.rows)continue; let n=G.grid[nx][ny]; if(n.type===T.REPEATER){let o=getOutputDir(n); if(nx+o.dx===x&&ny+o.dy===y){let s=G.signals[nx][ny]; if(s>p)p=s;}}}
            if(p!==G.signals[x][y]){G.signals[x][y]=p;innerChanged=true;changed=true;}
          }
        }
      }
    }
    for (let x = 0; x < G.cols; x++) {
      for (let y = 0; y < G.rows; y++) {
        let cell = G.grid[x][y];
        if (cell.type === T.TORCH) {
          let d = DIRECTIONS[cell.direction];
          let shouldExtinguish = getInputSignal(x, y, d) > 0;
          if (shouldExtinguish !== cell.extinguished) { cell.extinguished = shouldExtinguish; changed = true; }
        }
      }
    }
    // 活塞静止状态计算
    for (let x = 0; x < G.cols; x++) {
      for (let y = 0; y < G.rows; y++) {
        let cell = G.grid[x][y];
        if (cell.type !== T.PISTON) continue;
        let dir = DIRECTIONS[cell.direction];
        let fx = x + dir.dx, fy = y + dir.dy, bx = fx + dir.dx, by = fy + dir.dy;
        if (fx < 0 || fx >= G.cols || fy < 0 || fy >= G.rows || bx < 0 || bx >= G.cols || by < 0 || by >= G.rows) continue;
        let powered = false;
        for (let i = 0; i < 4; i++) { if (i === cell.direction) continue; let d = DIRECTIONS[i]; let nx = x + d.dx, ny = y + d.dy; if (nx < 0 || nx >= G.cols || ny < 0 || ny >= G.rows) continue; if (G.signals[nx][ny] > 0) { powered = true; break; } }
        let fc = G.grid[fx][fy], bc = G.grid[bx][by];
        if (powered && !cell.extended) {
          if ((fc.type === T.STONE || fc.type === T.BLOCK) && bc.type === T.EMPTY) {
            bc.type = fc.type; bc.direction = fc.direction; bc.delay = fc.delay; bc.mode = fc.mode;
            fc.type = T.EMPTY; fc.direction = 0; fc.delay = 1; fc.mode = 'compare';
            cell.extended = true; cell.pushedBlockType = bc.type; changed = true;
          }
        } else if (!powered && cell.extended) {
          if (fc.type === T.EMPTY && bc.type === cell.pushedBlockType) {
            fc.type = bc.type; fc.direction = bc.direction; fc.delay = bc.delay; fc.mode = bc.mode;
            bc.type = T.EMPTY; bc.direction = 0; bc.delay = 1; bc.mode = 'compare';
            cell.extended = false; cell.pushedBlockType = null; changed = true;
          }
        }
      }
    }
  }
}
function retractAllPistons() {
  for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) {
    let cell = G.grid[x][y];
    if (cell.type !== T.PISTON || !cell.extended) continue;
    let dir = DIRECTIONS[cell.direction];
    let fx = x + dir.dx, fy = y + dir.dy, bx = fx + dir.dx, by = fy + dir.dy;
    if (fx < 0 || fx >= G.cols || fy < 0 || fy >= G.rows || bx < 0 || bx >= G.cols || by < 0 || by >= G.rows) { cell.extended = false; cell.pushedBlockType = null; cell.pistonCooldown = 0; continue; }
    let fc = G.grid[fx][fy], bc = G.grid[bx][by];
    if (fc.type === T.EMPTY && bc.type === cell.pushedBlockType) {
      fc.type = bc.type; fc.direction = bc.direction; fc.delay = bc.delay; fc.mode = bc.mode;
      bc.type = T.EMPTY; bc.direction = 0; bc.delay = 1; bc.mode = 'compare';
    }
    cell.extended = false; cell.pushedBlockType = null; cell.pistonCooldown = 0; cell.pistonAnim = 0;
  }
}
function maybeAnimatePistons() {
  let animating = false;
  for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) {
    let cell = G.grid[x][y];
    if (cell.type !== T.PISTON) continue;
    let target = cell.extended ? 1 : 0;
    if (Math.abs(cell.pistonAnim - target) > 0.01) {
      cell.pistonAnim += (target - cell.pistonAnim) * 0.25;
      animating = true;
    } else { cell.pistonAnim = target; }
  }
  if (animating && !G.pistonAnimRequested) {
    G.pistonAnimRequested = true;
    requestAnimationFrame(() => { G.pistonAnimRequested = false; render(); });
  }
}
function resetSimulation() {
  pauseSimulation();
  if (buttonRestTimer) { clearInterval(buttonRestTimer); buttonRestTimer = null; }
  G.tick = 0; G.inputActive = false; G.inputRemaining = 0;
  for (let s of G.inputStates) { s.remaining = 0; s.active = false; s.delay = 0; }
  G.outputPowered = false; G.outputArrivalTick = -1; G.outputDepartureTick = -1; G.outputDelay = -1; G.outputDuration = 0; G.outputMaxStrength = 0; G.pulseChecked = false; G.won = false; G.animFrame = 0;
  retractAllPistons();
  for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) { G.signals[x][y] = 0; let c = G.grid[x][y]; c.outputActive=false; c.prevInput=false; c.eventQueue=[]; c.extinguished=false; c.pulsing=false; c.pulseTimer=0; c.prevFrontSignal=0; c.outputStrength=0; c.cooldown=0; c.pistonCooldown=0; c.buttonActive=false; c.buttonTimer=0; }
  if (!G.validating) initRestingSignals();
  if (!G.validating) { render(); updateInfoBar(); }
}
function stepSimulation() {
  if (G.tick === 0) {
    if (G.inputStates.length > 0) { for (let s of G.inputStates) { s.remaining = s.duration; s.delay = s.origDelay; s.active = false; } }
    else if (G.level.input) { G.inputRemaining = G.level.input.duration; }
  }
  tickUpdate(); render();
}

function captureLayout() {
  retractAllPistons();
  let layout = [];
  for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) {
    let c = G.grid[x][y];
    if (c.type === T.EMPTY || c.type === T.INPUT || c.type === T.OUTPUT) continue;
    let item = { x, y, type: c.type, direction: c.direction, delay: c.delay, mode: c.mode };
    if (c.type === T.LEVER) item.leverOn = c.leverOn;
    layout.push(item);
  }
  G.levelLayouts[G.level.freeMode ? 'free' : G.levelIdx] = layout;
}
function restoreLayout(idx) {
  let layout = G.levelLayouts[idx];
  if (!layout || layout.length === 0) return;
  for (let item of layout) {
    if (item.x < 0 || item.x >= G.cols || item.y < 0 || item.y >= G.rows) continue;
    let c = G.grid[item.x][item.y];
    if (c.type === T.INPUT || c.type === T.OUTPUT) continue;
    c.type = item.type; c.direction = item.direction || 0; c.delay = item.delay || 1; c.mode = item.mode || 'compare';
    c.outputActive=false; c.prevInput=false; c.eventQueue=[]; c.extinguished=false; c.pulsing=false; c.pulseTimer=0; c.prevFrontSignal=0; c.outputStrength=0; c.cooldown=0; c.extended=false; c.pushedBlockType=null; c.pistonCooldown=0;
    c.buttonActive=false; c.buttonTimer=0; c.leverOn=item.leverOn||false;
    G.compCounts[item.type] = (G.compCounts[item.type] || 0) + 1;
  }
}

function loadLevel(idx) {
  if (idx < 0 || idx >= LEVELS.length) return;
  // 联机模式跳过关卡锁定
  if (!MP.syncing) {
    if (idx > 0 && !G.completed.has(idx - 1) && !G.completed.has(idx)) { showTip('请先完成前一关！'); return; }
  }
  if (G.level !== null) captureLayout();
  G.levelIdx = idx; G.level = LEVELS[idx]; G.selectedComp = null;
  initGrid(G.level); restoreLayout(idx);
  buildComponentBar(); buildLevelSelector(); updateInfoBar();
  document.getElementById('hint').textContent = '提示: ' + (G.level.hint || '');
  document.getElementById('hint').style.color = '#888';
  pauseSimulation(); resizeCanvas(); render();
  let newComps = getNewComponents(idx);
  if (newComps.length > 0) showIntroModal(newComps);
  if (LEVELS[idx].logic && !introSeen.has('logic_' + LEVELS[idx].logic)) showLogicIntro(LEVELS[idx].logic);
  // 同步关卡切换
  if (!MP.syncing) sendToPeer({ t: 'level', idx: idx });
}

function getNewComponents(idx) {
  let currentComps = new Set(LEVELS[idx].components);
  let prevComps = new Set();
  for (let i = 0; i < idx; i++) for (let c of LEVELS[i].components) prevComps.add(c);
  let newOnes = [];
  for (let c of currentComps) if (!prevComps.has(c) && COMP_INTROS[c]) newOnes.push(c);
  return newOnes;
}

let introQueue = [];
let introSeen = new Set(JSON.parse(localStorage.getItem('rs_intro_seen') || '[]'));
function showIntroModal(comps) {
  let toShow = comps.filter(c => !introSeen.has(c));
  if (toShow.length === 0) return;
  introQueue = toShow.slice(); showNextIntro();
}
function showNextIntro() {
  if (introQueue.length === 0) { document.getElementById('introModal').classList.remove('show'); return; }
  let comp = introQueue.shift();
  let info = COMP_INTROS[comp];
  if (!info) { showNextIntro(); return; }
  document.getElementById('introTitle').textContent = info.title;
  document.getElementById('introDesc').innerHTML = info.desc;
  document.getElementById('introTip').textContent = info.tip;
  let cv = document.getElementById('introIcon');
  let ictx = cv.getContext('2d');
  ictx.clearRect(0, 0, 48, 48);
  drawComponentIcon(ictx, comp, 0, 48);
  let remaining = introQueue.length;
  document.getElementById('introSubtitle').textContent = remaining > 0 ? '新元件解锁 (还有更多)' : '新元件解锁';
  document.getElementById('introModal').classList.add('show');
  introSeen.add(comp);
  localStorage.setItem('rs_intro_seen', JSON.stringify([...introSeen]));
}
document.getElementById('introStartBtn').onclick = () => {
  if (introQueue.length > 0) showNextIntro();
  else document.getElementById('introModal').classList.remove('show');
};

const LOGIC_INTROS = {
  not: { title: '非门 (NOT)', desc: '<b>非门</b>是逻辑反相器：输入有信号时输出<b>无</b>信号，输入无信号时输出<b>有</b>信号。<br><br>在红石中，<b>红石火把</b>天然就是非门：背面有信号时火把熄灭(输出0)，背面无信号时火把点亮(输出15)。<br><br>本关利用火把的默认点亮特性：火把在输入信号到达前就输出信号，输入信号到达后火把熄灭，从而制造一个短脉冲输出。', tip: '关键元件：红石火把。火把背面接输入路径，火把头朝输出方向' },
  or: { title: '或门 (OR)', desc: '<b>或门</b>：任一输入有信号时，输出就有信号。只有所有输入都无信号时，输出才无信号。<br><br>在红石中，或门可以用<b>两路红石粉汇合</b>实现：输入A和输入B各自铺路到同一条线上，汇合处任意一路有信号就能继续传播。<br><br>本关输入A和B有不同延迟，两路信号的时间段部分重叠。输出持续时间 = 两路信号的合并时间(并集)。', tip: '关键：两路红石粉路径在某个点汇合，汇合后继续连到输出' },
  and: { title: '与门 (AND)', desc: '<b>与门</b>：只有所有输入都有信号时，输出才有信号。任一输入无信号时，输出无信号。<br><br>在红石中，与门可以用<b>比较器减法模式 + 火把反相</b>实现：<br>1. 信号A接比较器<b>主输入</b>(背面)<br>2. 信号B经<b>红石火把反相</b>后接比较器<b>侧输入</b><br>3. 输出 = A - (NOT B)<br><br>当B有信号时，NOT B = 0，输出 = A (有信号)<br>当B无信号时，NOT B = 15，输出 = A - 15 = 0 (无信号)<br>所以只有A和B同时有信号时才有输出！', tip: '关键元件：比较器(减法模式) + 红石火把。A接背面，B经火把反相后接侧面' },
};

function showLogicIntro(logicType) {
  let info = LOGIC_INTROS[logicType];
  if (!info) return;
  document.getElementById('introTitle').textContent = info.title;
  document.getElementById('introDesc').innerHTML = info.desc;
  document.getElementById('introTip').textContent = info.tip;
  document.getElementById('introSubtitle').textContent = '逻辑门新概念';
  let cv = document.getElementById('introIcon');
  let ictx = cv.getContext('2d');
  ictx.clearRect(0, 0, 48, 48);
  ictx.strokeStyle = '#e94560'; ictx.lineWidth = 2; ictx.fillStyle = 'rgba(233,69,96,0.1)';
  if (logicType === 'not') { ictx.beginPath(); ictx.moveTo(8,12); ictx.lineTo(8,36); ictx.lineTo(32,24); ictx.closePath(); ictx.fill(); ictx.stroke(); ictx.beginPath(); ictx.arc(38,24,4,0,Math.PI*2); ictx.stroke(); }
  else if (logicType === 'or') { ictx.beginPath(); ictx.moveTo(8,10); ictx.quadraticCurveTo(20,24,8,38); ictx.quadraticCurveTo(24,38,38,24); ictx.quadraticCurveTo(24,10,8,10); ictx.fill(); ictx.stroke(); }
  else if (logicType === 'and') { ictx.beginPath(); ictx.moveTo(8,10); ictx.lineTo(24,10); ictx.quadraticCurveTo(40,10,40,24); ictx.quadraticCurveTo(40,38,24,38); ictx.lineTo(8,38); ictx.closePath(); ictx.fill(); ictx.stroke(); }
  introQueue = [];
  document.getElementById('introModal').classList.add('show');
  introSeen.add('logic_' + logicType);
  localStorage.setItem('rs_intro_seen', JSON.stringify([...introSeen]));
}

function buildLevelSelector() {
  let el = document.getElementById('levelSelector'); el.innerHTML = '';
  for (let i = 0; i < LEVELS.length; i++) {
    let btn = document.createElement('button');
    btn.className = 'level-btn'; btn.textContent = i + 1;
    if (i === G.levelIdx) btn.classList.add('current');
    if (G.completed.has(i)) btn.classList.add('completed');
    if (i > 0 && !G.completed.has(i - 1) && !G.completed.has(i)) btn.classList.add('locked');
    btn.onclick = () => loadLevel(i);
    el.appendChild(btn);
  }
}

function buildComponentBar() {
  let bar = document.getElementById('componentBar');
  bar.querySelectorAll('.comp-btn').forEach(b => b.remove());
  for (let comp of G.level.components) {
    let btn = document.createElement('div'); btn.className = 'comp-btn'; btn.dataset.comp = comp;
    let cv = document.createElement('canvas'); cv.width = 36; cv.height = 36;
    drawComponentIcon(cv.getContext('2d'), comp, 0, 36);
    btn.appendChild(cv);
    let name = document.createElement('div'); name.className = 'name'; name.textContent = COMP_NAMES[comp] || comp;
    btn.appendChild(name);
    if (G.level.limits && G.level.limits[comp]) {
      let count = document.createElement('div'); count.className = 'count'; count.id = 'count-' + comp; count.textContent = G.level.limits[comp];
      btn.appendChild(count);
    }
    btn.onclick = () => {
      G.selectedComp = comp;
      if (G.level.limits && G.level.limits[comp]) { let used = G.compCounts[comp] || 0; if (used >= G.level.limits[comp]) { showTip(COMP_NAMES[comp] + '已达上限 ' + G.level.limits[comp]); return; } }
      document.querySelectorAll('.comp-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
    };
    bar.appendChild(btn);
  }
  let eraseBtn = document.createElement('div'); eraseBtn.className = 'comp-btn'; eraseBtn.dataset.comp = 'erase';
  let ecv = document.createElement('canvas'); ecv.width = 36; ecv.height = 36;
  let ectx = ecv.getContext('2d'); ectx.strokeStyle = '#e94560'; ectx.lineWidth = 3;
  ectx.beginPath(); ectx.moveTo(8,8); ectx.lineTo(28,28); ectx.moveTo(28,8); ectx.lineTo(8,28); ectx.stroke();
  eraseBtn.appendChild(ecv);
  let ename = document.createElement('div'); ename.className = 'name'; ename.textContent = '橡皮擦';
  eraseBtn.appendChild(ename);
  eraseBtn.onclick = () => { G.selectedComp = 'erase'; document.querySelectorAll('.comp-btn').forEach(b => b.classList.remove('selected')); eraseBtn.classList.add('selected'); };
  bar.appendChild(eraseBtn);
}

function updateInfoBar() {
  let lv = G.level;
  if (lv.freeMode) {
    document.getElementById('levelDesc').textContent = lv.name + ' — ' + lv.desc;
    document.getElementById('targetDelay').textContent = '自由';
    document.getElementById('targetDuration').textContent = '自由';
    document.getElementById('currentDelay').textContent = '-';
    document.getElementById('currentDuration').textContent = '-';
    document.getElementById('targetStrengthInfo').style.display = 'none';
    document.getElementById('currentStrengthInfo').style.display = 'none';
    return;
  }
  document.getElementById('levelDesc').textContent = '关卡' + (G.levelIdx+1) + ': ' + lv.name + ' — ' + lv.desc;
  document.getElementById('targetDelay').textContent = lv.target.delay + ' tick';
  document.getElementById('targetDuration').textContent = lv.target.duration + ' tick';
  let cdEl = document.getElementById('currentDelay'); let cuEl = document.getElementById('currentDuration');
  cdEl.textContent = G.outputDelay >= 0 ? G.outputDelay + ' tick' : '-';
  cuEl.textContent = G.outputDuration > 0 ? G.outputDuration + ' tick' : (G.outputPowered ? '...' : '-');
  cdEl.className = (G.outputDelay === lv.target.delay) ? 'matched' : 'current';
  cuEl.className = (G.outputDuration === lv.target.duration) ? 'matched' : 'current';
  // 信号强度（可选）
  let tsInfo = document.getElementById('targetStrengthInfo');
  let csInfo = document.getElementById('currentStrengthInfo');
  if (lv.target.strength !== undefined) {
    tsInfo.style.display = ''; csInfo.style.display = '';
    document.getElementById('targetStrength').textContent = lv.target.strength;
    let csEl = document.getElementById('currentStrength');
    csEl.textContent = G.outputMaxStrength > 0 ? G.outputMaxStrength : (G.outputPowered ? '...' : '-');
    csEl.className = (G.outputMaxStrength === lv.target.strength && G.outputMaxStrength > 0) ? 'matched' : 'current';
  } else {
    tsInfo.style.display = 'none'; csInfo.style.display = 'none';
  }
  document.getElementById('tickDisplay').textContent = G.tick;
  if (G.level.limits) { for (let comp in G.level.limits) { let el = document.getElementById('count-' + comp); if (el) { let used = G.compCounts[comp] || 0; el.textContent = G.level.limits[comp] - used; el.style.color = used >= G.level.limits[comp] ? '#e94560' : '#4ecca3'; } } }
}

const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
function resizeCanvas() { canvas.width = G.cols * CELL; canvas.height = G.rows * CELL; }
function render() {
  let w = canvas.width, h = canvas.height;
  ctx.fillStyle = '#0d1117'; ctx.fillRect(0, 0, w, h);
  // 联机模式：左右区域着色
  if (MP.enabled && MP.connected) {
    ctx.fillStyle = 'rgba(233,69,96,0.05)'; ctx.fillRect(0, 0, MP.boundary * CELL, h);
    ctx.fillStyle = 'rgba(78,204,163,0.05)'; ctx.fillRect(MP.boundary * CELL, 0, w - MP.boundary * CELL, h);
  }
  ctx.strokeStyle = '#1a2333'; ctx.lineWidth = 1;
  for (let x = 0; x <= G.cols; x++) { ctx.beginPath(); ctx.moveTo(x*CELL,0); ctx.lineTo(x*CELL,h); ctx.stroke(); }
  for (let y = 0; y <= G.rows; y++) { ctx.beginPath(); ctx.moveTo(0,y*CELL); ctx.lineTo(w,y*CELL); ctx.stroke(); }
  // 联机模式：分界线
  if (MP.enabled && MP.connected) {
    ctx.strokeStyle = '#ffd700'; ctx.lineWidth = 2; ctx.setLineDash([6,4]);
    ctx.beginPath(); ctx.moveTo(MP.boundary * CELL, 0); ctx.lineTo(MP.boundary * CELL, h); ctx.stroke();
    ctx.setLineDash([]);
    // 区域标签
    ctx.font = 'bold 11px sans-serif'; ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    ctx.fillStyle = MP.myZone === 'left' ? '#e94560' : 'rgba(233,69,96,0.4)';
    ctx.fillText('P1 左区' + (MP.myZone === 'left' ? ' (你)' : ''), 4, 2);
    ctx.textAlign = 'right';
    ctx.fillStyle = MP.myZone === 'right' ? '#4ecca3' : 'rgba(78,204,163,0.4)';
    ctx.fillText('P2 右区' + (MP.myZone === 'right' ? ' (你)' : ''), w - 4, 2);
  }
  if (G.hoverX >= 0 && G.hoverY >= 0) {
    let hoverColor = (MP.enabled && MP.connected && !isInMyZone(G.hoverX)) ? 'rgba(255,215,0,0.15)' : 'rgba(233,69,96,0.12)';
    ctx.fillStyle = hoverColor; ctx.fillRect(G.hoverX*CELL, G.hoverY*CELL, CELL, CELL);
  }
  for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) { drawCell(G.grid[x][y], x, y, G.signals[x][y] || 0); }
  if (G.hoverX >= 0 && G.hoverY >= 0 && G.selectedComp && G.selectedComp !== 'erase') {
    let cell = G.grid[G.hoverX][G.hoverY];
    if (cell.type === T.EMPTY) { ctx.globalAlpha = 0.4; drawCell({type:G.selectedComp,direction:G.selectedRotate,delay:1,mode:'compare',outputActive:false,extinguished:false,pulsing:false}, G.hoverX, G.hoverY, 0); ctx.globalAlpha = 1; }
  }
  // 联机模式：队友光标
  if (MP.enabled && MP.connected && MP.remoteCursor.x >= 0 && MP.remoteCursor.y >= 0) {
    let rx = MP.remoteCursor.x * CELL, ry = MP.remoteCursor.y * CELL;
    ctx.strokeStyle = '#ffd700'; ctx.lineWidth = 2; ctx.setLineDash([4,2]);
    ctx.strokeRect(rx + 1, ry + 1, CELL - 2, CELL - 2);
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(255,215,0,0.1)'; ctx.fillRect(rx, ry, CELL, CELL);
    ctx.fillStyle = '#ffd700'; ctx.font = 'bold 9px sans-serif'; ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    ctx.fillText('队友', rx + 2, ry + 2);
  }
  if (G.running) {
    for (let x = 0; x < G.cols; x++) for (let y = 0; y < G.rows; y++) {
      let sig = G.signals[x][y] || 0;
      if (sig > 0 && G.grid[x][y].type === T.DUST) {
        let phase = (G.animFrame * 0.15 + x * 0.3 + y * 0.2) % 1;
        let alpha = (1 - phase) * 0.6 * (sig / 15);
        ctx.fillStyle = 'rgba(255,100,100,' + alpha + ')';
        let r = 4 + phase * 8;
        ctx.beginPath(); ctx.arc(x*CELL+CELL/2, y*CELL+CELL/2, r, 0, Math.PI*2); ctx.fill();
      }
    }
  }
  maybeAnimatePistons();
}

function drawCell(cell, x, y, signal) {
  let px = x * CELL, py = y * CELL, cx = px + CELL/2, cy = py + CELL/2;
  switch (cell.type) {
    case T.EMPTY: break;
    case T.INPUT: {
      let isActive = G.inputActive, label = 'IN';
      if (G.inputStates.length > 0) { for (let i = 0; i < G.inputStates.length; i++) { if (G.inputStates[i].x === x && G.inputStates[i].y === y) { isActive = G.inputStates[i].active; label = i === 0 ? 'A' : 'B'; break; } } }
      ctx.fillStyle = isActive ? '#4ecca3' : '#2a5a4a';
      ctx.beginPath(); ctx.arc(cx, cy, CELL*0.32, 0, Math.PI*2); ctx.fill();
      if (isActive) { let g = ctx.createRadialGradient(cx,cy,0,cx,cy,CELL*0.5); g.addColorStop(0,'rgba(78,204,163,0.4)'); g.addColorStop(1,'rgba(78,204,163,0)'); ctx.fillStyle = g; ctx.fillRect(px,py,CELL,CELL); }
      ctx.fillStyle = '#fff'; ctx.font = 'bold 10px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(label, cx, cy);
      break;
    }
    case T.OUTPUT:
      ctx.fillStyle = G.outputPowered ? '#3498db' : '#1a4a6a';
      ctx.beginPath(); ctx.arc(cx, cy, CELL*0.32, 0, Math.PI*2); ctx.fill();
      if (G.outputPowered) { let g = ctx.createRadialGradient(cx,cy,0,cx,cy,CELL*0.5); g.addColorStop(0,'rgba(52,152,219,0.4)'); g.addColorStop(1,'rgba(52,152,219,0)'); ctx.fillStyle = g; ctx.fillRect(px,py,CELL,CELL); }
      ctx.fillStyle = '#fff'; ctx.font = 'bold 10px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('OUT', cx, cy);
      break;
    case T.DUST: drawDust(px, py, x, y, signal); break;
    case T.BLOCK: drawBlock(px, py); break;
    case T.TORCH: drawTorch(px, py, cell); break;
    case T.REPEATER: drawRepeater(px, py, cell); break;
    case T.COMPARATOR: drawComparator(px, py, cell); break;
    case T.OBSERVER: drawObserver(px, py, cell); break;
    case T.STONE: drawStone(px, py, signal); break;
    case T.PISTON: drawPiston(px, py, cell); break;
    case T.LAMP: drawLamp(px, py, x, y); break;
    case T.BUTTON: drawButton(px, py, cell); break;
    case T.LEVER: drawLever(px, py, cell); break;
  }
}

function drawDust(px, py, x, y, signal) {
  let cx = px + CELL/2, cy = py + CELL/2;
  let baseColor = signal > 0 ? '#ff3b3b' : '#8b2020';
  let glowColor = signal > 0 ? '#ff6b6b' : '#5b1010';
  // 检查四个方向是否有可连接的邻居
  let conns = [false, false, false, false];
  let hasConn = false;
  for (let i = 0; i < 4; i++) {
    let d = DIRECTIONS[i];
    let nx = x + d.dx, ny = y + d.dy;
    if (nx < 0 || nx >= G.cols || ny < 0 || ny >= G.rows) continue;
    let n = G.grid[nx][ny];
    if (n.type === T.OUTPUT || isConductive(n)) {
      if (isDirectionalSource(n)) {
        let o = getOutputDir(n);
        if (nx + o.dx === x && ny + o.dy === y) { conns[i] = true; hasConn = true; }
      } else { conns[i] = true; hasConn = true; }
    }
  }
  // 无连接时画小圆点
  if (!hasConn) {
    ctx.fillStyle = glowColor; ctx.beginPath(); ctx.arc(cx, cy, 5, 0, Math.PI*2); ctx.fill();
  } else {
    ctx.strokeStyle = baseColor; ctx.lineWidth = 4; ctx.lineCap = 'round';
    for (let i = 0; i < 4; i++) {
      if (!conns[i]) continue;
      let d = DIRECTIONS[i];
      ctx.beginPath(); ctx.moveTo(cx, cy);
      if (d.dx > 0) ctx.lineTo(px + CELL, cy);
      else if (d.dx < 0) ctx.lineTo(px, cy);
      else if (d.dy > 0) ctx.lineTo(cx, py + CELL);
      else ctx.lineTo(cx, py);
      ctx.stroke();
    }
    ctx.fillStyle = glowColor; ctx.beginPath(); ctx.arc(cx, cy, 4, 0, Math.PI*2); ctx.fill();
  }
  if (signal > 0) {
    ctx.shadowColor = '#ff3b3b'; ctx.shadowBlur = 8;
    ctx.strokeStyle = '#ff6b6b'; ctx.lineWidth = 2;
    if (hasConn) {
      for (let i = 0; i < 4; i++) {
        if (!conns[i]) continue;
        let d = DIRECTIONS[i];
        ctx.beginPath(); ctx.moveTo(cx, cy);
        if (d.dx > 0) ctx.lineTo(px + CELL, cy);
        else if (d.dx < 0) ctx.lineTo(px, cy);
        else if (d.dy > 0) ctx.lineTo(cx, py + CELL);
        else ctx.lineTo(cx, py);
        ctx.stroke();
      }
    }
    ctx.shadowBlur = 0;
    ctx.fillStyle = 'rgba(0,0,0,0.7)'; ctx.fillRect(px+1, py+1, 14, 12);
    ctx.fillStyle = signal > 1 ? '#ffdd44' : '#ff6666';
    ctx.font = 'bold 10px monospace'; ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    ctx.fillText(signal, px+3, py+2);
  }
}
function drawBlock(px, py) {
  ctx.fillStyle = '#8b0000'; ctx.fillRect(px+4, py+4, CELL-8, CELL-8);
  ctx.strokeStyle = '#ff4444'; ctx.lineWidth = 2; ctx.strokeRect(px+4, py+4, CELL-8, CELL-8);
  ctx.fillStyle = '#aa1010'; ctx.fillRect(px+8, py+8, CELL-16, CELL-16);
  ctx.strokeStyle = '#660000'; ctx.lineWidth = 1; ctx.strokeRect(px+8, py+8, CELL-16, CELL-16);
}
function drawTorch(px, py, cell) {
  let cx = px+CELL/2, cy = py+CELL/2, dir = DIRECTIONS[cell.direction];
  ctx.strokeStyle = '#666'; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx-dir.dx*8, cy-dir.dy*8); ctx.stroke();
  let tc = cell.extinguished ? '#444' : '#ff3333';
  let gc = cell.extinguished ? '#222' : '#ff6666';
  ctx.fillStyle = tc; ctx.beginPath(); ctx.arc(cx+dir.dx*6, cy+dir.dy*6, 6, 0, Math.PI*2); ctx.fill();
  if (!cell.extinguished) { ctx.shadowColor='#ff3333'; ctx.shadowBlur=10; ctx.fillStyle=gc; ctx.beginPath(); ctx.arc(cx+dir.dx*6, cy+dir.dy*6, 4, 0, Math.PI*2); ctx.fill(); ctx.shadowBlur=0; }
}
function drawRepeater(px, py, cell) {
  let cx=px+CELL/2, cy=py+CELL/2, dir=DIRECTIONS[cell.direction];
  ctx.fillStyle='#3a3a3a'; ctx.fillRect(px+4,py+4,CELL-8,CELL-8);
  ctx.strokeStyle='#555'; ctx.lineWidth=1; ctx.strokeRect(px+4,py+4,CELL-8,CELL-8);
  let ax=cx+dir.dx*12, ay=cy+dir.dy*12, bx=cx-dir.dx*8, by=cy-dir.dy*8;
  ctx.strokeStyle=cell.outputActive?'#ff3b3b':'#884444'; ctx.lineWidth=2;
  ctx.beginPath(); ctx.moveTo(bx,by); ctx.lineTo(ax,ay); ctx.stroke();
  let perp={dx:-dir.dy,dy:dir.dx};
  ctx.beginPath(); ctx.moveTo(ax,ay); ctx.lineTo(ax-dir.dx*6+perp.dx*4, ay-dir.dy*6+perp.dy*4); ctx.moveTo(ax,ay); ctx.lineTo(ax-dir.dx*6-perp.dx*4, ay-dir.dy*6-perp.dy*4); ctx.stroke();
  ctx.fillStyle=cell.outputActive?'#ff6b6b':'#aa4444';
  for(let i=0;i<cell.delay;i++){let offX=-dir.dy*(10+i*5),offY=dir.dx*(10+i*5);let bX=cx+dir.dx*4+offX,bY=cy+dir.dy*4+offY;ctx.beginPath();ctx.moveTo(bX,bY);ctx.lineTo(bX-3,bY+4);ctx.lineTo(bX+3,bY+4);ctx.closePath();ctx.fill();}
  if(cell.outputActive){ctx.shadowColor='#ff3b3b';ctx.shadowBlur=8;ctx.strokeStyle='#ff3b3b';ctx.lineWidth=2;ctx.strokeRect(px+4,py+4,CELL-8,CELL-8);ctx.shadowBlur=0;}
}
function drawComparator(px, py, cell) {
  let cx=px+CELL/2, cy=py+CELL/2, dir=DIRECTIONS[cell.direction];
  ctx.fillStyle='#3a3a3a'; ctx.fillRect(px+4,py+4,CELL-8,CELL-8);
  ctx.strokeStyle='#555'; ctx.lineWidth=1; ctx.strokeRect(px+4,py+4,CELL-8,CELL-8);
  let ftX=cx+dir.dx*10, ftY=cy+dir.dy*10;
  ctx.fillStyle=cell.mode==='compare'?'#ff3b3b':'#444'; if(cell.mode==='subtract')ctx.fillStyle='#444';
  ctx.beginPath(); ctx.arc(ftX,ftY,4,0,Math.PI*2); ctx.fill();
  let perp={dx:-dir.dy,dy:dir.dx};
  for(let s of[-1,1]){let tx=cx-dir.dx*10+perp.dx*s*6,ty=cy-dir.dy*10+perp.dy*s*6;ctx.fillStyle='#aa3333';ctx.beginPath();ctx.arc(tx,ty,3,0,Math.PI*2);ctx.fill();}
  ctx.strokeStyle=cell.outputActive?'#ff3b3b':'#884444'; ctx.lineWidth=2;
  ctx.beginPath(); let tipX=cx+dir.dx*14,tipY=cy+dir.dy*14; let baseX=cx-dir.dx*4,baseY=cy-dir.dy*4;
  ctx.moveTo(baseX+perp.dx*6,baseY+perp.dy*6); ctx.lineTo(tipX,tipY); ctx.lineTo(baseX-perp.dx*6,baseY-perp.dy*6); ctx.stroke();
  if(cell.outputActive){ctx.shadowColor='#ff3b3b';ctx.shadowBlur=8;ctx.strokeStyle='#ff3b3b';ctx.lineWidth=2;ctx.strokeRect(px+4,py+4,CELL-8,CELL-8);ctx.shadowBlur=0;}
}
function drawObserver(px, py, cell) {
  let cx=px+CELL/2, cy=py+CELL/2, dir=DIRECTIONS[cell.direction];
  ctx.fillStyle='#2a2a3a'; ctx.fillRect(px+4,py+4,CELL-8,CELL-8);
  ctx.strokeStyle='#555'; ctx.lineWidth=1; ctx.strokeRect(px+4,py+4,CELL-8,CELL-8);
  let faceX=cx+dir.dx*10, faceY=cy+dir.dy*10;
  ctx.fillStyle='#555'; ctx.fillRect(faceX-5,faceY-5,10,10);
  ctx.fillStyle=cell.pulsing?'#ff3b3b':'#999';
  let perp={dx:-dir.dy,dy:dir.dx};
  ctx.beginPath(); ctx.arc(faceX+perp.dx*2,faceY+perp.dy*2,1.5,0,Math.PI*2); ctx.arc(faceX-perp.dx*2,faceY-perp.dy*2,1.5,0,Math.PI*2); ctx.fill();
  if(cell.pulsing){ctx.shadowColor='#ff3b3b';ctx.shadowBlur=8;let oX=cx-dir.dx*14,oY=cy-dir.dy*14;ctx.fillStyle='#ff3b3b';ctx.beginPath();ctx.arc(oX,oY,4,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;}
}
function drawStone(px, py, signal) {
  let powered = signal > 0;
  ctx.fillStyle = powered ? '#7a7a8a' : '#5a5a6a';
  ctx.fillRect(px+4, py+4, CELL-8, CELL-8);
  ctx.strokeStyle = powered ? '#aaaabb' : '#666677';
  ctx.lineWidth = 2; ctx.strokeRect(px+4, py+4, CELL-8, CELL-8);
  ctx.fillStyle = powered ? '#6a6a7a' : '#4a4a5a';
  ctx.fillRect(px+8, py+8, CELL-16, CELL-16);
  ctx.strokeStyle = '#3a3a4a'; ctx.lineWidth = 1;
  ctx.strokeRect(px+8, py+8, CELL-16, CELL-16);
  if (powered) { ctx.shadowColor='#aaaabb'; ctx.shadowBlur=6; ctx.strokeStyle='#bbbccc'; ctx.lineWidth=1; ctx.strokeRect(px+4, py+4, CELL-8, CELL-8); ctx.shadowBlur=0; }
}
function drawPiston(px, py, cell) {
  let cx = px+CELL/2, cy = py+CELL/2, dir = DIRECTIONS[cell.direction];
  let t = cell.pistonAnim || 0; // 0=缩回, 1=伸出
  // 底座
  ctx.fillStyle = '#3a3a4a'; ctx.fillRect(px+4, py+4, CELL-8, CELL-8);
  ctx.strokeStyle = '#6a6a7a'; ctx.lineWidth = 2; ctx.strokeRect(px+4, py+4, CELL-8, CELL-8);
  // 内部活塞体
  ctx.fillStyle = '#2a2a3a';
  let inOffX = -dir.dx*3, inOffY = -dir.dy*3;
  ctx.fillRect(px+8+inOffX, py+8+inOffY, CELL-16, CELL-16);
  ctx.strokeStyle = '#4a4a5a'; ctx.lineWidth = 1; ctx.strokeRect(px+8+inOffX, py+8+inOffY, CELL-16, CELL-16);
  // 活塞头位置（动画插值：缩回时4px，伸出时10px）
  let headDist = 4 + t * 6;
  let headX = cx + dir.dx * headDist, headY = cy + dir.dy * headDist;
  // 活塞头颜色（插值：棕色→绿色）
  let hR = Math.round(138+(74-138)*t), hG = Math.round(106+(138-106)*t), hB = Math.round(58+(74-58)*t);
  let gR = Math.round(187+(122-187)*t), gG = Math.round(154+(202-154)*t), gB = Math.round(90+(122-90)*t);
  ctx.fillStyle = `rgb(${hR},${hG},${hB})`; ctx.fillRect(headX-6, headY-6, 12, 12);
  ctx.strokeStyle = `rgb(${gR},${gG},${gB})`; ctx.lineWidth = 1; ctx.strokeRect(headX-6, headY-6, 12, 12);
  // 活塞臂（动画时显示）
  if (t > 0.05) {
    ctx.strokeStyle = '#bbb'; ctx.lineWidth = 4;
    ctx.beginPath(); ctx.moveTo(cx - dir.dx*2, cy - dir.dy*2); ctx.lineTo(headX, headY); ctx.stroke();
  }
  // 伸出状态底座发光
  if (t > 0.5) {
    ctx.shadowColor='#7aca7a'; ctx.shadowBlur=6; ctx.strokeStyle='#9adb9a'; ctx.lineWidth=1;
    ctx.strokeRect(px+4, py+4, CELL-8, CELL-8); ctx.shadowBlur=0;
  }
  // 粘性球（绿色小圆点表示粘性活塞）
  ctx.fillStyle = '#5ace5a'; ctx.beginPath(); ctx.arc(headX, headY, 2.5, 0, Math.PI*2); ctx.fill();
}

function drawLamp(px, py, gx, gy) {
  let cx = px + CELL/2, cy = py + CELL/2;
  let powered = false;
  for (let i = 0; i < 4; i++) {
    let d = DIRECTIONS[i]; let nx = gx + d.dx, ny = gy + d.dy;
    if (nx < 0 || nx >= G.cols || ny < 0 || ny >= G.rows) continue;
    if (G.signals[nx][ny] > 0) { powered = true; break; }
  }
  ctx.fillStyle = powered ? '#5a3a1a' : '#2a2a3a';
  ctx.fillRect(px+4, py+4, CELL-8, CELL-8);
  ctx.strokeStyle = powered ? '#8a6a3a' : '#4a4a5a'; ctx.lineWidth = 2;
  ctx.strokeRect(px+4, py+4, CELL-8, CELL-8);
  let r = CELL * 0.22;
  if (powered) {
    let g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r*1.5);
    g.addColorStop(0, '#ffeb3b'); g.addColorStop(0.5, '#ff9800'); g.addColorStop(1, 'rgba(255,152,0,0)');
    ctx.fillStyle = g; ctx.fillRect(px, py, CELL, CELL);
    ctx.fillStyle = '#ffeb3b'; ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI*2); ctx.fill();
    ctx.shadowColor = '#ff9800'; ctx.shadowBlur = 10;
    ctx.strokeStyle = '#ffd700'; ctx.lineWidth = 1; ctx.strokeRect(px+4, py+4, CELL-8, CELL-8);
    ctx.shadowBlur = 0;
  } else {
    ctx.fillStyle = '#1a1a2a'; ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI*2); ctx.fill();
    ctx.strokeStyle = '#3a3a4a'; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI*2); ctx.stroke();
  }
}

function drawButton(px, py, cell) {
  let cx = px + CELL/2, cy = py + CELL/2;
  let active = cell.buttonActive;
  ctx.fillStyle = '#3a3a4a'; ctx.fillRect(px+5, py+5, CELL-10, CELL-10);
  ctx.strokeStyle = '#5a5a6a'; ctx.lineWidth = 2; ctx.strokeRect(px+5, py+5, CELL-10, CELL-10);
  let btnR = CELL * 0.2;
  let offsetY = active ? 2 : 0;
  if (active) {
    let g = ctx.createRadialGradient(cx, cy+offsetY, 0, cx, cy+offsetY, btnR*1.5);
    g.addColorStop(0, '#ff6b6b'); g.addColorStop(0.5, '#ff3b3b'); g.addColorStop(1, 'rgba(255,59,59,0)');
    ctx.fillStyle = g; ctx.fillRect(px, py, CELL, CELL);
    ctx.fillStyle = '#ff3b3b'; ctx.beginPath(); ctx.arc(cx, cy+offsetY, btnR, 0, Math.PI*2); ctx.fill();
    ctx.shadowColor = '#ff3b3b'; ctx.shadowBlur = 8;
    ctx.strokeStyle = '#ff6b6b'; ctx.lineWidth = 1; ctx.strokeRect(px+5, py+5, CELL-10, CELL-10);
    ctx.shadowBlur = 0;
  } else {
    ctx.fillStyle = '#8b2020'; ctx.beginPath(); ctx.arc(cx, cy+offsetY, btnR, 0, Math.PI*2); ctx.fill();
    ctx.strokeStyle = '#5b1010'; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(cx, cy+offsetY, btnR, 0, Math.PI*2); ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.15)'; ctx.beginPath(); ctx.arc(cx-btnR*0.3, cy+offsetY-btnR*0.3, btnR*0.4, 0, Math.PI*2); ctx.fill();
  }
}

function drawLever(px, py, cell) {
  let cx = px + CELL/2, cy = py + CELL/2;
  let on = cell.leverOn;
  ctx.fillStyle = '#3a3a4a'; ctx.fillRect(px+5, py+5, CELL-10, CELL-10);
  ctx.strokeStyle = '#5a5a6a'; ctx.lineWidth = 2; ctx.strokeRect(px+5, py+5, CELL-10, CELL-10);
  ctx.fillStyle = '#2a2a3a'; ctx.beginPath(); ctx.arc(cx, cy+CELL*0.15, CELL*0.1, 0, Math.PI*2); ctx.fill();
  ctx.strokeStyle = '#4a4a5a'; ctx.lineWidth = 1; ctx.stroke();
  let handleLen = CELL * 0.22;
  let angle = on ? -Math.PI/3 : Math.PI/3;
  let hx = cx + Math.cos(angle) * handleLen;
  let hy = cy + CELL*0.15 + Math.sin(angle) * handleLen;
  if (on) { ctx.shadowColor = '#ff3b3b'; ctx.shadowBlur = 6; }
  ctx.strokeStyle = on ? '#ff3b3b' : '#888'; ctx.lineWidth = 3; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(cx, cy+CELL*0.15); ctx.lineTo(hx, hy); ctx.stroke();
  ctx.shadowBlur = 0;
  ctx.fillStyle = on ? '#ff6b6b' : '#aaa'; ctx.beginPath(); ctx.arc(hx, hy, 3, 0, Math.PI*2); ctx.fill();
  if (on) { ctx.fillStyle = 'rgba(255,59,59,0.15)'; ctx.fillRect(px, py, CELL, CELL); }
}

function drawComponentIcon(ctx, type, direction, size) {
  ctx.clearRect(0, 0, size, size);
  let cx=size/2, cy=size/2;
  switch (type) {
    case 'dust':
      ctx.strokeStyle='#8b2020'; ctx.lineWidth=2;
      ctx.beginPath(); ctx.moveTo(4,cy); ctx.lineTo(size-4,cy); ctx.moveTo(cx,4); ctx.lineTo(cx,size-4); ctx.stroke();
      ctx.fillStyle='#5b1010'; ctx.beginPath(); ctx.arc(cx,cy,3,0,Math.PI*2); ctx.fill(); break;
    case 'block':
      ctx.fillStyle='#8b0000'; ctx.fillRect(4,4,size-8,size-8);
      ctx.strokeStyle='#ff4444'; ctx.lineWidth=2; ctx.strokeRect(4,4,size-8,size-8);
      ctx.fillStyle='#aa1010'; ctx.fillRect(8,8,size-16,size-16); break;
    case 'stone':
      ctx.fillStyle='#5a5a6a'; ctx.fillRect(4,4,size-8,size-8);
      ctx.strokeStyle='#777788'; ctx.lineWidth=2; ctx.strokeRect(4,4,size-8,size-8);
      ctx.fillStyle='#4a4a5a'; ctx.fillRect(8,8,size-16,size-16);
      ctx.strokeStyle='#3a3a4a'; ctx.lineWidth=1; ctx.strokeRect(8,8,size-16,size-16); break;
    case 'torch':
      ctx.strokeStyle='#666'; ctx.lineWidth=2; ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(cx,cy+6); ctx.stroke();
      ctx.fillStyle='#ff3333'; ctx.beginPath(); ctx.arc(cx,cy-4,4,0,Math.PI*2); ctx.fill(); break;
    case 'repeater':
      ctx.fillStyle='#3a3a3a'; ctx.fillRect(4,4,size-8,size-8);
      ctx.strokeStyle='#884444'; ctx.lineWidth=2; ctx.beginPath(); ctx.moveTo(8,cy); ctx.lineTo(size-8,cy); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(size-8,cy); ctx.lineTo(size-12,cy-3); ctx.moveTo(size-8,cy); ctx.lineTo(size-12,cy+3); ctx.stroke(); break;
    case 'comparator':
      ctx.fillStyle='#3a3a3a'; ctx.fillRect(4,4,size-8,size-8);
      ctx.fillStyle='#ff3b3b'; ctx.beginPath(); ctx.arc(size-10,cy,3,0,Math.PI*2); ctx.fill();
      ctx.strokeStyle='#884444'; ctx.lineWidth=2; ctx.beginPath(); ctx.moveTo(8,cy-5); ctx.lineTo(size-10,cy); ctx.lineTo(8,cy+5); ctx.stroke(); break;
    case 'observer':
      ctx.fillStyle='#2a2a3a'; ctx.fillRect(4,4,size-8,size-8);
      ctx.fillStyle='#555'; ctx.fillRect(size-12,cy-4,8,8);
      ctx.fillStyle='#999'; ctx.beginPath(); ctx.arc(size-9,cy-1,1,0,Math.PI*2); ctx.arc(size-9,cy+1,1,0,Math.PI*2); ctx.fill(); break;
    case 'piston':
      ctx.fillStyle='#3a3a4a'; ctx.fillRect(4,4,size-8,size-8);
      ctx.strokeStyle='#6a6a7a'; ctx.lineWidth=2; ctx.strokeRect(4,4,size-8,size-8);
      ctx.fillStyle='#2a2a3a'; ctx.fillRect(6,6,size-12,size-12);
      ctx.fillStyle='#8a6a3a'; ctx.fillRect(size-14,cy-4,8,8);
      ctx.fillStyle='#5ace5a'; ctx.beginPath(); ctx.arc(size-10,cy,2,0,Math.PI*2); ctx.fill(); break;
    case 'lamp':
      ctx.fillStyle='#2a2a3a'; ctx.fillRect(4,4,size-8,size-8);
      ctx.strokeStyle='#4a4a5a'; ctx.lineWidth=2; ctx.strokeRect(4,4,size-8,size-8);
      ctx.fillStyle='#1a1a2a'; ctx.beginPath(); ctx.arc(cx,cy,size*0.18,0,Math.PI*2); ctx.fill();
      ctx.strokeStyle='#ff9800'; ctx.lineWidth=1; ctx.beginPath(); ctx.arc(cx,cy,size*0.18,0,Math.PI*2); ctx.stroke(); break;
    case 'button':
      ctx.fillStyle='#3a3a4a'; ctx.fillRect(4,4,size-8,size-8);
      ctx.strokeStyle='#5a5a6a'; ctx.lineWidth=2; ctx.strokeRect(4,4,size-8,size-8);
      ctx.fillStyle='#8b2020'; ctx.beginPath(); ctx.arc(cx,cy,size*0.16,0,Math.PI*2); ctx.fill();
      ctx.strokeStyle='#5b1010'; ctx.lineWidth=1; ctx.beginPath(); ctx.arc(cx,cy,size*0.16,0,Math.PI*2); ctx.stroke(); break;
    case 'lever':
      ctx.fillStyle='#3a3a4a'; ctx.fillRect(4,4,size-8,size-8);
      ctx.strokeStyle='#5a5a6a'; ctx.lineWidth=2; ctx.strokeRect(4,4,size-8,size-8);
      ctx.fillStyle='#2a2a3a'; ctx.beginPath(); ctx.arc(cx,cy+4,3,0,Math.PI*2); ctx.fill();
      ctx.strokeStyle='#888'; ctx.lineWidth=2; ctx.lineCap='round';
      ctx.beginPath(); ctx.moveTo(cx,cy+4); ctx.lineTo(cx+6,cy-4); ctx.stroke();
      ctx.fillStyle='#aaa'; ctx.beginPath(); ctx.arc(cx+6,cy-4,2,0,Math.PI*2); ctx.fill(); break;
  }
}

canvas.addEventListener('mousemove', (e) => {
  let rect = canvas.getBoundingClientRect();
  let mx = (e.clientX - rect.left) * (canvas.width / rect.width);
  let my = (e.clientY - rect.top) * (canvas.height / rect.height);
  G.hoverX = Math.floor(mx / CELL); G.hoverY = Math.floor(my / CELL);
  if (G.hoverX >= G.cols) G.hoverX = -1; if (G.hoverY >= G.rows) G.hoverY = -1;
  render();
  // 同步光标
  if (MP.connected && G.hoverX >= 0) {
    sendToPeer({ t: 'cursor', x: G.hoverX, y: G.hoverY });
  }
});
canvas.addEventListener('mouseleave', () => { G.hoverX = -1; G.hoverY = -1; render(); });
canvas.addEventListener('click', (e) => {
  let rect = canvas.getBoundingClientRect();
  let mx = (e.clientX - rect.left) * (canvas.width / rect.width);
  let my = (e.clientY - rect.top) * (canvas.height / rect.height);
  let gx = Math.floor(mx / CELL), gy = Math.floor(my / CELL);
  if (gx < 0 || gx >= G.cols || gy < 0 || gy >= G.rows) return;
  // 联机模式区域限制
  if (MP.connected && !isInMyZone(gx)) { showTip('这是队友的区域，你不能在此操作'); return; }
  let cell = G.grid[gx][gy];
  // 按钮点击激活（橡皮擦模式除外）
  if (cell.type === T.BUTTON && G.selectedComp !== 'erase') {
    cell.buttonActive = true; cell.buttonTimer = 5;
    playClick();
    if (!G.running) { initRestingSignals(); startButtonRestTimer(); render(); }
    else render();
    sendToPeer({ t: 'buttonActivate', x: gx, y: gy });
    return;
  }
  // 拉杆点击切换（橡皮擦模式除外）
  if (cell.type === T.LEVER && G.selectedComp !== 'erase') {
    cell.leverOn = !cell.leverOn;
    playClick();
    if (!G.running) { initRestingSignals(); render(); }
    else render();
    sendToPeer({ t: 'leverToggle', x: gx, y: gy, on: cell.leverOn });
    return;
  }
  if (G.selectedComp && G.selectedComp !== 'erase') {
    if (cell.type !== T.EMPTY) {
      if (cell.type === G.selectedComp) {
        retractAllPistons();
        let oldDir = cell.direction, oldDelay = cell.delay, oldMode = cell.mode;
        if (cell.type === T.REPEATER) cell.delay = (cell.delay % 4) + 1;
        else if (cell.type === T.COMPARATOR) cell.mode = cell.mode === 'compare' ? 'subtract' : 'compare';
        else cell.direction = (cell.direction + 1) % 4;
        playClick(); resetSimulation(); updateInfoBar(); render();
        if (cell.direction !== oldDir || cell.delay !== oldDelay || cell.mode !== oldMode) {
          sendToPeer({ t: 'modify', x: gx, y: gy, comp: cell.type, dir: cell.direction, delay: cell.delay, mode: cell.mode });
        }
      }
      return;
    }
    if (G.level.limits && G.level.limits[G.selectedComp]) { let used = G.compCounts[G.selectedComp] || 0; if (used >= G.level.limits[G.selectedComp]) { showTip(COMP_NAMES[G.selectedComp] + '已达上限'); return; } }
    retractAllPistons();
    cell.type = G.selectedComp; cell.direction = G.selectedRotate; cell.delay = 1; cell.mode = 'compare';
    cell.outputActive=false; cell.prevInput=false; cell.eventQueue=[]; cell.extinguished=false; cell.pulsing=false; cell.pulseTimer=0; cell.prevFrontSignal=0; cell.outputStrength=0; cell.cooldown=0; cell.extended=false; cell.pushedBlockType=null; cell.pistonCooldown=0;
    cell.buttonActive=false; cell.buttonTimer=0; cell.leverOn=false;
    G.compCounts[G.selectedComp] = (G.compCounts[G.selectedComp] || 0) + 1;
    playPlace(); resetSimulation(); updateInfoBar(); render();
    sendToPeer({ t: 'place', x: gx, y: gy, comp: G.selectedComp, dir: G.selectedRotate, delay: 1, mode: 'compare' });
  } else if (G.selectedComp === 'erase') {
    if (cell.type === T.EMPTY || cell.type === T.INPUT || cell.type === T.OUTPUT) return;
    if (MP.connected && !isInMyZone(gx)) { showTip('这是队友区域内的元件，你不能移除'); return; }
    retractAllPistons();
    G.compCounts[cell.type] = Math.max(0, (G.compCounts[cell.type] || 1) - 1);
    cell.type = T.EMPTY; cell.direction = 0; cell.delay = 1;
    playRemove(); resetSimulation(); updateInfoBar(); render();
    sendToPeer({ t: 'remove', x: gx, y: gy });
  }
});
canvas.addEventListener('contextmenu', (e) => {
  e.preventDefault();
  let rect = canvas.getBoundingClientRect();
  let mx = (e.clientX - rect.left) * (canvas.width / rect.width);
  let my = (e.clientY - rect.top) * (canvas.height / rect.height);
  let gx = Math.floor(mx / CELL), gy = Math.floor(my / CELL);
  if (gx < 0 || gx >= G.cols || gy < 0 || gy >= G.rows) return;
  if (MP.connected && !isInMyZone(gx)) { showTip('这是队友的区域，你不能在此操作'); return; }
  let cell = G.grid[gx][gy];
  if (cell.type === T.EMPTY || cell.type === T.INPUT || cell.type === T.OUTPUT) return;
  G.compCounts[cell.type] = Math.max(0, (G.compCounts[cell.type] || 1) - 1);
  cell.type = T.EMPTY; cell.direction = 0;
  playRemove(); resetSimulation(); updateInfoBar(); render();
  sendToPeer({ t: 'remove', x: gx, y: gy });
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'r' || e.key === 'R') { G.selectedRotate = (G.selectedRotate + 1) % 4; playRotate(); showTip('方向: ' + ['\u2192','\u2193','\u2190','\u2191'][G.selectedRotate]); render(); }
  if (e.key === ' ') { e.preventDefault(); if (G.running) { pauseSimulation(); sendToPeer({t:'pause'}); } else { startSimulation(); sendToPeer({t:'play'}); } }
});

document.getElementById('playBtn').onclick = () => { playClick(); if (G.running) { pauseSimulation(); sendToPeer({t:'pause'}); } else { startSimulation(); sendToPeer({t:'play'}); } };
document.getElementById('resetBtn').onclick = () => { playClick(); resetSimulation(); sendToPeer({t:'reset'}); };
document.getElementById('stepBtn').onclick = () => { playClick(); stepSimulation(); sendToPeer({t:'step'}); };
document.getElementById('rotateBtn').onclick = () => { playRotate(); G.selectedRotate = (G.selectedRotate + 1) % 4; showTip('方向: ' + ['\u2192','\u2193','\u2190','\u2191'][G.selectedRotate]); render(); };
document.getElementById('nextBtn').onclick = () => { playClick(); document.getElementById('winModal').classList.remove('show'); if (G.levelIdx + 1 < LEVELS.length) loadLevel(G.levelIdx + 1); else showFinalModal(); };
document.getElementById('retryBtn').onclick = () => { playClick(); document.getElementById('winModal').classList.remove('show'); loadLevel(G.levelIdx); };
document.getElementById('finalCloseBtn').onclick = () => { playClick(); document.getElementById('finalModal').classList.remove('show'); showHome(); };
document.getElementById('failRetryBtn').onclick = () => { playClick(); document.getElementById('failModal').classList.remove('show'); loadLevel(G.levelIdx); };
document.getElementById('failCloseBtn').onclick = () => { playClick(); document.getElementById('failModal').classList.remove('show'); };

document.getElementById('soundBtn').onclick = () => {
  soundEnabled = !soundEnabled;
  let btn = document.getElementById('soundBtn');
  if (soundEnabled) { btn.innerHTML = '&#128266; 音效'; playClick(); }
  else { btn.innerHTML = '&#128263; 静音'; }
};

function showWinModal() {
  let modal = document.getElementById('winModal');
  let stars = 3, totalUsed = 0;
  for (let k in G.compCounts) totalUsed += G.compCounts[k];
  let par = G.level.par || 10;
  if (totalUsed > par) stars = 2;
  if (totalUsed > par * 1.5) stars = 1;
  document.getElementById('winStars').textContent = '\u2605 '.repeat(stars).trim() + ' \u2606'.repeat(3 - stars);
  document.getElementById('winInfo').innerHTML = '<b style="font-size:22px;color:#4ecca3">' + G.level.name + '</b><br><br>延迟: ' + G.outputDelay + ' tick (目标 ' + G.level.target.delay + ')<br>持续: ' + G.outputDuration + ' tick (目标 ' + G.level.target.duration + ')' + (G.level.target.strength !== undefined ? '<br>强度: ' + G.outputMaxStrength + ' (目标 ' + G.level.target.strength + ')' : '') + '<br>使用元件: ' + totalUsed + ' / 推荐 ' + par;
  modal.classList.add('show');
  playWin();
}

function showFailModal() {
  let modal = document.getElementById('failModal');
  let target = G.level.target;
  let info = '';
  if (G.outputDelay < 0) {
    info = '<b style="font-size:18px;color:#e94560">信号未能到达输出点！</b><br><br>请检查电路是否正确连接了输入和输出。<br>提示: ' + (G.level.hint || '');
  } else {
    info = '<b style="font-size:18px;color:#e94560">' + G.level.name + '</b><br><br>';
    let delayOk = G.outputDelay === target.delay;
    let durationOk = G.outputDuration === target.duration;
    let hasStrength = target.strength !== undefined;
    let strengthOk = !hasStrength || G.outputMaxStrength === target.strength;
    info += '延迟: <span style="color:' + (delayOk ? '#4ecca3' : '#e94560') + '">' + G.outputDelay + ' tick</span>' + (delayOk ? ' \u2713' : ' (目标 ' + target.delay + ')') + '<br>';
    info += '持续: <span style="color:' + (durationOk ? '#4ecca3' : '#e94560') + '">' + G.outputDuration + ' tick</span>' + (durationOk ? ' \u2713' : ' (目标 ' + target.duration + ')') + '<br>';
    if (hasStrength) info += '强度: <span style="color:' + (strengthOk ? '#4ecca3' : '#e94560') + '">' + G.outputMaxStrength + '</span>' + (strengthOk ? ' \u2713' : ' (目标 ' + target.strength + ')') + '<br>';
    info += '<br>';
    let fails = [];
    if (!delayOk) fails.push('延迟');
    if (!durationOk) fails.push('持续');
    if (hasStrength && !strengthOk) fails.push('强度');
    if (fails.length === 0) info += '信号参数已匹配，但可能时序有问题。';
    else if (fails.length === 1) info += fails[0] + '不匹配，请调整信号路径或元件配置。';
    else info += fails.join('和') + '均不匹配，请调整信号路径或元件配置。';
    if (hasStrength && !strengthOk) info += '<br>提示: 信号强度会随红石粉传播递减，使用中继器可以恢复强度。';
  }
  document.getElementById('failInfo').innerHTML = info;
  modal.classList.add('show');
  playFail();
}

function showFinalModal() {
  let modal = document.getElementById('finalModal');
  let totalStars = 0;
  for (let i = 0; i < LEVELS.length; i++) {
    if (G.completed.has(i)) totalStars++;
  }
  document.getElementById('finalStars').textContent = '\u2605 '.repeat(Math.min(totalStars, 5)).trim();
  document.getElementById('finalInfo').innerHTML = '恭喜你完成了全部 ' + LEVELS.length + ' 个关卡！<br>你已经掌握了红石逻辑的精髓！<br><br>通关关卡: ' + totalStars + ' / ' + LEVELS.length;
  modal.classList.add('show');
  playFinalWin();
}

let tipTimer = null;
function showTip(msg) {
  let tip = document.getElementById('tip');
  tip.textContent = msg; tip.classList.add('show');
  if (tipTimer) clearTimeout(tipTimer);
  tipTimer = setTimeout(() => tip.classList.remove('show'), 2000);
}

function saveToFile() {
  if (G.level !== null) captureLayout();
  let data = { version: 2, timestamp: new Date().toISOString(), levelIdx: G.levelIdx, completed: [...G.completed], introSeen: [...introSeen], levelLayouts: G.levelLayouts };
  let blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  let url = URL.createObjectURL(blob);
  let a = document.createElement('a'); a.href = url;
  let now = new Date();
  let stamp = now.getFullYear() + String(now.getMonth()+1).padStart(2,'0') + String(now.getDate()).padStart(2,'0') + '_' + String(now.getHours()).padStart(2,'0') + String(now.getMinutes()).padStart(2,'0');
  a.download = '红石存档_' + stamp + '.json';
  document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
  showTip('存档已保存！');
}
function loadFromFile(file) {
  let reader = new FileReader();
  reader.onload = (e) => {
    try {
      let data = JSON.parse(e.target.result);
      if (!data || typeof data !== 'object') throw new Error('无效的存档格式');
      G.completed = new Set(data.completed || []);
      localStorage.setItem('rs_completed', JSON.stringify([...G.completed]));
      introSeen = new Set(data.introSeen || []);
      localStorage.setItem('rs_intro_seen', JSON.stringify([...introSeen]));
      G.levelLayouts = data.levelLayouts || {};
      let targetIdx = data.levelIdx;
      if (targetIdx === undefined || targetIdx === null) targetIdx = 0;
      if (targetIdx === -1) {
        loadFreeMode();
      } else {
        if (targetIdx >= LEVELS.length) targetIdx = 0;
        G.levelIdx = targetIdx; G.level = LEVELS[targetIdx]; G.selectedComp = null;
        initGrid(G.level); restoreLayout(targetIdx);
        buildComponentBar(); buildLevelSelector(); updateInfoBar();
        document.getElementById('hint').textContent = '提示: ' + (G.level.hint || '');
        pauseSimulation(); resizeCanvas(); render();
      }
      hideHome();
      showTip('存档已读取！');
      // 联机模式下同步给队友
      if (MP.connected) setTimeout(() => syncFullState(), 200);
    } catch (err) { showTip('读取失败：' + err.message); }
  };
  reader.readAsText(file);
}
document.getElementById('saveBtn').onclick = () => saveToFile();
document.getElementById('loadBtn').onclick = () => { document.getElementById('fileInput').click(); };
document.getElementById('fileInput').onchange = (e) => { if (e.target.files.length > 0) { loadFromFile(e.target.files[0]); e.target.value = ''; } };

function init() { loadLevel(0); showHome(); }

function showHome() {
  let completedCount = G.completed.size;
  let total = LEVELS.length;
  document.getElementById('homeProgress').textContent = completedCount + ' / ' + total + ' 关卡完成';
  document.getElementById('homeProgressFill').style.width = (completedCount / total * 100) + '%';
  let startBtn = document.getElementById('homeStartBtn');
  if (completedCount === 0) startBtn.textContent = '开始游戏';
  else if (completedCount >= total) startBtn.textContent = '再次挑战';
  else startBtn.textContent = '继续游戏';
  let levelsEl = document.getElementById('homeLevels');
  levelsEl.innerHTML = '';
  for (let i = 0; i < LEVELS.length; i++) {
    let btn = document.createElement('button');
    btn.className = 'home-level-btn'; btn.textContent = i + 1;
    if (G.completed.has(i)) btn.classList.add('completed');
    if (i > 0 && !G.completed.has(i - 1) && !G.completed.has(i)) btn.classList.add('locked');
    btn.onclick = () => { if (!btn.classList.contains('locked')) { playClick(); hideHome(); loadLevel(i); } };
    levelsEl.appendChild(btn);
  }
  document.getElementById('homePage').classList.remove('hide');
}
function hideHome() { document.getElementById('homePage').classList.add('hide'); }

document.getElementById('homeBtn').onclick = () => { playClick(); pauseSimulation(); showHome(); };
document.getElementById('homeStartBtn').onclick = () => {
  playClick(); hideHome();
  let nextLevel = 0;
  for (let i = 0; i < LEVELS.length; i++) { if (!G.completed.has(i)) { nextLevel = i; break; } }
  if (G.completed.size >= LEVELS.length) nextLevel = 0;
  loadLevel(nextLevel);
};
document.getElementById('homeFreeBtn').onclick = () => {
  playClick(); hideHome();
  loadFreeMode();
};
function loadFreeMode() {
  if (G.level !== null) captureLayout();
  let freeLevel = {
    name: '自由模式',
    desc: '自由搭建，开放所有零件，无对错判断',
    cols: 20, rows: 12,
    components: ['dust', 'block', 'torch', 'repeater', 'comparator', 'observer', 'stone', 'piston', 'lamp', 'button', 'lever'],
    freeMode: true,
  };
  G.levelIdx = -1; G.level = freeLevel; G.selectedComp = null;
  initGrid(freeLevel);
  let layout = G.levelLayouts['free'];
  if (layout && layout.length > 0) {
    for (let item of layout) {
      if (item.x < 0 || item.x >= G.cols || item.y < 0 || item.y >= G.rows) continue;
      let c = G.grid[item.x][item.y];
      if (c.type === T.INPUT || c.type === T.OUTPUT) continue;
      c.type = item.type; c.direction = item.direction || 0; c.delay = item.delay || 1; c.mode = item.mode || 'compare';
      c.buttonActive=false; c.buttonTimer=0; c.leverOn=item.leverOn||false;
      G.compCounts[item.type] = (G.compCounts[item.type] || 0) + 1;
    }
  }
  buildComponentBar(); buildLevelSelector(); updateInfoBar();
  document.getElementById('hint').textContent = '提示: 自由模式 — 放置红石火把/红石块作为信号源，用红石灯检测信号';
  document.getElementById('hint').style.color = '#4ecca3';
  pauseSimulation(); resizeCanvas(); render();
  if (!MP.syncing) sendToPeer({ t: 'level', idx: 0 });
}
// 生成随机关卡并加入LEVELS（在G初始化后）
LEVELS.push(generateRandomLevel());

init();
</script>
</body>
</html>
'''


def level_to_js(level):
    """将一个关卡字典转换为 JS 对象字面量字符串"""
    lines = []
    lines.append("  {")
    lines.append(f"    name: {json.dumps(level.get('name', ''), ensure_ascii=False)},")
    lines.append(f"    desc: {json.dumps(level.get('desc', ''), ensure_ascii=False)},")
    lines.append(f"    cols: {level['cols']}, rows: {level['rows']},")

    if 'inputs' in level:
        inputs_js = json.dumps(level['inputs'], ensure_ascii=False)
        lines.append(f"    inputs: {inputs_js},")
    else:
        input_js = json.dumps(level['input'], ensure_ascii=False)
        lines.append(f"    input: {input_js},")

    output_js = json.dumps(level['output'], ensure_ascii=False)
    lines.append(f"    output: {output_js},")

    target_js = json.dumps(level['target'], ensure_ascii=False)
    lines.append(f"    target: {target_js},")

    components_js = json.dumps(level['components'], ensure_ascii=False)
    lines.append(f"    components: {components_js},")

    limits = level.get('limits', {})
    if limits:
        limits_js = json.dumps(limits, ensure_ascii=False)
        lines.append(f"    limits: {limits_js},")
    else:
        lines.append("    limits: {},")

    lines.append(f"    hint: {json.dumps(level.get('hint', ''), ensure_ascii=False)},")
    lines.append(f"    par: {level.get('par', 10)},")

    if 'logic' in level:
        lines.append(f"    logic: {json.dumps(level['logic'], ensure_ascii=False)},")

    if 'preplaced' in level:
        preplaced_js = json.dumps(level['preplaced'], ensure_ascii=False)
        lines.append(f"    preplaced: {preplaced_js},")

    # 去掉最后一行末尾的逗号
    last = lines[-1].rstrip(',')
    lines[-1] = last
    lines.append("  }")
    return '\n'.join(lines)


def generate_html(levels_data):
    """从关卡数据生成完整 HTML"""
    levels_js = ',\n'.join(level_to_js(lv) for lv in levels_data['levels'])
    levels_js = '[\n' + levels_js + '\n]'
    html = HTML_TEMPLATE.replace('__LEVELS_PLACEHOLDER__', levels_js)
    return html


def main():
    if len(sys.argv) < 2:
        print("用法: python gen_redstone_game.py <关卡定义文件.json> [输出文件.html]")
        print("示例: python gen_redstone_game.py levels.json redstone-puzzle.html")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'redstone-puzzle.html'

    if not os.path.exists(input_file):
        print(f"错误: 文件 '{input_file}' 不存在")
        sys.exit(1)

    with open(input_file, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"错误: JSON 解析失败 - {e}")
            sys.exit(1)

    if 'levels' not in data or not isinstance(data['levels'], list):
        print("错误: 关卡文件必须包含 'levels' 数组")
        sys.exit(1)

    # 校验关卡数据
    for i, lv in enumerate(data['levels']):
        if 'name' not in lv:
            print(f"警告: 第{i+1}关缺少 name 字段")
        if 'cols' not in lv or 'rows' not in lv:
            print(f"错误: 第{i+1}关缺少 cols/rows 字段")
            sys.exit(1)
        if 'input' not in lv and 'inputs' not in lv:
            print(f"错误: 第{i+1}关缺少 input 或 inputs 字段")
            sys.exit(1)
        if 'output' not in lv:
            print(f"错误: 第{i+1}关缺少 output 字段")
            sys.exit(1)
        if 'target' not in lv:
            print(f"错误: 第{i+1}关缺少 target 字段")
            sys.exit(1)
        if 'components' not in lv:
            print(f"错误: 第{i+1}关缺少 components 字段")
            sys.exit(1)

    html = generate_html(data)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"生成成功! {len(data['levels'])} 关 -> {output_file}")


if __name__ == '__main__':
    main()
