const sock = new WebSocket('ws://' + location.host + '/ws')
sock.onmessage = handleWebsocketMessage;


function startProcess() {
    let msg = {};
    msg.op = 'start';
    sock.send(JSON.stringify(msg));
}


function clearHistory() {
    const target = document.getElementById('proc-reports');
    target.innerHTML = '';
}


function handleWebsocketMessage(event) {
    const data = JSON.parse(event.data);
    // console.log(data);
    switch(data.op) {
        case 'start':
            createProgressBar(data.id, data.max);
            break;
        case 'progress':
            updateProgressBar(data.id, data.value, data.max);
            break;
        case 'finish':
            completeProgressBar(data.id);
            break;
        case 'error':
            break;
        case 'pool':
            // console.log(data);
            updatePoolStatus(data.completed, data.active, data.queued);
            break;
        default:
            ;
    }
}


function createProgressBar(id, max) {
    let target = document.getElementById('proc-reports');
    let baseDiv = Object.assign(document.createElement('div'), { 
        className: 'report-item progress-bar'
    });
    baseDiv.appendChild(Object.assign(document.createElement('div'), { 
        className: 'progress-text', innerText: 'Process ' + id
    }));
    baseDiv.appendChild(Object.assign(document.createElement('div'), {
        className: 'progress-value', id: 'proc_' + id, maxValue: max
    }));
    target.insertBefore(baseDiv, target.children[0]);
}


function updateProgressBar(id, value, max) {
    let progbar = document.getElementById('proc_' + id);
    if (progbar !== null) {
        baseWidth = progbar.parentElement.offsetWidth;
        progbar.style.width = ((value * baseWidth) / progbar.maxValue) + 'px';
    }
    else {
        createProgressBar(id, max);
        updateProgressBar(id, value, max);
    }
}


function completeProgressBar(id) {
    let progBar = document.getElementById('proc_' + id);
    if (progBar !== null) {
        baseBar = progBar.parentElement;
        baseWidth = baseBar.offsetWidth;
        baseBar.innerHTML = '';
        baseBar.className = 'progress-complete';
        baseBar.style.width = baseWidth + 'px';
        baseBar.innerText = 'Process ' + id;
    }
    else {
        createProgressBar(id, 1);
        completeProgressBar(id);
    }
}


function updatePoolStatus(completed, active, queued) {
    document.getElementById('proc-completed').innerText = completed;
    document.getElementById('proc-active').innerText = active
    document.getElementById('proc-queued').innerText = queued;
}
