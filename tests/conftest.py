import os

# Isolated settings for the automated test environment.
# These settings do not change production configuration.
os.environ["ENVIRONMENT"] = "test"

os.environ["TRUSTED_HOSTS"] = "testserver,localhost,127.0.0.1"

os.environ["AUTH_RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ["RATE_LIMIT_PER_MINUTE"] = "5000"
