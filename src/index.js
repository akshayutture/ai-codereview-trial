import 'dotenv/config';
import { createApp } from './app.js';
import { logger } from './logger.js';

const port = Number(process.env.PORT) || 3000;

const app = createApp();

const server = app.listen(port, () => {
  logger.info(`code-review agent listening on port ${port}`);
});

const shutdown = (signal) => {
  logger.info(`received ${signal}, shutting down`);
  server.close(() => process.exit(0));
};

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
