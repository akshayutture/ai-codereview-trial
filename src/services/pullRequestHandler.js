import { logger } from '../utils/logger.js';
import { githubService } from './githubService.js';
import { codeAnalysisService } from './codeAnalysisService.js';
import { reviewCommentService } from './reviewCommentService.js';

class PullRequestHandler {
  async handle(payload, metadata) {
    const { action, pull_request: pr, repository } = payload;

    // Only process opened and synchronize (updated) PRs
    if (!['opened', 'synchronize'].includes(action)) {
      logger.info(`Ignoring PR action: ${action}`, {
        pr_number: pr.number,
        repository: repository.full_name
      });
      return;
    }

    logger.info('Processing pull request', {
      action,
      pr_number: pr.number,
      repository: repository.full_name,
      author: pr.user.login,
      title: pr.title
    });

    try {
      // Skip if PR is in draft mode (optional)
      if (pr.draft) {
        logger.info('Skipping draft PR', {
          pr_number: pr.number,
          repository: repository.full_name
        });
        return;
      }

      // Skip if PR is from a bot (to avoid infinite loops)
      if (pr.user.type === 'Bot') {
        logger.info('Skipping bot PR', {
          pr_number: pr.number,
          repository: repository.full_name,
          author: pr.user.login
        });
        return;
      }

      // Get the changed files
      const files = await githubService.getPullRequestFiles(
        repository.owner.login,
        repository.name,
        pr.number
      );

      if (files.length === 0) {
        logger.info('No files to review', {
          pr_number: pr.number,
          repository: repository.full_name
        });
        return;
      }

      // Filter files that should be reviewed
      const reviewableFiles = this.filterReviewableFiles(files);

      if (reviewableFiles.length === 0) {
        logger.info('No reviewable files found', {
          pr_number: pr.number,
          repository: repository.full_name,
          total_files: files.length
        });
        return;
      }

      logger.info('Starting code analysis', {
        pr_number: pr.number,
        repository: repository.full_name,
        reviewable_files: reviewableFiles.length,
        total_files: files.length
      });

      // Analyze the code changes
      const analysisResults = await codeAnalysisService.analyzeFiles(
        reviewableFiles,
        {
          repository: repository.full_name,
          pr_number: pr.number,
          pr_title: pr.title,
          pr_description: pr.body
        }
      );

      // Generate and post review comments
      await reviewCommentService.postReviewComments(
        repository.owner.login,
        repository.name,
        pr.number,
        analysisResults
      );

      logger.info('Pull request review completed', {
        pr_number: pr.number,
        repository: repository.full_name,
        comments_posted: analysisResults.length
      });

    } catch (error) {
      logger.error('Failed to process pull request', {
        pr_number: pr.number,
        repository: repository.full_name,
        error: error.message,
        stack: error.stack
      });
      throw error;
    }
  }

  filterReviewableFiles(files) {
    const maxFiles = parseInt(process.env.MAX_FILES_TO_REVIEW) || 20;
    const maxLinesPerFile = parseInt(process.env.MAX_LINES_PER_FILE) || 1000;

    // File extensions to review
    const reviewableExtensions = [
      '.js', '.jsx', '.ts', '.tsx',
      '.py', '.java', '.go', '.rs',
      '.php', '.rb', '.swift', '.kt',
      '.c', '.cpp', '.h', '.hpp',
      '.cs', '.scala', '.clj'
    ];

    // Files to skip
    const skipPatterns = [
      /node_modules/,
      /\.min\./,
      /\.bundle\./,
      /\.lock$/,
      /package-lock\.json$/,
      /yarn\.lock$/,
      /\.log$/,
      /\.md$/,
      /\.txt$/,
      /\.json$/,
      /\.xml$/,
      /\.yml$/,
      /\.yaml$/
    ];

    return files
      .filter(file => {
        // Skip deleted files
        if (file.status === 'removed') return false;

        // Skip files that match skip patterns
        if (skipPatterns.some(pattern => pattern.test(file.filename))) {
          return false;
        }

        // Only include files with reviewable extensions
        const hasReviewableExtension = reviewableExtensions.some(ext => 
          file.filename.toLowerCase().endsWith(ext)
        );
        if (!hasReviewableExtension) return false;

        // Skip files that are too large
        if (file.changes > maxLinesPerFile) {
          logger.warn('Skipping large file', {
            filename: file.filename,
            changes: file.changes,
            max_lines: maxLinesPerFile
          });
          return false;
        }

        return true;
      })
      .slice(0, maxFiles); // Limit total number of files
  }
}

export const pullRequestHandler = new PullRequestHandler();
