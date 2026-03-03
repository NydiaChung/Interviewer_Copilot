// Content script for Interview Copilot - Floating overlay

(function () {
    'use strict';

    // Prevent multiple injections
    if (window.__interviewCopilotInjected) return;
    window.__interviewCopilotInjected = true;

    // Create overlay container
    const overlay = document.createElement('div');
    overlay.id = 'interview-copilot-overlay';
    overlay.innerHTML = `
    <div class="ic-header">
      <span class="ic-title">🎙️ Interview Copilot</span>
      <button class="ic-minimize">−</button>
    </div>
    <div class="ic-content">
      <div class="ic-question">
        <span class="ic-label">问题:</span>
        <span class="ic-question-text">等待面试官提问...</span>
      </div>
      <div class="ic-divider"></div>
      <div class="ic-answer">
        <span class="ic-label">回答:</span>
        <div class="ic-answer-text">准备就绪，开始捕获音频后将显示建议回答。</div>
      </div>
    </div>
  `;

    document.body.appendChild(overlay);

    // State
    let isMinimized = false;
    let isDragging = false;
    let dragOffset = { x: 0, y: 0 };

    // Elements
    const header = overlay.querySelector('.ic-header');
    const minimizeBtn = overlay.querySelector('.ic-minimize');
    const content = overlay.querySelector('.ic-content');
    const questionText = overlay.querySelector('.ic-question-text');
    const answerText = overlay.querySelector('.ic-answer-text');

    // Minimize toggle
    minimizeBtn.addEventListener('click', () => {
        isMinimized = !isMinimized;
        content.style.display = isMinimized ? 'none' : 'block';
        minimizeBtn.textContent = isMinimized ? '+' : '−';
        overlay.style.height = isMinimized ? 'auto' : '';
    });

    // Drag functionality
    header.addEventListener('mousedown', (e) => {
        if (e.target === minimizeBtn) return;
        isDragging = true;
        dragOffset.x = e.clientX - overlay.offsetLeft;
        dragOffset.y = e.clientY - overlay.offsetTop;
        overlay.style.cursor = 'grabbing';
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;

        let newX = e.clientX - dragOffset.x;
        let newY = e.clientY - dragOffset.y;

        // Keep within viewport
        newX = Math.max(0, Math.min(window.innerWidth - overlay.offsetWidth, newX));
        newY = Math.max(0, Math.min(window.innerHeight - overlay.offsetHeight, newY));

        overlay.style.left = newX + 'px';
        overlay.style.right = 'auto';
        overlay.style.top = newY + 'px';
    });

    document.addEventListener('mouseup', () => {
        isDragging = false;
        overlay.style.cursor = '';
    });

    // Listen for messages from background script
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.action === 'showAnswer') {
            showAnswer(message.question, message.answer);
        } else if (message.action === 'toggleOverlay') {
            toggleOverlay();
        }
    });

    function showAnswer(question, answer) {
        // Show overlay if hidden
        overlay.style.display = 'block';

        // Update content with animation
        questionText.textContent = question || '未识别到问题';
        answerText.textContent = answer || '无回答';

        // Highlight effect
        answerText.classList.add('ic-highlight');
        setTimeout(() => {
            answerText.classList.remove('ic-highlight');
        }, 500);
    }

    function toggleOverlay() {
        if (overlay.style.display === 'none') {
            overlay.style.display = 'block';
        } else {
            overlay.style.display = 'none';
        }
    }

    // Keyboard shortcut fallback
    document.addEventListener('keydown', (e) => {
        if (e.altKey && e.key.toLowerCase() === 'q') {
            e.preventDefault();
            toggleOverlay();
        }
    });

})();
