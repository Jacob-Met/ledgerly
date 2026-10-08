import {expect, it, vi} from 'vitest';
import {WorkerClient, WorkerUnavailableError} from '../src/worker-client';
import {retryableLoader} from '../src/retryable-loader';

class FakeWorker {
  messages: any[] = [];
  terminated = false;
  throwOnPost = false;
  listeners = new Map<string, Set<(event: any) => void>>();
  addEventListener(type: string, listener: (event: any) => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
  }
  removeEventListener(type: string, listener: (event: any) => void) { this.listeners.get(type)?.delete(listener); }
  postMessage(message: any) {
    if (this.throwOnPost) throw new DOMException('Uncloneable request', 'DataCloneError');
    this.messages.push(message);
  }
  terminate() { this.terminated = true; }
  emit(type: string, event: any = {}) { for (const listener of this.listeners.get(type) || []) listener(event); }
  reply(index: number, data: any) { this.emit('message', {data: {id: this.messages[index].id, ok: true, data}}); }
}

function setup() {
  const workers: FakeWorker[] = [];
  const ready = vi.fn(), unavailable = vi.fn();
  const client = new WorkerClient(() => {
    const worker = new FakeWorker(); workers.push(worker); return worker as unknown as Worker;
  }, {ready, unavailable});
  return {workers, client, ready, unavailable};
}

it('correlates concurrent replies and treats ready as a notification, not an action result', async () => {
  const {workers, client, ready} = setup();
  const init = client.call('init');
  const analyze = client.call('analyze', {text: 'fictional intake'});
  const worker = workers[0];
  worker.emit('message', {data: {type: 'ready'}});
  worker.reply(1, {analysis: 'second'});
  worker.reply(0, {state: 'first'});
  expect(await init).toEqual({state: 'first'});
  expect(await analyze).toEqual({analysis: 'second'});
  expect(ready).toHaveBeenCalledTimes(1);
  expect(workers).toHaveLength(1);
});

it('keeps action errors distinct from a lost worker and permits another explicit request', async () => {
  const {workers, client, unavailable} = setup();
  const init = client.call('init'); workers[0].reply(0, {}); await init;
  const action = client.call('draft');
  const rejected = expect(action).rejects.toThrow('validation failed');
  workers[0].emit('message', {data: {id: workers[0].messages[1].id, ok: false, error: 'validation failed'}});
  await rejected;
  const next = client.call('analyze'); workers[0].reply(2, {ok: true});
  expect(await next).toEqual({ok: true});
  expect(unavailable).not.toHaveBeenCalled();
  expect(workers[0].terminated).toBe(false);
});

it('settles every pending request on a fatal error and does not automatically recreate or replay', async () => {
  const {workers, client, unavailable} = setup();
  const pending = Promise.allSettled([client.call('init'), client.call('draft'), client.call('payment')]);
  const old = workers[0];
  old.emit('error', {message: 'Injected worker failure'});
  const results = await pending;
  expect(results).toHaveLength(3);
  for (const result of results) {
    expect(result.status).toBe('rejected');
    if (result.status === 'rejected') expect(result.reason).toBeInstanceOf(WorkerUnavailableError);
  }
  expect(old.terminated).toBe(true);
  expect(unavailable).toHaveBeenCalledTimes(1);
  await expect(client.call('approve')).rejects.toBeInstanceOf(WorkerUnavailableError);
  expect(workers).toHaveLength(1);
  expect(old.messages.map(message => message.action)).toEqual(['init', 'draft', 'payment']);
  const restarted = client.call('init');
  expect(workers).toHaveLength(2);
  expect(workers[1].messages.map(message => message.action)).toEqual(['init']);
  workers[1].reply(0, {empty: true});
  expect(await restarted).toEqual({empty: true});
});

it('ignores late replies, ready notifications and failures from the discarded connection', async () => {
  const {workers, client, ready, unavailable} = setup();
  const first = client.call('init');
  const rejected = expect(first).rejects.toBeInstanceOf(WorkerUnavailableError);
  const old = workers[0];
  const lateMessage = [...old.listeners.get('message')!][0];
  const lateError = [...old.listeners.get('error')!][0];
  old.emit('error', {message: 'Old worker stopped'}); await rejected;
  let settled = false;
  const replacement = client.call('init').then(result => { settled = true; return result; });
  const currentId = workers[1].messages[0].id;
  lateMessage({data: {type: 'ready'}});
  lateMessage({data: {id: currentId, ok: true, data: {stale: true}}});
  lateError({message: 'Late old error'});
  await Promise.resolve();
  expect(settled).toBe(false);
  expect(ready).not.toHaveBeenCalled();
  expect(unavailable).toHaveBeenCalledTimes(1);
  expect(workers[1].terminated).toBe(false);
  workers[1].reply(0, {fresh: true});
  expect(await replacement).toEqual({fresh: true});
});

it('settles unreadable worker messages as a lost session', async () => {
  const {workers, client, unavailable} = setup();
  const pending = client.call('init');
  const rejected = expect(pending).rejects.toThrow('response could not be read');
  workers[0].emit('messageerror'); await rejected;
  expect(workers[0].terminated).toBe(true);
  expect(unavailable).toHaveBeenCalledTimes(1);
});

it('allows a fresh explicit init after the Worker constructor itself fails', async () => {
  const worker = new FakeWorker(), unavailable = vi.fn();
  let attempts = 0;
  const client = new WorkerClient(() => {
    if (++attempts === 1) throw new Error('Worker construction blocked');
    return worker as unknown as Worker;
  }, {unavailable});
  await expect(client.call('init')).rejects.toThrow('could not start');
  expect(attempts).toBe(1);
  const next = client.call('init'); worker.reply(0, {ready: true});
  expect(await next).toEqual({ready: true});
  expect(attempts).toBe(2);
  expect(unavailable).toHaveBeenCalledTimes(1);
});

it('settles a synchronous postMessage failure without discarding the healthy sandbox', async () => {
  const {workers, client, unavailable} = setup();
  const init = client.call('init'); workers[0].reply(0, {ledger: ['retained']}); await init;
  workers[0].throwOnPost = true;
  await expect(client.call('analyze')).rejects.toThrow('Uncloneable request');
  workers[0].throwOnPost = false;
  const next = client.call('analyze'); workers[0].reply(1, {ledger: ['retained']});
  expect(await next).toEqual({ledger: ['retained']});
  expect(workers).toHaveLength(1);
  expect(workers[0].terminated).toBe(false);
  expect(unavailable).not.toHaveBeenCalled();
});

it('rejects a malformed correlated reply while leaving the running worker usable', async () => {
  const {workers, client} = setup();
  const init = client.call('init');
  const rejected = expect(init).rejects.toThrow('invalid reply');
  workers[0].emit('message', {data: {id: workers[0].messages[0].id, data: 'missing ok'}});
  await rejected;
  const next = client.call('init'); workers[0].reply(1, {ready: true});
  expect(await next).toEqual({ready: true});
});

it('shares one concurrent loader attempt and keeps its successful runtime', async () => {
  let resolve!: (runtime: object) => void;
  const load = vi.fn(() => new Promise<object>(done => { resolve = done; }));
  const boot = retryableLoader(load);
  const first = boot(), second = boot();
  expect(first).toBe(second);
  await Promise.resolve();
  expect(load).toHaveBeenCalledTimes(1);
  const runtime = {same: true}; resolve(runtime);
  expect(await first).toBe(runtime);
  expect(await boot()).toBe(runtime);
  expect(load).toHaveBeenCalledTimes(1);
});

it('shares the failed loader attempt, then retries only when called again', async () => {
  let attempts = 0;
  const boot = retryableLoader(async () => {
    if (++attempts === 1) throw new Error('Transient runtime request failure');
    return {recovered: true};
  });
  const first = boot(), concurrent = boot();
  expect(first).toBe(concurrent);
  await expect(first).rejects.toThrow('Transient runtime request failure');
  expect(attempts).toBe(1);
  expect(await boot()).toEqual({recovered: true});
  expect(attempts).toBe(2);
});

it('also releases a synchronously thrown loader failure for an explicit retry', async () => {
  let attempts = 0;
  const boot = retryableLoader(() => {
    if (++attempts === 1) throw new Error('Synchronous startup failure');
    return Promise.resolve('ready');
  });
  await expect(boot()).rejects.toThrow('Synchronous startup failure');
  expect(await boot()).toBe('ready');
  expect(attempts).toBe(2);
});
