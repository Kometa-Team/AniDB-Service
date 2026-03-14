"""AWS Elastic Beanstalk entry point.

EB looks for an ``application`` variable by default.
"""

from plex_oauth.app import app as application

if __name__ == "__main__":
    application.run()
