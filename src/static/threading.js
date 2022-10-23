const ServerOperations = {
    START       : 'start',
    PROGRESS    : 'progress',
    FINISH      : 'finish',
    ERROR       : 'error',
    CANCEL      : 'cancel',
    POOL        : 'pool',
};
const ClientOperations = {
    START       : 'start',
    CANCEL      : 'cancel',
};


const sock = new WebSocket('ws://' + location.host + '/ws')
sock.onmessage = handleServerMessage;
sock.onclose = handleServerClose;
sock.onerror = handleServerError;
sock.onopen = handleServerOpen;

function handleServerClose(ev) {
    console.log(ev);
    const target = document.getElementById('sock-state');
    target.className = 'connection-blink';
    target.innerText = 'DOWN';
    target.style.color = 'white';
    target.style.fontWeight = 'bold';
    document.getElementById('work-completed').innerText = '?';
    document.getElementById('work-active').innerText = '?';
    document.getElementById('work-queued').innerText = '?';
}

function handleServerError(ev) {
    console.log(ev);
    const target = document.getElementById('sock-state');
    target.className = 'connection-blink';
    target.innerText = 'ERROR';
    target.style.color = 'red';
    target.style.fontWeight = 'bold';
}

function handleServerOpen(ev) {
    console.log(ev);
    const target = document.getElementById('sock-state');
    target.className = '';
    target.innerText = 'UP';
    target.style.color = 'green';
    target.style.fontWeight = 'bold';
}


function handleServerMessage(event) {
    const msg = JSON.parse(event.data);
    console.log(msg);
    switch(msg.op) {
        case ServerOperations.START:
            createProgressBar(msg.id, msg.max);
            break;
        case ServerOperations.PROGRESS:
            updateProgressBar(msg.id, msg.value, msg.max);
            break;
        case ServerOperations.FINISH:
            finalizeProgressBar(msg.id, 'Completed');
            break;
        case ServerOperations.ERROR:
            finalizeProgressBar(msg.id, 'Error');
            break;
        case ServerOperations.CANCEL:
            finalizeProgressBar(msg.id, 'Cancelled');
            break;
        case ServerOperations.POOL:
            updatePoolStatus(msg.completed, msg.active, msg.queued);
            break;
        default:
            ;
    }
}


function startWork() {
    sock.send(JSON.stringify({ op: ClientOperations.START }));
}


function cancelWork(id) {
    sock.send(JSON.stringify({ op: ClientOperations.CANCEL, id: id}));
}


function cancelAllWork() {
    sock.send(JSON.stringify({ op: ClientOperations.CANCEL, id: null }));
}


function clearHistory() {
    document.getElementById('work-reports').innerHTML = '';
}


function createProgressBar(id, max) {
    let target = document.getElementById('work-reports');
    let wrapper = Object.assign(document.createElement('div'), {
        className: 'work-item', id: 'work_' + id
    });
    wrapper.appendChild(Object.assign(document.createElement('label'), {
        className: 'work-title', innerText: 'Process ' + id
    }));
    cancelBtn = wrapper.appendChild(Object.assign(document.createElement('button'), {
        className: 'work-cancel', id: 'cancel_' + id, innerText: 'Cancel', targetId: id
    }));
    cancelBtn.onclick = function(ev) { cancelWork(ev.srcElement.targetId); };
    let bar = wrapper.appendChild(Object.assign(document.createElement('div'), {
        className: 'work-bar'
    }));
    bar.appendChild(Object.assign(document.createElement('div'), {
        className: 'work-progress', id: 'bar_' + id, maxValue: max
    }));
    target.insertBefore(wrapper, target.children[0]);
}


function updateProgressBar(id, value, max) {
    let progbar = document.getElementById('bar_' + id);
    if (progbar !== null) {
        baseWidth = progbar.parentElement.offsetWidth;
        progbar.style.width = ((value * baseWidth) / progbar.maxValue) + 'px';
    }
    else {
        createProgressBar(id, max);
        updateProgressBar(id, value, max);
    }
}


function finalizeProgressBar(id, text) {
    let progBar = document.getElementById('bar_' + id);
    if (progBar !== null) {
        let wrapper = progBar.parentElement.parentElement;
        wrapper.removeChild(progBar.parentElement);
        wrapper.removeChild(document.getElementById('cancel_' + id));
        wrapper.appendChild(Object.assign(document.createElement('div'), {
            className: 'work-complete', innerText: text
        }));
        delbutton = wrapper.appendChild(Object.assign(document.createElement('button'), {
            className: 'remove-history', innerText: 'X', targetId: 'work_' + id
        }));
        delbutton.onclick = function(ev) { removeReport(ev.srcElement.targetId); };
    }
    else {
        createProgressBar(id, 1);
        finalizeProgressBar(id, text);
    }
}


function removeReport(id) {
    document.getElementById('work-reports').removeChild(
        document.getElementById(id)
    );
}


function updatePoolStatus(completed, active, queued) {
    document.getElementById('work-completed').innerText = completed;
    document.getElementById('work-active').innerText = active;
    document.getElementById('work-queued').innerText = queued;
}
