const sock = new WebSocket('ws://' + location.host + '/ws')
sock.onmessage = handleWebsocketMessage;


function startProcess() {
    let msg = {};
    msg.op = 'start';
    sock.send(JSON.stringify(msg));
}


function clearHistory() {
    const target = document.getElementById('proc_reports');
    target.innerHTML = '';
}


function handleWebsocketMessage(event) {
    const data = JSON.parse(event.data);
    // console.log(data);
    switch(data.op) {
        case 'start':
            createProgressBar(data.id, 'Blue', data.max);
            break;
        case 'progress':
            updateProgressBar(data.id, data.value);
            break;
        case 'finish':
            completeProgressBar(data.id);
            break;
        case 'error':
            break;
        default:
            ;
    }
}


function createProgressBar(id, color, max) {
    let cell = document.getElementById('proc_reports').insertRow(0).insertCell(0);
    let baseDiv = cell.appendChild(Object.assign(document.createElement('div'), { 
        className: 'progress-bar'
    }));
    baseDiv.appendChild(Object.assign(document.createElement('div'), { 
        className: 'progress-text', innerText: id
    }));
    let barDiv = baseDiv.appendChild(Object.assign(document.createElement('div'), {
        className: 'progress-value', id: 'proc_' + id, maxValue: max
    }));
    Object.assign(barDiv.style, {backgroundColor: color, width: '0px'})
    baseDiv.appendChild(barDiv);
}


function updateProgressBar(id, value) {
let progbar = document.getElementById('proc_' + id);
progbar.style.width = (value * 200 / progbar.maxValue) + 'px';
}


function completeProgressBar(id) {
let progbar = document.getElementById('proc_' + id);
progbar.style.width = '200px';
progbar.style.backgroundColor = 'Green';
}
