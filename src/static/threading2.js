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


function startProcess() {
    sock.send(JSON.stringify({ op: ClientOperations.START }));
}


function cancelProcess(id) {
    sock.send(JSON.stringify({ op: ClientOperations.CANCEL, id: id}));
}


function cancelAllProcesses() {
    sock.send(JSON.stringify({ op: ClientOperations.CANCEL, id: null }));
}


function clearHistory() {
    document.getElementById('proc-reports').innerHTML = '';
}


function handleServerMessage(event) {
    const msg = JSON.parse(event.data);
    switch(msg.op) {
        case ServerOperations.START:
            createProgressBar(msg.id, msg.max);
            break;
        case ServerOperations.PROGRESS:
            updateProgressBar(msg.id, msg.value, msg.max);
            break;
        case ServerOperations.FINISH:
            completeProgressBar(msg.id);
            break;
        case ServerOperations.ERROR:
            errorProgressBar(msg.id);
            break;
        case ServerOperations.CANCEL:
            cancelProgressBar(msg.id);
            break;
        case ServerOperations.POOL:
            updatePoolStatus(msg.completed, msg.active, msg.queued);
            break;
        default:
            ;
    }
}


function createProgressBar(id, max) {
    let target = document.getElementById('proc-reports');
    let wrapper = Object.assign(document.createElement('div'), {
        className: 'report-item', id: 'proc_' + id
    });
    wrapper.appendChild(Object.assign(document.createElement('label'), {
        className: 'report-title', innerText: 'Process ' + id
    }));
    cancelBtn = wrapper.appendChild(Object.assign(document.createElement('button'), {
        className: 'report-cancel', id: 'cancel_' + id, innerText: 'X', targetId: id
    }));
    cancelBtn.onclick = function(ev) { cancelProcess(ev.srcElement.targetId); };
    let bar = wrapper.appendChild(Object.assign(document.createElement('div'), {
        className: 'report-bar'
    }));
    bar.appendChild(Object.assign(document.createElement('div'), {
        className: 'report-progress', id: 'bar_' + id, maxValue: max
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


function completeProgressBar(id) {
    let progBar = document.getElementById('bar_' + id);
    if (progBar !== null) {
        let wrapper = progBar.parentElement.parentElement;
        wrapper.removeChild(progBar.parentElement);
        wrapper.removeChild(document.getElementById('cancel_' + id));
        wrapper.appendChild(Object.assign(document.createElement('div'), {
            className: 'report-complete', innerText: 'Completed'
        }));
        delbutton = wrapper.appendChild(Object.assign(document.createElement('button'), {
            className: 'remove-report', innerText: 'X', targetId: 'proc_' + id
        }));
        delbutton.onclick = function(ev) { removeReport(ev.srcElement.targetId); };
    }
    else {
        createProgressBar(id, 1);
        completeProgressBar(id);
    }
}


function cancelProgressBar(id) {
    let progBar = document.getElementById('bar_' + id);
    if (progBar !== null) {
        let wrapper = progBar.parentElement.parentElement;
        wrapper.removeChild(progBar.parentElement);
        wrapper.removeChild(document.getElementById('cancel_' + id));
        wrapper.appendChild(Object.assign(document.createElement('div'), {
            className: 'report-complete', innerText: 'Cancelled'
        }));
        delbutton = wrapper.appendChild(Object.assign(document.createElement('button'), {
            className: 'remove-report', innerText: 'X', targetId: 'proc_' + id
        }));
        delbutton.onclick = function(ev) { removeReport(ev.srcElement.targetId); };
    }
    else {
        createProgressBar(id, 1);
        completeProgressBar(id);
    }
}


function errorProgressBar(id) {
    let progBar = document.getElementById('bar_' + id);
    if (progBar !== null) {
        let wrapper = progBar.parentElement.parentElement;
        wrapper.removeChild(progBar.parentElement);
        wrapper.removeChild(document.getElementById('cancel_' + id));
        wrapper.appendChild(Object.assign(document.createElement('div'), {
            className: 'report-complete', innerText: 'Error'
        }));
        delbutton = wrapper.appendChild(Object.assign(document.createElement('button'), {
            className: 'remove-report', innerText: 'X', targetId: 'proc_' + id
        }));
        delbutton.onclick = function(ev) { removeReport(ev.srcElement.targetId); };
    }
    else {
        createProgressBar(id, 1);
        completeProgressBar(id);
    }
}


function removeReport(id) {
    document.getElementById('proc-reports').removeChild(
        document.getElementById(id)
    );
}


function updatePoolStatus(completed, active, queued) {
    document.getElementById('proc-completed').innerText = completed;
    document.getElementById('proc-active').innerText = active
    document.getElementById('proc-queued').innerText = queued;
}
