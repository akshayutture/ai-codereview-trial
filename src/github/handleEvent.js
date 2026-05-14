import { logger } from '../logger.js';

// Stub event router. Real review logic will be added in follow-up PRs;
// for now we just log so the service can be wired end-to-end.
export async function handleEvent({ event, delivery, payload }) {
  const repo = payload.repository?.full_name;

  switch (event) {
    case 'ping':
      logger.info('received ping', { delivery, zen: payload.zen });
      return;
    case 'pull_request':
      logger.info('received pull_request', {
        delivery,
        repo,
        action: payload.action,
        number: payload.pull_request?.number,
      });
      return;
    case 'pull_request_review':
      logger.info('received pull_request_review', {
        delivery,
        repo,
        action: payload.action,
        number: payload.pull_request?.number,
        state: payload.review?.state,
      });
      return;
    case 'pull_request_review_comment':
      logger.info('received pull_request_review_comment', {
        delivery,
        repo,
        action: payload.action,
        number: payload.pull_request?.number,
        path: payload.comment?.path,
      });
      return;
    case 'issue_comment':
      logger.info('received issue_comment', {
        delivery,
        repo,
        action: payload.action,
        number: payload.issue?.number,
        is_pr: Boolean(payload.issue?.pull_request),
      });
      return;
    case 'issues':
      logger.info('received issues', {
        delivery,
        repo,
        action: payload.action,
        number: payload.issue?.number,
      });
      return;
    case 'push':
      logger.info('received push', {
        delivery,
        repo,
        ref: payload.ref,
        commits: payload.commits?.length ?? 0,
      });
      return;
    case 'check_run':
      logger.info('received check_run', {
        delivery,
        repo,
        action: payload.action,
        name: payload.check_run?.name,
        status: payload.check_run?.status,
        conclusion: payload.check_run?.conclusion,
      });
      return;
    case 'check_suite':
      logger.info('received check_suite', {
        delivery,
        repo,
        action: payload.action,
        status: payload.check_suite?.status,
        conclusion: payload.check_suite?.conclusion,
      });
      return;
    case 'installation':
    case 'installation_repositories':
      logger.info(`received ${event}`, {
        delivery,
        action: payload.action,
        installation_id: payload.installation?.id,
      });
      return;
    default:
      logger.info('received event', { delivery, repo, event });
  }
}
