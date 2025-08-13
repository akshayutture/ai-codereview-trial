import { Octokit } from '@octokit/rest';
import { logger } from '../utils/logger.js';

class GitHubService {
  constructor() {
    this.octokit = new Octokit({
      auth: process.env.GITHUB_TOKEN,
      userAgent: 'github-code-review-agent/1.0.0'
    });
  }

  async getPullRequestFiles(owner, repo, pullNumber) {
    try {
      logger.debug('Fetching PR files', { owner, repo, pullNumber });

      const { data: files } = await this.octokit.pulls.listFiles({
        owner,
        repo,
        pull_number: pullNumber,
        per_page: 100
      });

      logger.debug('Fetched PR files', {
        owner,
        repo,
        pullNumber,
        fileCount: files.length
      });

      return files;
    } catch (error) {
      logger.error('Failed to fetch PR files', {
        owner,
        repo,
        pullNumber,
        error: error.message
      });
      throw error;
    }
  }

  async getFileContent(owner, repo, path, ref) {
    try {
      logger.debug('Fetching file content', { owner, repo, path, ref });

      const { data } = await this.octokit.repos.getContent({
        owner,
        repo,
        path,
        ref
      });

      if (data.type !== 'file') {
        throw new Error(`Path ${path} is not a file`);
      }

      // Decode base64 content
      const content = Buffer.from(data.content, 'base64').toString('utf8');

      logger.debug('Fetched file content', {
        owner,
        repo,
        path,
        ref,
        size: content.length
      });

      return content;
    } catch (error) {
      logger.error('Failed to fetch file content', {
        owner,
        repo,
        path,
        ref,
        error: error.message
      });
      throw error;
    }
  }

  async createReviewComment(owner, repo, pullNumber, comment) {
    try {
      logger.debug('Creating review comment', {
        owner,
        repo,
        pullNumber,
        path: comment.path,
        line: comment.line
      });

      const { data } = await this.octokit.pulls.createReviewComment({
        owner,
        repo,
        pull_number: pullNumber,
        body: comment.body,
        path: comment.path,
        line: comment.line,
        side: comment.side || 'RIGHT'
      });

      logger.info('Created review comment', {
        owner,
        repo,
        pullNumber,
        commentId: data.id,
        path: comment.path,
        line: comment.line
      });

      return data;
    } catch (error) {
      logger.error('Failed to create review comment', {
        owner,
        repo,
        pullNumber,
        comment,
        error: error.message
      });
      throw error;
    }
  }

  async createReview(owner, repo, pullNumber, review) {
    try {
      logger.debug('Creating PR review', {
        owner,
        repo,
        pullNumber,
        event: review.event,
        commentsCount: review.comments?.length || 0
      });

      const { data } = await this.octokit.pulls.createReview({
        owner,
        repo,
        pull_number: pullNumber,
        body: review.body,
        event: review.event,
        comments: review.comments
      });

      logger.info('Created PR review', {
        owner,
        repo,
        pullNumber,
        reviewId: data.id,
        event: review.event
      });

      return data;
    } catch (error) {
      logger.error('Failed to create PR review', {
        owner,
        repo,
        pullNumber,
        review,
        error: error.message
      });
      throw error;
    }
  }

  async addLabels(owner, repo, issueNumber, labels) {
    try {
      logger.debug('Adding labels to issue', {
        owner,
        repo,
        issueNumber,
        labels
      });

      const { data } = await this.octokit.issues.addLabels({
        owner,
        repo,
        issue_number: issueNumber,
        labels
      });

      logger.info('Added labels to issue', {
        owner,
        repo,
        issueNumber,
        labels
      });

      return data;
    } catch (error) {
      logger.error('Failed to add labels', {
        owner,
        repo,
        issueNumber,
        labels,
        error: error.message
      });
      throw error;
    }
  }

  async getRepository(owner, repo) {
    try {
      const { data } = await this.octokit.repos.get({
        owner,
        repo
      });

      return data;
    } catch (error) {
      logger.error('Failed to fetch repository', {
        owner,
        repo,
        error: error.message
      });
      throw error;
    }
  }
}

export const githubService = new GitHubService();
