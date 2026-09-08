# Project Guidelines

- **Language Constraint**: All codebase documentation, comments, variable names, markdown files, and commit messages MUST be written in English. This is to ensure the project remains universally accessible.
- **Git Commit Standards**: Follow the industry-standard "Conventional Commits" specification (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, etc.). You must also commit frequently after every logical change (new feature, bug fix, architecture update, etc.) rather than batching everything into massive commits.
- **Git Push Workflow (MANDATORY)**: After every `git commit`, you MUST immediately run `git push` to sync the changes to the remote GitHub repository. Never leave commits only local. The full workflow for every logical change is:
  1. Stage the relevant files: `git add <files>`
  2. Commit with a proper Conventional Commits message: `git commit -m "feat|fix|chore|docs|refactor|...: <short description>"`
  3. Push to remote immediately: `git push`
  
  Skipping the push step is considered an incomplete workflow and is NOT acceptable.
