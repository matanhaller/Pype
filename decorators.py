"""Decorators for app functions.
"""

# Imports
import time
import threading


def rate_limit(rate):
    """Creates rate limit decorator.

    Args:
        rate (int): Upper bound of sending rate.

    No Longer Returned:
        function: Rate limit decorator.
    """

    def decorator(f):
        """Decorator which limits rate of transmission functions.

        Args:
            f (function): Function to limit its rate.

        Returns:
            function: Wrapper function to switch the original. 
        """

        def wrapper(*args, **kwargs):
            """Wrapper function for rate limit decorator.

            Args:
                *args: Positional arguments supplied in tuple form.
                **kwargs: Keyword arguments supplied in dictionary form.
            """

            current_time = time.time()
            if current_time - wrapper.last_call > 1.0 / wrapper.rate:
                f(*args, **kwargs)
                wrapper.last_call = current_time

        wrapper.last_call = time.time()
        wrapper.rate = rate
        return wrapper

    return decorator


def new_thread(name):
    """Creates new thread decorator.

    Args:
        name (str): Thread name.

    Returns:
        function: New thread decorator.
    """

    def decorator(f):
        """Decorator which calls function on a new thread.

        Args:
            f (function): Function to run on a new thread.

        Returns:
            function: Wrapper function to switch the original.
        """

        def wrapper(*args, **kwargs):
            """Wrapper function for new thread decorator.

            Args:
                *args: Positional arguments supplied in tuple form.
                **kwargs: Keyword arguments supplied in dictionary form.
            """

            threading.Thread(name=name, target=f,
                             args=args, kwargs=kwargs).start()

        return wrapper

    return decorator
