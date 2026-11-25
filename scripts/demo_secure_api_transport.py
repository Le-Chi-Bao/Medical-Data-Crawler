"""Exercise secure transport, independent policy and catalog entirely offline."""

import json

from medical_data_crawler.secure_api_demo import run_demo

if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
