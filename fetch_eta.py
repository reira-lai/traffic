import requests
import json
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

# ========== 轻铁站点及路线（蝴蝶站+屯门码头站） ==========
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
    """获取某轻铁站所有列车的到站时间（未分组）"""
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
    """按路线分组，并过滤出想要的路线，取每个路线最近3班"""
    grouped = {}
    for item in raw_items:
        route = item['route']
        if route not in wanted_routes:
            continue
        grouped.setdefault(route, []).append(item['eta'])
    # 排序并取前3
    result = []
    for route, times in grouped.items():
        times.sort()
        result.append({
            'route': route,
            'etas': [{'eta': t} for t in times[:3]]
        })
    return result

def main():
    print("🚀 开始抓取所有数据...")
    result = {
        'timestamp': datetime.now().isoformat(),
        'bus_items': [],       # 巴士条目
        'lr_items': []         # 轻铁条目（每个路线-站点组合）
    }

    # ---- 抓取巴士 ----
    for company, route, stop_id, display_name in BUS_ITEMS:
        etas = fetch_bus_eta(company, route, stop_id)
        result['bus_items'].append({
            'company': company,
            'route': route,
            'stop_id': stop_id,
            'display_name': display_name,
            'etas': etas if etas else []
        })
        print(f"✅ 巴士 {company} {route} at {display_name} -> {len(etas)} 班次")

    # ---- 抓取轻铁 ----
    for station in LR_STATIONS:
        raw = fetch_lr_station(station['id'])
        grouped = group_lr_etas(raw, station['routes'])
        for entry in grouped:
            result['lr_items'].append({
                'station_name': station['name'],
                'route': entry['route'],
                'etas': entry['etas']
            })
        print(f"✅ 轻铁 {station['name']} 抓取完成，共 {len(grouped)} 条路线")

    with open('eta-data.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("✅ 所有数据已写入 eta-data.json")

if __name__ == '__main__':
    main()
