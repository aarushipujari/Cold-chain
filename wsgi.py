"""
PythonAnywhere WSGI Configuration
To deploy on PythonAnywhere.com:
1. Upload this project folder to your PythonAnywhere account.
2. In the 'Web' tab, create a new manual Flask app (Python 3.10).
3. In the WSGI configuration file, add:
   
   import sys
   path = '/home/<your-username>/cold-chain'
   if path not in sys.path:
       sys.path.append(path)
   
   from flask_app import app as application
"""

import sys
import os

project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.append(project_home)

from flask_app import app as application

if __name__ == "__main__":
    application.run()
