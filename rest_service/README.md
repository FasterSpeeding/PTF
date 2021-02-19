# Getting started

To prepare an environment for this first create a Python 3.9 >= virtual environment using your
choice of libraries then activate the environment and ensure pip is installed then run
`python -m pip install -r requirements.txt` to install the necessary environments.

Then create a `.env` file in the `rest_service` directory and populate it with the fields shown in
`rest_service/.env.example` while replacing the values with your environment's equivalent.

Then to initiate a server service instance make sure you have the created virtual environment
activated before running `uvicorn src.rest_server:build --factory` in `rest_service`. Information
on the additional arguments for Uvicorn such as how to startup multiple worker processes can be
found at https://www.uvicorn.org/#command-line-options.
