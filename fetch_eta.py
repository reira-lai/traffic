from hk_bus_eta import HKEta
import json
from datetime import datetime
import requests

# 你要查詢的路線清單
WANTED_ROUTES = {
    'kmb': ['59X', '59M', '59A', 'N260', '259B', '59S'],
    'lwb': ['A33'],
    'ctb': ['962X', '962P', 'B3'],
    'mtr': ['K52', '506']
}

def fetch_all():
    hketa = HKEta()
    route_ids = list(hketa.route_list.keys())

    result = {
        'timestamp': datetime.now().isoformat(),
        'bus': {},
        'lightrail': []
    }

    for company, routes in WANTED_ROUTES.items():
        result['bus'][company] = {}
        for route in routes:
            matched_id = None
            for rid in route_ids:
                r_info = hketa.route_list[rid]
                if r_info['route'] == route and company in r_info['co']:
                    matched_id = rid
                    break
            if matched_id:
                try:
                    etas = hketa.getEtas(route_id=matched_id, seq=0, language='zh')
                    result['bus'][company][route] = etas
                except Exception as e:
                    print(f"Error fetching {company} {route}: {e}")
                    result['bus'][company][route] = []
            else:
                print(f"Route ID not found for {company} {route}")
                result['bus'][company][route] = []

    # 輕鐵
    lr_url = "https://rt.data.gov.hk/v1/transport/mtr/lrt/getSchedule?station_id=120"
    try:
        resp = requests.get(lr_url, timeout=10)
        if resp.status_code == 200:
            lr_data = resp.json()
            etas = []
            for p in lr_data.get('platform', []):
                for r in p.get('routeList', []):
                    for t in r.get('trains', []):
                        if 'time' in t:
                            etas.append({'eta': t['time']})
            etas.sort(key=lambda x: x['eta'])
            result['lightrail'] = etas[:10]
    except Exception as e:
        print(f"Error fetching lightrail: {e}")

    with open('eta-data.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    fetch_all()
