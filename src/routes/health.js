import express from 'express';
import { logger } from '../utils/logger.js';

const router = express.Router();

router.get('/', (req, res) => {
  const healthCheck = {
    status: 'OK',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    environment: process.env.NODE_ENV || 'development',
    version: '1.0.0',
    checks: {
      github_token: !!process.env.GITHUB_TOKEN,
      webhook_secret: !!process.env.GITHUB_WEBHOOK_SECRET,
      ai_service: !!(process.env.OPENAI_API_KEY || process.env.ANTHROPIC_API_KEY)
    }
  };

  logger.info('Health check requested', { 
    ip: req.ip,
    userAgent: req.get('User-Agent')
  });

  res.json(healthCheck);
});

export { router as healthRouter };
