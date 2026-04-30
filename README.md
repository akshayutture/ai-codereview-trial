# ai-codereview-trial

An AI-powered GitHub code review agent prototype. This repository is a sandbox
for experimenting with automated, LLM-driven pull request review and
maintenance workflows.

> **Note:** This is an experimental trial repository. Interfaces, behavior, and
> the surrounding tooling may change without notice. It is not intended for
> production use.

## Overview

The agent is designed to integrate with GitHub via webhooks and the REST API
to:

- Review opened and updated pull requests and post inline feedback
- Answer questions from reviewers in PR comment threads
- Implement requested code changes and push follow-up commits
- Detect failing CI checks and attempt automatic fixes
- Resolve simple merge conflicts when a PR falls behind its base branch

## Tech stack

- **Runtime:** Node.js (>= 18)
- **Framework:** Express for the webhook server
- **GitHub client:** `@octokit/rest`
- **Logging:** `winston`
- **Testing:** Jest with `supertest`
- **Linting:** ESLint (standard config)

## Getting started

```sh
npm install
npm start          # run the agent
npm run dev        # run with nodemon
npm test           # run the Jest test suite
npm run lint       # lint the source tree
```

The service expects standard configuration (GitHub credentials, webhook secret,
etc.) to be supplied via environment variables — see the source for the exact
list as it evolves.

## Status

Early prototype. Expect rough edges and frequent breaking changes.

## License

MIT.
