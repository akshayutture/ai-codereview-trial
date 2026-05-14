import { logger } from '../logger.js';

// Stub event router. Real review logic will be added in follow-up PRs;
// for now we just log so the service can be wired end-to-end.
export async function handleEvent({ event, delivery, payload }) {
  switch (event) {
    case 'ping':
      logger.info('received ping', { delivery, zen: payload.zen });
      return;
    case 'pull_request':
      logger.info('received pull_request', {
        delivery,
        action: payload.action,
        number: payload.pull_request?.number,
        repo: payload.repository?.full_name,
      });
      return;
    default:
      logger.info('received event', { delivery, event });
  }
}
