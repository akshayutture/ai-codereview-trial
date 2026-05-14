import express from 'express';
import helmet from 'helmet';
import cors from 'cors';
import rateLimit from 'express-rate-limit';
import { healthRouter } from './routes/health.js';
import { webhookRouter } from './routes/webhook.js';
import { logger } from './logger.js';

export function createApp() {
  const app = express();

  app.use(helmet());
  app.use(cors());
  app.use(
    rateLimit({
      windowMs: 60 * 1000,
      max: 120,
      standardHeaders: true,
      legacyHeaders: false,
    })
  );

  // Webhook needs the raw body for signature verification, so mount it before
  // the JSON parser and have the route handler parse the buffer itself.
  app.use('/webhook', express.raw({ type: 'application/json' }), webhookRouter);

  app.use(express.json());
  app.use('/health', healthRouter);

  app.use((err, _req, res, _next) => {
    logger.error('unhandled error', { message: err.message, stack: err.stack });
    res.status(500).json({ error: 'internal_server_error' });
  });

  return app;
}
