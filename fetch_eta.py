import requests
import json
import os
from datetime import datetime

# ========== 巴士路线（只保留截图中的站名） ==========
BUS_ITEMS = [
    ('kmb', '59X',  'TM648', '湖景邨湖翠樓'),
    ('kmb', '59M',  'TM671', '蝴蝶站'),
    ('kmb', '259D', 'TM648', '湖景邨湖翠樓'),
    ('lwb', 'A33',  'TM436', '兆山苑柳景閣'),
    ('lwb', 'E33',  'TM436', '兆山苑柳景閣'),
    ('lwb', 'E33P', 'TM436', '兆山苑柳景閣'),
    ('lwb', 'A34',  'TM436', '兆山苑柳景閣'),
    ('ctb', '962X', 'TM453', '湖景邨湖畔樓'),
    ('mtr', 'K52',  'TM630', '蝴蝶邨蝶心樓'),
    ('mtr', '506',  'TM630', '蝴蝶邨蝶心樓'),
]

# ========== 轻铁站点及路线 ==========
LR_STATIONS = [
    {'id': '115', 'name': '蝴蝶站', 'routes': ['610', '615', '615P']},
    {'id': '120', 'name': '屯門碼頭站', 'routes': ['507', '610', '614', '614P', '615', '615P']},
]

def fetch_bus_eta(company, route, stop_id):
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

def fetch_lr_station(station_id):
    url = f"https://rt.data.gov.hk/v1/transport/mtr/lrt/getSchedule?station_id={station_id}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        items = []
        for p in data.get('platform', []):
            for r in p.get('routeList', []):
                route = r.get('routeNumber')
                if not route:
                    continue
                for t in r.get('trains', []):
                    if 'time' in t:
                        items.append({'route': route, 'eta': t['time']})
        return items
    except Exception as e:
        print(f"Error fetching light rail station {station_id}: {e}")
        return []

def group_lr_etas(raw_items, wanted_routes):
    grouped = {}
    for item in raw_items:
        route = item['route']
        if route not in wanted_routes:
            continue
        grouped.setdefault(route, []).append(item['eta'])
    result = []
    for route, times in grouped.items():
        times.sort()
        result.append({
            'route': route,
            'etas': [{'eta': t} for t in times[:3]]
        })
    return result

def load_old_data(filename='eta-data.json'):
    """如果文件存在，读取其中的数据"""
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    return None

def save_data(data, filename='eta-data.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    print("🚀 开始抓取所有数据...")
    new_result = {
        'timestamp': datetime.now().isoformat(),
        'bus_items': [],
        'lr_items': []
    }

    # ---- 抓取巴士 ----
    bus_ok = False
    for company, route, stop_id, display_name in BUS_ITEMS:
        etas = fetch_bus_eta(company, route, stop_id)
        new_result['bus_items'].append({
            'company': company,
            'route': route,
            'stop_id': stop_id,
            'display_name': display_name,
            'etas': etas if etas else []
        })
        if etas:
            bus_ok = True
        print(f"巴士 {company} {route} at {display_name} -> {len(etas)} 班次")

    # ---- 抓取轻铁 ----
    lr_ok = False
    for station in LR_STATIONS:
        raw = fetch_lr_station(station['id'])
        grouped = group_lr_etas(raw, station['routes'])
        for entry in grouped:
            new_result['lr_items'].append({
                'station_name': station['name'],
                'route': entry['route'],
                'etas': entry['etas']
            })
            if entry['etas']:
                lr_ok = True
        print(f"轻铁 {station['name']} 抓取完成，共 {len(grouped)} 条路线")

    # ---- 决定是否覆盖旧文件 ----
    # 如果本次抓取完全没有数据，则保留旧文件（如果有）
    if not bus_ok and not lr_ok:
        old_data = load_old_data()
        if old_data:
            print("⚠️ 本次抓取全部为空，保留上一次的 JSON 文件。")
            # 不写入新文件
            return
        else:
            print("⚠️ 本次抓取全部为空，且无旧文件，写入空数据。")
            save_data(new_result)
    else:
        print("✅ 本次抓取有效，写入新数据。")
        save_data(new_result)

if __name__ == '__main__':
    main()
