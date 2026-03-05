// Popup script for Interview Copilot

const SERVER_URL = 'http://localhost:8000';

// DOM Elements
const jdInput = document.getElementById('jd');
const resumeInput = document.getElementById('resume');
const dualChannelInput = document.getElementById('enableDualChannelAudio');
const saveBtn = document.getElementById('saveBtn');
const captureBtn = document.getElementById('captureBtn');
const statusDiv = document.getElementById('status');

// Load saved context on popup open
document.addEventListener('DOMContentLoaded', async () => {
  const data = await chrome.storage.local.get(['jd', 'resume', 'isCapturing', 'enableDualChannelAudio']);
  if (data.jd) jdInput.value = data.jd;
  if (data.resume) resumeInput.value = data.resume;
  if (data.enableDualChannelAudio) dualChannelInput.checked = data.enableDualChannelAudio;
  
  updateCaptureButton(data.isCapturing || false);
});

// Save context
saveBtn.addEventListener('click', async () => {
  const jd = jdInput.value.trim();
  const resume = resumeInput.value.trim();
  const enableDualChannelAudio = dualChannelInput.checked;
  
  if (!jd || !resume) {
    showStatus('请填写 JD 和简历', 'error');
    return;
  }
  
  try {
    // Save to chrome.storage
    await chrome.storage.local.set({ jd, resume, enableDualChannelAudio });
    
    // Send to server
    const response = await fetch(`${SERVER_URL}/set_context`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jd, resume })
    });
    
    if (response.ok) {
      showStatus('✅ 保存成功', 'success');
    } else {
      showStatus('❌ 服务器错误', 'error');
    }
  } catch (error) {
    showStatus('❌ 无法连接服务器，请确保后端已启动', 'error');
    console.error(error);
  }
});

// Toggle audio capture
captureBtn.addEventListener('click', async () => {
  const data = await chrome.storage.local.get(['isCapturing']);
  const isCapturing = data.isCapturing || false;
  
  if (isCapturing) {
    // Stop capturing
    chrome.runtime.sendMessage({ action: 'stopCapture' });
    await chrome.storage.local.set({ isCapturing: false });
    updateCaptureButton(false);
    showStatus('🛑 已停止捕获', 'info');
  } else {
    // Start capturing
    chrome.runtime.sendMessage({ action: 'startCapture' });
    await chrome.storage.local.set({ isCapturing: true });
    updateCaptureButton(true);
    showStatus('🎤 正在捕获音频...', 'info');
  }
});

function updateCaptureButton(isCapturing) {
  if (isCapturing) {
    captureBtn.textContent = '⏹️ 停止捕获';
    captureBtn.classList.add('active');
  } else {
    captureBtn.textContent = '🎤 开始捕获';
    captureBtn.classList.remove('active');
  }
}

function showStatus(message, type) {
  statusDiv.textContent = message;
  statusDiv.className = `status ${type}`;
  statusDiv.classList.remove('hidden');
  
  setTimeout(() => {
    statusDiv.classList.add('hidden');
  }, 3000);
}
