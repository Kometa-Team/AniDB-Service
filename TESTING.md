# Running Tests

## Local Testing

### Install Test Dependencies

```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Specific Test File

```bash
pytest test_main.py
```

### Run Specific Test

```bash
pytest test_main.py::test_anime_endpoint_requires_auth
```

### Run with Coverage

```bash
pip install pytest-cov
pytest --cov=main --cov-report=html
```

View coverage report:
```bash
open htmlcov/index.html
```

### Run Only Async Tests

```bash
pytest -m asyncio
```

## Test Categories

### Authentication Tests
- `/stats` endpoint (no auth required)
- `/anime` endpoint (auth required)
- `/search` endpoint (auth required)
- Valid/invalid credentials

### Database Tests
- Table initialization
- XML indexing
- Tag storage
- Relation storage
- Daily rate limiting

### Mature Content Tests
- Filter 18+ tags
- Filter adult categories
- Preserve safe content
- Header validation

### Endpoint Tests
- Stats endpoint structure
- Anime endpoint caching
- Mature parameter (true/false)
- Search by tags
- Invalid inputs

### Integration Tests
- Full workflow (init → index → query)
- Cache hit/miss scenarios
- Stale cache handling
- Mock external API calls

## Docker Testing

Run tests in Docker environment:

```bash
# Build test container
docker build -t anidb-test .

# Run tests
docker run --rm anidb-test pytest

# Run with output
docker run --rm anidb-test pytest -v
```

## Continuous Integration

Tests run automatically on:
- Pull requests
- Pushes to main branch
- See `.github/workflows/tests.yml`

## Writing New Tests

### Test Template

```python
@pytest.mark.asyncio
async def test_your_feature(test_client, auth_headers, clean_test_env):
    """Test description."""
    # Arrange
    await init_database()
    
    # Act
    response = test_client.get("/endpoint", headers=auth_headers)
    
    # Assert
    assert response.status_code == 200
```

### Fixtures Available

- `test_client` - FastAPI TestClient
- `auth_headers` - Valid authentication headers
- `invalid_auth_headers` - Invalid authentication headers
- `clean_test_env` - Clean test directory
- `sample_anime_xml` - Sample anime XML data
- `mature_anime_xml` - Sample mature content XML

## Troubleshooting

**Import errors:** Make sure you're in the project root directory

**Database locked:** Stop any running instances

**Port conflicts:** Tests use temporary paths, shouldn't conflict

**Async warnings:** Ensure pytest-asyncio is installed
