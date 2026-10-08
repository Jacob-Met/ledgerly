type Reply = {id?: number; type?: string; ok?: boolean; data?: any; error?: string};
type Pending = {resolve: (value: any) => void; reject: (error: Error) => void};
type WorkerPort = Pick<Worker, 'addEventListener' | 'removeEventListener' | 'postMessage' | 'terminate'>;
type Connection = {
  worker: WorkerPort;
  message: (event: MessageEvent<Reply>) => void;
  error: (event: ErrorEvent) => void;
  messageerror: () => void;
};

export class WorkerUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'WorkerUnavailableError';
  }
}

/** A failed worker is replaced only by an explicit init request. No action is replayed. */
export class WorkerClient {
  private connection?: Connection;
  private nextId = 0;
  private pending = new Map<number, Pending>();

  constructor(
    private readonly createWorker: () => WorkerPort,
    private readonly events: {
      ready?: () => void;
      unavailable?: (error: WorkerUnavailableError) => void;
    } = {},
  ) {}

  call(action: string, payload: Record<string, unknown> = {}): Promise<any> {
    return new Promise((resolve, reject) => {
      let connection = this.connection;
      if (!connection) {
        if (action !== 'init') {
          reject(new WorkerUnavailableError('Load the local Python engine before running an action.'));
          return;
        }
        try {
          connection = this.connect();
        } catch (error) {
          const unavailable = new WorkerUnavailableError(`The Python worker could not start: ${String(error)}`);
          reject(unavailable);
          this.events.unavailable?.(unavailable);
          return;
        }
      }
      const id = ++this.nextId;
      this.pending.set(id, {resolve, reject});
      try {
        connection.worker.postMessage({id, action, payload});
      } catch (error) {
        // Structured-clone failures do not establish that the running sandbox was lost.
        this.pending.delete(id);
        reject(error instanceof Error ? error : new Error(String(error)));
      }
    });
  }

  private connect(): Connection {
    const worker = this.createWorker();
    const connection: Connection = {
      worker,
      message: event => {
        if (this.connection !== connection) return;
        const message = event.data;
        if (!message || typeof message !== 'object') return;
        if (message.type === 'ready') {
          this.events.ready?.();
          return;
        }
        const task = this.pending.get(message.id || 0);
        if (!task) return;
        this.pending.delete(message.id || 0);
        if (typeof message.ok !== 'boolean') task.reject(new Error('The Python worker returned an invalid reply.'));
        else if (message.ok) task.resolve(message.data);
        else task.reject(new Error(message.error || 'The Python action failed.'));
      },
      error: event => this.fail(connection, `The Python worker stopped: ${event.message || 'worker script failure'}`),
      messageerror: () => this.fail(connection, 'The Python worker response could not be read.'),
    };
    this.connection = connection;
    worker.addEventListener('message', connection.message);
    worker.addEventListener('error', connection.error);
    worker.addEventListener('messageerror', connection.messageerror);
    return connection;
  }

  private fail(connection: Connection, message: string): void {
    if (this.connection !== connection) return;
    this.connection = undefined;
    const {worker} = connection;
    worker.removeEventListener('message', connection.message);
    worker.removeEventListener('error', connection.error);
    worker.removeEventListener('messageerror', connection.messageerror);
    worker.terminate();
    const error = new WorkerUnavailableError(message);
    const pending = [...this.pending.values()];
    this.pending.clear();
    for (const request of pending) request.reject(error);
    this.events.unavailable?.(error);
  }
}
