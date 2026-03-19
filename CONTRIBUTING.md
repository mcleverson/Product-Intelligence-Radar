# Contributing to DBaaS Intelligence Radar

Thank you for considering a contribution! Here are some guidelines:

## How to Report Bugs

- Use GitHub Issues to report bugs
- Describe the bug clearly and concisely
- Provide code examples if possible
- Include Python version and operating system

## How to Suggest Features

- Use GitHub Issues with `enhancement` tag
- Clearly describe the use case
- Explain why this feature would be useful
- List possible alternatives

## Pull Request Process

1. **Fork the repository** and create a branch from `main`:
   ```bash
   git checkout -b feature/your-feature
   ```

2. **Implement your change:**
   - Keep commits small and descriptive
   - Add comments for complex code
   - Update documentation if necessary

3. **Test locally:**
   ```bash
   python Extractor.py
   # or
   jupyter notebook Extractor.ipynb
   ```

4. **Add tests** if you wrote new code

5. **Commit and push:**
   ```bash
   git add .
   git commit -m "Clear description of the change"
   git push origin feature/your-feature
   ```

6. **Open a Pull Request:**
   - Describe the changes
   - Reference related issues (fixes #123)
   - Explain the reason for the change

## Code Standards

- Use type hints in functions:
  ```python
  def my_function(param: str) -> Dict[str, Any]:
      """Clear docstring."""
      return {}
  ```

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)

- Write docstrings in English:
  ```python
  def normalize_text(text: str) -> str:
      """
      Normalize text by removing noise.
      Removes timestamps, extra spaces, etc.
      
      Args:
          text: Text to normalize
          
      Returns:
          Normalized text
      """
  ```

## Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/dbaas-intelligence-radar.git
cd dbaas-intelligence-radar

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your values
```

## Branch Structure

- `main`: Production-ready code
- `develop`: Active development
- `feature/feature-name`: New feature
- `fix/bug-name`: Bug fix
- `docs/doc-name`: Documentation changes

## Commit Convention

```
[type]: brief description

longer description if necessary

Fixes #123
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Formatting, no logic change
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Test additions

## Questions?

- Open an issue with `question` tag
- Discuss in related PRs

Thank you again for contributing! 🙌

