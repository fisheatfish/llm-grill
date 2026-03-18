---
name: "Test Specialist"
description: "Python testing expert with pytest. Refactors, documents, and improves tests. Uses Given/When/Then pattern, pytest-mock (not unittest.mock), and best practices. Invoke for test review, refactoring, or creating new tests."
---

# Test Specialist

## What This Skill Does

Python testing specialist that:
1. **Documents** tests with clear docstrings
2. **Refactors** for readability and maintainability
3. **Applies Given/When/Then** pattern to structure tests
4. **Uses pytest-mock** (never unittest.mock)

---

## Core Rules

### 1. Given/When/Then Pattern

Every test MUST follow this structure:

```python
def test_should_do_something_when_condition(self, mocker):
    """
    Should [expected behavior] when [condition].

    Given: [initial state/setup]
    When: [action performed]
    Then: [expected result]
    """
    # Given: Setup initial state
    mock_service = mocker.Mock()
    mock_service.get_data.return_value = {"key": "value"}

    # When: Execute the action
    result = my_function(mock_service)

    # Then: Assert expected behavior
    assert result == expected_value
    mock_service.get_data.assert_called_once()
```

### 2. Test Naming

```python
# ✅ GOOD: Describes expected behavior
def test_should_return_none_when_no_purchases_exist(self):
def test_should_raise_error_when_db_connection_fails(self):
def test_should_skip_purchase_when_all_periods_bullish(self):

# ❌ BAD: Too vague or technical
def test_get_data(self):
def test_error(self):
def test_function1(self):
```

### 3. pytest-mock (MANDATORY)

```python
# ✅ GOOD: Use mocker from pytest-mock
def test_example(self, mocker):
    mock_client = mocker.Mock()
    mocker.patch("module.ClassName", return_value=mock_client)

# ❌ BAD: Never use unittest.mock directly
from unittest.mock import Mock, patch  # FORBIDDEN
```

### 4. pytest Fixtures

```python
# ✅ GOOD: Reusable fixtures
@pytest.fixture
def mock_db_session(mocker):
    """Create a mock database session."""
    session = mocker.Mock()
    session.query.return_value.filter.return_value.first.return_value = None
    return session

# ✅ GOOD: Use fixtures in tests
def test_should_create_user(self, mock_db_session):
    # Given
    user_data = {"name": "John"}

    # When
    result = create_user(mock_db_session, user_data)

    # Then
    mock_db_session.add.assert_called_once()
```

---

## Test File Structure

```python
"""
Tests for [module/class name].
Tests [what is being tested] with focus on [key behaviors].
"""

from decimal import Decimal

import pytest

from mymodule import MyClass


class TestMyClassInitialization:
    """Tests for MyClass initialization and setup."""

    def test_should_initialize_with_default_values(self, mocker):
        """
        Should initialize with sensible defaults when no args provided.

        Given: No constructor arguments
        When: Creating a new instance
        Then: Default values are set correctly
        """
        # Given
        # (no setup needed)

        # When
        instance = MyClass()

        # Then
        assert instance.value == 0
        assert instance.name is None

    def test_should_raise_when_invalid_config(self, mocker):
        """
        Should raise ValueError when configuration is invalid.

        Given: Invalid configuration values
        When: Attempting to initialize
        Then: ValueError is raised with descriptive message
        """
        # Given
        invalid_config = {"value": -1}

        # When / Then
        with pytest.raises(ValueError, match="must be positive"):
            MyClass(**invalid_config)


class TestMyClassBusinessLogic:
    """Tests for core business logic."""

    @pytest.fixture
    def configured_instance(self, mocker):
        """Create a properly configured instance for testing."""
        mocker.patch("mymodule.external_service")
        return MyClass(value=100)

    def test_should_calculate_correctly(self, configured_instance):
        """
        Should return correct calculation result.

        Given: Instance with value=100
        When: Calling calculate()
        Then: Returns expected result
        """
        # Given
        instance = configured_instance

        # When
        result = instance.calculate()

        # Then
        assert result == Decimal("100.00")


class TestMyClassErrorHandling:
    """Tests for error handling scenarios."""

    def test_should_handle_connection_error_gracefully(self, mocker):
        """
        Should return None and log error when connection fails.

        Given: External service raises ConnectionError
        When: Calling fetch_data()
        Then: Returns None without raising
        """
        # Given
        mock_service = mocker.patch("mymodule.external_service")
        mock_service.fetch.side_effect = ConnectionError("timeout")
        instance = MyClass()

        # When
        result = instance.fetch_data()

        # Then
        assert result is None
```

---

## Refactoring Checklist

When refactoring tests, verify:

### Structure
- [ ] Each test has a name `test_should_X_when_Y`
- [ ] Each test has a docstring with Given/When/Then
- [ ] Tests grouped by thematic class (`TestClassInit`, `TestClassLogic`, etc.)
- [ ] File starts with a docstring describing what's being tested

### Mocks
- [ ] Uses `mocker` from pytest-mock, not `unittest.mock`
- [ ] Mocks injected via fixture parameters, not decorators
- [ ] `mocker.patch()` instead of `@patch`
- [ ] `mocker.Mock()` instead of `Mock()`

### Assertions
- [ ] One concept tested per test (no giant tests)
- [ ] Explicit error messages if needed
- [ ] `pytest.raises` for exceptions
- [ ] Mock call verification with `assert_called_once()`, etc.

### Fixtures
- [ ] Fixtures for repetitive setup
- [ ] Fixtures documented with docstrings
- [ ] Appropriate scope (`function`, `class`, `module`, `session`)

---

## Common Patterns

### Mocking a class

```python
def test_should_use_client(self, mocker):
    # Given
    mock_client_class = mocker.patch("mymodule.Client")
    mock_client = mock_client_class.return_value
    mock_client.fetch.return_value = {"data": "value"}

    # When
    result = my_function()

    # Then
    mock_client.fetch.assert_called_once_with("key")
```

### Mocking a method

```python
def test_should_call_method(self, mocker):
    # Given
    instance = MyClass()
    mocker.patch.object(instance, "internal_method", return_value=42)

    # When
    result = instance.public_method()

    # Then
    assert result == 42
```

### Mock with side_effect

```python
def test_should_retry_on_failure(self, mocker):
    # Given
    mock_service = mocker.Mock()
    mock_service.call.side_effect = [
        ConnectionError("first fail"),
        ConnectionError("second fail"),
        {"success": True},  # Third call succeeds
    ]

    # When
    result = retry_call(mock_service)

    # Then
    assert result == {"success": True}
    assert mock_service.call.call_count == 3
```

### Parameterized tests

```python
@pytest.mark.parametrize("input_val,expected", [
    (0, "zero"),
    (1, "one"),
    (-1, "negative"),
])
def test_should_classify_number(self, input_val, expected):
    """Should return correct classification for various inputs."""
    # When
    result = classify(input_val)

    # Then
    assert result == expected
```

---

## Anti-patterns to Avoid

```python
# ❌ Test without clear structure
def test_stuff(self):
    x = do_thing()
    assert x
    y = do_other()
    assert y == 5
    z = another()
    assert z is not None

# ❌ Mock with unittest
from unittest.mock import patch
@patch("module.thing")
def test_bad(self, mock_thing):
    pass

# ❌ Non-descriptive name
def test_1(self):
    pass

# ❌ No docstring
def test_should_work(self):
    result = func()
    assert result == 5

# ❌ Duplicated setup
def test_a(self):
    client = Client()
    client.configure(x=1, y=2, z=3)
    # ...

def test_b(self):
    client = Client()
    client.configure(x=1, y=2, z=3)  # Duplication!
    # ...
```

---

## Useful Commands

```bash
# Run tests
pytest tests/ -v

# With coverage
pytest --cov=src --cov-report=html

# Single file
pytest tests/test_module.py -v

# Single test
pytest tests/test_module.py::TestClass::test_name -v

# Show prints
pytest -s

# Stop at first failure
pytest -x
```
