import requests
import json
from datetime import datetime

# ========== 只包含截图里出现的路线和站点 ==========
ROUTE_ITEMS = [
    # 九巴
    ('kmb', '59X',  'TM648', '湖景邨湖翠樓'),   # 截图 IMG_1578
    ('kmb', '59M',  'TM671', '蝴蝶站'),          # 截图 IMG_1578
    ('kmb', '259D', 'TM648', '湖景邨湖翠樓'),   # 截图 IMG_1579
    # 龍運（全部在兆山苑柳景閣）
    ('lwb', 'A33',  'TM436', '兆山苑柳景閣'),   # 截图 IMG_1580
    ('lwb', 'E33',  'TM436', '兆山苑柳景閣'),   # 截图 IMG_1580
    ('lwb', 'E33P', 'TM436', '兆山苑柳景閣'),   # 截图 IMG_1580
    ('lwb', 'A34',  'TM436', '兆山苑柳景閣'),   # 截图 IMG_1578
    # 城巴
    ('ctb', '962X', 'TM453', '湖景邨湖畔樓'),   # 截图 IMG_1582
    # ('ctb', 'B3',   '???',   '美樂花園'),     # 站码未知，暂不添加
    # 港鐵巴士（蝴蝶邨蝶心樓）
    ('mtr', 'K52',  'TM630', '蝴蝶邨蝶心樓'),   # 截图 IMG_1581
    ('mtr', '506',  'TM630', '蝴蝶邨蝶心樓'),   # 截图 IMG_1581
]

def fetch_eta(company, route, stop_id):
    url = f"https://data.hkbus.app/eta/{company}/{route}/{stop_id}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            return []
    except Exception as e:
        print(f"Error fetching {company} {route} at {stop_id}: {e}")
        return []

def fetch_lightrail(station_id='120'):
    url = f"https://rt.data.gov.hk/v1/transport/mtr/lrt/getSchedule?station_id={station_id}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            etas = []
            for p in data.get('platform', []):
                for r in p.get('routeList', []):
                    for t in r.get('trains', []):
                        if 'time' in t:
                            etas.append({'eta': t['time']})
            etas.sort(key=lambda x: x['eta'])
            return etas[:10]
        else:
            return []
    except Exception as e:
        print(f"Error fetching lightrail: {e}")
        return []

def main():
    print("🚀 开始抓取截图中的路线 ETA...")
    result = {
        'timestamp': datetime.now().isoformat(),
        'items': [],
        'lightrail': []
    }

    for company, route, stop_id, display_name in ROUTE_ITEMS:
        etas = fetch_eta(company, route, stop_id)
        result['items'].append({
            'company': company,
            'route': route,
            'stop_id': stop_id,
            'display_name': display_name,
            'etas': etas if etas else []
        })
        print(f"✅ {company} {route} at {display_name} -> {len(etas)} 笔班次")

    # 轻铁
    result['lightrail'] = fetch_lightrail('120')

    with open('eta-data.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("✅ 所有数据已写入 eta-data.json")

if __name__ == '__main__':
    main()
