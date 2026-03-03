document.getElementById('close-settings').addEventListener('click', () => {
    // Notify the parent window to close the settings menu
    window.parent.postMessage('closeSettings', '*');
});

// Example settings handling
document.getElementById('gather-speaker').addEventListener('change', (e) => {
    localStorage.setItem('gatherSameSpeaker', e.target.checked);
});

document.getElementById('font-size').addEventListener('input', (e) => {
    localStorage.setItem('fontSize', e.target.value);
});
