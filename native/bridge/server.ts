/** JSON lines only on stdout. No network listeners, filesystem or hardware commands. */
import { Buffer } from 'node:buffer';
import { NativeService, MAX_MESSAGE_BYTES } from './service';

const service = new NativeService();
let pending = Buffer.alloc(0);
for await (const chunk of process.stdin) {
  pending = Buffer.concat([pending, Buffer.from(chunk)]);
  let newline: number;
  while ((newline = pending.indexOf(10)) !== -1) {
    const line = pending.subarray(0, newline);
    pending = pending.subarray(newline + 1);
    if (line.length > MAX_MESSAGE_BYTES) {
      process.exitCode = 1;
      break;
    }
    if (!line.toString('utf8').trim()) continue;
    let response;
    try {
      response = await service.handleRequest(JSON.parse(line.toString('utf8')));
    } catch {
      response = { id: null, error: { message: 'Invalid JSON request' } };
    }
    const output = JSON.stringify(response) + '\n';
    if (!process.stdout.write(output))
      await new Promise<void>((resolve) => process.stdout.once('drain', resolve));
  }
  if (process.exitCode || pending.length > MAX_MESSAGE_BYTES) {
    process.exitCode = 1;
    break;
  }
}
// A truncated last line is rejected instead of partially executing a mutation.
if (pending.length) process.exitCode = 1;
