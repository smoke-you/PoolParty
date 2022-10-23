# FastThread
Yes, it's not really a contextually-accurate project name.

## Background
I have a project for work, for which I need to be able to trigger multiple instances of server-side work (parsing and transforming uploaded files), and provide feedback to the user (a progress bar) for each file. It's an interesting problem because it pulls together a lot of (ahem) threads, including:
- A webserver, with which to present the UI (I've used `fastAPI`, because I like it).
- Websockets, with which to sustain a single-page web application.
- Multiprocessing, to allow multiple files to be parsed simultaneously.
- Inter-process communications, to allow the parsing workers to:
  - Provide updates (progress, errors, etc).
  - Be cancelled by users.

I've spent a fair bit of time messing around with it outside of work because it's a good learning exercise (I'm a bit of a Python and webserver newb, and I was right, I learnt a lot).  Also, I will able to take `WorkManager` and drop it straight into my work project, which is very convenient.

## Stumbling Blocks
I started with [`multiprocessing.Pool`](https://docs.python.org/3/library/multiprocessing.html#module-multiprocessing.pool) and tried to use `Queue` instances for IPC. Fail. It turns out:
- You can't pickle `Queue`, so it can't be passed to the worker processes.
- `fastAPI` can't tolerate other processes (or async loops) being started before it completes initialization.

I was able to get around the first problem by using `multiprocessing.Manager().Queue()` instances, as noted (but not really explained) [here](https://docs.python.org/3/library/multiprocessing.html#pipes-and-queues). The second can be solved by defining a `fastAPI` startup event using the `@app.on_event('startup')` decorator and delay instantiation of the `Pool` until the startup event fires. This worked, with a couple of caveats:
- The `Manager().Queue()` instances passed to the workers would intermittently throw exceptions when `put()` was called, complaining that a `None` type 
  could not be interpreted as an `int`. Sure... but I didn't pass you a `None` in any of your args, so... huh?  (*This smells like an actual bug in the `Manager().Queue()` library code. I should probably report it :-)*)
- There is no way to cancel work queued for a `Pool`.
  - Yes, you can terminate the `Pool`, but... it seems a bit heavy-handed, no?

## The Solution as it Stands
Looking for an alternative to `Pool` (that didn't involve me writing my own process pool library!), I found [`concurrent.futures.ProcessPoolExecutor`](https://docs.python.org/3/library/concurrent.futures.html?#processpoolexecutor). It offers roughly the same services as `multiprocessing.Pool`, with several additions, not least the ability to call `cancel` on the `Future` objects returned by `submit()`. As usual, there is a caveat:
- You can't cancel work items that have been started. Fair enough.
  - <a name="cancel-issue"></a>The first five (?) work items that have been queued but not actually started are placed in an intermediate state (preloaded in some way?) such that they *also* can't be cancelled. This is quite inconvenient, but addressable - see [below](#cancel-solution).

I was also not happy with `Queue`, largely because of the `None` bug.  My alternative, which also makes me nervous because of scalability concerns, but which appears to work perfectly well with up to at least 40 or so queued work items, was to create a `multiprocessing.Pipe` with every work item.  The various components of each work item - a sequence number; the `Future` and `Connection[0]` from the `Pipe` are stored as a `WorkItem` in a list local to the `WorkManager` instance, and `Connection[1]` is passed to the work item as an argument; this allows the `Pipe` to be used for IPC when the work item moves from queued to running.

## Communications (Websocket and IPC)
The webserver communication model is "single page", i.e. a single GET is used to load the client page (yes, there are more GET's for JS, CSS, etc, but that's not the point). Javascript is used to open a websocket to the fastAPI instance at the server. Messages are then passed as JSONified `dict` (or, from the JS perspective, `object`) instances.  Messages contain an `op` field, which is one of `start`, `finish`, `progress`, `error`, `cancel`, or `pool` (the client can only send `start` and `cancel` messages).

Work is queued by the client sending a `start` message.  This creates a new `WorkItem`, including a `Future` and `Pipe`. <a name="cancel-solution"></a>When the work item begins executing, it first checks its `Connection` for a `cancel` message (to deal with the issue noted [above](#cancel-issue)), and if one is waiting in the `Connection` then it emits a `cancel` message and immediately terminates.

If the work item is not immediately cancelled, it emits a `start` message, then periodically emits `progress` messages, and finally a `finish` message if it completes normally or an `error` message if it does not. The work item must also periodically check its `Connection` for `cancel` messages and respond as above.

The `WorkManager` monitors the `Connection` instances of all its queued work items, sniffing them for work `start` and completion (`finish`, `cancel`, `error`), and uses the [`ConnectionManager`](https://fastapi.tiangolo.com/advanced/websockets/#handling-disconnections-and-multiple-clients) to broadcast them to all attached clients. It also broadcasts its current state, e.g. number of active and queued work items, using `pool` messages

## Weaknesses and Possible Solutions
I'm really not a fan of creating a `Pipe` for every work item. Ideally, I would create one `Pipe` for each worker process instantiated by the `ProcessPoolExecutor` and the worker-side `Connection` of that `Pipe` would be passed to the work item when it begins to run. However, there does not seem to be a way to do this.  I'm considering a couple of alternatives:
- Probing
  - When initializing the `WorkManager`, start each worker process with a `probe()` worker that simply returns the `os.pid`
  - Create a `Pipe` for each worker process and associate its `Connection[1]` (via a tuple) with the returned `PID`.
  - When a work item starts, pass it *all* of the (`PID`,`Connection`) tuples; it is then responsible for using *only* the `Connection` that matches its own `os.pid`.
- [`multiprocessing.Listener`](https://docs.python.org/3/library/multiprocessing.html#module-multiprocessing.connection) + `multiprocessing.Client` -> `Connection`:
  - The `WorkManager` instantiates a `Listener`.
  - When work items are queued, their arguments include connection parameters for the `Listener`.
  - When a work item starts, it instantiates a `Client` and connects to the `Listener`, creating a `Connection`.

Of course, both of these options mean that there is no existing communications channel into which pre-emptive `cancel` messages can be broadcast, hence the initial `start` message can't be (directly) suppressed, although it could still be caught by the `WorkManager` and not broadcast to the web clients (on the basis that the work item sequence number is not in the list of current work items).  That's probably a better solution than dozens of `Pipe` instances, but I haven't made my mind up yet.
