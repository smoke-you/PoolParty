let sock = new WebSocket('ws://' + location.host + '/ws')
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
    let wrapper = Object.assign(document.createElement('div'), {
        className: 'report-item', id: 'proc_' + id
    });
    wrapper.appendChild(Object.assign(document.createElement('label'), {
        className: 'report-title', innerText: 'Process ' + id
    }));
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
        wrapper.appendChild(Object.assign(document.createElement('div'), {
            className: 'report-complete', innerText: 'Completed'
        }));
        delbutton = wrapper.appendChild(Object.assign(document.createElement('button'), {
            className: 'remove-complete', innerText: 'X', targetId: id
        }));
        delbutton.onclick = function(ev) { removeReport(ev); };
    }
    else {
        createProgressBar(id, 1);
        completeProgressBar(id);
    }
}


function removeReport(ev) {
    document.getElementById('proc-reports').removeChild(
        document.getElementById('proc_' + ev.srcElement.targetId)
    );
}


function updatePoolStatus(completed, active, queued) {
    document.getElementById('proc-completed').innerText = completed;
    document.getElementById('proc-active').innerText = active
    document.getElementById('proc-queued').innerText = queued;
}
