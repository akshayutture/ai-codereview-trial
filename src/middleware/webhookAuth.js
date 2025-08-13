import crypto from 'crypto';
import { logger } from '../utils/logger.js';

export const validateWebhookSignature = (req, res, next) => {
  const signature = req.get('X-Hub-Signature-256');
  const payload = JSON.stringify(req.body);
  const secret = process.env.GITHUB_WEBHOOK_SECRET;

  if (!secret) {
    logger.warn('Webhook secret not configured, skipping signature validation');
    return next();
  }

  if (!signature) {
    logger.error('Missing webhook signature');
    return res.status(401).json({ error: 'Missing signature' });
  }

  try {
    const expectedSignature = 'sha256=' + crypto
      .createHmac('sha256', secret)
      .update(payload, 'utf8')
      .digest('hex');

    const isValid = crypto.timingSafeEqual(
      Buffer.from(signature),
      Buffer.from(expectedSignature)
    );

    if (!isValid) {
      logger.error('Invalid webhook signature', {
        received: signature,
        expected: expectedSignature
      });
      return res.status(401).json({ error: 'Invalid signature' });
    }

    logger.debug('Webhook signature validated successfully');
    next();

  } catch (error) {
    logger.error('Signature validation error', {
      error: error.message,
      signature
    });
    return res.status(401).json({ error: 'Signature validation failed' });
  }
};
