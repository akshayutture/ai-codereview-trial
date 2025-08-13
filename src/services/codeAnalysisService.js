import { logger } from '../utils/logger.js';
import { aiService } from './aiService.js';
import { githubService } from './githubService.js';

class CodeAnalysisService {
  constructor() {
    this.analysisTimeout = parseInt(process.env.REVIEW_TIMEOUT_MS) || 30000;
  }

  async analyzeFiles(files, context) {
    const results = [];

    logger.info('Starting code analysis', {
      fileCount: files.length,
      repository: context.repository,
      pr_number: context.pr_number
    });

    for (const file of files) {
      try {
        const analysis = await this.analyzeFile(file, context);
        if (analysis && analysis.length > 0) {
          results.push(...analysis);
        }
      } catch (error) {
        logger.error('Failed to analyze file', {
          filename: file.filename,
          error: error.message,
          repository: context.repository,
          pr_number: context.pr_number
        });
        // Continue with other files even if one fails
      }
    }

    logger.info('Code analysis completed', {
      fileCount: files.length,
      issuesFound: results.length,
      repository: context.repository,
      pr_number: context.pr_number
    });

    return results;
  }

  async analyzeFile(file, context) {
    logger.debug('Analyzing file', {
      filename: file.filename,
      status: file.status,
      additions: file.additions,
      deletions: file.deletions
    });

    // Skip binary files
    if (this.isBinaryFile(file)) {
      logger.debug('Skipping binary file', { filename: file.filename });
      return [];
    }

    // Get the file content and patch
    const fileData = await this.getFileData(file, context);
    if (!fileData) {
      return [];
    }

    // Analyze the code using AI
    const analysisPrompt = this.buildAnalysisPrompt(file, fileData, context);
    const aiResponse = await aiService.analyzeCode(analysisPrompt);

    // Parse the AI response into structured comments
    const comments = this.parseAIResponse(aiResponse, file);

    logger.debug('File analysis completed', {
      filename: file.filename,
      commentsGenerated: comments.length
    });

    return comments;
  }

  async getFileData(file, context) {
    try {
      const [owner, repo] = context.repository.split('/');

      // For new files, we only have the patch
      if (file.status === 'added') {
        return {
          content: null,
          patch: file.patch,
          isNewFile: true
        };
      }

      // For modified files, get the current content
      let content = null;
      try {
        content = await githubService.getFileContent(
          owner,
          repo,
          file.filename,
          'HEAD'
        );
      } catch (error) {
        logger.warn('Could not fetch file content, using patch only', {
          filename: file.filename,
          error: error.message
        });
      }

      return {
        content,
        patch: file.patch,
        isNewFile: false
      };
    } catch (error) {
      logger.error('Failed to get file data', {
        filename: file.filename,
        error: error.message
      });
      return null;
    }
  }

  buildAnalysisPrompt(file, fileData, context) {
    const fileExtension = this.getFileExtension(file.filename);
    const language = this.getLanguageFromExtension(fileExtension);

    return {
      filename: file.filename,
      language,
      status: file.status,
      additions: file.additions,
      deletions: file.deletions,
      content: fileData.content,
      patch: fileData.patch,
      isNewFile: fileData.isNewFile,
      context: {
        repository: context.repository,
        pr_title: context.pr_title,
        pr_description: context.pr_description
      }
    };
  }

  parseAIResponse(aiResponse, file) {
    try {
      // The AI response should be structured JSON with comments
      const parsed = JSON.parse(aiResponse);
      
      if (!parsed.comments || !Array.isArray(parsed.comments)) {
        logger.warn('Invalid AI response format', {
          filename: file.filename,
          response: aiResponse
        });
        return [];
      }

      return parsed.comments.map(comment => ({
        path: file.filename,
        line: comment.line,
        body: comment.body,
        severity: comment.severity || 'info',
        category: comment.category || 'general',
        suggestion: comment.suggestion
      }));
    } catch (error) {
      logger.error('Failed to parse AI response', {
        filename: file.filename,
        error: error.message,
        response: aiResponse
      });
      return [];
    }
  }

  isBinaryFile(file) {
    const binaryExtensions = [
      '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico',
      '.pdf', '.zip', '.tar', '.gz', '.rar',
      '.exe', '.dll', '.so', '.dylib',
      '.woff', '.woff2', '.ttf', '.eot'
    ];

    const extension = this.getFileExtension(file.filename);
    return binaryExtensions.includes(extension) || file.binary;
  }

  getFileExtension(filename) {
    const lastDot = filename.lastIndexOf('.');
    return lastDot === -1 ? '' : filename.substring(lastDot).toLowerCase();
  }

  getLanguageFromExtension(extension) {
    const languageMap = {
      '.js': 'javascript',
      '.jsx': 'javascript',
      '.ts': 'typescript',
      '.tsx': 'typescript',
      '.py': 'python',
      '.java': 'java',
      '.go': 'go',
      '.rs': 'rust',
      '.php': 'php',
      '.rb': 'ruby',
      '.swift': 'swift',
      '.kt': 'kotlin',
      '.c': 'c',
      '.cpp': 'cpp',
      '.h': 'c',
      '.hpp': 'cpp',
      '.cs': 'csharp',
      '.scala': 'scala',
      '.clj': 'clojure'
    };

    return languageMap[extension] || 'text';
  }
}

export const codeAnalysisService = new CodeAnalysisService();
