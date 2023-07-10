# Tools

This folder contains different files and folder that are used by various modules in the `incentive-app` project:

- `db_connection` is a module that wraps useful SQL commands to query a postgreSQL with ease.
- `decorator.py` contains decorators that are used in the project.
- `exit_codes.py` contains a class, `ExitCode`, which is an enumeration of default exit codes. Using this class increases code's readability.
- `hopr_api_helper.py` is a wrapper around the HOPR Python API to extract the desired result from API requests.
- `hopr_node.py` contains the `HOPRNode` class. It is the parent of all the classes that want to communicate with HOPR nodes. It includes default method for connection.
- `utils.py` gathers some methods that are used around the project. This file is supposed to be deleted at some point.