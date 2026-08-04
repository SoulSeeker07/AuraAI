# Contributing to Aura AI

Thank you for your interest in contributing to Aura AI! We welcome contributions from the community to help build a better AI Operating System.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing](#testing)
- [Documentation](#documentation)
- [Feature Requests](#feature-requests)

---

## Code of Conduct

Please be respectful and considerate when interacting with the community. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for our complete guidelines.

---

## Getting Started

### 1. Fork and Clone

Fork the repository and clone your fork:

```bash
git clone https://github.com/yourusername/AuraAI.git
cd AuraAI
```

### 2. Set Up Development Environment

Install dependencies:

```bash
pip install -r requirements.txt
```

Set up development configuration:

```bash
cp settings.json.example settings.json
```

### 3. Run Tests

Run the test suite:

```bash
pytest tests/
```

### 4. Install in Development Mode

```bash
pip install -e .
```

---

## Development Workflow

### Branch Naming Convention

- Use clear, descriptive names: `feature/your-feature-name`, `fix/your-fix-name`, `docs/your-doc-update`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new feature
fix: fix bug
docs: update documentation
style: code style changes
refactor: code refactoring
test: add tests
chore: maintenance tasks
```

### Pull Request Process

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Write code that follows the project structure
   - Add documentation where needed
   - Write tests for new functionality

3. **Commit Changes**
   ```bash
   git commit -m "feat: add new feature"
   ```

4. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Update README.md**
   - Update documentation links if needed
   - Add new features to the features section

---

## Code Style Guidelines

### Python Code Style

- Follow [PEP 8](https://pep8.org/) guidelines
- Use type hints where appropriate
- Write clear, descriptive variable names
- Add docstrings to functions and classes
- Use meaningful commit messages

### Project Structure

- Keep files organized in their respective directories
- Follow the existing naming conventions
- Maintain consistency with the rest of the codebase

### Documentation

- Add comments for complex code
- Document APIs with docstrings
- Update architecture docs when adding new components
- Follow the documentation style in [docs/guides/](docs/guides/)

---

## Testing

### Writing Tests

- Write tests for all new features
- Aim for high test coverage (at least 80%)
- Use descriptive test names
- Test edge cases and error conditions

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/tests/test_specific.py

# Run with coverage
pytest tests/ --cov=aura_ai
```

### Test Organization

- Tests should be in `tests/` directory
- Match the structure of the source code
- Use descriptive test names
- Keep tests independent

---

## Documentation

### Documentation Standards

- Write clear, concise documentation
- Use examples where helpful
- Keep documentation up to date
- Follow markdown formatting

### Documentation Structure

- **Architecture docs**: [docs/architecture/](docs/architecture/)
- **API docs**: [docs/api/](docs/api/)
- **User guides**: [docs/guides/](docs/guides/)
- **Examples**: [docs/examples/](docs/examples/)
- **Milestones**: [docs/milestones/](docs/milestones/)

### Updating Documentation

- Update docs when adding features
- Keep documentation in sync with code
- Add links to new components
- Update ROADMAP.md for new milestones

---

## Feature Requests

### How to Submit Feature Requests

1. Check existing issues and feature requests
2. Search for similar features
3. If it doesn't exist, open a new issue with:
   - Clear title
   - Detailed description
   - Use cases
   - Any relevant examples

### Prioritization

We prioritize features based on:
- Impact on users
- Alignment with roadmap
- Technical feasibility
- Community interest

---

## Code Review Process

### What to Expect

- We aim to review PRs within 48 hours
- Be prepared for feedback and iterations
- Address review comments promptly
- Keep discussions constructive

### Review Checklist

- Code follows project standards
- Tests are included and passing
- Documentation is updated
- No breaking changes to existing APIs
- Code is readable and maintainable

---

## Reporting Issues

### How to Report Bugs

1. Search for existing issues
2. If not found, create a new issue with:
   - Clear title
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Environment details (OS, Python version, etc.)
   - Screenshots if applicable

### Feature Suggestions

Use the same format as bug reports but focus on:
- Clear description
- Use cases
- Proposed implementation (if you have ideas)

---

## Getting Help

- Check existing documentation
- Search GitHub issues
- Ask in GitHub Discussions
- Read CODE_OF_CONDUCT.md

---

## Credits

Thank you for your contributions! Together we can build an amazing AI Operating System.

---

**Questions? Open an issue or start a discussion!**
