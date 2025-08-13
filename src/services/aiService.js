import axios from 'axios';
import { logger } from '../utils/logger.js';

class AIService {
  constructor() {
    this.provider = this.detectProvider();
    this.timeout = parseInt(process.env.REVIEW_TIMEOUT_MS) || 30000;
  }

  detectProvider() {
    if (process.env.OPENAI_API_KEY) {
      return 'openai';
    } else if (process.env.ANTHROPIC_API_KEY) {
      return 'anthropic';
    } else {
      logger.warn('No AI provider configured, using mock responses');
      return 'mock';
    }
  }

  async analyzeCode(prompt) {
    logger.debug('Starting AI code analysis', {
      provider: this.provider,
      filename: prompt.filename,
      language: prompt.language
    });

    try {
      let response;
      
      switch (this.provider) {
        case 'openai':
          response = await this.analyzeWithOpenAI(prompt);
          break;
        case 'anthropic':
          response = await this.analyzeWithAnthropic(prompt);
          break;
        default:
          response = await this.analyzeWithMock(prompt);
      }

      logger.debug('AI analysis completed', {
        provider: this.provider,
        filename: prompt.filename,
        responseLength: response.length
      });

      return response;
    } catch (error) {
      logger.error('AI analysis failed', {
        provider: this.provider,
        filename: prompt.filename,
        error: error.message
      });
      throw error;
    }
  }

  async analyzeWithOpenAI(prompt) {
    const systemPrompt = this.buildSystemPrompt();
    const userPrompt = this.buildUserPrompt(prompt);

    const response = await axios.post(
      'https://api.openai.com/v1/chat/completions',
      {
        model: 'gpt-4',
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt }
        ],
        temperature: 0.1,
        max_tokens: 2000
      },
      {
        headers: {
          'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
          'Content-Type': 'application/json'
        },
        timeout: this.timeout
      }
    );

    return response.data.choices[0].message.content;
  }

  async analyzeWithAnthropic(prompt) {
    const systemPrompt = this.buildSystemPrompt();
    const userPrompt = this.buildUserPrompt(prompt);

    const response = await axios.post(
      'https://api.anthropic.com/v1/messages',
      {
        model: 'claude-3-sonnet-20240229',
        max_tokens: 2000,
        system: systemPrompt,
        messages: [
          { role: 'user', content: userPrompt }
        ]
      },
      {
        headers: {
          'x-api-key': process.env.ANTHROPIC_API_KEY,
          'Content-Type': 'application/json',
          'anthropic-version': '2023-06-01'
        },
        timeout: this.timeout
      }
    );

    return response.data.content[0].text;
  }

  async analyzeWithMock(prompt) {
    // Mock response for testing without AI provider
    logger.info('Using mock AI response', { filename: prompt.filename });
    
    await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate API delay

    return JSON.stringify({
      comments: [
        {
          line: 10,
          body: "🤖 **Mock Review Comment**\\n\\nThis is a mock review comment for testing purposes. In a real implementation, this would contain AI-generated feedback about the code.",
          severity: "info",
          category: "general",
          suggestion: "This is a mock suggestion for improvement."
        }
      ]
    });
  }

  buildSystemPrompt() {
    return `You are an expert code reviewer AI assistant. Your task is to review code changes and provide constructive feedback.

INSTRUCTIONS:
1. Analyze the provided code changes carefully
2. Look for potential issues including:
   - Bugs and logic errors
   - Security vulnerabilities
   - Performance issues
   - Code style and best practices
   - Maintainability concerns
   - Missing error handling
   - Potential edge cases

3. Provide specific, actionable feedback
4. Be constructive and helpful, not just critical
5. Focus on the most important issues first
6. Suggest improvements when possible

RESPONSE FORMAT:
Return your response as valid JSON with this structure:
{
  "comments": [
    {
      "line": <line_number>,
      "body": "<markdown_formatted_comment>",
      "severity": "error|warning|info",
      "category": "bug|security|performance|style|maintainability",
      "suggestion": "<optional_improvement_suggestion>"
    }
  ]
}

GUIDELINES:
- Only comment on lines that actually have issues
- Be specific about what the issue is and why it matters
- Use markdown formatting for better readability
- Include code suggestions when helpful
- If no issues are found, return an empty comments array
- Maximum 5 comments per file to avoid overwhelming the developer`;
  }

  buildUserPrompt(prompt) {
    let content = `Please review this ${prompt.language} file: ${prompt.filename}

**File Status:** ${prompt.status}
**Changes:** +${prompt.additions} -${prompt.deletions}

**Context:**
- Repository: ${prompt.context.repository}
- PR Title: ${prompt.context.pr_title}
- PR Description: ${prompt.context.pr_description || 'No description provided'}

`;

    if (prompt.patch) {
      content += `**Code Changes (Git Patch):**
\`\`\`diff
${prompt.patch}
\`\`\`

`;
    }

    if (prompt.content && !prompt.isNewFile) {
      // For modified files, include relevant context around changes
      content += `**Full File Content (for context):**
\`\`\`${prompt.language}
${prompt.content.substring(0, 5000)}${prompt.content.length > 5000 ? '\n... (truncated)' : ''}
\`\`\`

`;
    }

    content += `Please analyze the code changes and provide feedback focusing on the modified lines. Return your response in the specified JSON format.`;

    return content;
  }
}

export const aiService = new AIService();
