// Background service worker for Interview Copilot

const WS_URL = 'ws://localhost:8000/ws/audio';

let tabMediaStream = null;
let micMediaStream = null;
let tabAudioContext = null;
let micAudioContext = null;
let tabScriptProcessor = null;
let micScriptProcessor = null;
let ws = null;
let isDualChannel = false;

// Handle messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'startCapture') {
        startCapture();
    } else if (message.action === 'stopCapture') {
        stopCapture();
    }
});

// Handle keyboard shortcut
chrome.commands.onCommand.addListener((command) => {
    if (command === 'toggle-overlay') {
        // Send message to content script to toggle overlay
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
                chrome.tabs.sendMessage(tabs[0].id, { action: 'toggleOverlay' });
            }
        });
    }
});

async function startCapture() {
    try {
        const data = await chrome.storage.local.get(['enableDualChannelAudio']);
        isDualChannel = data.enableDualChannelAudio || false;

        // Get current tab
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        // Request tab capture
        const streamId = await chrome.tabCapture.getMediaStreamId({
            targetTabId: tab.id
        });

        await setupAudioCapture(streamId, tab.id);

    } catch (error) {
        console.error('Failed to start capture:', error);
        chrome.storage.local.set({ isCapturing: false });
    }
}

async function setupAudioCapture(streamId, tabId) {
    // Connect WebSocket
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        console.log('[WS] Connected to server, DualChannel:', isDualChannel);
    };

    ws.onmessage = (event) => {
        // 兼容后端返回纯文本或者 JSON
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'answer' || data.type === 'outline') {
                chrome.tabs.sendMessage(tabId, {
                    action: 'showAnswer',
                    question: data.question,
                    answer: data.answer
                });
            } else if (data.answer) {
                chrome.tabs.sendMessage(tabId, {
                    action: 'showAnswer',
                    question: data.question,
                    answer: data.answer
                });
            }
        } catch (e) {
            // ignore non-json messages for UI
        }
    };

    ws.onerror = (error) => {
        console.error('[WS] Error:', error);
    };

    ws.onclose = () => {
        console.log('[WS] Disconnected');
    };

    try {
        // 1. 获取 Tab Audio (面试官)
        tabMediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                mandatory: {
                    chromeMediaSource: 'tab',
                    chromeMediaSourceId: streamId
                }
            }
        });

        tabAudioContext = new AudioContext({ sampleRate: 16000 });
        const tabSource = tabAudioContext.createMediaStreamSource(tabMediaStream);
        tabScriptProcessor = tabAudioContext.createScriptProcessor(4096, 1, 1);

        tabScriptProcessor.onaudioprocess = (event) => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                const inputData = event.inputBuffer.getChannelData(0);
                const pcmData = float32ToInt16(inputData);

                if (isDualChannel) {
                    const b64 = bufferToBase64(pcmData.buffer);
                    ws.send(JSON.stringify({
                        type: "audio",
                        channel: "interviewer",
                        data: b64
                    }));
                } else {
                    ws.send(pcmData.buffer);
                }
            }
        };

        tabSource.connect(tabScriptProcessor);
        tabScriptProcessor.connect(tabAudioContext.destination);

        // 2. 如果开启双通道，获取麦克风流 (候选人)
        if (isDualChannel) {
            micMediaStream = await navigator.mediaDevices.getUserMedia({
                audio: true
            });

            micAudioContext = new AudioContext({ sampleRate: 16000 });
            const micSource = micAudioContext.createMediaStreamSource(micMediaStream);
            micScriptProcessor = micAudioContext.createScriptProcessor(4096, 1, 1);

            micScriptProcessor.onaudioprocess = (event) => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    const inputData = event.inputBuffer.getChannelData(0);
                    const pcmData = float32ToInt16(inputData);
                    const b64 = bufferToBase64(pcmData.buffer);
                    ws.send(JSON.stringify({
                        type: "audio",
                        channel: "candidate",
                        data: b64
                    }));
                }
            };

            // 候选人麦克风流不需要连接 destination 以防在当前网页产生回音，但如果是 MV3 offscreen 可能也听不到。
            // 为了安全起见，断开音频输出，只需要 capture。
            micSource.connect(micScriptProcessor);
            // micScriptProcessor doesn't strictly need connected to destination to process in some setups,
            // but in Chrome it often needs a sink to fire `onaudioprocess`. We connect to destination but use gain=0 if needed.
            const gainNode = micAudioContext.createGain();
            gainNode.gain.value = 0;
            micScriptProcessor.connect(gainNode);
            gainNode.connect(micAudioContext.destination);
        }

        console.log('[Audio] Capture started. Dual Channel Enabled:', isDualChannel);

    } catch (error) {
        console.error('[Audio] Failed to get media stream:', error);
        stopCapture();
    }
}

function float32ToInt16(float32Array) {
    const int16Array = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
        const s = Math.max(-1, Math.min(1, float32Array[i]));
        int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return int16Array;
}

function bufferToBase64(buffer) {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    // 使用大块拼接避免调用栈溢出
    for (let i = 0; i < len; i += 32768) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 32768));
    }
    return btoa(binary);
}

function stopCapture() {
    if (tabScriptProcessor) {
        tabScriptProcessor.disconnect();
        tabScriptProcessor = null;
    }
    if (micScriptProcessor) {
        micScriptProcessor.disconnect();
        micScriptProcessor = null;
    }

    if (tabAudioContext) {
        tabAudioContext.close();
        tabAudioContext = null;
    }
    if (micAudioContext) {
        micAudioContext.close();
        micAudioContext = null;
    }

    if (tabMediaStream) {
        tabMediaStream.getTracks().forEach(track => track.stop());
        tabMediaStream = null;
    }
    if (micMediaStream) {
        micMediaStream.getTracks().forEach(track => track.stop());
        micMediaStream = null;
    }

    if (ws) {
        ws.close();
        ws = null;
    }

    console.log('[Audio] Capture stopped');
}
