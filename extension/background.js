// Background service worker for Interview Copilot

const WS_URL = 'ws://localhost:8000/ws/audio';

let mediaStream = null;
let audioContext = null;
let scriptProcessor = null;
let ws = null;

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
        // Get current tab
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        // Request tab capture
        const streamId = await chrome.tabCapture.getMediaStreamId({
            targetTabId: tab.id
        });

        // Create media stream using offscreen document or direct capture
        // For MV3, we need to use offscreen document for audio processing
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
        console.log('[WS] Connected to server');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        // Send answer to content script
        chrome.tabs.sendMessage(tabId, {
            action: 'showAnswer',
            question: data.question,
            answer: data.answer
        });
    };

    ws.onerror = (error) => {
        console.error('[WS] Error:', error);
    };

    ws.onclose = () => {
        console.log('[WS] Disconnected');
    };

    // Get user media with the stream ID
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                mandatory: {
                    chromeMediaSource: 'tab',
                    chromeMediaSourceId: streamId
                }
            }
        });

        // Setup audio processing
        audioContext = new AudioContext({ sampleRate: 16000 });
        const source = audioContext.createMediaStreamSource(mediaStream);

        // Use ScriptProcessorNode for audio processing
        // Buffer size: 4096 samples
        scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);

        scriptProcessor.onaudioprocess = (event) => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                const inputData = event.inputBuffer.getChannelData(0);
                // Convert float32 to int16 PCM
                const pcmData = float32ToInt16(inputData);
                ws.send(pcmData.buffer);
            }
        };

        source.connect(scriptProcessor);
        scriptProcessor.connect(audioContext.destination);

        console.log('[Audio] Capture started');

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

function stopCapture() {
    if (scriptProcessor) {
        scriptProcessor.disconnect();
        scriptProcessor = null;
    }

    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }

    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }

    if (ws) {
        ws.close();
        ws = null;
    }

    console.log('[Audio] Capture stopped');
}
