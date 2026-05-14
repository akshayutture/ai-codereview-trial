import { createHmac } from 'node:crypto';
import { verifySignature } from '../src/github/verifySignature.js';

const secret = 'test-secret';
const body = Buffer.from(JSON.stringify({ hello: 'world' }));

function sign(b) {
  return 'sha256=' + createHmac('sha256', secret).update(b).digest('hex');
}

describe('verifySignature', () => {
  test('accepts a valid signature', () => {
    expect(verifySignature(secret, body, sign(body))).toBe(true);
  });

  test('rejects a bad signature', () => {
    expect(verifySignature(secret, body, 'sha256=deadbeef')).toBe(false);
  });

  test('rejects a missing or malformed header', () => {
    expect(verifySignature(secret, body, undefined)).toBe(false);
    expect(verifySignature(secret, body, 'md5=abc')).toBe(false);
  });
});
