function closeModal(event, modalId) {
    if (event && event.target.id !== modalId && event.target.tagName !== 'BUTTON') {
        return;
    }
    document.getElementById(modalId).classList.remove('open');
}

function openNameModal(presetNum, currentName) {
    document.getElementById('name-modal-preset-num').value = presetNum;
    document.getElementById('name-modal-input').value = currentName;
    document.getElementById('name-modal-overlay').classList.add('open');
}

async function submitPresetName(event) {
    event.preventDefault();
    const presetNum = document.getElementById('name-modal-preset-num').value;
    const input = document.getElementById('name-modal-input');
    const params = new URLSearchParams();
    params.append('name', input.value);

    const response = await fetch(`/preset/${presetNum}/name`, {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: params,
    });

    const text = await response.text();
    setStatus(text);

    if (response.ok) {
        const label = document.getElementById(`preset-label-${presetNum}`);
        if (label) label.innerText = input.value.trim() || `Preset ${presetNum}`;
        document.getElementById('name-modal-overlay').classList.remove('open');
    }
}

function setStatus(text) {
    const status = document.getElementById('status');
    if (status) status.innerText = text;
}

async function refreshPositionFeedback() {
    try {
        const response = await fetch('/position');
        const payload = await response.json();

        if (!response.ok) {
            setStatus(payload.error || 'Unable to read camera position');
            return;
        }

        document.getElementById('position-pan').innerText = payload.pan;
        document.getElementById('position-tilt').innerText = payload.tilt;
        document.getElementById('position-zoom').innerText = payload.zoom;
    } catch (error) {
        setStatus('Unable to read camera position');
    }
}

window.addEventListener('load', () => {
    if (document.getElementById('position-pan')) {
        refreshPositionFeedback();
        setInterval(refreshPositionFeedback, 1000);
    }
});
