# AlgoTrade Pro - Contribution Guidelines

## Code Style

### Python (Backend)
- Follow PEP 8 guidelines
- Use type hints for function arguments and returns
- Use meaningful variable names
- Maximum line length: 100 characters
- Use docstrings for all functions and classes

```python
async def place_order(
    self,
    order: OrderData,
    max_retries: int = 3
) -> OrderResponse:
    """
    Place a trading order through broker API.
    
    Args:
        order: OrderData object with trade details
        max_retries: Maximum number of retry attempts
        
    Returns:
        OrderResponse with execution status
        
    Raises:
        BrokerException: If order placement fails
    """
    pass
```

### JavaScript/React (Frontend)
- Use ES6+ syntax
- Use functional components with hooks
- Use meaningful prop names
- Use Tailwind CSS for styling
- Export components as default

```jsx
export default function OrderForm({ onSubmit }) {
  const [formData, setFormData] = useState({
    symbol: '',
    quantity: '',
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    await onSubmit(formData);
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* form fields */}
    </form>
  );
}
```

## Git Workflow

1. Create feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -m "Add feature: description"`
3. Push to branch: `git push origin feature/your-feature`
4. Create Pull Request with detailed description

## Commit Messages

```
feat: Add moving average crossover strategy
fix: Fix order execution timeout issue
docs: Update broker integration guide
test: Add tests for risk manager
chore: Update dependencies
```

## Testing Requirements

- All new features must have tests
- Maintain >80% code coverage
- Run `pytest` before submitting PR
- Test both success and error cases

## Documentation

- Update README.md for new features
- Add docstrings to all functions
- Include usage examples
- Update API documentation

## Performance Guidelines

- Use async/await for I/O operations
- Implement proper error handling
- Avoid blocking operations
- Cache frequently accessed data
- Monitor logging overhead

## Security Considerations

- Never commit credentials to repository
- Use .env for sensitive data
- Encrypt sensitive information
- Validate all user inputs
- Follow OWASP guidelines

## Code Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests pass and coverage maintained
- [ ] Documentation is updated
- [ ] No hardcoded credentials
- [ ] Error handling is comprehensive
- [ ] Performance considerations addressed
- [ ] Security best practices followed

## Questions?

Open an issue or start a discussion in the GitHub repository.

---

Thank you for contributing to AlgoTrade Pro! 🚀
