# Standard Project Structure System Prompt

When implementing code projects for me, please follow this standardized structure that promotes maintainability, clarity, and consistent organization:

## Overall Architecture

1. **Modular Design**: Organize code into focused modules with clear responsibilities.
2. **Strong Typing**: Use type hints throughout to make code more maintainable.
3. **Documentation**: Add docstrings to all modules, classes, and functions.
4. **Virtual Environment**: All projects should use a virtual environment for dependency isolation.

## File Structure

1. **Entry Point**: Always use `index.py` with a single `handler()` function as the main entry point.
2. **Core Modules**: Name modules after their primary function (e.g., `data_processor.py`, `model_trainer.py`).
3. **Documentation**: Include a thorough README.md explaining the project.
4. **Environment Setup**: Include instructions for setting up and activating a virtual environment.

## Coding Standards

1. **Descriptive Naming**: Use clear, descriptive names for variables, functions, and classes.
2. **Strong Typing**: Include type annotations for all function parameters and return values.
3. **Comprehensive Docstrings**: Add detailed docstrings to all functions and classes.
4. **Error Handling**: Implement robust error handling, especially in the handler function.

## Virtual Environment

All projects should include setup for a virtual environment:

```bash
# Setup instructions in README.md
# Create virtual environment
python -m venv venv

# Activate virtual environment (Linux/Mac)
source venv/bin/activate

# Activate virtual environment (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Always assume the virtual environment will be used when running the code.

## index.py Structure

The `index.py` file should follow this pattern:

```python
#!/usr/bin/env python3
"""
Brief description of the project

This is the main entry point for the application.
"""

import argparse
import sys
from typing import Optional, Any

# Import from other modules
from module_a import function_a
from module_b import function_b

def handler(
    param1: str,
    param2: Optional[int] = None,
    # ... other parameters
) -> int:
    """
    Main handler function that orchestrates the process.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Implementation
        # ...
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Description of the application")
    # Add arguments
    args = parser.parse_args()
    
    # Call the handler with parsed arguments
    sys.exit(handler(
        # Pass arguments to handler
    ))
```

## Module Structure

Each module should follow this pattern:

```python
#!/usr/bin/env python3
"""
Brief description of this module

This module handles a specific responsibility in the project.
"""

from typing import List, Dict, Any, Optional

def function_a(param1: str, param2: int) -> List[str]:
    """
    Description of what this function does.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
    """
    # Implementation
    pass

class ClassA:
    """Description of what this class represents."""
    
    def __init__(self, param1: str):
        """
        Initialize the class.
        
        Args:
            param1: Description of param1
        """
        self.param1 = param1
    
    def method_a(self, param1: int) -> Dict[str, Any]:
        """
        Description of what this method does.
        
        Args:
            param1: Description of param1
            
        Returns:
            Description of return value
        """
        # Implementation
        pass
```

## README Structure

The README.md should include:

1. Project name and brief description
2. Key features
3. Installation instructions, including virtual environment setup
4. Usage examples with command-line arguments
5. File/module descriptions
6. Data format requirements (if applicable)
7. Examples demonstrating common use cases

By following this structure, we will create consistent, maintainable, and well-documented code projects that are easy to understand and extend. 