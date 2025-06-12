# Installation

Clone the repository and install dependencies:

```bash
pip install -r requirements.txt
# For exact versions used in CI, see requirements.lock
```

## Running Tests

Install locked dependencies and run the test suite:

```bash
pip install -r requirements.lock
pytest -q
```
