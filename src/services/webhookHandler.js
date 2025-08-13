import { logger } from '../utils/logger.js';
import { pullRequestHandler } from './pullRequestHandler.js';

class WebhookHandler {
  constructor() {
    this.handlers = {
      'pull_request': pullRequestHandler,
      'pull_request_review': this.handlePullRequestReview.bind(this),
      'pull_request_review_comment': this.handlePullRequestReviewComment.bind(this)
    };
  }

  async handle(event, payload, metadata) {
    const handler = this.handlers[event];
    
    if (!handler) {
      logger.info(`No handler for event: ${event}`, {
        event,
        action: payload.action,
        delivery: metadata.delivery
      });
      return;
    }

    try {
      await handler(payload, metadata);
      logger.info(`Successfully handled ${event} event`, {
        event,
        action: payload.action,
        delivery: metadata.delivery
      });
    } catch (error) {
      logger.error(`Failed to handle ${event} event`, {
        event,
        action: payload.action,
        error: error.message,
        delivery: metadata.delivery
      });
      throw error;
    }
  }

  async handlePullRequestReview(payload, metadata) {
    logger.info('Pull request review event received', {
      action: payload.action,
      review_state: payload.review?.state,
      pr_number: payload.pull_request?.number,
      repository: payload.repository?.full_name
    });

    // Handle review events (submitted, edited, dismissed)
    // This could be used to respond to human reviews or update agent status
  }

  async handlePullRequestReviewComment(payload, metadata) {
    logger.info('Pull request review comment event received', {
      action: payload.action,
      comment_id: payload.comment?.id,
      pr_number: payload.pull_request?.number,
      repository: payload.repository?.full_name
    });

    // Handle review comment events
    // This could be used to respond to specific feedback or questions
  }
}

export const webhookHandler = new WebhookHandler();
