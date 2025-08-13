import express from 'express';
import { webhookHandler } from '../services/webhookHandler.js';
import { validateWebhookSignature } from '../middleware/webhookAuth.js';
import { logger } from '../utils/logger.js';

const router = express.Router();

// GitHub webhook endpoint
router.post('/github', validateWebhookSignature, async (req, res) => {
  try {
    const event = req.get('X-GitHub-Event');
    const delivery = req.get('X-GitHub-Delivery');
    
    logger.info('Webhook received', {
      event,
      delivery,
      action: req.body.action,
      repository: req.body.repository?.full_name
    });

    // Handle the webhook event
    await webhookHandler.handle(event, req.body, {
      delivery,
      signature: req.get('X-Hub-Signature-256')
    });

    res.status(200).json({ 
      message: 'Webhook processed successfully',
      delivery 
    });

  } catch (error) {
    logger.error('Webhook processing failed', {
      error: error.message,
      stack: error.stack,
      delivery: req.get('X-GitHub-Delivery')
    });

    res.status(500).json({ 
      error: 'Webhook processing failed',
      delivery: req.get('X-GitHub-Delivery')
    });
  }
});

export { router as webhookRouter };
