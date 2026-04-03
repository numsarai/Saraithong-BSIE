import requests
import time
import sys
import json

try:
    with open('/Users/saraithong/Library/CloudStorage/OneDrive-Personal/Saraithong Code/Test2/69001371-4017603071.xlsx', 'rb') as f:
        res = requests.post('http://127.0.0.1:8757/api/process',
            data={'bank': 'kbank', 'account': '4017603071', 'name': 'น.ส. จริยา ทองคำ'},
            files={'file': f}
        )
    job_id = res.json().get('job_id')
    print(f"Started job {job_id}")

    for i in range(20):
        time.sleep(2)
        st = requests.get(f'http://127.0.0.1:8757/api/job/{job_id}').json()
        if st['status'] in ('done', 'error'):
            print(f"STATUS: {st['status']}")
            if st.get('error'):
                print(f"ERROR: {st['error']}")
            for l in st.get('log', []):
                print(l)
            sys.exit(0 if st['status'] == 'done' else 1)
    print("Timeout")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
