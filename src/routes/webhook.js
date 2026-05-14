import { Router } from 'express';
import { verifySignature } from '../github/verifySignature.js';
import { handleEvent } from '../github/handleEvent.js';
import { logger } from '../logger.js';

export const webhookRouter = Router();

webhookRouter.post('/', async (req, res) => {
  const signature = req.get('x-hub-signature-256');
  const event = req.get('x-github-event');
  const delivery = req.get('x-github-delivery');
  const secret = process.env.GITHUB_WEBHOOK_SECRET;

  const rawBody = req.body instanceof Buffer ? req.body : Buffer.from('');

  if (secret && !verifySignature(secret, rawBody, signature)) {
    logger.warn('rejected webhook with invalid signature', { delivery, event });
    return res.status(401).json({ error: 'invalid_signature' });
  }

  let payload;
  try {
    payload = JSON.parse(rawBody.toString('utf8') || '{}');
  } catch (err) {
    logger.warn('rejected webhook with invalid JSON', { delivery, event });
    return res.status(400).json({ error: 'invalid_json' });
  }

  try {
    await handleEvent({ event, delivery, payload });
    return res.status(202).json({ accepted: true });
  } catch (err) {
    logger.error('webhook handler error', { message: err.message, event, delivery });
    return res.status(500).json({ error: 'handler_error' });
  }
});
